"""
ユーロ圏消費者信頼感指数サービス
Eurostat APIから Consumer Confidence Indicator データを取得

指標:
- Consumer Confidence Indicator - Euro Area 20
- 季節調整済み (SA)
- バランス値 (BAL)

データソース:
- Eurostat (European Statistical Office)
- Dataset: ei_bsco_m (Business and Consumer Surveys)

発表スケジュール:
- 毎月25日〜翌月8日 18:00-18:10 CET

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.eurozone.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "eurozone" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "eurostat_consumer_confidence_cache.json"


class EurostatConsumerConfidenceService:
    """ユーロ圏消費者信頼感指数サービス (Eurostat API)"""

    DATA_CACHE_KEY = "eurozone:consumer_confidence:data"
    ECONALPHA_ID = "eurostat_consumer_confidence"
    FMP_EVENT_PATTERN = "Consumer Confidence"

    # Eurostat API設定
    EUROSTAT_API_BASE = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data"
    DATASET = "ei_bsco_m"

    # Series key components:
    # M = Monthly
    # BS-CSMCI = Consumer confidence indicator
    # SA = Seasonally adjusted, not calendar adjusted
    # BAL = Balance
    # EA20 = Euro area - 20 countries (from 2023)
    SERIES_KEY = "M.BS-CSMCI.SA.BAL.EA20"

    def __init__(self):
        pass

    def get_consumer_confidence_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """消費者信頼感指数データを取得"""
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
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # Eurostat APIから取得
        api_result = self._fetch_from_eurostat()
        if api_result:
            next_release = get_next_release_by_pattern(self.FMP_EVENT_PATTERN)
            latest = api_result[-1] if api_result else None

            cache_payload = {
                "data": api_result,
                "latest": latest,
                "metadata": {
                    "source": "Eurostat",
                    "dataset": self.DATASET,
                    "indicator": "Consumer Confidence Indicator - Euro Area 20",
                    "unit": "Balance",
                    "adjustment": "Seasonally adjusted",
                    "description": "消費者信頼感指数（ユーロ圏20カ国）",
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": api_result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "eurostat_api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _fetch_from_eurostat(self, start_date: str = "2015-01") -> Optional[List[Dict]]:
        """Eurostat APIからデータを取得"""
        url = f"{self.EUROSTAT_API_BASE}/{self.DATASET}/{self.SERIES_KEY}"

        params = {
            "startPeriod": start_date,
            "format": "JSON"
        }

        try:
            print(f"[EurostatConsumerConfidence] Fetching data from Eurostat: {self.SERIES_KEY}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Eurostat JSON形式を解析
            values = data.get("value", {})
            if not values:
                print("[EurostatConsumerConfidence] No values found in response")
                return None

            # 時間次元を取得
            time_dimension = data.get("dimension", {}).get("time", {})
            time_category = time_dimension.get("category", {})
            time_index = time_category.get("index", {})

            # index -> date のマッピングを作成
            index_to_date = {v: k for k, v in time_index.items()}

            # 結果リストを構築
            result = []
            for idx_str, value in values.items():
                idx = int(idx_str)
                date_str = index_to_date.get(idx)

                if date_str and value is not None:
                    result.append({
                        "date": date_str,
                        "value": float(value)
                    })

            # 日付でソート
            result.sort(key=lambda x: x["date"])

            print(f"[EurostatConsumerConfidence] Fetched {len(result)} data points")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[EurostatConsumerConfidence] Request error: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[EurostatConsumerConfidence] Parse error: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_pattern(self.FMP_EVENT_PATTERN, last_updated_str)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[EurostatConsumerConfidence] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[EurostatConsumerConfidence] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Eurostat Consumer Confidence",
            "source": "Eurostat API",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(self.FMP_EVENT_PATTERN),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
eurostat_consumer_confidence_service = EurostatConsumerConfidenceService()
