"""
原油（WTI） 前年比 (YoY) サービス

yfinance の CL=F 月足終値から前年比(%)を計算して返す。
pct_change(periods=12) 方式

更新スケジュール: 日次（JST 7:00）
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
DATA_CACHE_FILE = CACHE_DIR / "crude_oil_yoy_cache.json"

# Redis
DATA_CACHE_KEY = "market:crude_oil_yoy:data"


class CrudeOilYoyService:
    """原油（WTI） 前年比 サービス（月足ベース）"""

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
        """原油YoYデータを取得"""
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
            logger.error(f"[CrudeOilYoY] Build error: {e}")
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
            "metadata": {"source": "yfinance"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """yfinanceからWTI原油月足を取得し、前年比を計算（pct_change(12)方式）"""
        import yfinance as yf
        import pandas as pd

        logger.info("[CrudeOilYoY] Building data (monthly)...")

        try:
            ticker = yf.Ticker("CL=F")
            end_dt = datetime.now(JST) + timedelta(days=35)
            hist = ticker.history(
                start="2013-01-01",
                end=end_dt.strftime("%Y-%m-%d"),
                interval="1mo",
            )
            if hist.empty:
                logger.error("[CrudeOilYoY] No monthly data from yfinance")
                return None

            df = hist[["Close"]].copy()
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()

            # 月足の終値から前年比（12ヶ月前比）
            df["YoY"] = df["Close"].pct_change(periods=12) * 100

            result_data: List[Dict[str, Any]] = []
            for idx, row in df.iterrows():
                yoy_val = row["YoY"]
                close_val = row["Close"]
                if pd.isna(yoy_val) or pd.isna(close_val):
                    continue
                dt = pd.Timestamp(idx)
                date_str = dt.strftime("%Y-%m-%d")
                result_data.append({
                    "date": date_str,
                    "crude_oil_yoy": round(float(yoy_val), 2),
                    "crude_oil_close": round(float(close_val), 2),
                })

            if not result_data:
                return None

            latest = result_data[-1].copy()
            now_str = datetime.now(JST).isoformat()

            logger.info(
                f"[CrudeOilYoY] Built {len(result_data)} monthly data points "
                f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
                f"latest YoY={latest['crude_oil_yoy']}%"
            )

            return {
                "data": result_data,
                "latest": latest,
                "metadata": {
                    "source": "yfinance (CL=F)",
                    "indicator": "Crude Oil (WTI) YoY (Monthly)",
                    "unit": "%",
                    "frequency": "monthly",
                    "data_count": len(result_data),
                    "start_date": result_data[0]["date"],
                    "end_date": result_data[-1]["date"],
                },
                "cached": False,
                "source": "model",
                "last_updated": now_str,
            }

        except Exception as e:
            logger.error(f"[CrudeOilYoY] yfinance error: {e}")
            return None

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(DATA_CACHE_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[CrudeOilYoY] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[CrudeOilYoY] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(DATA_CACHE_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[CrudeOilYoY] Redis load error: {e}")
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
            logger.error(f"[CrudeOilYoY] File load error: {e}")
        return None


# シングルトン
crude_oil_yoy_service = CrudeOilYoyService()
