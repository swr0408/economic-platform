"""
住宅着工件数・建設許可件数サービス

FREDから住宅着工件数 (HOUST) と建設許可件数 (PERMIT) を取得

指標:
- 住宅着工件数（季節調整済み年率換算、千戸）
- 建設許可件数（季節調整済み年率換算、千戸）

データソース:
- FRED: HOUST (Housing Starts: Total)
- FRED: PERMIT (Building Permits)

発表スケジュール:
- 月次（毎月17-19日頃 8:30 ET）

キャッシュ方式: FMP発表日時ベース判定方式
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


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "housing"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class HousingStartsPermitsService:
    """住宅着工件数・建設許可件数サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"

    # シリーズID
    HOUSING_STARTS_SERIES_ID = "HOUST"
    BUILDING_PERMITS_SERIES_ID = "PERMIT"

    # キャッシュキー
    DATA_CACHE_KEY = "housing:starts_permits:data"
    DATA_CACHE_FILE = CACHE_DIR / "housing_starts_permits_cache.json"

    # FMPマッピング用ID
    ECONALPHA_ID = "housing_starts"

    # デフォルトの開始日
    DEFAULT_START_DATE = "2000-01-01"

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_housing_starts_permits_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        住宅着工件数・建設許可件数データを取得

        Args:
            force_refresh: 強制更新フラグ

        Returns:
            {
                "housing_starts": {
                    "data": [{...}],
                    "latest": {...}
                },
                "building_permits": {
                    "data": [{...}],
                    "latest": {...}
                },
                "next_release": {...},
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
                        "housing_starts": cached_data.get("housing_starts", {}),
                        "building_permits": cached_data.get("building_permits", {}),
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
                if last_updated_str and not self._should_refresh(last_updated_str):
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    return {
                        "housing_starts": file_cache.get("housing_starts", {}),
                        "building_permits": file_cache.get("building_permits", {}),
                        "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # FREDから両方のデータを取得
        housing_starts_data = self._fetch_series(self.HOUSING_STARTS_SERIES_ID)
        building_permits_data = self._fetch_series(self.BUILDING_PERMITS_SERIES_ID)

        if housing_starts_data or building_permits_data:
            housing_starts_with_changes = self._calculate_changes(housing_starts_data)
            building_permits_with_changes = self._calculate_changes(building_permits_data)

            housing_starts_latest = housing_starts_with_changes[-1] if housing_starts_with_changes else None
            building_permits_latest = building_permits_with_changes[-1] if building_permits_with_changes else None
            now_str = datetime.now(JST).isoformat()

            # 発表レース対策（ラグガード）: 住宅着工・建設許可は同時発表。両系列とも最新月が
            # 既存キャッシュを超えていなければ（＝ソース未反映）last_updated を旧値のまま維持し、
            # should_refresh の「消化済み」誤判定による翌月まで凍結を防ぎ次回再取得で自己回復させる。
            existing_cache = redis_client.get(self.DATA_CACHE_KEY)
            new_hs = housing_starts_latest.get("date") if housing_starts_latest else None
            new_bp = building_permits_latest.get("date") if building_permits_latest else None
            old_hs = old_bp = None
            if existing_cache:
                if existing_cache.get("housing_starts", {}).get("latest"):
                    old_hs = existing_cache["housing_starts"]["latest"].get("date")
                if existing_cache.get("building_permits", {}).get("latest"):
                    old_bp = existing_cache["building_permits"]["latest"].get("date")
            hs_not_newer = bool(old_hs and new_hs and new_hs <= old_hs)
            bp_not_newer = bool(old_bp and new_bp and new_bp <= old_bp)
            if hs_not_newer and bp_not_newer:
                last_updated = existing_cache.get("last_updated", now_str)
                print(f"  Housing Starts/Permits: data not newer (hs={new_hs}, bp={new_bp}), keeping last_updated={last_updated}")
            else:
                last_updated = now_str

            cache_payload = {
                "housing_starts": {
                    "data": housing_starts_with_changes,
                    "latest": housing_starts_latest
                },
                "building_permits": {
                    "data": building_permits_with_changes,
                    "latest": building_permits_latest
                },
                "last_updated": last_updated
            }

            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "housing_starts": cache_payload["housing_starts"],
                "building_permits": cache_payload["building_permits"],
                "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
                "cached": False,
                "source": "api",
                "last_updated": last_updated
            }

        # フォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "housing_starts": file_cache.get("housing_starts", {}),
                "building_permits": file_cache.get("building_permits", {}),
                "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "housing_starts": {"data": [], "latest": None},
            "building_permits": {"data": [], "latest": None},
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_series(self, series_id: str) -> List[Dict[str, Any]]:
        """FREDから指定シリーズを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print(f"Fetching {series_id} from FRED...")

            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": self.DEFAULT_START_DATE,
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
                            "value": round(float(obs["value"]), 1)
                        })
                    except (ValueError, TypeError):
                        continue

            print(f"Fetched {len(result)} records from FRED ({series_id})")
            return result

        except Exception as e:
            print(f"Error fetching {series_id}: {e}")
            return []

    def _calculate_changes(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """前月比・前年比・四半期比を計算"""
        result = []
        for i, item in enumerate(raw_data):
            entry = {
                "date": item["date"],
                "value": item["value"],
                "mom": None,
                "yoy": None,
                "qoq": None,
            }

            # 前月比
            if i >= 1:
                prev_value = raw_data[i - 1]["value"]
                if prev_value and prev_value != 0:
                    entry["mom"] = round(((item["value"] - prev_value) / prev_value) * 100, 2)

            # 前年比
            if i >= 12:
                year_ago_value = raw_data[i - 12]["value"]
                if year_ago_value and year_ago_value != 0:
                    entry["yoy"] = round(((item["value"] - year_ago_value) / year_ago_value) * 100, 2)

            result.append(entry)

        # 四半期比（QoQ）を計算
        self._calculate_quarterly_qoq(result)

        return result

    def _calculate_quarterly_qoq(self, data: List[Dict[str, Any]]) -> None:
        """四半期平均のQoQ変化率を計算し、各月のqoqフィールドに設定

        手順:
        1. 月次データを四半期ごとにグループ化
        2. 各四半期の平均値を算出
        3. QoQ(%) = (当四半期平均 / 前四半期平均 - 1) × 100
        4. 四半期に属する全3ヶ月にQoQ値を設定
        """
        from collections import defaultdict

        # 四半期ごとにグループ化
        quarters: Dict[str, List[float]] = defaultdict(list)
        month_to_quarter: Dict[str, str] = {}

        for item in data:
            dt = datetime.strptime(item["date"], "%Y-%m-%d")
            q = (dt.month - 1) // 3 + 1
            quarter_key = f"{dt.year}Q{q}"
            quarters[quarter_key].append(item["value"])
            month_to_quarter[item["date"]] = quarter_key

        # 四半期平均を計算
        quarter_avg: Dict[str, float] = {}
        for qk, values in quarters.items():
            if len(values) == 3:
                quarter_avg[qk] = sum(values) / 3
            # 不完全な四半期（3ヶ月揃っていない）はスキップ

        # ソートされた四半期リスト
        sorted_quarters = sorted(quarter_avg.keys())

        # QoQを計算
        quarter_qoq: Dict[str, float] = {}
        for i, qk in enumerate(sorted_quarters):
            if i >= 1:
                prev_avg = quarter_avg[sorted_quarters[i - 1]]
                if prev_avg and prev_avg != 0:
                    qoq_val = ((quarter_avg[qk] / prev_avg) - 1) * 100
                    quarter_qoq[qk] = round(qoq_val, 2)

        # 各月にQoQ値を設定
        for item in data:
            qk = month_to_quarter.get(item["date"])
            if qk and qk in quarter_qoq:
                item["qoq"] = quarter_qoq[qk]

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュ更新判定（FMP 3分方式）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not self.DATA_CACHE_FILE.exists():
                return None
            with open(self.DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {self.DATA_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Housing Starts / Building Permits",
            "source": "FRED",
            "series_ids": [self.HOUSING_STARTS_SERIES_ID, self.BUILDING_PERMITS_SERIES_ID],
            "cache_method": "FMP発表日時ベース判定",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "housing_starts_count": len(cached_data.get("housing_starts", {}).get("data", [])) if cached_data else 0,
            "building_permits_count": len(cached_data.get("building_permits", {}).get("data", [])) if cached_data else 0,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": self.DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
housing_starts_permits_service = HousingStartsPermitsService()
