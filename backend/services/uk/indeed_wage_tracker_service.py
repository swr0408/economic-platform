"""
UK Indeed賃金トラッカーサービス
Indeed GitHubからイギリスの賃金成長データを取得

指標:
- Posted Wage Growth YoY (求人賃金成長率 前年比)
- 3ヶ月移動平均

データソース:
- Indeed Hiring Lab GitHub Repository
- https://github.com/hiring-lab/indeed-wage-tracker

発表スケジュール:
- 毎月15日以降に更新される
- 15日以降に1日1回チェックし、新規データがあれば更新
- 更新されたらその月は以降スキップ

キャッシュ方式: 発表日時ベース判定方式（アメリカ・ユーロ圏と同方式）
"""
import json
import requests
import pandas as pd
from io import StringIO
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "indeed_wage_tracker_cache.json"

# Indeed GitHub raw data URL
INDEED_WAGE_URL = "https://raw.githubusercontent.com/hiring-lab/indeed-wage-tracker/main/posted-wage-growth-by-country.csv"


class IndeedWageTrackerUKService:
    """UK Indeed賃金トラッカーサービス"""

    DATA_CACHE_KEY = "uk:indeed_wage_tracker:data"
    LAST_CHECK_KEY = "uk:indeed_wage_tracker:last_check"
    MONTHLY_UPDATE_KEY = "uk:indeed_wage_tracker:monthly_updated"
    COUNTRY_CODE = "GB"  # United Kingdom

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Indeed賃金成長データを取得"""
        now = datetime.now(JST)

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
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    return {
                        "data": file_cache.get("data", []),
                        "latest": file_cache.get("latest"),
                        "metadata": file_cache.get("metadata", {}),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str,
                    }

        # Indeed GitHubから取得
        csv_data = self._fetch_csv_data()

        if csv_data is not None:
            uk_data = self._process_country_data(csv_data)

            # 前回のデータと比較して更新されているかチェック
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            is_new_data = self._is_data_updated(cached_data, uk_data)

            if is_new_data:
                # 新しいデータがあった場合、今月の更新フラグを立てる
                self._set_monthly_updated()
                print(f"[IndeedWageUK] New data detected, setting monthly update flag")

            # 最新値を取得
            latest = uk_data[-1] if uk_data else None

            cache_payload = {
                "data": uk_data,
                "latest": latest,
                "latest_data_date": latest.get("date") if latest else None,
                "metadata": {
                    "source": "Indeed - Wage Growth Tracker",
                    "url": INDEED_WAGE_URL,
                    "data_start": "2019-01-01",
                    "country": "United Kingdom",
                    "country_code": self.COUNTRY_CODE,
                    "unit": "%",
                },
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            # 最後のチェック時刻を更新
            self._set_last_check_time()

            return {
                "data": uk_data,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "cached": False,
                "source": "indeed_github",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _fetch_csv_data(self) -> Optional[pd.DataFrame]:
        """
        Indeed GitHubリポジトリからCSVデータを取得

        Returns:
            DataFrame with all data or None if error occurs
        """
        try:
            print(f"[IndeedWageUK] Fetching from GitHub: {INDEED_WAGE_URL}")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(INDEED_WAGE_URL, headers=headers, timeout=60)
            response.raise_for_status()

            # Parse CSV
            csv_data = StringIO(response.text)
            df = pd.read_csv(csv_data)

            print(f"[IndeedWageUK] Successfully fetched CSV with {len(df)} rows")
            return df

        except requests.exceptions.RequestException as e:
            print(f"[IndeedWageUK] Error fetching data: {e}")
            return None
        except Exception as e:
            print(f"[IndeedWageUK] Error parsing CSV data: {e}")
            return None

    def _process_country_data(self, df: pd.DataFrame) -> List[Dict]:
        """
        UKのデータを処理

        Args:
            df: Full DataFrame

        Returns:
            List of processed data points
        """
        # Filter by country code
        country_df = df[df["jobcountry"] == self.COUNTRY_CODE].copy()

        if len(country_df) == 0:
            print(f"[IndeedWageUK] No data found for country code: {self.COUNTRY_CODE}")
            return []

        result_data = []

        for _, row in country_df.iterrows():
            try:
                # Get date value
                date_value = row["month"]
                wage_value = row["posted_wage_growth_yoy"]
                ma3_value = row.get("posted_wage_growth_yoy_3moavg")

                # Skip if date or wage value is NaN
                if pd.isna(date_value) or pd.isna(wage_value):
                    continue

                # Parse date (format: "Jan-19" -> 2019-01-01)
                date_obj = pd.to_datetime(date_value, format="%b-%y")
                date_str = date_obj.strftime("%Y-%m-01")

                # Create data point (multiply by 100 to convert to percentage)
                data_point = {
                    "date": date_str,
                    "value": round(float(wage_value) * 100, 2),  # 0.0256 -> 2.56%
                }

                # Add 3-month moving average if available
                if pd.notna(ma3_value):
                    data_point["ma3"] = round(float(ma3_value) * 100, 2)
                else:
                    data_point["ma3"] = None

                result_data.append(data_point)

            except Exception as e:
                print(f"[IndeedWageUK] Error processing row: {e}")
                continue

        # Sort by date
        result_data.sort(key=lambda x: x["date"])

        print(f"[IndeedWageUK] Processed {len(result_data)} data points for UK")
        return result_data

    def _is_data_updated(self, cached_data: Optional[Dict], new_data: List[Dict]) -> bool:
        """新しいデータがあるかチェック"""
        if not cached_data:
            return True

        cached_list = cached_data.get("data", [])
        if not cached_list:
            return True

        # 最新の日付を比較
        cached_latest_date = cached_list[-1].get("date") if cached_list else None
        new_latest_date = new_data[-1].get("date") if new_data else None

        if cached_latest_date != new_latest_date:
            return True

        # 同じ日付でも値が変わっている可能性をチェック
        cached_latest = cached_list[-1] if cached_list else {}
        new_latest = new_data[-1] if new_data else {}

        for key in ["value", "ma3"]:
            if cached_latest.get(key) != new_latest.get(key):
                return True

        return False

    def _is_monthly_updated(self) -> bool:
        """今月既に更新されているかチェック"""
        try:
            now = datetime.now(JST)
            current_month_key = f"{now.year}-{now.month:02d}"

            stored_month = redis_client.get(self.MONTHLY_UPDATE_KEY)
            return stored_month == current_month_key
        except Exception:
            return False

    def _set_monthly_updated(self) -> None:
        """今月の更新フラグをセット"""
        try:
            now = datetime.now(JST)
            current_month_key = f"{now.year}-{now.month:02d}"
            redis_client.set(self.MONTHLY_UPDATE_KEY, current_month_key, expire=0)
        except Exception as e:
            print(f"[IndeedWageUK] Error setting monthly update flag: {e}")

    def _should_check_update(self) -> bool:
        """更新チェックすべきかどうか（15日以降1日1回チェック）"""
        try:
            now = datetime.now(JST)

            # 15日より前はチェック不要
            if now.day < 15:
                return False

            # 今月既に更新されていたらスキップ
            if self._is_monthly_updated():
                return False

            # 最後のチェック時刻を取得
            last_check_str = redis_client.get(self.LAST_CHECK_KEY)
            if not last_check_str:
                return True

            last_check = datetime.fromisoformat(last_check_str)
            if last_check.tzinfo is None:
                last_check = last_check.replace(tzinfo=JST)

            # 24時間以上経過していたらチェック
            if now - last_check > timedelta(hours=24):
                return True

            return False

        except Exception as e:
            print(f"[IndeedWageUK] Error checking update schedule: {e}")
            return True

    def _set_last_check_time(self) -> None:
        """最後のチェック時刻を更新"""
        try:
            redis_client.set(
                self.LAST_CHECK_KEY,
                datetime.now(JST).isoformat(),
                expire=0
            )
        except Exception as e:
            print(f"[IndeedWageUK] Error setting last check time: {e}")

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定
        - 15日以降、かつ24時間以上経過していたらチェック
        - 今月既に更新されていたらスキップ
        """
        try:
            now = datetime.now(JST)

            # 15日より前はリフレッシュ不要
            if now.day < 15:
                return False

            # 今月既に更新されていたらリフレッシュ不要
            if self._is_monthly_updated():
                return False

            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            # 月が変わっていたらリフレッシュ
            if last_updated.year != now.year or last_updated.month != now.month:
                return True

            # 24時間以上経過していたらリフレッシュ
            if now - last_updated > timedelta(hours=24):
                return True

            return False

        except Exception as e:
            print(f"[IndeedWageUK] Error checking refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[IndeedWageUK] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[IndeedWageUK] Cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"[IndeedWageUK] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        redis_client.delete(self.MONTHLY_UPDATE_KEY)
        redis_client.delete(self.LAST_CHECK_KEY)
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Indeed Wage Tracker UK",
            "source": "Indeed Hiring Lab (GitHub)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
            "monthly_updated": self._is_monthly_updated(),
        }


# シングルトンインスタンス
indeed_wage_tracker_uk_service = IndeedWageTrackerUKService()
