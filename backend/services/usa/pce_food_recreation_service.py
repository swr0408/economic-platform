"""
PCEデフレーター飲食宿泊・娯楽サービス
BEA NIPA Table 84（T20804）からPCE価格指数を取得

指標:
- pce_food_services: 飲食宿泊（Food services and accommodations）前年比
- pce_recreation: 娯楽（Recreation services）前年比

データソース:
- BEA NIPA Table 2.8.4: Price Indexes for Personal Consumption Expenditures by Major Type of Product
- https://apps.bea.gov/iTable/?reqid=19&step=3&isuri=1&1921=survey&1903=84

平均時給（前年比）:
- 既存のaverage_hourly_earnings_serviceから取得

発表スケジュール:
- Personal Income and Outlays（毎月末 8:30 AM ET）

キャッシュ方式: 発表日時ベース判定方式
"""
import os
import json
from datetime import datetime
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

# BEA API設定
BEA_API_BASE = "https://apps.bea.gov/api/data/"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "pce_food_recreation_cache.json"


class PCEFoodRecreationService:
    """PCEデフレーター飲食宿泊・娯楽サービス"""

    DATA_CACHE_KEY = "bea:pce_food_recreation:data"
    ECONALPHA_ID = "pce_mom"  # FMPマッピング用ID（PCEと同じスケジュール）

    def __init__(self):
        self.api_key = os.environ.get("BEA_API_KEY", "")

    def get_pce_food_recreation_data(
        self,
        start_year: int = 2015,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        PCEデフレーター飲食宿泊・娯楽データを取得

        Returns:
            {
                "data": [{
                    "date": str,
                    "food_services_yoy": float | null,  # 飲食宿泊前年比
                    "recreation_yoy": float | null,     # 娯楽前年比
                    "avg_hourly_earnings_yoy": float | null  # 平均時給前年比
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
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    return {
                        "data": file_cache.get("data", []),
                        "latest": file_cache.get("latest"),
                        "next_release": None,
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # BEA APIから取得
        api_data = self._fetch_from_bea(start_year)

        if api_data:
            # 平均時給データをマージ
            merged_data = self._merge_with_avg_hourly_earnings(api_data)

            latest = merged_data[-1] if merged_data else None

            cache_payload = {
                "data": merged_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": merged_data,
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

    def _fetch_from_bea(self, start_year: int) -> Optional[List[Dict[str, Any]]]:
        """BEA NIPA APIからPCEデフレーターデータを取得"""
        try:
            if not self.api_key:
                print("BEA_API_KEY not set")
                return None

            current_year = datetime.now().year
            year_range = ",".join(str(year) for year in range(start_year - 1, current_year + 2))

            print(f"Fetching PCE Food & Recreation from BEA (T20804)...")

            # Table 2.8.4: Price Indexes for Personal Consumption Expenditures by Major Type of Product
            params = {
                "UserID": self.api_key,
                "method": "GetData",
                "datasetname": "NIPA",
                "TableName": "T20804",
                "Frequency": "M",  # 月次
                "Year": year_range,
                "ResultFormat": "JSON"
            }

            response = requests.get(BEA_API_BASE, params=params, timeout=60)
            response.raise_for_status()
            raw = response.json()

            api = raw.get("BEAAPI") if isinstance(raw, dict) else None
            if api and "Error" in api:
                err = api.get("Error", {})
                msg = err.get("ErrorDetail") or err.get("ErrorCode") or "BEA error"
                print(f"BEA API error: {msg}")
                return None

            data_rows = (api or {}).get("Results", {}).get("Data") if api else None

            if not data_rows:
                print("No data available from BEA T20804")
                return None

            return self._process_data(data_rows, start_year)

        except Exception as e:
            print(f"Error fetching PCE Food & Recreation from BEA: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _process_data(self, data_rows: List[Dict], start_year: int) -> List[Dict[str, Any]]:
        """BEAデータを整形"""
        # TimePeriodごとに値を集計
        temp: Dict[str, Dict[str, float]] = {}

        for row in data_rows:
            line_desc = row.get("LineDescription") or row.get("SeriesDescription") or ""

            # 対象の系列を識別（完全一致でチェック）
            key = None
            if line_desc == "Food services and accommodations":
                key = "food_services"
            elif line_desc == "Recreation services":
                key = "recreation"

            if not key:
                continue

            tp = row.get("TimePeriod")
            if not tp:
                continue

            # 月次形式: 2024M01
            try:
                year = int(tp[:4])
                month = int(tp[5:7])
                date_str = f"{year}-{month:02d}-01"
            except (ValueError, IndexError):
                continue

            val = row.get("DataValue")
            if val in (None, "", ".", "NaN", "(NA)"):
                continue

            try:
                num = float(str(val).replace(",", ""))
            except Exception:
                continue

            if date_str not in temp:
                temp[date_str] = {}
            temp[date_str][key] = num

        # 前年比を計算
        sorted_dates = sorted(temp.keys())
        result = []

        for date_str in sorted_dates:
            row_data = temp[date_str]

            # start_year未満はスキップ
            try:
                curr_date = datetime.strptime(date_str, "%Y-%m-%d")
                if curr_date.year < start_year:
                    continue
            except Exception:
                continue

            # 12ヶ月前の日付を計算
            try:
                prev_date = curr_date.replace(year=curr_date.year - 1)
                prev_date_str = prev_date.strftime("%Y-%m-%d")
            except Exception:
                continue

            # 前年比を計算
            food_services_yoy = None
            recreation_yoy = None

            if prev_date_str in temp:
                prev_data = temp[prev_date_str]

                if "food_services" in row_data and "food_services" in prev_data:
                    prev_val = prev_data["food_services"]
                    if prev_val and prev_val != 0:
                        food_services_yoy = round(
                            ((row_data["food_services"] - prev_val) / prev_val) * 100, 2
                        )

                if "recreation" in row_data and "recreation" in prev_data:
                    prev_val = prev_data["recreation"]
                    if prev_val and prev_val != 0:
                        recreation_yoy = round(
                            ((row_data["recreation"] - prev_val) / prev_val) * 100, 2
                        )

            # 前年比が計算できたデータのみ追加
            if food_services_yoy is not None or recreation_yoy is not None:
                result.append({
                    "date": date_str,
                    "food_services_yoy": food_services_yoy,
                    "recreation_yoy": recreation_yoy,
                    "avg_hourly_earnings_yoy": None  # 後でマージ
                })

        print(f"Processed {len(result)} months of PCE Food & Recreation data")
        return result

    def _merge_with_avg_hourly_earnings(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """平均時給データをマージ"""
        try:
            from services.usa.average_hourly_earnings_service import average_hourly_earnings_service

            ahe_data = average_hourly_earnings_service.get_average_hourly_earnings_data()
            ahe_list = ahe_data.get("data", [])

            # 日付をキーにマップ作成
            ahe_map = {item["date"]: item.get("yoy") for item in ahe_list}

            # データにマージ
            for item in data:
                date_str = item["date"]
                if date_str in ahe_map:
                    item["avg_hourly_earnings_yoy"] = ahe_map[date_str]

            return data

        except Exception as e:
            print(f"Error merging average hourly earnings: {e}")
            return data

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP 3分方式）"""
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
            "indicator": "PCE Food Services & Recreation",
            "source": "BEA NIPA T20804",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
pce_food_recreation_service = PCEFoodRecreationService()
