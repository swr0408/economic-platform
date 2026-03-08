"""
CNN Fear & Greed Index サービス

データ項目:
- fear_greed: Fear & Greed Index 総合スコア (0-100)
- rating: センチメント文字列 (extreme fear / fear / neutral / greed / extreme greed)
- sp500: S&P 500 日足終値（yfinance経由）

データソース:
- CNN Fear & Greed Index API:
  https://production.dataviz.cnn.io/index/fearandgreed/graphdata/{start_date}
- S&P 500: yfinance (^GSPC)

更新スケジュール: 毎営業日 7:10 PM ET
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

# キャッシュ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "fear_greed_cache.json"

# Redis
DATA_CACHE_KEY = "market:fear_greed:data"

# CNN API
CNN_API_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
CNN_START_DATE = "2021-02-01"

# HTTP headers (CNN blocks non-browser requests without proper headers)
CNN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://edition.cnn.com/",
    "Accept-Language": "en-US,en;q=0.9",
}


class FearGreedService:
    """CNN Fear & Greed Index データ取得サービス"""

    def _should_refresh(self) -> bool:
        """キャッシュの更新が必要かどうか判定"""
        try:
            cached = redis_client.get(DATA_CACHE_KEY)
            if not cached:
                return True

            last_updated_str = cached.get("last_updated")
            if not last_updated_str:
                return True

            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)

            # 6時間以内に更新されていればスキップ
            if (now - last_updated).total_seconds() < 6 * 3600:
                return False

            return True
        except Exception:
            return True

    def get_fear_greed_data(
        self, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Fear & Greed Index データを取得"""
        # キャッシュ確認
        if not force_refresh and not self._should_refresh():
            cached = self._load_from_redis()
            if cached and cached.get("data"):
                return cached

        # CNN APIからデータ取得
        try:
            data = self._fetch_from_cnn()
            if data and data.get("data"):
                # S&P 500 データをマージ
                data = self._merge_sp500(data)
                self._save_to_cache(data)
                return data
        except Exception as e:
            logger.error(f"[FearGreed] CNN API error: {e}")

        # フォールバック: Redis → ファイル
        cached = self._load_from_redis()
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "CNN Fear & Greed Index"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _fetch_from_cnn(self) -> Optional[Dict[str, Any]]:
        """CNN APIからFear & Greedデータを取得"""
        url = f"{CNN_API_URL}/{CNN_START_DATE}"
        logger.info(f"[FearGreed] Fetching from CNN API: {url}")

        resp = requests.get(url, headers=CNN_HEADERS, timeout=30)
        resp.raise_for_status()
        raw = resp.json()

        # fear_and_greed_historical からグラフデータを抽出
        historical = raw.get("fear_and_greed_historical", {})
        graph_data = historical.get("data", [])
        current = raw.get("fear_and_greed", {})

        if not graph_data:
            logger.warning("[FearGreed] No historical data in API response")
            return None

        # データ変換: timestamp (ms) → YYYY-MM-DD
        result_data: List[Dict[str, Any]] = []
        for point in graph_data:
            ts_ms = point.get("x")
            score = point.get("y")
            rating = point.get("rating", "")

            if ts_ms is None or score is None:
                continue

            dt = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
            date_str = dt.strftime("%Y-%m-%d")

            result_data.append({
                "date": date_str,
                "score": round(score, 1),
                "rating": rating,
            })

        # 日付でソートし、重複を除去（最後のものを採用）
        result_data.sort(key=lambda x: x["date"])
        seen_dates: Dict[str, int] = {}
        for i, item in enumerate(result_data):
            seen_dates[item["date"]] = i
        result_data = [result_data[i] for i in sorted(seen_dates.values())]

        # 最新値
        latest = None
        if result_data:
            latest = result_data[-1].copy()

        # current情報を追加
        if current:
            latest_info = {
                "score": round(current.get("score", 0), 1),
                "rating": current.get("rating", ""),
                "previous_close": round(current.get("previous_close", 0), 1),
                "previous_1_week": round(current.get("previous_1_week", 0), 1),
                "previous_1_month": round(current.get("previous_1_month", 0), 1),
                "previous_1_year": (
                    round(current.get("previous_1_year", 0), 1)
                    if current.get("previous_1_year") is not None
                    else None
                ),
            }
            if latest:
                latest.update(latest_info)

        now_str = datetime.now(JST).isoformat()

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "CNN Fear & Greed Index",
                "data_count": len(result_data),
                "start_date": result_data[0]["date"] if result_data else None,
                "end_date": result_data[-1]["date"] if result_data else None,
            },
            "cached": False,
            "source": "api",
            "last_updated": now_str,
        }

    def _merge_sp500(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """yfinanceでS&P 500の日足データを取得し、Fear & Greedデータにマージ"""
        try:
            import yfinance as yf

            # データ範囲を確認
            items = data.get("data", [])
            if not items:
                return data

            start_date = items[0]["date"]
            end_dt = datetime.strptime(items[-1]["date"], "%Y-%m-%d") + timedelta(days=5)
            end_date = end_dt.strftime("%Y-%m-%d")

            ticker = yf.Ticker("^GSPC")
            hist = ticker.history(start=start_date, end=end_date, interval="1d")

            if hist.empty:
                logger.warning("[FearGreed] No S&P 500 data from yfinance")
                return data

            # 日付 → 終値のマップ
            sp500_map: Dict[str, float] = {}
            for idx, row in hist.iterrows():
                date_str = idx.strftime("%Y-%m-%d")
                sp500_map[date_str] = round(float(row["Close"]), 2)

            # マージ
            for item in items:
                item["sp500"] = sp500_map.get(item["date"])

            # latest にも追加
            if data.get("latest") and items:
                latest_date = data["latest"].get("date")
                if latest_date and latest_date in sp500_map:
                    data["latest"]["sp500"] = sp500_map[latest_date]

            return data
        except Exception as e:
            logger.error(f"[FearGreed] S&P 500 merge error: {e}")
            return data

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        """Redis + ファイルキャッシュに保存"""
        try:
            redis_client.set(DATA_CACHE_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[FearGreed] Redis save error: {e}")

        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[FearGreed] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        """Redisキャッシュから読み込み"""
        try:
            data = redis_client.get(DATA_CACHE_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[FearGreed] Redis load error: {e}")
        return None

    def _load_from_file(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュから読み込み"""
        try:
            if DATA_CACHE_FILE.exists():
                with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["cached"] = True
                data["source"] = "file"
                return data
        except Exception as e:
            logger.error(f"[FearGreed] File load error: {e}")
        return None


# シングルトン
fear_greed_service = FearGreedService()
