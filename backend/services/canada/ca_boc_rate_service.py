"""
カナダ中央銀行（BOC）政策金利サービス

指標:
- BOC Policy Rate（オーバーナイトレート目標）

データソース:
- Bank of Canada Valet API
- https://www.bankofcanada.ca/valet/observations/V39079/json

発表スケジュール:
- 年8回（FMPから次回発表日時取得）
- 通常は水曜日の09:45 EST/EDT

キャッシュ方式:
- 通常時: BOC Valet APIから日次取得
- 発表日: FMPから発表値を取得しDBに格納
"""
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client
from services.canada.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")
TORONTO = ZoneInfo("America/Toronto")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "canada" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ca_boc_rate_cache.json"


class CaBocRateService:
    """カナダ中央銀行政策金利サービス"""

    DATA_CACHE_KEY = "canada:ca_boc_rate:data"
    ECONALPHA_ID = "ca_boc_rate"
    FMP_COUNTRY = "CA"
    FMP_EVENT_PATTERN = "BoC Interest Rate Decision"

    # BOC Valet API
    # V39079: オーバーナイトレート目標（Target for the Overnight Rate）
    VALET_URL = "https://www.bankofcanada.ca/valet/observations/V39079/json"

    def __init__(self):
        pass

    def get_ca_boc_rate_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダBOC政策金利データを取得"""
        # 次回発表日を取得
        next_release = get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY)

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
                    "indicator": "Policy Rate",
                    "description": "カナダ中央銀行政策金利（オーバーナイトレート目標）",
                    "unit": "%",
                    "series_id": "V39079",
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
            # 2017年から現在までのデータを取得
            today = date.today()
            start_date = "2017-01-01"
            end_date = today.strftime("%Y-%m-%d")

            url = f"{self.VALET_URL}?start_date={start_date}&end_date={end_date}"
            print(f"[CaBocRate] Fetching data from: {url}")

            resp = requests.get(url, timeout=30)
            resp.raise_for_status()

            data = resp.json()
            observations = data.get("observations", [])

            result = []

            for obs in observations:
                date_str = obs.get("d")
                value_obj = obs.get("V39079", {})
                value_str = value_obj.get("v")

                if not date_str or not value_str:
                    continue

                try:
                    value = float(value_str)
                    result.append({
                        "date": date_str,
                        "value": value,
                    })
                except (ValueError, TypeError):
                    continue

            # 日付でソート
            result.sort(key=lambda x: x["date"])

            print(f"[CaBocRate] Loaded {len(result)} daily records")
            if result:
                print(f"[CaBocRate] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CaBocRate] Latest: {latest['date']} = {latest['value']}%")

            return result

        except Exception as e:
            print(f"[CaBocRate] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日ベース）"""
        return should_refresh_by_pattern(
            self.FMP_EVENT_PATTERN,
            last_updated_str,
            country=self.FMP_COUNTRY
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CaBocRate] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaBocRate] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "BOC Policy Rate",
            "source": "Bank of Canada",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ca_boc_rate_service = CaBocRateService()
