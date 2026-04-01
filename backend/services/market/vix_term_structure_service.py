"""
VIX期間構造 (VIX Term Structure) サービス

データソース: yfinance
  - ^VIX9D: VIX 9-Day
  - ^VIX: VIX (30-Day)
  - ^VIX3M: VIX 3-Month
  - ^GSPC: S&P 500

計算:
  - VIX9D/VIX レシオ: VIX9D ÷ VIX (1未満 = コンタンゴ / 1超 = バックワーデーション)
  - VIX/VIX3M レシオ: VIX ÷ VIX3M (1未満 = コンタンゴ / 1超 = バックワーデーション)

更新スケジュール: 日次（JST 7:00）
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
import yfinance as yf
import pandas as pd

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "vix_term_structure_cache.json"

REDIS_KEY = "market:vix_term_structure:data"

TICKERS = {
    "vix9d": "^VIX9D",
    "vix": "^VIX",
    "vix3m": "^VIX3M",
    "sp500": "^GSPC",
}

DATA_YEARS = 15


class VixTermStructureService:
    """VIX期間構造サービス"""

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
            logger.error(f"VIX期間構造データ取得エラー: {e}")

        cached = self._load_from_redis()
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "yfinance", "description": "VIX Term Structure"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _fetch_data(self) -> Dict[str, Any]:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=DATA_YEARS * 365)
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # yfinanceは並列ダウンロードすると内部状態が競合するため逐次取得
        ticker_data: Dict[str, Dict[str, float]] = {}
        for key, ticker in TICKERS.items():
            try:
                df = yf.download(ticker, start=start_str, end=end_str, progress=False, auto_adjust=False)
                if df.empty:
                    ticker_data[key] = {}
                    continue
                # MultiIndex列からClose値を安全に取得
                if isinstance(df.columns, pd.MultiIndex):
                    close_series = df[("Close", ticker)]
                else:
                    close_series = df["Close"]
                result: Dict[str, float] = {}
                for idx, val in close_series.items():
                    date_str = idx.strftime("%Y-%m-%d")
                    result[date_str] = round(float(val), 4)
                ticker_data[key] = result
            except Exception as e:
                logger.error(f"yfinance {ticker} ダウンロードエラー: {e}")
                ticker_data[key] = {}

        vix9d_map = ticker_data.get("vix9d", {})
        vix_map = ticker_data.get("vix", {})
        vix3m_map = ticker_data.get("vix3m", {})
        sp500_map = ticker_data.get("sp500", {})

        all_dates = sorted(set(vix_map.keys()) | set(vix9d_map.keys()) | set(vix3m_map.keys()))

        data: List[Dict[str, Any]] = []
        for date_str in all_dates:
            vix_val = vix_map.get(date_str)
            if vix_val is None:
                continue

            vix9d_val = vix9d_map.get(date_str)
            vix3m_val = vix3m_map.get(date_str)
            sp500_val = sp500_map.get(date_str)

            ratio_9d_vix = None
            ratio_vix_3m = None

            if vix9d_val is not None and vix_val > 0:
                ratio_9d_vix = round(vix9d_val / vix_val, 4)
            if vix3m_val is not None and vix3m_val > 0:
                ratio_vix_3m = round(vix_val / vix3m_val, 4)

            item: Dict[str, Any] = {
                "date": date_str,
                "vix": round(vix_val, 2),
            }
            if vix9d_val is not None:
                item["vix9d"] = round(vix9d_val, 2)
            if vix3m_val is not None:
                item["vix3m"] = round(vix3m_val, 2)
            if sp500_val is not None:
                item["sp500"] = round(sp500_val, 2)
            if ratio_9d_vix is not None:
                item["ratio_9d_vix"] = ratio_9d_vix
            if ratio_vix_3m is not None:
                item["ratio_vix_3m"] = ratio_vix_3m

            data.append(item)

        latest = data[-1] if data else None

        logger.info(
            f"VIX期間構造: {len(data)}件取得 "
            f"(VIX9D: {len(vix9d_map)}, VIX: {len(vix_map)}, VIX3M: {len(vix3m_map)})"
        )

        return {
            "data": data,
            "latest": latest,
            "metadata": {
                "source": "yfinance",
                "tickers": TICKERS,
                "description": "VIX Term Structure (VIX9D / VIX / VIX3M)",
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


vix_term_structure_service = VixTermStructureService()
