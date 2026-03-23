"""
米国長短金利差（イールドスプレッド）サービス

FREDから米国国債利回りデータを取得し、各種スプレッドを計算する。

スプレッド:
  1. 2s10s: 10年 − 2年（最もポピュラーな逆イールド指標）
  2. 3m10y: 10年 − 3ヶ月（NY連銀も重視する景気後退予測指標）
  3. 5s30s: 30年 − 5年
  4. 10s30s: 30年 − 10年
  5. 3m2y: 2年 − 3ヶ月（短期金利期待を反映）

データソース:
  - FRED: DGS2, DGS5, DGS10, DGS30, DGS3MO

更新スケジュール:
  - 毎日 JST 6:00（米国債利回りは前営業日分が翌朝更新される）
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "us_interest_rate_spread_cache.json"

REDIS_KEY = "market:us_interest_rate_spread:data"

FRED_BASE_URL = "https://api.stlouisfed.org/fred"

# FRED系列ID
FRED_SERIES = {
    "dgs3mo": "DGS3MO",  # 3ヶ月国債利回り
    "dgs2": "DGS2",       # 2年国債利回り
    "dgs5": "DGS5",       # 5年国債利回り
    "dgs10": "DGS10",     # 10年国債利回り
    "dgs30": "DGS30",     # 30年国債利回り
}

DATA_YEARS = 30


class UsInterestRateSpreadService:
    """米国長短金利差サービス"""

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

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
            logger.error(f"米国長短金利差データ取得エラー: {e}")

        cached = self._load_from_redis()
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "FRED", "description": "US Interest Rate Spreads"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _fetch_data(self) -> Dict[str, Any]:
        """FREDから各利回りを取得しスプレッドを計算"""
        yield_data: Dict[str, Dict[str, float]] = {}  # {series: {date: value}}

        for key, series_id in FRED_SERIES.items():
            series_data = self._fetch_fred_series(series_id)
            yield_data[key] = series_data
            logger.info(f"  {series_id}: {len(series_data)}件取得")

        if not yield_data.get("dgs10") or not yield_data.get("dgs2"):
            logger.error("主要利回りデータが取得できませんでした")
            return {}

        # 全日付を収集
        all_dates = set()
        for series in yield_data.values():
            all_dates.update(series.keys())
        all_dates_sorted = sorted(all_dates)

        # スプレッド計算
        data: List[Dict[str, Any]] = []
        for date_str in all_dates_sorted:
            dgs3mo = yield_data.get("dgs3mo", {}).get(date_str)
            dgs2 = yield_data.get("dgs2", {}).get(date_str)
            dgs5 = yield_data.get("dgs5", {}).get(date_str)
            dgs10 = yield_data.get("dgs10", {}).get(date_str)
            dgs30 = yield_data.get("dgs30", {}).get(date_str)

            entry: Dict[str, Any] = {"date": date_str}

            # 2s10s = 10年 − 2年
            if dgs10 is not None and dgs2 is not None:
                entry["spread_2s10s"] = round(dgs10 - dgs2, 4)

            # 3m10y = 10年 − 3ヶ月
            if dgs10 is not None and dgs3mo is not None:
                entry["spread_3m10y"] = round(dgs10 - dgs3mo, 4)

            # 5s30s = 30年 − 5年
            if dgs30 is not None and dgs5 is not None:
                entry["spread_5s30s"] = round(dgs30 - dgs5, 4)

            # 10s30s = 30年 − 10年
            if dgs30 is not None and dgs10 is not None:
                entry["spread_10s30s"] = round(dgs30 - dgs10, 4)

            # 3m2y = 2年 − 3ヶ月
            if dgs2 is not None and dgs3mo is not None:
                entry["spread_3m2y"] = round(dgs2 - dgs3mo, 4)

            # 個別利回りも格納
            if dgs3mo is not None:
                entry["dgs3mo"] = dgs3mo
            if dgs2 is not None:
                entry["dgs2"] = dgs2
            if dgs5 is not None:
                entry["dgs5"] = dgs5
            if dgs10 is not None:
                entry["dgs10"] = dgs10
            if dgs30 is not None:
                entry["dgs30"] = dgs30

            # スプレッドが1つでもある場合のみ追加
            if any(k.startswith("spread_") for k in entry):
                data.append(entry)

        latest = data[-1] if data else None

        if latest:
            logger.info(
                f"米国長短金利差: {len(data)}件取得 "
                f"(2s10s: {latest.get('spread_2s10s', 'N/A')}%, "
                f"3m10y: {latest.get('spread_3m10y', 'N/A')}%)"
            )

        return {
            "data": data,
            "latest": latest,
            "metadata": {
                "source": "FRED",
                "series_ids": list(FRED_SERIES.values()),
                "description": "US Treasury Yield Spreads (2s10s, 3m10y, 5s30s, 10s30s, 3m2y)",
                "data_points": len(data),
                "spreads": {
                    "spread_2s10s": "10Y − 2Y",
                    "spread_3m10y": "10Y − 3M",
                    "spread_5s30s": "30Y − 5Y",
                    "spread_10s30s": "30Y − 10Y",
                    "spread_3m2y": "2Y − 3M",
                },
            },
            "cached": False,
            "source": "api",
            "last_updated": datetime.now(JST).isoformat(),
        }

    def _fetch_fred_series(self, series_id: str) -> Dict[str, float]:
        """FRED APIから1つの系列を取得"""
        try:
            if not self.api_key:
                logger.error("FRED_API_KEY not set")
                return {}

            end_date = datetime.now()
            start_date = end_date - timedelta(days=DATA_YEARS * 365)

            url = f"{FRED_BASE_URL}/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date.strftime("%Y-%m-%d"),
                "sort_order": "asc",
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            raw = response.json()

            result: Dict[str, float] = {}
            for obs in raw.get("observations", []):
                if obs.get("value") and obs["value"] != ".":
                    try:
                        result[obs["date"]] = round(float(obs["value"]), 4)
                    except (ValueError, TypeError):
                        continue

            return result

        except Exception as e:
            logger.error(f"FRED {series_id} 取得エラー: {e}")
            return {}

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


us_interest_rate_spread_service = UsInterestRateSpreadService()
