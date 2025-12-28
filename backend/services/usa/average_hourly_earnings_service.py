"""
平均時給 / 自発的離職率サービス
FRED APIからCES0500000003 & JTSQURデータを取得

指標:
- CES0500000003: 平均時給（Average Hourly Earnings of All Employees, Total Private）
- JTSQUR: 自発的離職率（Quits Rate: Total Nonfarm）

データソース:
- FRED: https://fred.stlouisfed.org/series/CES0500000003
- FRED: https://fred.stlouisfed.org/series/JTSQUR

発表スケジュール:
- 平均時給: BLS Employment Situation（雇用統計）毎月1〜15日
- 発表時刻: 21:30 (夏) / 22:30 (冬) JST
- 自発的離職率: JOLTS（毎月29日〜翌13日）

キャッシュ方式: 発表期間ベース判定方式
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client
from services.usa.release_schedule_utils import UNEMPLOYMENT_RATE_CHECKER


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# FREDシリーズID
AHE_SERIES_ID = "CES0500000003"  # 平均時給
JTSQUR_SERIES_ID = "JTSQUR"      # 自発的離職率

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "average_hourly_earnings_cache.json"


class AverageHourlyEarningsService:
    """平均時給 / 自発的離職率サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:average_hourly_earnings:data"

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")
        self.schedule_checker = UNEMPLOYMENT_RATE_CHECKER

    def get_average_hourly_earnings_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        平均時給 / 自発的離職率データを取得

        Returns:
            {
                "data": [{"date": str, "yoy": float, "mom": float, "quits_rate": float}, ...],
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

        # FRED APIから取得
        api_data = self._fetch_from_api(start_date)

        if api_data:
            # latestはdataとは別のオブジェクトとしてコピー（参照を共有しない）
            latest = dict(api_data[-1]) if api_data else None

            # quits_rateがnullの場合、最新のquits_rateを持つエントリを探す（latestのみ更新）
            if latest and latest.get("quits_rate") is None:
                for entry in reversed(api_data):
                    if entry.get("quits_rate") is not None:
                        latest["quits_rate"] = entry.get("quits_rate")
                        latest["quits_rate_date"] = entry.get("date")
                        break

            cache_payload = {
                "data": api_data,
                "latest": latest,
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

    def _fetch_from_api(self, start_date: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """FRED APIから平均時給データを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return None

            print("Fetching Average Hourly Earnings from FRED...")

            if not start_date:
                start_date = "2000-01-01"

            # 平均時給（水準値）
            ahe_level = self._fetch_series(AHE_SERIES_ID, start_date)
            # 平均時給（前年比）
            ahe_yoy = self._fetch_series_with_units(AHE_SERIES_ID, start_date, "pc1")
            # 自発的離職率
            jtsqur_raw = self._fetch_series(JTSQUR_SERIES_ID, start_date)

            if not ahe_level:
                return None

            # データをマージ
            merged_data = self._merge_data(ahe_level, ahe_yoy, jtsqur_raw)

            print(f"Fetched {len(merged_data)} Average Hourly Earnings records")
            return merged_data

        except Exception as e:
            print(f"Error fetching Average Hourly Earnings: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_series(self, series_id: str, start_date: str) -> List[Dict[str, Any]]:
        """FRED APIからシリーズデータを取得"""
        try:
            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date,
                "sort_order": "asc"
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            observations = data.get("observations", [])

            result = []
            for obs in observations:
                try:
                    value_str = obs.get("value", "")
                    if value_str == "." or not value_str:
                        continue
                    value = float(value_str)
                    result.append({
                        "date": obs["date"],
                        "value": round(value, 2)
                    })
                except (ValueError, KeyError):
                    continue

            return result

        except Exception as e:
            print(f"Error fetching FRED series {series_id}: {e}")
            return []

    def _fetch_series_with_units(self, series_id: str, start_date: str, units: str) -> List[Dict[str, Any]]:
        """FRED APIからシリーズデータを取得（単位変換付き）"""
        try:
            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date,
                "sort_order": "asc",
                "units": units  # pc1=前年比、pch=前月比
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            observations = data.get("observations", [])

            result = []
            for obs in observations:
                try:
                    value_str = obs.get("value", "")
                    if value_str == "." or not value_str:
                        continue
                    value = float(value_str)
                    result.append({
                        "date": obs["date"],
                        "value": round(value, 2)
                    })
                except (ValueError, KeyError):
                    continue

            return result

        except Exception as e:
            print(f"Error fetching FRED series {series_id} with units {units}: {e}")
            return []

    def _merge_data(
        self,
        ahe_level: List[Dict[str, Any]],
        ahe_yoy: List[Dict[str, Any]],
        jtsqur: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """平均時給（水準・前年比）と自発的離職率データをマージ"""
        # 各データをマップに変換
        level_map = {item["date"]: item["value"] for item in ahe_level}
        yoy_map = {item["date"]: item["value"] for item in ahe_yoy}
        quits_map = {item["date"]: item["value"] for item in jtsqur}

        # 水準データから前月比を計算
        mom_map = {}
        sorted_dates = sorted(level_map.keys())
        for i in range(1, len(sorted_dates)):
            prev_date = sorted_dates[i - 1]
            curr_date = sorted_dates[i]
            prev_value = level_map[prev_date]
            curr_value = level_map[curr_date]
            if prev_value and prev_value != 0:
                mom = ((curr_value - prev_value) / prev_value) * 100
                mom_map[curr_date] = round(mom, 2)

        # 全データをマージ（前年比をベースに）
        result = []
        for date in sorted(yoy_map.keys()):
            entry = {
                "date": date,
                "yoy": yoy_map.get(date),
                "mom": mom_map.get(date),
                "quits_rate": quits_map.get(date)
            }
            result.append(entry)

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定（発表期間ベース）

        発表期間: 毎月1〜15日
        発表時刻: 21:30 (夏) / 22:30 (冬) JST
        """
        return self.schedule_checker.should_refresh(last_updated_str)

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
            "indicator": "Average Hourly Earnings / Quits Rate",
            "source": "FRED",
            "series_ids": [AHE_SERIES_ID, JTSQUR_SERIES_ID],
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "schedule_status": self.schedule_checker.get_status(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
average_hourly_earnings_service = AverageHourlyEarningsService()
