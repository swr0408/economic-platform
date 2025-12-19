"""
銀行貸し出し態度サービス
FRED APIからSLOOS（Senior Loan Officer Opinion Survey）データを取得

シリーズID:
- DRTSCILM: Net Percentage of Domestic Banks Tightening Standards for
           Commercial and Industrial Loans to Large and Middle-Market Firms

発表スケジュール:
- 四半期ごと（2月、5月、8月、11月の初旬）
- 発表時刻: 14:00 ET

キャッシュ方式: last_updated判定（TTLなし）
スケジューラ: 発表日の23:00 JST（14:00 ET + 9時間）に更新
"""
import os
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo

import requests

from core.redis_client import redis_client

# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# FREDシリーズID
BANK_LENDING_SERIES_ID = "DRTSCILM"

# SLOOS発表スケジュール（年間固定パターン: 2月、5月、8月、11月の第1月曜日付近）
# 実際の発表日はFedカレンダーで確認が必要だが、通常は月初の月曜日
SLOOS_RELEASE_MONTHS = [2, 5, 8, 11]


class BankLendingService:
    """銀行貸し出し態度サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    CACHE_KEY = "fred:series:bank_lending"
    SCHEDULE_CACHE_KEY = "sloos:schedule"

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_bank_lending_standards(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        銀行貸し出し態度データを取得

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float}, ...],
                "latest": {"date": "YYYY-MM-DD", "value": float},
                "next_release": {"date": "YYYY-MM-DD", "quarter": "2025Q1"},
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # キャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CACHE_KEY)
            if cached_data:
                # 次回発表日を動的に計算
                next_release = self._get_next_sloos_release()
                return {
                    "data": cached_data.get("data", []),
                    "latest": cached_data.get("latest"),
                    "next_release": next_release,
                    "cached": True,
                    "source": "redis",
                    "last_updated": cached_data.get("last_updated")
                }

        # 外部APIから取得
        api_data = self._fetch_from_api(start_date)

        if api_data:
            # 最新値を取得
            latest = api_data[-1] if api_data else None
            next_release = self._get_next_sloos_release()

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            # TTLなし（last_updated判定方式）
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)

            return {
                "data": api_data,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        return {
            "data": [],
            "latest": None,
            "next_release": self._get_next_sloos_release(),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_api(
        self,
        start_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """FRED APIからデータを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print(f"Fetching Bank Lending Standards from FRED ({BANK_LENDING_SERIES_ID})...")

            # デフォルト期間（1990年から）
            if not start_date:
                start_date = "1990-01-01"

            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": BANK_LENDING_SERIES_ID,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date,
                "sort_order": "asc"
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            result = []
            for obs in data.get("observations", []):
                if obs.get("value") and obs["value"] != ".":
                    try:
                        result.append({
                            "date": obs["date"],
                            "value": round(float(obs["value"]), 2)
                        })
                    except (ValueError, TypeError):
                        continue

            print(f"Fetched {len(result)} records from FRED (Bank Lending Standards)")
            return result

        except Exception as e:
            print(f"Error fetching Bank Lending Standards: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _get_next_sloos_release(self) -> Optional[Dict[str, Any]]:
        """
        次回SLOOS発表日を計算

        SLOOSは四半期ごとに発表（2月、5月、8月、11月の初旬）
        通常は月の第1月曜日に発表
        """
        today = date.today()
        current_year = today.year

        # 今年と来年の発表月をチェック
        for year in [current_year, current_year + 1]:
            for month in SLOOS_RELEASE_MONTHS:
                # 各発表月の第1月曜日を計算
                first_day = date(year, month, 1)
                # 第1月曜日: 1日の曜日から計算
                days_until_monday = (7 - first_day.weekday()) % 7
                if days_until_monday == 0 and first_day.weekday() != 0:
                    days_until_monday = 7
                first_monday = first_day.replace(day=1 + days_until_monday if first_day.weekday() != 0 else 1)

                # 実際の発表日は月初3-5営業日付近のため、第1月曜日を目安とする
                release_date = first_monday

                if release_date > today:
                    # 発表対象の四半期を計算（前四半期のデータ）
                    if month == 2:
                        quarter = f"{year-1}Q4"
                    elif month == 5:
                        quarter = f"{year}Q1"
                    elif month == 8:
                        quarter = f"{year}Q2"
                    else:  # 11月
                        quarter = f"{year}Q3"

                    return {
                        "date": release_date.strftime("%Y-%m-%d"),
                        "quarter": quarter,
                        "title": f"SLOOS {quarter}"
                    }

        return None

    def get_sloos_schedule(self, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        SLOOS発表スケジュールを取得

        Args:
            year: 対象年（指定なしの場合は今年と来年）

        Returns:
            [{"date": "YYYY-MM-DD", "quarter": "YYYYQ#", "title": "..."}, ...]
        """
        if year is None:
            year = date.today().year

        schedule = []
        for target_year in [year, year + 1]:
            for month in SLOOS_RELEASE_MONTHS:
                # 第1月曜日を計算
                first_day = date(target_year, month, 1)
                days_until_monday = (7 - first_day.weekday()) % 7
                if days_until_monday == 0 and first_day.weekday() != 0:
                    days_until_monday = 7
                first_monday = first_day.replace(
                    day=1 + days_until_monday if first_day.weekday() != 0 else 1
                )

                # 対象四半期
                if month == 2:
                    quarter = f"{target_year-1}Q4"
                elif month == 5:
                    quarter = f"{target_year}Q1"
                elif month == 8:
                    quarter = f"{target_year}Q2"
                else:
                    quarter = f"{target_year}Q3"

                schedule.append({
                    "date": first_monday.strftime("%Y-%m-%d"),
                    "quarter": quarter,
                    "title": f"SLOOS {quarter}",
                    "release_time": "14:00 ET"
                })

        return schedule

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cache_exists = redis_client.exists(self.CACHE_KEY)
        ttl = redis_client.ttl(self.CACHE_KEY) if cache_exists else -1

        cached_data = redis_client.get(self.CACHE_KEY) if cache_exists else None

        return {
            "series_id": BANK_LENDING_SERIES_ID,
            "cache_key": self.CACHE_KEY,
            "exists": cache_exists,
            "ttl_seconds": ttl,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None
        }

    def get_latest_value(self) -> Optional[Dict[str, Any]]:
        """最新の銀行貸し出し態度を取得"""
        result = self.get_bank_lending_standards()
        return result.get("latest")


# シングルトンインスタンス
bank_lending_service = BankLendingService()
