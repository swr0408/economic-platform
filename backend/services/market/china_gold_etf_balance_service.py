"""
中国金ETF残高 (518880 華安黄金ETF) サービス

データソース:
  - DB: china_gold_etf_balance テーブル（日次）
  - CSVインポート + scheduler日次SSE API更新

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
DATA_CACHE_FILE = CACHE_DIR / "china_gold_etf_balance_data_cache.json"

REDIS_KEY = "market:china_gold_etf_balance:data"


class ChinaGoldEtfBalanceService:
    """中国金ETF残高 日次サービス"""

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
            logger.error(f"[ChinaGoldEtfBalance] Build error: {e}")
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
            "metadata": {"source": "Shanghai Stock Exchange"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _build_data(self) -> Optional[Dict[str, Any]]:
        from core.database import SessionLocal
        from sqlalchemy import text

        logger.info("[ChinaGoldEtfBalance] Building data from DB...")

        try:
            with SessionLocal() as session:
                rows = session.execute(
                    text("""
                        SELECT date, total_shares_wan
                        FROM china_gold_etf_balance
                        ORDER BY date ASC
                    """)
                ).fetchall()
        except Exception as e:
            logger.error(f"[ChinaGoldEtfBalance] DB error: {e}")
            return None

        if not rows:
            logger.error("[ChinaGoldEtfBalance] No data in DB")
            return None

        result_data: List[Dict[str, Any]] = []
        for row in rows:
            item = {
                "date": row[0].strftime("%Y-%m-%d"),
                "total_shares_wan": round(float(row[1]), 2) if row[1] is not None else None,
            }
            result_data.append(item)

        latest = result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[ChinaGoldEtfBalance] Built {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest={latest.get('total_shares_wan')}"
        )

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "Shanghai Stock Exchange",
                "fund_code": "518880",
                "fund_name": "華安黄金ETF",
                "frequency": "daily",
                "unit": "万份",
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
            logger.error(f"[ChinaGoldEtfBalance] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[ChinaGoldEtfBalance] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(REDIS_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[ChinaGoldEtfBalance] Redis load error: {e}")
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
            logger.error(f"[ChinaGoldEtfBalance] File load error: {e}")
        return None


china_gold_etf_balance_service = ChinaGoldEtfBalanceService()
