"""
Indeed賃金トラッカーサービス
Indeed Hiring Lab から CSV データを取得

指標:
- posted_wage_growth_yoy: 求人掲載賃金の前年同月比成長率
- posted_wage_growth_yoy_3moavg: 3ヶ月移動平均

データソース:
- Indeed Hiring Lab: https://github.com/hiring-lab/indeed-wage-tracker
- CSV URL: https://raw.githubusercontent.com/hiring-lab/indeed-wage-tracker/main/posted-wage-growth-by-country.csv

発表スケジュール:
- 毎月15日以降に更新される
- 15日以降に1日1回チェックし、新規データがあれば更新
- 更新されたらその月は以降スキップ

キャッシュ方式: 発表日時ベース判定方式
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd
import io

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# データURL
INDEED_WAGE_CSV_URL = "https://raw.githubusercontent.com/hiring-lab/indeed-wage-tracker/main/posted-wage-growth-by-country.csv"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "indeed_wage_tracker_cache.json"


class IndeedWageTrackerService:
    """Indeed賃金トラッカーサービス"""

    DATA_CACHE_KEY = "indeed:wage_tracker:data"
    LAST_CHECK_KEY = "indeed:wage_tracker:last_check"
    MONTHLY_UPDATE_KEY = "indeed:wage_tracker:monthly_updated"
    ECONALPHA_ID = "indeed_wage"  # FMPマッピング用ID

    def __init__(self):
        pass

    def get_indeed_wage_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Indeed賃金トラッカーデータを取得

        Returns:
            {
                "data": [{
                    "date": str,
                    "value": float,      # 原数値（前年同月比）
                    "ma3": float | null  # 3ヶ月移動平均
                }, ...],
                "latest": {...},
                "next_release": {"date": str, "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        now = datetime.now(JST)

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                latest_data_date = cached_data.get("latest_data_date")
                if last_updated_str and not should_refresh_by_fmp_schedule(
                    self.ECONALPHA_ID, last_updated_str
                ):
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
                latest_data_date = file_cache.get("latest_data_date")
                if last_updated_str and not should_refresh_by_fmp_schedule(
                    self.ECONALPHA_ID, last_updated_str
                ):
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    return {
                        "data": file_cache.get("data", []),
                        "latest": file_cache.get("latest"),
                        "next_release": None,
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # Indeed から取得
        api_data = self._fetch_from_indeed()

        if api_data:
            # 前回のデータと比較して更新されているかチェック
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            is_new_data = self._is_data_updated(cached_data, api_data)

            if is_new_data:
                # 新しいデータがあった場合、今月の更新フラグを立てる
                self._set_monthly_updated()
                print(f"[Indeed] New data detected, setting monthly update flag")

            latest = api_data[-1] if api_data else None

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "latest_data_date": latest.get("date") if latest else None,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            # 最後のチェック時刻を更新
            self._set_last_check_time()

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

    def _fetch_from_indeed(self) -> Optional[List[Dict[str, Any]]]:
        """Indeed Hiring Lab から CSV データを取得"""
        try:
            print("Fetching Indeed Wage Tracker...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(INDEED_WAGE_CSV_URL, headers=headers, timeout=60)
            response.raise_for_status()

            # CSV を解析
            df = pd.read_csv(io.StringIO(response.text))

            # USAのデータのみ抽出
            usa_df = df[df['jobcountry'] == 'US'].copy()

            if usa_df.empty:
                print("No USA data found in Indeed wage tracker")
                return None

            result_data = []

            for _, row in usa_df.iterrows():
                month_str = row['month']  # 例: "Jan-19"

                # 日付を変換（MMM-YY → YYYY-MM-01）
                try:
                    date_obj = datetime.strptime(month_str, "%b-%y")
                    date_str = date_obj.strftime('%Y-%m-01')
                except ValueError:
                    continue

                # データポイントを作成
                # CSVの値は小数（例: 0.0234 = 2.34%）なので100倍する
                value = row.get('posted_wage_growth_yoy')
                ma3 = row.get('posted_wage_growth_yoy_3moavg')

                if pd.isna(value):
                    continue

                data_point = {
                    "date": date_str,
                    "value": round(float(value) * 100, 2) if not pd.isna(value) else None,
                    "ma3": round(float(ma3) * 100, 2) if not pd.isna(ma3) else None
                }

                result_data.append(data_point)

            # 日付でソート（昇順）
            result_data.sort(key=lambda x: x['date'])

            print(f"Fetched {len(result_data)} Indeed Wage Tracker records")
            return result_data

        except Exception as e:
            print(f"Error fetching Indeed Wage Tracker: {e}")
            import traceback
            traceback.print_exc()
            return None

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

        for key in ['value', 'ma3']:
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
            print(f"Error setting monthly update flag: {e}")

    def _should_check_update(self) -> bool:
        """更新チェックすべきかどうか（15日以降1日1回チェック）"""
        try:
            now = datetime.now(JST)

            # 15日より前はチェック不要
            if now.day < 15:
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
            print(f"Error checking update schedule: {e}")
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
            print(f"Error setting last check time: {e}")

    def _should_refresh_for_new_month(self, last_updated_str: str) -> bool:
        """新しい月になったらリフレッシュすべきか"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 月が変わっていたらリフレッシュ
            if last_updated.year != now.year or last_updated.month != now.month:
                return True

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return False

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
        redis_client.delete(self.MONTHLY_UPDATE_KEY)
        redis_client.delete(self.LAST_CHECK_KEY)
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Indeed Wage Tracker",
            "source": "Indeed Hiring Lab",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
            "monthly_updated": self._is_monthly_updated()
        }


# シングルトンインスタンス
indeed_wage_tracker_service = IndeedWageTrackerService()
