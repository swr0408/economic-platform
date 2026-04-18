"""
米国天然ガス貯蔵量 (EIA Natural Gas Storage) サービス

データソース:
  - EIA API v2: 週次データ
  - エンドポイント: /v2/natural-gas/stor/wkly/data/
  - シリーズ: NW2_EPG0_SWO_R48_BCF
  - 毎週木曜 15:30 UTC (金曜 00:30 JST)

1系列:
  - NW2_EPG0_SWO_R48_BCF: Working Gas in Underground Storage (BCF)

更新: 6時間TTL (Redis + ファイル)
"""
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

from core.redis_client import redis_client

# .envファイルからEIA_API_KEYをフォールバック読み込み
if not os.environ.get("EIA_API_KEY"):
    try:
        from dotenv import load_dotenv
        _env_path = Path(__file__).parent.parent.parent.parent / ".env"
        if _env_path.exists():
            load_dotenv(_env_path, override=False)
    except ImportError:
        pass

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "us_natural_gas_storage_cache.json"

REDIS_KEY = "market:us_natural_gas_storage:data"

EIA_API_URL = "https://api.eia.gov/v2/natural-gas/stor/wkly/data/"
TARGET_SERIES_KEY = "NW2_EPG0_SWO_R48_BCF"


class UsNaturalGasStorageService:
    """EIA 米国天然ガス貯蔵量サービス"""

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
                cached["next_release"] = self._get_next_release()
                return cached

        try:
            data = self._build_data()
            if data and data.get("data"):
                self._save_to_cache(data)
                data["next_release"] = self._get_next_release()
                return data
        except Exception as e:
            logger.error(f"[NatGasStorage] Build error: {e}")
            import traceback
            traceback.print_exc()

        cached = self._load_from_redis()
        if cached and cached.get("data"):
            cached["next_release"] = self._get_next_release()
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            cached["next_release"] = self._get_next_release()
            return cached

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "metadata": {"source": "EIA"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        try:
            from services.usa.fmp_next_release_utils import get_next_release_from_fmp
            return get_next_release_from_fmp("us_natural_gas_storage")
        except Exception as e:
            logger.error(f"[NatGasStorage] Next release error: {e}")
            return None

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """EIA API v2からデータを取得"""
        logger.info("[NatGasStorage] Building data from EIA API v2...")

        api_key = os.environ.get("EIA_API_KEY", "")
        if not api_key:
            logger.warning("[NatGasStorage] EIA_API_KEY not set")
            return None

        all_rows = self._fetch_from_eia(api_key)
        if not all_rows:
            return None

        result_data: List[Dict[str, Any]] = []
        for row in all_rows:
            period = row.get("period", "")
            value = row.get("value")
            if not period or value is None:
                continue
            try:
                val = round(float(value), 0)
            except (ValueError, TypeError):
                continue
            result_data.append({"date": period, "value": val})

        if not result_data:
            logger.error("[NatGasStorage] No data from EIA API")
            return None

        result_data.sort(key=lambda x: x["date"])

        # Calculate YoY
        date_idx_map = {d["date"]: i for i, d in enumerate(result_data)}
        for item in result_data:
            val = item["value"]
            current_date = datetime.strptime(item["date"], "%Y-%m-%d")
            target_date = current_date - timedelta(days=364)

            best_match = None
            best_diff = 999
            for offset_days in range(-7, 8):
                check_date = target_date + timedelta(days=offset_days)
                check_str = check_date.strftime("%Y-%m-%d")
                if check_str in date_idx_map:
                    diff = abs(offset_days)
                    if diff < best_diff:
                        best_diff = diff
                        best_match = date_idx_map[check_str]

            if best_match is not None:
                prev_val = result_data[best_match]["value"]
                if prev_val and prev_val != 0:
                    yoy_pct = ((val - prev_val) / prev_val) * 100
                    item["yoy"] = round(yoy_pct, 2)
                else:
                    item["yoy"] = None
            else:
                item["yoy"] = None

        latest = result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[NatGasStorage] {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest value={latest.get('value')}"
        )

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "EIA",
                "frequency": "weekly",
                "unit": "BCF",
                "series": "Working Gas in Underground Storage, Lower 48 States",
                "data_count": len(result_data),
                "start_date": result_data[0]["date"],
                "end_date": result_data[-1]["date"],
            },
            "cached": False,
            "source": "model",
            "last_updated": now_str,
        }

    def _fetch_from_eia(self, api_key: str) -> Optional[List[Dict[str, Any]]]:
        """EIA API v2から週次データを取得"""
        all_rows: List[Dict[str, Any]] = []
        offset = 0
        length = 5000

        while True:
            try:
                resp = requests.get(EIA_API_URL, params={
                    "api_key": api_key,
                    "frequency": "weekly",
                    "data[0]": "value",
                    "facets[series][]": TARGET_SERIES_KEY,
                    "sort[0][column]": "period",
                    "sort[0][direction]": "asc",
                    "offset": offset,
                    "length": length,
                }, timeout=30, headers={"User-Agent": "Mozilla/5.0"})

                if resp.status_code != 200:
                    logger.error(f"[NatGasStorage] EIA API error: HTTP {resp.status_code}")
                    return all_rows if all_rows else None

                data = resp.json()
                rows = data.get("response", {}).get("data", [])
                total = int(data.get("response", {}).get("total", 0))
                all_rows.extend(rows)

                if len(all_rows) >= total or len(rows) == 0:
                    break
                offset += length
            except Exception as e:
                logger.error(f"[NatGasStorage] EIA API error: {e}")
                return all_rows if all_rows else None

        logger.info(f"[NatGasStorage] Total rows fetched: {len(all_rows)}")
        return all_rows

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(REDIS_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[NatGasStorage] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[NatGasStorage] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(REDIS_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[NatGasStorage] Redis load error: {e}")
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
            logger.error(f"[NatGasStorage] File load error: {e}")
        return None


us_natural_gas_storage_service = UsNaturalGasStorageService()
