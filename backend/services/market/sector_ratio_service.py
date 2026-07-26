"""
セクターレシオ (Sector Ratio) サービス

ETFの価格比を算出し、景気サイクル・クレジットリスクのシグナルとして使用。

データソース: yfinance
  - XLY:   Consumer Discretionary SPDR (消費循環)
  - XLP:   Consumer Staples SPDR (消費安定)
  - XLF:   Financial SPDR (金融)
  - XLU:   Utilities SPDR (公益)
  - HYG:   iShares iBoxx HY Corp Bond (ハイイールド)
  - LQD:   iShares iBoxx IG Corp Bond (投資適格)
  - IEF:   iShares 7-10 Year Treasury (中期国債)
  - LBR=F: Lumber Futures (木材先物, CME新契約)
  - GC=F:  Gold Futures (金先物)
  - ^GSPC: S&P 500 (オーバーレイ用)

レシオ:
  - XLY/XLP:     消費循環 / 消費安定 → 景気サイクルの最もクリーンなシグナル
  - XLF/XLU:     金融 / 公益 → 金利・景気プロキシ
  - HYG/LQD:     ハイイールド / 投資適格 → クレジットリスクアペタイト
  - HYG/IEF:     ハイイールド / 中期国債 → リアルタイムクレジットスプレッド代替
  - Lumber/Gold:  木材 / 金 → 住宅需要vs安全資産。先行指標

更新スケジュール: 日次（JST 7:00）
"""
import json
import logging
import math
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
DATA_CACHE_FILE = CACHE_DIR / "sector_ratio_cache.json"

REDIS_KEY = "market:sector_ratio:data"

# S&P500（オーバーレイ）
BASE_TICKERS = {
    "sp500": "^GSPC",
}

# レシオ分子
NUMERATOR_TICKERS = {
    "xly": "XLY",
    "xlf": "XLF",
    "hyg_1": "HYG",  # HYG/LQD用
    "hyg_2": "HYG",  # HYG/IEF用（同じティッカーだが区別のためキーを分ける）
}

# レシオ分母
DENOMINATOR_TICKERS = {
    "xlp": "XLP",
    "xlu": "XLU",
    "lqd": "LQD",
    "ief": "IEF",
}

# 実際にダウンロードするユニークなティッカー
UNIQUE_TICKERS = {
    "xly": "XLY",
    "xlp": "XLP",
    "xlf": "XLF",
    "xlu": "XLU",
    "hyg": "HYG",
    "lqd": "LQD",
    "ief": "IEF",
    "lumber": "LBR=F",
    "gold": "GC=F",
    "sp500": "^GSPC",
}

# レシオ定義: (output_key, numerator_ticker_key, denominator_ticker_key)
RATIO_DEFS = [
    ("xly_xlp", "xly", "xlp"),
    ("xlf_xlu", "xlf", "xlu"),
    ("hyg_lqd", "hyg", "lqd"),
    ("hyg_ief", "hyg", "ief"),
    ("lumber_gold", "lumber", "gold"),
]

DATA_YEARS = 15


class SectorRatioService:
    """セクターレシオサービス"""

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
            logger.error(f"セクターレシオデータ取得エラー: {e}")

        cached = self._load_from_redis()
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "yfinance", "description": "Sector Ratios"},
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

        sp500_map = ticker_data.get("sp500", {})

        # 全日付はXLY（最も流動的なETF）をベースに
        xly_map = ticker_data.get("xly", {})
        all_dates = sorted(set(xly_map.keys()))

        data: List[Dict[str, Any]] = []
        for date_str in all_dates:
            item: Dict[str, Any] = {"date": date_str}

            # S&P500オーバーレイ
            # 注意: yfinanceは特定日にNaNを返すことがある。NaNはJSONとして不正で
            #       (json.dumpsが`NaN`を出力→フロントのJSON.parseが失敗→チャート全体が
            #       「データがありません」表示になる)、必ず有限値のみ採用する。
            sp500_val = sp500_map.get(date_str)
            if sp500_val is not None and math.isfinite(sp500_val):
                item["sp500"] = round(sp500_val, 2)

            # 各ETF/先物の生値
            has_any_ratio = False
            for key in ["xly", "xlp", "xlf", "xlu", "hyg", "lqd", "ief", "lumber", "gold"]:
                val = ticker_data.get(key, {}).get(date_str)
                if val is not None and math.isfinite(val):
                    item[key] = round(val, 2)

            # レシオ計算
            for ratio_key, num_key, den_key in RATIO_DEFS:
                num_val = ticker_data.get(num_key, {}).get(date_str)
                den_val = ticker_data.get(den_key, {}).get(date_str)
                if (
                    num_val is not None and den_val is not None
                    and math.isfinite(num_val) and math.isfinite(den_val)
                    and den_val > 0
                ):
                    item[ratio_key] = round(num_val / den_val, 4)
                    has_any_ratio = True

            if has_any_ratio:
                data.append(item)

        latest = data[-1] if data else None

        counts = {k: len(ticker_data.get(k, {})) for k in UNIQUE_TICKERS}
        logger.info(f"セクターレシオ: {len(data)}件取得 {counts}")

        return {
            "data": data,
            "latest": latest,
            "metadata": {
                "source": "yfinance",
                "tickers": UNIQUE_TICKERS,
                "description": "Sector Ratios (XLY/XLP, XLF/XLU, HYG/LQD, HYG/IEF, Lumber/Gold)",
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


sector_ratio_service = SectorRatioService()
