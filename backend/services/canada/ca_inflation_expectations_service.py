"""
カナダインフレ期待（BOC消費者調査）サービス

指標:
- 1年先インフレ期待（CES_C1_SHORT_TERM）
- 2年先インフレ期待（CES_C1_MID_TERM）
- 5年先インフレ期待（CES_C1_LONG_TERM）

データソース:
- Bank of Canada Valet API
- https://www.bankofcanada.ca/valet/observations/CES_C1_SHORT_TERM/json
- https://www.bankofcanada.ca/valet/observations/CES_C1_MID_TERM/json
- https://www.bankofcanada.ca/valet/observations/CES_C1_LONG_TERM/json

発表スケジュール:
- 四半期ごと（消費者調査と同時発表）
- BOC発表スケジュール参照
"""
import json
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client
from services.canada.fmp_next_release_utils import get_next_release_by_pattern


JST = ZoneInfo("Asia/Tokyo")
TORONTO = ZoneInfo("America/Toronto")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "canada" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ca_inflation_expectations_cache.json"

# BOC Valet API シリーズID
SERIES_SHORT_TERM = "CES_C1_SHORT_TERM"  # 1年先インフレ期待
SERIES_MID_TERM = "CES_C1_MID_TERM"       # 2年先インフレ期待
SERIES_LONG_TERM = "CES_C1_LONG_TERM"     # 5年先インフレ期待

VALET_BASE_URL = "https://www.bankofcanada.ca/valet/observations"

# FMPイベントパターン（Business Outlook Survey と同時発表）
FMP_EVENT_PATTERN = "Business Outlook Survey"


class CaInflationExpectationsService:
    """カナダインフレ期待サービス"""

    DATA_CACHE_KEY = "canada:ca_inflation_expectations:data"
    ECONALPHA_ID = "ca_inflation_expectations"

    def __init__(self):
        pass

    def get_ca_inflation_expectations_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダインフレ期待データを取得"""
        # 次回発表日を取得
        next_release = get_next_release_by_pattern(FMP_EVENT_PATTERN, country="CA")

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # データソースから取得
        result = self._load_from_source()
        if result:
            # 最新値を取得
            latest = result[-1] if result else None

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Bank of Canada",
                    "indicator": "Inflation Expectations",
                    "description": "カナダ消費者インフレ期待（1年・2年・5年先）",
                    "unit": "%",
                    "series_ids": [SERIES_SHORT_TERM, SERIES_MID_TERM, SERIES_LONG_TERM],
                },
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_source(self) -> List[Dict[str, Any]]:
        """BOC Valet APIからデータを取得"""
        try:
            # 2014年から現在までのデータを取得
            today = date.today()
            start_date = "2014-01-01"
            end_date = today.strftime("%Y-%m-%d")

            # 3つのシリーズを取得
            short_term_data = self._fetch_series(SERIES_SHORT_TERM, start_date, end_date)
            mid_term_data = self._fetch_series(SERIES_MID_TERM, start_date, end_date)
            long_term_data = self._fetch_series(SERIES_LONG_TERM, start_date, end_date)

            # データをマージ
            result = self._merge_series_data(short_term_data, mid_term_data, long_term_data)

            print(f"[CaInflationExp] Loaded {len(result)} quarterly records")
            if result:
                print(f"[CaInflationExp] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CaInflationExp] Latest: {latest['date']} - 1y: {latest.get('exp_1y')}%, 2y: {latest.get('exp_2y')}%, 5y: {latest.get('exp_5y')}%")

            return result

        except Exception as e:
            print(f"[CaInflationExp] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_series(self, series_id: str, start_date: str, end_date: str) -> Dict[str, float]:
        """単一系列のデータを取得"""
        try:
            url = f"{VALET_BASE_URL}/{series_id}/json?start_date={start_date}&end_date={end_date}"
            print(f"[CaInflationExp] Fetching {series_id} from: {url}")

            resp = requests.get(url, timeout=30)
            resp.raise_for_status()

            data = resp.json()
            observations = data.get("observations", [])

            result = {}
            for obs in observations:
                date_str = obs.get("d")
                value_obj = obs.get(series_id, {})
                value_str = value_obj.get("v")

                if not date_str or not value_str:
                    continue

                try:
                    value = float(value_str)
                    result[date_str] = round(value, 2)
                except (ValueError, TypeError):
                    continue

            print(f"[CaInflationExp] Loaded {len(result)} records for {series_id}")
            return result

        except Exception as e:
            print(f"[CaInflationExp] Error fetching {series_id}: {e}")
            return {}

    def _merge_series_data(
        self,
        short_term: Dict[str, float],
        mid_term: Dict[str, float],
        long_term: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """3つの系列データをマージ"""
        # すべての日付を収集
        all_dates = set(short_term.keys()) | set(mid_term.keys()) | set(long_term.keys())
        all_dates = sorted(list(all_dates))

        result = []
        for date_str in all_dates:
            item: Dict[str, Any] = {"date": date_str}

            if date_str in short_term:
                item["exp_1y"] = short_term[date_str]
            if date_str in mid_term:
                item["exp_2y"] = mid_term[date_str]
            if date_str in long_term:
                item["exp_5y"] = long_term[date_str]

            # 少なくとも1つのデータがあれば追加
            if any(k in item for k in ["exp_1y", "exp_2y", "exp_5y"]):
                result.append(item)

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)

            # 7日以上経過していたら更新
            if (now - last_updated).days >= 7:
                return True

            return False
        except Exception:
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CaInflationExp] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaInflationExp] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Inflation Expectations",
            "source": "Bank of Canada",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(FMP_EVENT_PATTERN, country="CA"),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ca_inflation_expectations_service = CaInflationExpectationsService()
