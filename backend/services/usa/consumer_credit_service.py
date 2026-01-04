"""
クレジットカードローン残高サービス
FRED APIからConsumer Loans: Credit Cards and Other Revolving Plansデータを取得

シリーズID:
- CCLACBW027SBOG: Consumer Loans: Credit Cards and Other Revolving Plans, All Commercial Banks
  (週次、水曜日終了、季節調整済み、10億ドル単位)

データソース:
- FRB H.8 Assets and Liabilities of Commercial Banks in the United States
- https://www.federalreserve.gov/releases/h8/

発表スケジュール:
- 毎週金曜日 16:15 ET（米国東部時間）

キャッシュ方式: 発表日時ベース判定方式
"""
import os
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# FREDシリーズID
SERIES_ID = "CCLACBW027SBOG"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "consumer_credit_cache.json"


class ConsumerCreditService:
    """クレジットカードローン残高サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:series:consumer_credit"
    ECONALPHA_ID = "consumer_credit"  # FMPマッピング用ID

    # 発表時刻設定（ET）- 毎週金曜日 16:15 ET
    RELEASE_HOUR_ET = 16
    RELEASE_MINUTE_ET = 15

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_consumer_credit_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        クレジットカードローン残高データを取得

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float, "mom": float, "yoy": float}, ...],
                "latest": {...},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": None,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    data = file_cache.get("data", [])

                    # Redisにも保存
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)

                    return {
                        "data": data,
                        "latest": file_cache.get("latest"),
                        "next_release": None,
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # 外部APIから取得
        api_data = self._fetch_from_api(start_date)

        if api_data:
            latest = api_data[-1] if api_data else None

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "latest_data_date": latest["date"] if latest else None,
                "last_updated": datetime.now(JST).isoformat()
            }
            # TTLなし（発表日時ベース判定方式）
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            # ファイルにも保存
            self._save_file_cache(cache_payload)

            return {
                "data": api_data,
                "latest": latest,
                "next_release": None,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": None,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_api(
        self,
        start_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """FRED APIからクレジットカードローン残高データを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print("Fetching Consumer Credit from FRED...")

            # デフォルト期間（2000年から）
            if not start_date:
                start_date = "2000-01-01"

            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": SERIES_ID,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date,
                "sort_order": "asc"
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            raw_data = []
            for obs in data.get("observations", []):
                if obs.get("value") and obs["value"] != ".":
                    try:
                        raw_data.append({
                            "date": obs["date"],
                            "value": round(float(obs["value"]), 2)
                        })
                    except (ValueError, TypeError):
                        continue

            # 週次データを月別に集計して月平均を算出
            monthly_data = self._aggregate_to_monthly(raw_data)

            print(f"Fetched {len(monthly_data)} monthly records from FRED (Consumer Credit)")
            return monthly_data

        except Exception as e:
            print(f"Error fetching Consumer Credit: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _aggregate_to_monthly(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        週次データを月別に集計して月平均を算出

        Args:
            raw_data: 週次データのリスト [{"date": "YYYY-MM-DD", "value": float}, ...]

        Returns:
            月次データのリスト [{"date": "YYYY-MM-01", "value": float, "mom": float, "yoy": float}, ...]
        """
        from collections import defaultdict

        # 月別にグループ化
        monthly_values: Dict[str, List[float]] = defaultdict(list)

        for item in raw_data:
            date_str = item["date"]
            value = item["value"]

            # YYYY-MM形式に変換
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                month_key = dt.strftime("%Y-%m")
                monthly_values[month_key].append(value)
            except ValueError:
                continue

        # 月平均を計算
        monthly_averages = []
        for month_key in sorted(monthly_values.keys()):
            values = monthly_values[month_key]
            avg_value = sum(values) / len(values)
            monthly_averages.append({
                "month_key": month_key,
                "date": f"{month_key}-01",  # YYYY-MM-01形式
                "value": round(avg_value, 2)
            })

        # 前月比と前年比を計算
        result = []
        for i, item in enumerate(monthly_averages):
            entry = {
                "date": item["date"],
                "value": item["value"],
                "mom": None,  # 前月比
                "yoy": None   # 前年比
            }

            # 前月比（1ヶ月前のデータがあれば）
            if i >= 1:
                prev_value = monthly_averages[i - 1]["value"]
                if prev_value and prev_value != 0:
                    mom_pct = ((item["value"] - prev_value) / prev_value) * 100
                    entry["mom"] = round(mom_pct, 2)

            # 前年比（12ヶ月前のデータがあれば）
            if i >= 12:
                year_ago_value = monthly_averages[i - 12]["value"]
                if year_ago_value and year_ago_value != 0:
                    yoy_pct = ((item["value"] - year_ago_value) / year_ago_value) * 100
                    entry["yoy"] = round(yoy_pct, 2)

            result.append(entry)

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        FMPスケジュールベースの3分方式で判定
        """
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)


    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None

            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "series_id": SERIES_ID,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
consumer_credit_service = ConsumerCreditService()
