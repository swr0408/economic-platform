"""
Russell 2000 / Russell 1000 レシオサービス

Russell 2000 (小型株) / Russell 1000 (大型株) の比率を算出し、
小型株 vs 大型株のリスク選好のシグナルとして使用。
Russell 2000 の価格も重ねて表示。

データソース: yfinance
  - ^RUT:  Russell 2000 (小型株指数)
  - ^RUI:  Russell 1000 (大型株指数)

更新スケジュール: 日次（JST 7:00）
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import yfinance as yf

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "russell2000_russell1000_cache.json"

REDIS_KEY = "market:russell2000_russell1000:data"

UNIQUE_TICKERS = {
    "russell2000": "^RUT",
    "russell1000": "^RUI",
}

DATA_YEARS = 15


class Russell2000Russell1000Service:
    """Russell 2000 / Russell 1000 レシオサービス"""

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
            today_refresh = now.replace(hour=6, minute=0, second=0, microsecond=0)
            if now >= today_refresh and last_updated < today_refresh:
                return True
            return False
        except Exception:
            return True

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        if not force_refresh and not self._should_refresh():
            cached = self._load_from_redis()
            if cached and cached.get("data"):
                return cached

        try:
            data = self._fetch_data()
            if data and data.get("data"):
                self._save_to_cache(data)
                return data
        except Exception as e:
            logger.error(f"Russell2000/Russell1000データ取得エラー: {e}")

        cached = self._load_from_redis()
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "yfinance", "description": "Russell 2000 / Russell 1000 Ratio"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _fetch_data(self) -> Dict[str, Any]:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=DATA_YEARS * 365)
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # yfinanceは逐次取得（並列だと内部状態が競合）
        ticker_data: Dict[str, Dict[str, float]] = {}
        for key, ticker in UNIQUE_TICKERS.items():
            try:
                df = yf.download(ticker, start=start_str, end=end_str, progress=False, auto_adjust=True)
                if df.empty:
                    ticker_data[key] = {}
                    continue
                result: Dict[str, float] = {}
                for idx, row in df.iterrows():
                    date_str = idx.strftime("%Y-%m-%d")
                    close_val = float(row["Close"].iloc[0]) if hasattr(row["Close"], "iloc") else float(row["Close"])
                    result[date_str] = round(close_val, 4)
                ticker_data[key] = result
                logger.info(f"  {key} ({ticker}): {len(result)}件")
            except Exception as e:
                logger.error(f"yfinance {ticker} ダウンロードエラー: {e}")
                ticker_data[key] = {}

        r2000_map = ticker_data.get("russell2000", {})
        r1000_map = ticker_data.get("russell1000", {})

        # 両方にデータがある日付のみ使用
        all_dates = sorted(set(r2000_map.keys()) & set(r1000_map.keys()))

        data: List[Dict[str, Any]] = []
        for date_str in all_dates:
            r2000_val = r2000_map.get(date_str)
            r1000_val = r1000_map.get(date_str)
            if r2000_val is None or r1000_val is None or r1000_val <= 0:
                continue

            ratio = round(r2000_val / r1000_val, 4)
            data.append({
                "date": date_str,
                "russell2000": round(r2000_val, 2),
                "russell1000": round(r1000_val, 2),
                "ratio": ratio,
            })

        latest = data[-1] if data else None

        logger.info(
            f"Russell2000/Russell1000: {len(data)}件取得 "
            f"(R2000: {len(r2000_map)}件, R1000: {len(r1000_map)}件)"
        )

        return {
            "data": data,
            "latest": latest,
            "metadata": {
                "source": "yfinance",
                "tickers": UNIQUE_TICKERS,
                "description": "Russell 2000 / Russell 1000 Ratio with Russell 2000 overlay",
                "data_points": len(data),
            },
            "cached": False,
            "source": "api",
            "last_updated": datetime.now(JST).isoformat(),
        }

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(REDIS_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"Redis保存エラー: {e}")

        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            logger.error(f"ファイルキャッシュ保存エラー: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            cached = redis_client.get(REDIS_KEY)
            if cached:
                cached["cached"] = True
                cached["source"] = "redis"
                return cached
        except Exception:
            pass
        return None

    def _load_from_file(self) -> Optional[Dict[str, Any]]:
        try:
            if DATA_CACHE_FILE.exists():
                with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["cached"] = True
                data["source"] = "file"
                return data
        except Exception:
            pass
        return None


russell2000_russell1000_service = Russell2000Russell1000Service()
