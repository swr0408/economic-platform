"""
米石油採掘装置（リグ）稼働数 (U.S. Oil Rig Count) サービス

データソース:
  - EIA API v2: 月次データ (1973年～最新)
    - シリーズ: E_ERTRRO_XR0_NUS_C (U.S. Crude Oil Rotary Rigs in Operation)
    - エンドポイント: /v2/natural-gas/enr/drill/data/
  - FMP DB蓄積: 週次データ (直近～最新週)
    - FMPイベント: "Baker Hughes Oil Rig Count"
    - 月次データの最新月以降を補完

更新: 6時間TTL (Redis + ファイル)
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "north_america_rig_count_cache.json"

REDIS_KEY = "market:north_america_rig_count:data"

# EIA API
EIA_API_URL = "https://api.eia.gov/v2/natural-gas/enr/drill/data/"
EIA_SERIES_ID = "E_ERTRRO_XR0_NUS_C"

# FMP event pattern (for DB lookup of weekly data)
FMP_EVENT_PATTERN = "Baker Hughes Oil Rig Count"


class NorthAmericaRigCountService:
    """米石油採掘装置（リグ）稼働数サービス"""

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
            logger.error(f"[RigCount] Build error: {e}")
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
            "metadata": {"source": "EIA / Baker Hughes"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """FMPから次回リグカウント発表日を取得"""
        try:
            from services.usa.fmp_next_release_utils import get_next_release_from_fmp
            return get_next_release_from_fmp("north_america_rig_count")
        except Exception as e:
            logger.error(f"[RigCount] Next release error: {e}")
            return None

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """EIA API + FMP DB からデータを構築"""
        logger.info("[RigCount] Building data...")

        # 1. EIA API: 月次データ (1973年～最新月)
        eia_data = self._fetch_from_eia()

        # 2. FMP DB: 週次データ (直近)
        fmp_data = self._load_from_fmp_db()

        # 3. マージ: EIA月次をベースにFMP週次で補完
        merged = {}

        if eia_data:
            for item in eia_data:
                merged[item["date"]] = item

        if fmp_data:
            # EIAの最新月以降のFMPデータのみ追加
            eia_latest_date = max(merged.keys()) if merged else "0000-00-00"
            for item in fmp_data:
                if item["date"] > eia_latest_date:
                    merged[item["date"]] = item

        result_data = sorted(merged.values(), key=lambda x: x["date"])

        if not result_data:
            logger.error("[RigCount] No data after merge")
            return None

        latest = result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[RigCount] {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"EIA={len(eia_data or [])}, FMP_added={len(result_data) - len(eia_data or [])}, "
            f"latest={latest.get('value')}"
        )

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "EIA / Baker Hughes",
                "frequency": "monthly",
                "unit": "rigs",
                "series": "U.S. Crude Oil Rotary Rigs in Operation",
                "eia_series": EIA_SERIES_ID,
                "data_count": len(result_data),
                "start_date": result_data[0]["date"],
                "end_date": result_data[-1]["date"],
            },
            "cached": False,
            "source": "model",
            "last_updated": now_str,
        }

    def _fetch_from_eia(self) -> Optional[List[Dict[str, Any]]]:
        """EIA API v2 から月次リグカウントデータを取得"""
        api_key = os.environ.get("EIA_API_KEY", "")
        if not api_key:
            logger.warning("[RigCount] EIA_API_KEY not set")
            return None

        try:
            params = {
                "api_key": api_key,
                "frequency": "monthly",
                "data[0]": "value",
                "facets[series][]": EIA_SERIES_ID,
                "sort[0][column]": "period",
                "sort[0][direction]": "asc",
                "offset": 0,
                "length": 5000,
            }
            resp = requests.get(EIA_API_URL, params=params, timeout=30, headers={
                "User-Agent": "Mozilla/5.0"
            })

            if resp.status_code != 200:
                logger.error(f"[RigCount] EIA API error: HTTP {resp.status_code}")
                return None

            data = resp.json()
            rows = data.get("response", {}).get("data", [])

            if not rows:
                logger.warning("[RigCount] No data from EIA API")
                return None

            result = []
            for row in rows:
                period = row.get("period", "")
                value = row.get("value")

                if not period or value is None:
                    continue

                try:
                    val = int(float(value))
                except (ValueError, TypeError):
                    continue

                # period is "YYYY-MM" → "YYYY-MM-01"
                date_str = f"{period}-01"
                result.append({"date": date_str, "value": val})

            logger.info(f"[RigCount] EIA: {len(result)} monthly records")
            return result

        except Exception as e:
            logger.error(f"[RigCount] EIA API error: {e}")
            return None

    def _load_from_fmp_db(self) -> List[Dict[str, Any]]:
        """FMP DBから週次データを取得"""
        try:
            from core.database import get_db_connection

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT datetime_utc, actual, estimate, previous
                        FROM economic_calendar_events
                        WHERE country = 'US'
                          AND event ILIKE %s
                          AND actual IS NOT NULL
                        ORDER BY datetime_utc ASC
                    """, (f"%{FMP_EVENT_PATTERN}%",))
                    rows = cur.fetchall()

                result = []
                seen_dates = set()

                for row in rows:
                    dt_utc, actual, estimate, previous = row
                    if dt_utc:
                        date_str = dt_utc.strftime("%Y-%m-%d")

                        if date_str in seen_dates:
                            continue
                        seen_dates.add(date_str)

                        result.append({
                            "date": date_str,
                            "value": round(float(actual)) if actual is not None else None,
                        })

                logger.info(f"[RigCount] FMP DB: {len(result)} weekly records")
                return result

        except Exception as e:
            logger.error(f"[RigCount] FMP DB load error: {e}")
            return []

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(REDIS_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[RigCount] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[RigCount] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(REDIS_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[RigCount] Redis load error: {e}")
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
            logger.error(f"[RigCount] File load error: {e}")
        return None


north_america_rig_count_service = NorthAmericaRigCountService()
