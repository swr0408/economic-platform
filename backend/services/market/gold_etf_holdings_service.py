"""
金ETF保有残高 サービス

データソース:
  - DB: gold_etf_holdings テーブル（日次、SPDR Gold Shares）
  - 金価格日足: yfinance (GC=F)

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

# キャッシュ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "gold_etf_holdings_cache.json"

# Redis
DATA_CACHE_KEY = "market:gold_etf_holdings:data"


class GoldEtfHoldingsService:
    """金ETF保有残高サービス"""

    def _should_refresh(self) -> bool:
        try:
            cached = redis_client.get(DATA_CACHE_KEY)
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
        """金ETF保有残高データを取得"""
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
            logger.error(f"[GoldEtf] Build error: {e}")
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
            "latest_gold": None,
            "metadata": {"source": "SPDR Gold Shares + yfinance"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """DBから取得し金価格日足を補完"""
        import yfinance as yf
        import pandas as pd
        from core.database import SessionLocal
        from sqlalchemy import text

        logger.info("[GoldEtf] Building data...")

        # 1. DBから全データ取得
        try:
            with SessionLocal() as session:
                rows = session.execute(text("""
                    SELECT date, holdings_ton, gold_price_usd
                    FROM gold_etf_holdings
                    ORDER BY date ASC
                """)).fetchall()
        except Exception as e:
            logger.error(f"[GoldEtf] DB error: {e}")
            return None

        if not rows:
            logger.error("[GoldEtf] No data in DB")
            return None

        # 2. yfinance GC=F 日足で最新金価格を取得（最新値ボックス用）
        gold_latest: Optional[Dict[str, Any]] = None
        try:
            ticker = yf.Ticker("GC=F")
            hist_d = ticker.history(period="5d", interval="1d")
            if not hist_d.empty:
                hist_d.index = pd.to_datetime(hist_d.index).tz_localize(None)
                hist_d = hist_d.sort_index()
                last_idx = hist_d.index[-1]
                gold_latest = {
                    "date": last_idx.strftime("%Y-%m-%d"),
                    "close": round(float(hist_d.iloc[-1]["Close"]), 2),
                }
        except Exception as e:
            logger.warning(f"[GoldEtf] yfinance error: {e}")

        # 3. データ構築
        result_data: List[Dict[str, Any]] = []
        for row in rows:
            date_str = row[0].strftime("%Y-%m-%d")
            holdings = round(float(row[1]), 2) if row[1] is not None else None
            gold_price = round(float(row[2]), 2) if row[2] is not None else None

            result_data.append({
                "date": date_str,
                "holdings_ton": holdings,
                "gold_price_usd": gold_price,
            })

        if not result_data:
            return None

        # 最新のholdings_tonがある行を探す
        latest = None
        for item in reversed(result_data):
            if item.get("holdings_ton") is not None:
                latest = item.copy()
                break
        if latest is None:
            latest = result_data[-1].copy()

        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[GoldEtf] Built {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest holdings={latest.get('holdings_ton')} ton, "
            f"latest_gold={gold_latest}"
        )

        return {
            "data": result_data,
            "latest": latest,
            "latest_gold": gold_latest,
            "metadata": {
                "source": "SPDR Gold Shares + yfinance (GC=F)",
                "indicator": "Gold ETF Holdings (SPDR)",
                "unit_holdings": "ton",
                "unit_price": "USD/oz",
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
            redis_client.set(DATA_CACHE_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[GoldEtf] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[GoldEtf] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(DATA_CACHE_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[GoldEtf] Redis load error: {e}")
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
            logger.error(f"[GoldEtf] File load error: {e}")
        return None


# シングルトン
gold_etf_holdings_service = GoldEtfHoldingsService()
