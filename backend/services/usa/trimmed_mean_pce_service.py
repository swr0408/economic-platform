"""
Trimmed Mean PCE Inflation Rate サービス
Dallas Fed から Excel データを取得

指標:
- 1-month: 1ヶ月変化率（年率換算）
- 6-month: 6ヶ月変化率（年率換算）
- 12-month: 12ヶ月変化率

データソース:
- Dallas Fed: https://www.dallasfed.org/research/pce

発表スケジュール:
- BEA Personal Income and Outlays発表後（毎月末頃）
- 次回更新日: https://www.dallasfed.org/research/pce#data

キャッシュ方式: PCEデフレーター発表日時ベース判定方式
"""
import io
import json
from datetime import datetime
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


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# データURL
DALLASFED_PCE_URL = "https://www.dallasfed.org/~/media/documents/research/pce/pcehist"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "trimmed_mean_pce_cache.json"


class TrimmedMeanPCEService:
    """Trimmed Mean PCE Inflation Rate サービス"""

    DATA_CACHE_KEY = "inflation:trimmed_mean_pce:data"
    # PCEデフレーターと同時発表のためpce_deflatorをECONALPHA_IDとして使用
    ECONALPHA_ID = "pce_deflator"

    def __init__(self):
        pass

    def get_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Trimmed Mean PCE Inflation Rate データを取得

        Returns:
            {
                "data": [{
                    "date": str,
                    "one_month": float | null,
                    "six_month": float | null,
                    "twelve_month": float | null,
                }, ...],
                "latest": {...},
                "next_release": {"date": str, "label": str} | null,
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
                if last_updated_str and not should_refresh_by_fmp_schedule(
                    self.ECONALPHA_ID, last_updated_str
                ):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not should_refresh_by_fmp_schedule(
                    self.ECONALPHA_ID, last_updated_str
                ):
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    return {
                        "data": file_cache.get("data", []),
                        "latest": file_cache.get("latest"),
                        "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # Dallas Fed から取得
        api_data = self._fetch_from_dallas_fed()

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
                "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
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
                "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_dallas_fed(self) -> Optional[List[Dict[str, Any]]]:
        """Dallas Fed から Excel データを取得"""
        try:
            print("Fetching Trimmed Mean PCE from Dallas Fed...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(DALLASFED_PCE_URL, headers=headers, timeout=60)
            response.raise_for_status()

            # Excel ファイルを解析
            excel_data = io.BytesIO(response.content)
            # header=2で3行目からデータ開始、最初の行がヘッダー
            df = pd.read_excel(excel_data, sheet_name='Web - Historical', header=2)

            result_data = []

            for idx, row in df.iterrows():
                # 最初の行はヘッダー行なのでスキップ
                if idx == 0:
                    continue

                date_value = row.iloc[0]

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
                        "one_month": None,
                        "six_month": None,
                        "twelve_month": None,
                    }

                    # 1-month (列1)
                    val_1m = row.iloc[1]
                    if self._is_valid_value(val_1m):
                        data_point['one_month'] = round(float(val_1m), 2)

                    # 6-month (列2)
                    val_6m = row.iloc[2]
                    if self._is_valid_value(val_6m):
                        data_point['six_month'] = round(float(val_6m), 2)

                    # 12-month (列3)
                    val_12m = row.iloc[3]
                    if self._is_valid_value(val_12m):
                        data_point['twelve_month'] = round(float(val_12m), 2)

                    # 少なくとも1つの値がある場合のみ追加
                    if any([
                        data_point['one_month'] is not None,
                        data_point['six_month'] is not None,
                        data_point['twelve_month'] is not None
                    ]):
                        result_data.append(data_point)

                except Exception as e:
                    continue

            # 日付でソート（昇順）
            result_data.sort(key=lambda x: x['date'])

            print(f"Fetched {len(result_data)} Trimmed Mean PCE records")
            return result_data

        except Exception as e:
            print(f"Error fetching Trimmed Mean PCE: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _is_valid_value(self, value) -> bool:
        """値が有効かチェック"""
        if pd.isna(value):
            return False
        if isinstance(value, str):
            v = value.strip()
            if v == '' or v == '.' or v == '#NAN' or v == '#N/A':
                return False
        try:
            float(value)
            return True
        except (ValueError, TypeError):
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
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Trimmed Mean PCE Inflation Rate",
            "source": "Dallas Fed",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
trimmed_mean_pce_service = TrimmedMeanPCEService()
