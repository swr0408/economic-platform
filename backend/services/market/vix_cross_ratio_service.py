"""
VIXクロスレシオ (VIX Cross Ratio) サービス

各ボラティリティ指数をVIXで割ったレシオを算出。
アセットクラス間のボラティリティ相対比較に使用。

データソース: yfinance
  - ^VIX:   VIX (S&P 500 IV, 基準)
  - ^VVIX:  VVIX (VIXのボラティリティ)
  - ^SKEW:  SKEW Index (テールリスク)
  - ^MOVE:  MOVE Index (米国債ボラティリティ)
  - ^VXN:   VXN (Nasdaq 100 IV)
  - ^OVX:   OVX (原油 IV)
  - ^GVZ:   GVZ (金 IV)
  - ^GSPC:  S&P 500 (オーバーレイ用)
  - ^TNX:   米国債10年利回り (MOVE/VIXオーバーレイ)
  - ^NDX:   Nasdaq 100 (VXN/VIXオーバーレイ)
  - CL=F:   WTI原油先物 (OVX/VIXオーバーレイ)
  - GC=F:   金先物 (GVZ/VIXオーバーレイ)

レシオ:
  - VVIX/VIX:  VIXのボラティリティ対VIX
  - SKEW/VIX:  テールリスク対VIX
  - MOVE/VIX:  米国債ボラティリティ対VIX
  - VXN/VIX:   Nasdaq IV対VIX (>1 = Nasdaq割高)
  - OVX/VIX:   原油IV対VIX
  - GVZ/VIX:   金IV対VIX

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
DATA_CACHE_FILE = CACHE_DIR / "vix_cross_ratio_cache.json"

REDIS_KEY = "market:vix_cross_ratio:data"

# VIX（分母）+ S&P500（オーバーレイ）
BASE_TICKERS = {
    "vix": "^VIX",
    "sp500": "^GSPC",
}

# レシオ対象（分子）
RATIO_TICKERS = {
    "vvix": "^VVIX",
    "skew": "^SKEW",
    "move": "^MOVE",
    "vxn": "^VXN",
    "ovx": "^OVX",
    "gvz": "^GVZ",
}

# 各レシオチャートのオーバーレイ価格
OVERLAY_TICKERS = {
    "us10y": "^TNX",
    "ndx": "^NDX",
    "wti": "CL=F",
    "gold": "GC=F",
}

ALL_TICKERS = {**BASE_TICKERS, **RATIO_TICKERS, **OVERLAY_TICKERS}

RATIO_KEYS = [
    ("vvix_vix", "vvix"),
    ("skew_vix", "skew"),
    ("move_vix", "move"),
    ("vxn_vix", "vxn"),
    ("ovx_vix", "ovx"),
    ("gvz_vix", "gvz"),
]

DATA_YEARS = 15


class VixCrossRatioService:
    """VIXクロスレシオサービス"""

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
            logger.error(f"VIXクロスレシオデータ取得エラー: {e}")

        cached = self._load_from_redis()
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "yfinance", "description": "VIX Cross Ratios"},
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
        for key, ticker in ALL_TICKERS.items():
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

        vix_map = ticker_data.get("vix", {})
        sp500_map = ticker_data.get("sp500", {})

        # オーバーレイ価格マップ
        us10y_map = ticker_data.get("us10y", {})
        ndx_map = ticker_data.get("ndx", {})
        wti_map = ticker_data.get("wti", {})
        gold_map = ticker_data.get("gold", {})

        all_dates = sorted(set(vix_map.keys()))

        data: List[Dict[str, Any]] = []
        for date_str in all_dates:
            vix_val = vix_map.get(date_str)
            if not vix_val or vix_val <= 0:
                continue

            item: Dict[str, Any] = {
                "date": date_str,
                "vix": round(vix_val, 2),
            }

            sp500_val = sp500_map.get(date_str)
            if sp500_val is not None:
                item["sp500"] = round(sp500_val, 2)

            # オーバーレイ価格
            us10y_val = us10y_map.get(date_str)
            if us10y_val is not None:
                item["us10y"] = round(us10y_val, 4)

            ndx_val = ndx_map.get(date_str)
            if ndx_val is not None:
                item["ndx"] = round(ndx_val, 2)

            wti_val = wti_map.get(date_str)
            if wti_val is not None:
                item["wti"] = round(wti_val, 2)

            gold_val = gold_map.get(date_str)
            if gold_val is not None:
                item["gold"] = round(gold_val, 2)

            # 各ボラティリティ指数の生値とレシオ
            for ratio_key, numerator_key in RATIO_KEYS:
                num_map = ticker_data.get(numerator_key, {})
                num_val = num_map.get(date_str)
                if num_val is not None:
                    item[numerator_key] = round(num_val, 2)
                    item[ratio_key] = round(num_val / vix_val, 4)

            data.append(item)

        latest = data[-1] if data else None

        counts = {k: len(ticker_data.get(k, {})) for k in ALL_TICKERS}
        logger.info(f"VIXクロスレシオ: {len(data)}件取得 {counts}")

        return {
            "data": data,
            "latest": latest,
            "metadata": {
                "source": "yfinance",
                "tickers": ALL_TICKERS,
                "description": "VIX Cross Ratios (VVIX/VIX, SKEW/VIX, MOVE/VIX, VXN/VIX, OVX/VIX, GVZ/VIX)",
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


vix_cross_ratio_service = VixCrossRatioService()
