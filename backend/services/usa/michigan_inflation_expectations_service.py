"""
ミシガン大学期待インフレ率サービス

University of Michigan Survey of Consumersからインフレ期待データを取得

指標:
- 1年先インフレ期待 (Median one-year ahead expected inflation rate)
- 5年先インフレ期待 (Median five-year ahead expected inflation rate)

データソース:
- インフレ期待CSV: https://www.sca.isr.umich.edu/files/tbmpx1px5.csv

発表スケジュール:
- 毎月2回（速報値と確報値）
- FMPカレンダーから取得

キャッシュ方式: FMP発表日時ベース3分方式
"""
import io
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "michigan_inflation_expectations_cache.json"

# ミシガン大学CSVデータURL
MICHIGAN_CSV_URL = "https://www.sca.isr.umich.edu/files/tbmpx1px5.csv"

# 月名変換マップ
MONTH_MAP = {
    'january': 1,
    'february': 2,
    'march': 3,
    'april': 4,
    'may': 5,
    'june': 6,
    'july': 7,
    'august': 8,
    'september': 9,
    'october': 10,
    'november': 11,
    'december': 12
}

# フォールバックTTL（時間）
FALLBACK_CACHE_TTL_HOURS = 24


class MichiganInflationExpectationsService:
    """ミシガン大学期待インフレ率サービス"""

    DATA_CACHE_KEY = "inflation:michigan_inflation_expectations:data"
    ECONALPHA_ID = "michigan_inflation_expectations"

    # 3分方式の更新ウィンドウ（分）
    UPDATE_WINDOW_MINUTES = 3

    def __init__(self):
        pass

    def get_inflation_expectations_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        ミシガン大学インフレ期待データを取得

        Args:
            force_refresh: 強制更新フラグ

        Returns:
            {
                "data": {
                    "one_year": [{"date": "YYYY-MM-DD", "value": float}, ...],
                    "five_year": [...]
                },
                "latest": {"one_year": float, "five_year": float, "date": str},
                "next_release": {"date": str, "datetime_jst": str, "label": str} | null,
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
                    # 次回発表日を取得
                    next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
                    return {
                        "data": cached_data.get("data", {}),
                        "latest": cached_data.get("latest"),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ミシガン大学CSVからデータを取得
        result = self._fetch_from_michigan_csv()
        if result and any(result.get(k) for k in ["one_year", "five_year"]):
            latest = self._get_latest_values(result)
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            cache_payload = {
                "data": result,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            # Redisに保存（TTLなし - 3分方式で管理）
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "University of Michigan",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
            return {
                "data": file_cache.get("data", {}),
                "latest": file_cache.get("latest"),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": {"one_year": [], "five_year": []},
            "latest": None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_michigan_csv(self) -> Dict[str, List[Dict[str, Any]]]:
        """ミシガン大学CSVからデータを取得"""
        try:
            print(f"Fetching Michigan Inflation Expectations from {MICHIGAN_CSV_URL}...")
            response = requests.get(MICHIGAN_CSV_URL, timeout=30)
            response.raise_for_status()

            # CSVデータを読み込み
            csv_content = response.content.decode('utf-8')
            df = pd.read_csv(io.StringIO(csv_content))
            print(f"Michigan data shape: {df.shape}")
            print(f"Michigan data columns: {list(df.columns)}")

            # データを処理
            result = {
                "one_year": self._process_monthly_data(df, "PX_MD"),
                "five_year": self._process_monthly_data(df, "PX5_MD", start_date="1990-04-01")
            }

            print(f"Loaded {len(result['one_year'])} one_year records, {len(result['five_year'])} five_year records")
            return result

        except Exception as e:
            print(f"Error fetching Michigan CSV: {e}")
            import traceback
            traceback.print_exc()
            return {"one_year": [], "five_year": []}

    def _process_monthly_data(
        self,
        df: pd.DataFrame,
        value_column: str,
        start_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        月次データを処理してAPI用フォーマットに変換

        Args:
            df: データフレーム
            value_column: 値の列名（PX_MD または PX5_MD）
            start_date: 開始日（例："1990-04-01"）

        Returns:
            API用フォーマットのデータ
        """
        try:
            result = []
            for _, row in df.iterrows():
                try:
                    # 月、年、値を取得
                    month_str = str(row['Month']).strip() if pd.notna(row['Month']) else None
                    year_str = str(row['YYYY']).strip() if pd.notna(row['YYYY']) else None
                    value_str = str(row[value_column]).strip() if pd.notna(row.get(value_column)) else None

                    # 空の行またはnanをスキップ
                    if not month_str or not year_str or not value_str:
                        continue
                    if month_str == 'nan' or year_str == 'nan' or value_str == 'nan':
                        continue

                    # 日付を解析
                    date_obj = self._parse_date(month_str, year_str)
                    if not date_obj:
                        continue

                    # 値を解析
                    try:
                        value = float(value_str)
                    except ValueError:
                        continue

                    result.append({
                        "date": date_obj.strftime('%Y-%m-%d'),
                        "value": value
                    })

                except Exception as e:
                    continue

            # 日付順にソート
            result.sort(key=lambda x: x["date"])

            # 開始日フィルタリング
            if start_date:
                result = [item for item in result if item["date"] >= start_date]

            return result

        except Exception as e:
            print(f"Error processing {value_column} data: {e}")
            return []

    def _parse_date(self, month_str: str, year_str: str) -> Optional[datetime]:
        """
        月と年の文字列から日付オブジェクトを作成

        Args:
            month_str: 月の文字列（例：'September'）
            year_str: 年の文字列（例：'2024'）

        Returns:
            日付オブジェクト
        """
        try:
            # 月名を数値に変換
            month_lower = month_str.lower()
            if month_lower not in MONTH_MAP:
                return None

            month_num = MONTH_MAP[month_lower]
            # float を int に変換（例：2024.0 -> 2024）
            year_num = int(float(year_str))

            return datetime(year_num, month_num, 1)

        except Exception as e:
            return None

    def _get_latest_values(
        self,
        data: Dict[str, List[Dict[str, Any]]]
    ) -> Optional[Dict[str, Any]]:
        """最新値を取得"""
        latest = {}
        latest_date = None

        for horizon in ["one_year", "five_year"]:
            series = data.get(horizon, [])
            if series:
                latest_point = series[-1]
                latest[horizon] = latest_point["value"]
                if not latest_date or latest_point["date"] > latest_date:
                    latest_date = latest_point["date"]

        if latest_date:
            latest["date"] = latest_date

        return latest if latest else None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定（FMP 3分方式）

        判定ロジック:
        1. FMPスケジュールベースで判定
        2. フォールバック: 24時間以上経過していれば更新
        """
        try:
            # FMPスケジュールベースで判定
            if should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str):
                return True

            # フォールバック: 24時間TTL
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            elapsed_hours = (now - last_updated).total_seconds() / 3600
            return elapsed_hours >= FALLBACK_CACHE_TTL_HOURS

        except Exception as e:
            print(f"Error checking refresh: {e}")
            return True

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
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        redis_client.delete(self.DATA_CACHE_KEY)
        if DATA_CACHE_FILE.exists():
            DATA_CACHE_FILE.unlink()
        return True

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        data_counts = {}
        if cached_data and cached_data.get("data"):
            for horizon in ["one_year", "five_year"]:
                data_counts[horizon] = len(cached_data["data"].get(horizon, []))

        return {
            "indicator": "Michigan Inflation Expectations",
            "source": "University of Michigan",
            "cache_method": "FMP発表日時ベース3分方式",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_counts": data_counts,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
michigan_inflation_expectations_service = MichiganInflationExpectationsService()
