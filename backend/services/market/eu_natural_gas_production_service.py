"""
EU天然ガス生産 (Eurostat NRG_CB_GASM) サービス

データソース:
  - Eurostat SDMX API: NRG_CB_GASM
  - 条件: geo=EU27_2020, siec=G3000, nrg_bal=IPRD, unit=MIO_M3
  - 月次データ（2008-01 ～）
  - 単位: 百万立方メートル (MIO_M3)

更新スケジュール: 月次（Eurostat）
更新: 6時間TTL (Redis + ファイル)
"""
import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "eu_natural_gas_production_cache.json"

REDIS_KEY = "market:eu_natural_gas_production:data"

EUROSTAT_API_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/sdmx/3.0/"
    "data/dataflow/ESTAT/NRG_CB_GASM/1.0"
)

# フィルタ条件
TARGET_GEO = "EU27_2020"
TARGET_NRG_BAL = "IPRD"  # Indigenous production（国内生産）
TARGET_SIEC = "G3000"    # Natural gas


class EuNaturalGasProductionService:
    """Eurostat EU天然ガス生産サービス"""

    def _should_refresh(self) -> bool:
        try:
            cached = redis_client.get(REDIS_KEY)
            if not cached:
                return True
            last_updated_str = cached.get("last_updated")
            if not last_updated_str:
                return True
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)
            return (now - last_updated).total_seconds() >= 6 * 3600
        except Exception:
            return True

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        if not force_refresh and not self._should_refresh():
            cached = self._load_from_redis()
            if cached and cached.get("data"):
                return cached

        try:
            data = self._build_data()
            if data and data.get("data"):
                self._save_to_cache(data)
                return data
        except Exception as e:
            logger.error(f"[EuNatGasProd] Build error: {e}")
            import traceback
            traceback.print_exc()

        cached = self._load_from_redis()
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "metadata": {"source": "Eurostat"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """Eurostat APIからTSVを取得・パース"""
        logger.info("[EuNatGasProd] Fetching from Eurostat API...")

        tsv_text = self._fetch_tsv()
        if not tsv_text:
            return None

        result_data = self._parse_tsv(tsv_text)
        if not result_data:
            logger.error("[EuNatGasProd] No data parsed from Eurostat TSV")
            return None

        result_data.sort(key=lambda x: x["date"])

        # YoY計算（12ヶ月前と比較）
        date_val_map = {d["date"]: d["value"] for d in result_data}
        for item in result_data:
            try:
                dt = datetime.strptime(item["date"], "%Y-%m-%d")
                prev_dt = dt.replace(year=dt.year - 1)
                prev_key = prev_dt.strftime("%Y-%m-%d")
                prev_val = date_val_map.get(prev_key)
                if prev_val and prev_val != 0:
                    item["yoy"] = round(((item["value"] - prev_val) / prev_val) * 100, 2)
                else:
                    item["yoy"] = None
            except Exception:
                item["yoy"] = None

        latest = result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[EuNatGasProd] {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest value={latest.get('value')} MIO_M3"
        )

        return {
            "data": result_data,
            "latest": latest,
            "next_release": None,
            "metadata": {
                "source": "Eurostat",
                "dataset": "NRG_CB_GASM",
                "frequency": "monthly",
                "unit": "MIO_M3",
                "series": "EU27 Natural Gas Indigenous Production",
                "data_count": len(result_data),
                "start_date": result_data[0]["date"],
                "end_date": result_data[-1]["date"],
            },
            "cached": False,
            "source": "model",
            "last_updated": now_str,
        }

    def _fetch_tsv(self) -> Optional[str]:
        """Eurostat SDMX APIからTSVを取得"""
        try:
            resp = requests.get(
                EUROSTAT_API_URL,
                params={
                    "format": "TSV",
                    "compress": "false",
                },
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=60,
            )
            if resp.status_code != 200:
                logger.error(f"[EuNatGasProd] Eurostat API error: HTTP {resp.status_code}")
                return None

            return resp.text
        except Exception as e:
            logger.error(f"[EuNatGasProd] Eurostat API error: {e}")
            return None

    def _parse_tsv(self, tsv_text: str) -> Optional[List[Dict[str, Any]]]:
        """TSVをパースしてEU27のIPRDデータを抽出"""
        lines = tsv_text.strip().split("\n")
        if len(lines) < 2:
            return None

        # ヘッダー行: freq,nrg_bal,siec,unit,geo\TIME_PERIOD TAB 2008-01 TAB ...
        header_parts = lines[0].split("\t")
        time_periods = [tp.strip() for tp in header_parts[1:]]

        # データ行からターゲット行を探す
        target_line = None
        for line in lines[1:]:
            parts = line.split("\t")
            key = parts[0]
            # M,IPRD,G3000,MIO_M3,EU27_2020
            if (TARGET_GEO in key and TARGET_NRG_BAL in key
                    and TARGET_SIEC in key):
                target_line = parts
                break

        if target_line is None:
            logger.error("[EuNatGasProd] Target row not found in TSV")
            return None

        values = target_line[1:]
        result_data: List[Dict[str, Any]] = []

        for i, tp in enumerate(time_periods):
            if i >= len(values):
                break

            raw_val = values[i].strip()
            # 欠損値（":", ": ", 空）をスキップ
            if not raw_val or raw_val == ":" or raw_val.startswith(":"):
                continue

            # フラグ除去（例: "2826.800 p" → "2826.800"）
            clean_val = re.sub(r"[a-z ]", "", raw_val)
            if not clean_val:
                continue

            try:
                value = round(float(clean_val), 3)
            except (ValueError, TypeError):
                continue

            # YYYY-MM → YYYY-MM-01
            date_str = f"{tp}-01"
            result_data.append({
                "date": date_str,
                "value": value,
            })

        return result_data if result_data else None

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(REDIS_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[EuNatGasProd] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[EuNatGasProd] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(REDIS_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[EuNatGasProd] Redis load error: {e}")
        return None

    def _load_from_file(self) -> Optional[Dict[str, Any]]:
        try:
            if DATA_CACHE_FILE.exists():
                with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["cached"] = True
                data["source"] = "file"
                return data
        except Exception as e:
            logger.error(f"[EuNatGasProd] File load error: {e}")
        return None


eu_natural_gas_production_service = EuNaturalGasProductionService()
