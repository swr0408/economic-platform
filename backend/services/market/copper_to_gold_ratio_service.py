"""
銅金レシオ (Copper-to-Gold Ratio) サービス

銅価格(HG=F) ÷ 金価格(GC=F) のレシオを算出。
景気サイクルのシグナルとして使用される。
レシオ上昇 = リスクオン（景気改善期待）、レシオ低下 = リスクオフ（景気後退期待）。

データソース: yfinance
  - HG=F: Copper Futures (COMEX)
  - GC=F: Gold Futures (COMEX)

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
DATA_CACHE_FILE = CACHE_DIR / "copper_to_gold_ratio_cache.json"

REDIS_KEY = "market:copper_to_gold_ratio:data"

TICKERS = {
    "copper": "HG=F",
    "gold": "GC=F",
}

DATA_YEARS = 15


class CopperToGoldRatioService:
    """銅金レシオサービス"""

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
            logger.error(f"銅金レシオデータ取得エラー: {e}")

        cached = self._load_from_redis()
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "yfinance", "description": "Copper-to-Gold Ratio"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _fetch_data(self) -> Dict[str, Any]:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=DATA_YEARS * 365)
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        ticker_data: Dict[str, Dict[str, float]] = {}
        for key, ticker in TICKERS.items():
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

        copper_map = ticker_data.get("copper", {})
        gold_map = ticker_data.get("gold", {})

        # 銅の日付をベースに
        all_dates = sorted(set(copper_map.keys()) & set(gold_map.keys()))

        data: List[Dict[str, Any]] = []
        for date_str in all_dates:
            copper_val = copper_map.get(date_str)
            gold_val = gold_map.get(date_str)
            if copper_val is not None and gold_val is not None and gold_val > 0:
                # 銅(セント/ポンド) / 金(ドル/オンス) × 1000 でスケーリング
                # 一般的な銅金レシオの表示方法
                ratio = round((copper_val / gold_val) * 1000, 4)
                data.append({
                    "date": date_str,
                    "value": ratio,
                    "copper": round(copper_val, 2),
                    "gold": round(gold_val, 2),
                })

        latest = data[-1] if data else None

        logger.info(f"銅金レシオ: {len(data)}件取得 (copper: {len(copper_map)}件, gold: {len(gold_map)}件)")

        return {
            "data": data,
            "latest": latest,
            "metadata": {
                "source": "yfinance",
                "tickers": TICKERS,
                "description": "Copper-to-Gold Ratio (HG/GC × 1000)",
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


copper_to_gold_ratio_service = CopperToGoldRatioService()
