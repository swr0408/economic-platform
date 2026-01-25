"""
Median CPI サービス
Cleveland Fed から ZIP/CSV データを取得

指標:
- Median CPI: FRB Cleveland Median CPI（前年比）
- 16% Trimmed Mean: 16%トリムド平均CPI（前年比）
- CPI: CPI-U All Items（前年比）
- Core CPI: CPI-U All Items Less Food and Energy（前年比）

データソース:
- Cleveland Fed: https://www.clevelandfed.org/research/data/us-inflation/median-cpi

発表スケジュール:
- CPI発表と同日（毎月中旬 8:30 ET）

キャッシュ方式: CPI発表日時ベース判定方式（us_cpi）
"""
import io
import json
import zipfile
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
CLEVELAND_FED_URL = "https://www.clevelandfed.org/-/media/files/webcharts/mediancpi/usinflationdata.zip?sc_lang=en"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "median_cpi_cache.json"


class MedianCPIService:
    """Median CPI サービス"""

    DATA_CACHE_KEY = "inflation:median_cpi:data"
    # CPIと同時発表のためus_cpiをECONALPHA_IDとして使用
    ECONALPHA_ID = "us_cpi"

    def __init__(self):
        pass

    def get_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Median CPI データを取得

        Returns:
            {
                "data": [{
                    "date": str,
                    "median_cpi": float | null,
                    "trimmed_mean_16": float | null,
                    "cpi": float | null,
                    "core_cpi": float | null,
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

        # Cleveland Fed から取得
        api_data = self._fetch_from_cleveland_fed()

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

    def _fetch_from_cleveland_fed(self) -> Optional[List[Dict[str, Any]]]:
        """Cleveland Fed から ZIP/CSV データを取得"""
        try:
            print("Fetching Median CPI from Cleveland Fed...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(CLEVELAND_FED_URL, headers=headers, timeout=60)
            response.raise_for_status()

            # ZIPを解凍してCSVを読み込み
            with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                csv_name = "usinflationdata.csv"
                with zf.open(csv_name) as f:
                    # ヘッダーなしで読み込み、2行目以降をデータとして扱う
                    # 行0: カラム名
                    # 行1: 出典情報
                    # 行2以降: データ
                    df = pd.read_csv(f, header=None, skiprows=2)

                    # カラム番号で必要なものを取得
                    # 0: Date
                    # 11: Revised FRB Cleveland Median CPI YoY
                    # 15: Revised 16% Trimmed Mean YoY
                    # 3: CPI-U All Items YoY
                    # 7: Core CPI YoY
                    subset = df[[0, 11, 15, 3, 7]].copy()
                    subset.columns = ['date_raw', 'median_cpi', 'trimmed_mean_16', 'cpi', 'core_cpi']

                    result_data = []

                    for _, row in subset.iterrows():
                        date_raw = row['date_raw']

                        # 日付が有効かチェック
                        if pd.isna(date_raw) or not isinstance(date_raw, str):
                            continue

                        try:
                            # MM/DD/YYYY形式を変換
                            date_obj = pd.to_datetime(date_raw, format='%m/%d/%Y')
                            date_str = date_obj.strftime('%Y-%m-%d')

                            # データポイントを作成
                            data_point = {
                                "date": date_str,
                                "median_cpi": None,
                                "trimmed_mean_16": None,
                                "cpi": None,
                                "core_cpi": None,
                            }

                            # Median CPI
                            val = row['median_cpi']
                            if self._is_valid_value(val):
                                data_point['median_cpi'] = round(float(val), 2)

                            # 16% Trimmed Mean
                            val = row['trimmed_mean_16']
                            if self._is_valid_value(val):
                                data_point['trimmed_mean_16'] = round(float(val), 2)

                            # CPI
                            val = row['cpi']
                            if self._is_valid_value(val):
                                data_point['cpi'] = round(float(val), 2)

                            # Core CPI
                            val = row['core_cpi']
                            if self._is_valid_value(val):
                                data_point['core_cpi'] = round(float(val), 2)

                            # 少なくとも1つの値がある場合のみ追加
                            if data_point['median_cpi'] is not None:
                                result_data.append(data_point)

                        except Exception:
                            continue

                    # 日付でソート（昇順）
                    result_data.sort(key=lambda x: x['date'])

                    print(f"Fetched {len(result_data)} Median CPI records")
                    return result_data

        except Exception as e:
            print(f"Error fetching Median CPI: {e}")
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
            "indicator": "Median CPI",
            "source": "Cleveland Fed",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
median_cpi_service = MedianCPIService()
