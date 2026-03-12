"""
API（米国石油協会）週間原油在庫 サービス

データソース:
  - 過去データ: CSV → DB (economic_calendar_events)
  - 最新値: FMP economic calendar → DB 積み上げ
  - FMPイベント: "API Crude Oil Stock Change"

データ:
  - 在庫変化量 (百万バレル, M)
  - 週次発表（毎週火曜 21:30 EST = 水曜 11:30 JST）

更新: 6時間TTL (Redis + ファイル)
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "api_weekly_crude_oil_inventories_cache.json"

REDIS_KEY = "market:api_weekly_crude_oil_inventories:data"

FMP_EVENT_PATTERN = "API Crude Oil Stock Change"


class ApiWeeklyCrudeOilInventoriesService:
    """API（米国石油協会）週間原油在庫サービス"""

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
            logger.error(f"[ApiCrudeInv] Build error: {e}")
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
            "metadata": {"source": "API (American Petroleum Institute)"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """FMPから次回API原油在庫発表日を取得"""
        try:
            from services.usa.fmp_next_release_utils import get_next_release_from_fmp
            return get_next_release_from_fmp("api_weekly_crude_oil_inventories")
        except Exception as e:
            logger.error(f"[ApiCrudeInv] Next release error: {e}")
            return None

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """DBからデータを取得して時系列を構築"""
        logger.info("[ApiCrudeInv] Building data from DB...")

        db_data = self._load_from_db()
        if not db_data:
            logger.error("[ApiCrudeInv] No data from DB")
            return None

        # 日付でソート
        db_data.sort(key=lambda x: x["date"])

        # 重複除去（同一日付は後の方を優先）
        seen = {}
        for item in db_data:
            seen[item["date"]] = item
        result_data = sorted(seen.values(), key=lambda x: x["date"])

        if not result_data:
            logger.error("[ApiCrudeInv] No data after dedup")
            return None

        latest = result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[ApiCrudeInv] Parsed {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest value={latest.get('value')}"
        )

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "API (American Petroleum Institute)",
                "frequency": "weekly",
                "unit": "M (Million Barrels)",
                "series": "API Weekly Crude Oil Stock Change",
                "data_count": len(result_data),
                "start_date": result_data[0]["date"],
                "end_date": result_data[-1]["date"],
            },
            "cached": False,
            "source": "model",
            "last_updated": now_str,
        }

    def _load_from_db(self) -> List[Dict[str, Any]]:
        """DBから履歴データを取得"""
        try:
            from core.database import get_db_connection

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT datetime_utc, event, actual, estimate, previous
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
                    dt_utc, event, actual, estimate, previous = row
                    if dt_utc:
                        date_str = dt_utc.strftime("%Y-%m-%d")

                        if date_str in seen_dates:
                            continue
                        seen_dates.add(date_str)

                        result.append({
                            "date": date_str,
                            "value": round(float(actual), 3) if actual is not None else None,
                            "forecast": round(float(estimate), 3) if estimate is not None else None,
                            "previous": round(float(previous), 3) if previous is not None else None,
                        })

                logger.info(f"[ApiCrudeInv] Loaded {len(result)} records from DB")
                return result

        except Exception as e:
            logger.error(f"[ApiCrudeInv] DB load error: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(REDIS_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[ApiCrudeInv] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[ApiCrudeInv] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(REDIS_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[ApiCrudeInv] Redis load error: {e}")
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
            logger.error(f"[ApiCrudeInv] File load error: {e}")
        return None


api_weekly_crude_oil_inventories_service = ApiWeeklyCrudeOilInventoriesService()
