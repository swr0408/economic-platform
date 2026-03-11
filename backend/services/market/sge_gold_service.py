"""
SGE Au(T+D) 上海黄金取引所 日次取引データ サービス

データソース:
  - DB: sge_au_td テーブル（日次）
  - Excel初回インポート + scheduler日次API更新

更新: 6時間TTL (Redis + ファイル)
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "sge_gold_cache.json"

REDIS_KEY = "market:sge_gold:data"


class SgeGoldService:
    """SGE Au(T+D) 日次取引データサービス"""

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
            logger.error(f"[SgeGold] Build error: {e}")
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
            "metadata": {"source": "Shanghai Gold Exchange"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _build_data(self) -> Optional[Dict[str, Any]]:
        from core.database import SessionLocal
        from sqlalchemy import text

        logger.info("[SgeGold] Building data from DB...")

        try:
            with SessionLocal() as session:
                rows = session.execute(
                    text("""
                        SELECT date, open_price, high_price, low_price, close_price,
                               settlement_price, volume_kg, amount_cny, open_interest
                        FROM sge_au_td
                        ORDER BY date ASC
                    """)
                ).fetchall()
        except Exception as e:
            logger.error(f"[SgeGold] DB error: {e}")
            return None

        if not rows:
            logger.error("[SgeGold] No data in DB")
            return None

        result_data: List[Dict[str, Any]] = []
        for row in rows:
            item = {
                "date": row[0].strftime("%Y-%m-%d"),
                "open": round(float(row[1]), 2) if row[1] is not None else None,
                "high": round(float(row[2]), 2) if row[2] is not None else None,
                "low": round(float(row[3]), 2) if row[3] is not None else None,
                "close": round(float(row[4]), 2) if row[4] is not None else None,
                "settlement": round(float(row[5]), 2) if row[5] is not None else None,
                "volume_kg": round(float(row[6]), 2) if row[6] is not None else None,
                "amount_cny": round(float(row[7]), 2) if row[7] is not None else None,
                "open_interest": int(row[8]) if row[8] is not None else None,
            }
            result_data.append(item)

        latest = result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[SgeGold] Built {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest close={latest.get('close')}"
        )

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "Shanghai Gold Exchange",
                "contract": "Au(T+D)",
                "frequency": "daily",
                "data_count": len(result_data),
                "start_date": result_data[0]["date"],
                "end_date": result_data[-1]["date"],
            },
            "cached": False,
            "source": "model",
            "last_updated": now_str,
        }

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(REDIS_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[SgeGold] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[SgeGold] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(REDIS_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[SgeGold] Redis load error: {e}")
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
            logger.error(f"[SgeGold] File load error: {e}")
        return None


sge_gold_service = SgeGoldService()
