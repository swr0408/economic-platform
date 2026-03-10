"""
金プレミアム/ディスカウント サービス（中国・インド）

データソース:
  - DB: gold_premium テーブル（Excel初期インポート + GoldHub API週次積み上げ）
  - 全履歴: 2003~ (Excel) + 最新分 (GoldHub API)

キャッシュ: Redis 6h TTL + JSONファイル
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
DATA_CACHE_FILE = CACHE_DIR / "gold_premium_cache.json"

REDIS_CACHE_KEY = "market:gold_premium:data"


class GoldPremiumService:
    """金プレミアム/ディスカウント（中国・インド）サービス"""

    def _should_refresh(self) -> bool:
        try:
            cached = redis_client.get(REDIS_CACHE_KEY)
            if not cached:
                return True
            last_updated_str = cached.get("last_updated")
            if not last_updated_str:
                return True
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)
            if (now - last_updated).total_seconds() < 6 * 3600:
                return False
            return True
        except Exception:
            return True

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """金プレミアム/ディスカウントデータを取得"""
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
            logger.error(f"[GoldPremium] Build error: {e}")
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
            "latest_china": None,
            "latest_india": None,
            "metadata": {"source": "World Gold Council"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """DBからデータを構築"""
        try:
            from core.database import SessionLocal
        except ImportError:
            from backend.core.database import SessionLocal
        from sqlalchemy import text

        logger.info("[GoldPremium] Building data from DB...")

        try:
            with SessionLocal() as session:
                rows = session.execute(text("""
                    SELECT date, china, india
                    FROM gold_premium
                    ORDER BY date ASC
                """)).fetchall()
        except Exception as e:
            logger.error(f"[GoldPremium] DB error: {e}")
            return None

        if not rows:
            logger.warning("[GoldPremium] No data in DB")
            return None

        result_data: List[Dict[str, Any]] = []
        for row in rows:
            date_str = row[0].strftime("%Y-%m-%d")
            china_val = round(float(row[1]), 2) if row[1] is not None else None
            india_val = round(float(row[2]), 2) if row[2] is not None else None
            result_data.append({
                "date": date_str,
                "china": china_val,
                "india": india_val,
            })

        # 最新値
        latest_china = None
        latest_india = None
        for item in reversed(result_data):
            if latest_china is None and item.get("china") is not None:
                latest_china = {"date": item["date"], "value": item["china"]}
            if latest_india is None and item.get("india") is not None:
                latest_india = {"date": item["date"], "value": item["india"]}
            if latest_china and latest_india:
                break

        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[GoldPremium] Built {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest_china={latest_china}, latest_india={latest_india}"
        )

        return {
            "data": result_data,
            "latest_china": latest_china,
            "latest_india": latest_india,
            "metadata": {
                "source": "World Gold Council (DB)",
                "indicator": "Gold Premium/Discount (China & India)",
                "unit": "US$/oz (5-day moving average)",
                "frequency": "daily (business days)",
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
            redis_client.set(REDIS_CACHE_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[GoldPremium] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[GoldPremium] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(REDIS_CACHE_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[GoldPremium] Redis load error: {e}")
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
            logger.error(f"[GoldPremium] File load error: {e}")
        return None


# シングルトン
gold_premium_service = GoldPremiumService()
