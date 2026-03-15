"""
EU天然ガス貯蔵量 (AGSI+ Aggregated Gas Storage Inventory) サービス

データソース:
  - AGSI+ API: https://agsi.gie.eu/api
  - EU集計エンドポイント: ?type=eu&from=YYYY-MM-DD&to=YYYY-MM-DD
  - 認証: x-key ヘッダー
  - 毎日更新 (19:30 CET / 23:00 CET)

主要フィールド:
  - gasInStorage: 在庫量 (TWh)
  - full: 充填率 (%)
  - injection: 注入量 (GWh/d)
  - withdrawal: 引出量 (GWh/d)

更新: 6時間TTL (Redis + ファイル)
"""
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

from core.redis_client import redis_client

# .envファイルからAGSI_API_KEYをフォールバック読み込み
if not os.environ.get("AGSI_API_KEY"):
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
DATA_CACHE_FILE = CACHE_DIR / "eu_natural_gas_storage_cache.json"

REDIS_KEY = "market:eu_natural_gas_storage:data"

AGSI_API_URL = "https://agsi.gie.eu/api"


def _safe_float(val: Any) -> Optional[float]:
    """文字列を安全にfloatに変換（AGSI+は数値を文字列で返す）"""
    if val is None or val == "" or val == "-":
        return None
    try:
        return round(float(val), 4)
    except (ValueError, TypeError):
        return None


class EuNaturalGasStorageService:
    """AGSI+ EU天然ガス貯蔵量サービス"""

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
            logger.error(f"[EuNatGas] Build error: {e}")
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
            "metadata": {"source": "AGSI+"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """AGSI+ APIからデータを取得・変換"""
        logger.info("[EuNatGas] Building data from AGSI+ API...")

        api_key = os.environ.get("AGSI_API_KEY", "")
        if not api_key:
            logger.warning("[EuNatGas] AGSI_API_KEY not set")
            return None

        all_rows = self._fetch_from_agsi(api_key)
        if not all_rows:
            return None

        result_data: List[Dict[str, Any]] = []
        for row in all_rows:
            date_str = row.get("gasDayStart", "")
            if not date_str:
                continue

            gas_in_storage = _safe_float(row.get("gasInStorage"))
            if gas_in_storage is None:
                continue

            result_data.append({
                "date": date_str,
                "gas_in_storage": gas_in_storage,
                "fill_rate": _safe_float(row.get("full")),
                "injection": _safe_float(row.get("injection")),
                "withdrawal": _safe_float(row.get("withdrawal")),
                "working_gas_volume": _safe_float(row.get("workingGasVolume")),
            })

        if not result_data:
            logger.error("[EuNatGas] No data from AGSI+ API")
            return None

        result_data.sort(key=lambda x: x["date"])

        # YoY計算（gas_in_storage に対して、365日前 ±7日ウィンドウ）
        date_idx_map = {d["date"]: i for i, d in enumerate(result_data)}
        for item in result_data:
            val = item["gas_in_storage"]
            try:
                current_date = datetime.strptime(item["date"], "%Y-%m-%d")
            except ValueError:
                item["yoy"] = None
                continue

            target_date = current_date - timedelta(days=365)

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
                prev_val = result_data[best_match]["gas_in_storage"]
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
            f"[EuNatGas] {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest gas_in_storage={latest.get('gas_in_storage')} TWh, "
            f"fill_rate={latest.get('fill_rate')}%"
        )

        return {
            "data": result_data,
            "latest": latest,
            "next_release": None,
            "metadata": {
                "source": "AGSI+",
                "frequency": "daily",
                "unit": "TWh",
                "series": "EU Aggregated Gas Storage Inventory",
                "data_count": len(result_data),
                "start_date": result_data[0]["date"],
                "end_date": result_data[-1]["date"],
            },
            "cached": False,
            "source": "model",
            "last_updated": now_str,
        }

    def _fetch_from_agsi(self, api_key: str) -> Optional[List[Dict[str, Any]]]:
        """AGSI+ APIからEU集計データをページネーション取得"""
        all_rows: List[Dict[str, Any]] = []
        today = datetime.now(JST).strftime("%Y-%m-%d")
        from_date = (datetime.now(JST) - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
        page = 1

        while True:
            try:
                resp = requests.get(
                    AGSI_API_URL,
                    params={
                        "type": "eu",
                        "from": from_date,
                        "to": today,
                        "page": page,
                        "size": 300,
                    },
                    headers={
                        "x-key": api_key,
                        "User-Agent": "Mozilla/5.0",
                    },
                    timeout=30,
                )

                if resp.status_code != 200:
                    logger.error(f"[EuNatGas] AGSI+ API error: HTTP {resp.status_code}")
                    return all_rows if all_rows else None

                data = resp.json()
                rows = data.get("data", [])
                last_page = data.get("last_page", 0)

                if isinstance(rows, list):
                    all_rows.extend(rows)
                else:
                    logger.warning(f"[EuNatGas] Unexpected data type: {type(rows)}")
                    break

                logger.info(f"[EuNatGas] Page {page}/{last_page}: {len(rows)} rows")

                if page >= last_page or len(rows) == 0:
                    break

                page += 1
                time.sleep(0.3)

            except Exception as e:
                logger.error(f"[EuNatGas] AGSI+ API error: {e}")
                return all_rows if all_rows else None

        logger.info(f"[EuNatGas] Total rows fetched: {len(all_rows)}")
        return all_rows

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(REDIS_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[EuNatGas] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[EuNatGas] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(REDIS_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[EuNatGas] Redis load error: {e}")
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
            logger.error(f"[EuNatGas] File load error: {e}")
        return None


eu_natural_gas_storage_service = EuNaturalGasStorageService()
