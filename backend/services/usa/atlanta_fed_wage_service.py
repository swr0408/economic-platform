"""
アトランタ連銀賃金トラッカーサービス
Atlanta Fed Wage Growth Tracker から Excel データを取得

指標:
- Overall: 全体の賃金上昇率（12ヶ月移動中央値）
- Full-time: フルタイム労働者
- Paid Hourly: 時給労働者
- Job Stayer: 在職者
- Job Switcher: 転職者

データソース:
- Atlanta Fed: https://www.atlantafed.org/chcs/wage-growth-tracker

発表スケジュール:
- 通常は毎月第2金曜日までに更新（CPSデータの公開後）
- 第2金曜日まで毎日チェックし、更新されたらその月はスキップ

キャッシュ方式: 発表日時ベース判定方式
"""
import os
import io
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path
from calendar import monthrange

import requests
import pandas as pd

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# データURL
ATLANTAFED_WAGE_URL = "https://www.atlantafed.org/-/media/documents/datafiles/chcs/wage-growth-tracker/wage-growth-data.xlsx"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "atlanta_fed_wage_cache.json"


def get_second_friday(year: int, month: int) -> datetime:
    """指定月の第2金曜日を取得"""
    # 月の1日から開始
    first_day = datetime(year, month, 1, tzinfo=ET)

    # 最初の金曜日を見つける
    days_until_friday = (4 - first_day.weekday()) % 7
    if days_until_friday == 0 and first_day.weekday() != 4:
        days_until_friday = 7
    first_friday = first_day + timedelta(days=days_until_friday)

    # 第2金曜日
    second_friday = first_friday + timedelta(days=7)

    return second_friday


class AtlantaFedWageService:
    """アトランタ連銀賃金トラッカーサービス"""

    DATA_CACHE_KEY = "atlantafed:wage_growth:data"
    LAST_CHECK_KEY = "atlantafed:wage_growth:last_check"
    MONTHLY_UPDATE_KEY = "atlantafed:wage_growth:monthly_updated"
    ECONALPHA_ID = "atlanta_fed_wage"  # FMPマッピング用ID

    def __init__(self):
        pass

    def get_atlanta_fed_wage_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        アトランタ連銀賃金トラッカーデータを取得

        Returns:
            {
                "data": [{
                    "date": str,
                    "overall": float,
                    "fulltime": float,
                    "paid_hourly": float,
                    "job_stayer": float,
                    "job_switcher": float,
                    "mom": float | null
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

        # Atlanta Fed から取得
        api_data = self._fetch_from_atlanta_fed()

        if api_data:
            latest = api_data[-1] if api_data else None

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "latest_data_date": latest.get("date") if latest else None,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
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

    def _fetch_from_atlanta_fed(self) -> Optional[List[Dict[str, Any]]]:
        """Atlanta Fed から Excel データを取得"""
        try:
            print("Fetching Atlanta Fed Wage Growth Tracker...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(ATLANTAFED_WAGE_URL, headers=headers, timeout=60)
            response.raise_for_status()

            # Excel ファイルを解析（data_overallシートを使用）
            excel_data = io.BytesIO(response.content)
            df = pd.read_excel(excel_data, sheet_name='data_overall', header=1)

            # 日付列を特定（Unnamed: 0）
            date_column = df.columns[0]

            result_data = []
            prev_overall = None

            for _, row in df.iterrows():
                date_value = row[date_column]

                # 日付が有効かチェック
                if pd.isna(date_value):
                    continue

                try:
                    # 日付を変換
                    date_obj = pd.to_datetime(date_value)
                    date_str = date_obj.strftime('%Y-%m-%d')

                    # データポイントを作成
                    data_point = {
                        "date": date_str,
                        "overall": None,
                        "fulltime": None,
                        "paid_hourly": None,
                        "job_stayer": None,
                        "job_switcher": None,
                    }

                    # 各列を処理
                    for col in df.columns:
                        if col == date_column:
                            continue

                        value = row[col]

                        # '.' は欠損値として扱う
                        if pd.isna(value) or (isinstance(value, str) and value.strip() == '.'):
                            continue

                        try:
                            if isinstance(value, (int, float)):
                                numeric_value = float(value)
                            elif isinstance(value, str):
                                numeric_value = float(value)
                            else:
                                continue

                            # 列名を正規化
                            if col == 'Overall':
                                data_point['overall'] = round(numeric_value, 2)
                            elif col == 'Full-time':
                                data_point['fulltime'] = round(numeric_value, 2)
                            elif col == 'Paid Hourly':
                                data_point['paid_hourly'] = round(numeric_value, 2)
                            elif col == 'Job Stayer':
                                data_point['job_stayer'] = round(numeric_value, 2)
                            elif col == 'Job Switcher':
                                data_point['job_switcher'] = round(numeric_value, 2)
                        except (ValueError, TypeError):
                            continue

                    # 少なくともoverall値がある場合のみ追加
                    if data_point['overall'] is not None:
                        result_data.append(data_point)

                except Exception as e:
                    continue

            # 日付でソート（昇順）
            result_data.sort(key=lambda x: x['date'])

            print(f"Fetched {len(result_data)} Atlanta Fed Wage Growth records")
            return result_data

        except Exception as e:
            print(f"Error fetching Atlanta Fed Wage Growth: {e}")
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

        for key in ['overall', 'fulltime', 'paid_hourly', 'job_stayer', 'job_switcher']:
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
        """更新チェックすべきかどうか（1日1回チェック）"""
        try:
            now = datetime.now(JST)

            # 今月の第2金曜日を取得
            second_friday = get_second_friday(now.year, now.month)
            second_friday_jst = second_friday.astimezone(JST)

            # 第2金曜日を過ぎていたらチェック不要（今月は更新されない）
            if now > second_friday_jst + timedelta(days=1):
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
            "indicator": "Atlanta Fed Wage Growth Tracker",
            "source": "Atlanta Fed",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
atlanta_fed_wage_service = AtlantaFedWageService()
