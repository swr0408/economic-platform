"""
セントルイス連銀金融ストレス指数（STLFSI4）サービス

FREDから STLFSI4 を取得し、S&P500をオーバーレイとして重ねて表示する。
STLFSI4 は 18 の週次データシリーズから構成され、金融ストレスの度合いを測定する。
0 が歴史的平均を示し、正値がストレス増大、負値が平均以下のストレスを意味する。

データソース:
  - FRED: STLFSI4 (St. Louis Fed Financial Stress Index)
  - yfinance: ^GSPC (S&P 500)

更新スケジュール:
  - 毎週木曜日（水曜発表だが取りこぼし防止のため）
  - JST 23:05（CDT 9:05 AM）に初回取得
  - JST 28:05（CDT 14:05 PM = 翌日4:05 JST）に再取得
  - いずれも取得できなければ翌営業日に再確認
"""
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests
import yfinance as yf

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "financial_stress_index_cache.json"

REDIS_KEY = "market:financial_stress_index:data"

FRED_SERIES_ID = "STLFSI4"
FRED_BASE_URL = "https://api.stlouisfed.org/fred"

DATA_YEARS = 20


class FinancialStressIndexService:
    """セントルイス連銀金融ストレス指数（STLFSI4）サービス"""

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
            logger.error(f"金融ストレス指数データ取得エラー: {e}")

        cached = self._load_from_redis()
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "FRED", "description": "St. Louis Fed Financial Stress Index (STLFSI4)"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _fetch_data(self) -> Dict[str, Any]:
        # 1. FREDからSTLFSI4を取得
        stlfsi4_data = self._fetch_fred_data()
        if not stlfsi4_data:
            return {}

        # 2. yfinanceからS&P500を取得
        sp500_map = self._fetch_sp500_data()

        # 3. マージ
        data: List[Dict[str, Any]] = []
        for item in stlfsi4_data:
            date_str = item["date"]
            entry: Dict[str, Any] = {
                "date": date_str,
                "value": item["value"],
            }
            # S&P500は週次データの日付に最も近い取引日を探す
            sp500_val = self._find_nearest_sp500(sp500_map, date_str)
            if sp500_val is not None:
                entry["sp500"] = round(sp500_val, 2)
            data.append(entry)

        latest = data[-1] if data else None

        logger.info(
            f"金融ストレス指数: {len(data)}件取得 "
            f"(STLFSI4: {len(stlfsi4_data)}件, S&P500: {len(sp500_map)}件)"
        )

        return {
            "data": data,
            "latest": latest,
            "metadata": {
                "source": "FRED + yfinance",
                "series_id": FRED_SERIES_ID,
                "description": "St. Louis Fed Financial Stress Index (STLFSI4) with S&P 500 overlay",
                "data_points": len(data),
            },
            "cached": False,
            "source": "api",
            "last_updated": datetime.now(JST).isoformat(),
        }

    def _fetch_fred_data(self) -> List[Dict[str, Any]]:
        """FRED APIからSTLFSI4データを取得"""
        try:
            if not self.api_key:
                logger.error("FRED_API_KEY not set")
                return []

            end_date = datetime.now()
            start_date = end_date - timedelta(days=DATA_YEARS * 365)

            url = f"{FRED_BASE_URL}/series/observations"
            params = {
                "series_id": FRED_SERIES_ID,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date.strftime("%Y-%m-%d"),
                "sort_order": "asc",
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            raw = response.json()

            result = []
            for obs in raw.get("observations", []):
                if obs.get("value") and obs["value"] != ".":
                    try:
                        result.append({
                            "date": obs["date"],
                            "value": round(float(obs["value"]), 4),
                        })
                    except (ValueError, TypeError):
                        continue

            logger.info(f"  STLFSI4: {len(result)}件取得")
            return result

        except Exception as e:
            logger.error(f"FRED STLFSI4取得エラー: {e}")
            return []

    def _fetch_sp500_data(self) -> Dict[str, float]:
        """yfinanceからS&P500の日次終値を取得"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=DATA_YEARS * 365)
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")

            df = yf.download("^GSPC", start=start_str, end=end_str, progress=False, auto_adjust=True)
            if df.empty:
                return {}

            result: Dict[str, float] = {}
            for idx, row in df.iterrows():
                date_str = idx.strftime("%Y-%m-%d")
                close_val = float(row["Close"].iloc[0]) if hasattr(row["Close"], "iloc") else float(row["Close"])
                result[date_str] = close_val

            logger.info(f"  S&P500: {len(result)}件取得")
            return result

        except Exception as e:
            logger.error(f"yfinance S&P500取得エラー: {e}")
            return {}

    def _find_nearest_sp500(self, sp500_map: Dict[str, float], target_date: str) -> Optional[float]:
        """STLFSI4の日付に最も近いS&P500の値を返す（±3日以内）"""
        if not sp500_map:
            return None

        # まず完全一致
        if target_date in sp500_map:
            return sp500_map[target_date]

        # ±3日以内で最も近い日を探す
        try:
            target = datetime.strptime(target_date, "%Y-%m-%d")
            for delta in range(1, 4):
                for d in [timedelta(days=delta), timedelta(days=-delta)]:
                    check_date = (target + d).strftime("%Y-%m-%d")
                    if check_date in sp500_map:
                        return sp500_map[check_date]
        except Exception:
            pass

        return None

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


financial_stress_index_service = FinancialStressIndexService()
