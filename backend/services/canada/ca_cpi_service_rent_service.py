"""
カナダCPI サービス/家賃（粘着性CPI）サービス

指標:
- CPI All-items (総合CPI)
- CPI excl. food and energy (コアCPI)
- CPI Services (サービス)
- CPI Shelter (住居)
- CPI Rent (家賃)

すべてYoY（前年比）で表示

データソース:
- Statistics Canada WDS API (Table 18-10-0004-01)
- Vector IDs: v41690973, v41691233, v41691230, v41691050, v41691052

値の解釈:
- BoCが重視する粘着領域（サービス/家賃）のインフレ動向を把握
- サービスCPIが高止まりすると利下げが遅れる

発表スケジュール:
- 毎月中旬
- 発表時刻: 08:30 ET
"""
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client
from services.canada.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")
TORONTO = ZoneInfo("America/Toronto")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "canada" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ca_cpi_service_rent_cache.json"

# Statistics Canada WDS API
WDS_BASE = "https://www150.statcan.gc.ca/t1/wds/rest"

# CPI構成項目のベクターID（Table 18-10-0004-01, Canada, 季節調整前, 2002=100）
CPI_VECTORS = {
    "all_items": 41690973,      # CPI All-items
    "ex_food_energy": 41691233,  # CPI excl. food and energy (コア)
    "services": 41691230,        # CPI Services
    "shelter": 41691050,         # CPI Shelter (住居)
    "rent": 41691052,            # CPI Rent (家賃)
}

# FMPイベントパターン（既存CPI FMPマッピングを共有）
FMP_CPI_PATTERN = "CPI"


class CaCpiServiceRentService:
    """カナダCPI サービス/家賃サービス"""

    DATA_CACHE_KEY = "canada:ca_cpi_service_rent:data"
    CACHE_TTL = 86400  # 24時間

    def __init__(self):
        pass

    def get_ca_cpi_service_rent_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダCPI サービス/家賃データを取得"""
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
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # データソースから取得
        result = self._load_from_source()
        if result:
            latest = result[-1] if result else None
            next_release = get_next_release_by_pattern(FMP_CPI_PATTERN, country="CA")

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Statistics Canada",
                    "table": "18-10-0004-01",
                    "indicator": "CPI Service / Rent (Sticky CPI)",
                    "description": "カナダCPI サービス/家賃（粘着性CPI）",
                    "unit": "% (YoY)",
                    "frequency": "monthly",
                    "base_year": "2002=100",
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=self.CACHE_TTL)
            self._save_file_cache(cache_payload)

            return {
                "data": result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_source(self) -> List[Dict[str, Any]]:
        """StatCan WDS APIからCPI構成項目のインデックスを取得し、YoYを計算"""
        try:
            # 全ベクターのデータを取得
            index_data = self._fetch_vector_data()
            if not index_data:
                return []

            # YoYを計算
            result = self._calculate_yoy(index_data)

            print(f"[CaCpiServiceRent] Loaded {len(result)} monthly records")
            if result:
                print(f"[CaCpiServiceRent] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CaCpiServiceRent] Latest: {latest['date']} "
                      f"all_items={latest.get('all_items')} "
                      f"services={latest.get('services')} "
                      f"rent={latest.get('rent')}")

            return result

        except Exception as e:
            print(f"[CaCpiServiceRent] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_vector_data(self) -> Dict[str, Dict[str, float]]:
        """
        StatCan WDS APIからベクターデータを取得

        Returns:
            {
                "all_items": {"2020-01-01": 136.8, ...},
                "services": {"2020-01-01": 145.2, ...},
                ...
            }
        """
        try:
            vector_ids = list(CPI_VECTORS.values())

            # getBulkVectorDataByRange で全ベクターを一括取得
            url = f"{WDS_BASE}/getBulkVectorDataByRange"
            payload = {
                "vectorIds": vector_ids,
                "startDataPointReleaseDate": "2000-01-01T00:00",
                "endDataPointReleaseDate": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M"),
            }

            print(f"[CaCpiServiceRent] Fetching data from WDS API for {len(vector_ids)} vectors")
            resp = requests.post(url, json=payload, timeout=60)
            resp.raise_for_status()

            data = resp.json()

            # ベクターID→フィールド名のマッピング
            id_to_field = {v: k for k, v in CPI_VECTORS.items()}

            result: Dict[str, Dict[str, float]] = {field: {} for field in CPI_VECTORS.keys()}

            for item in data:
                status = item.get("status")
                if status != "SUCCESS":
                    print(f"[CaCpiServiceRent] Vector status not SUCCESS: {status}")
                    continue

                obj = item.get("object", {})
                vector_id = obj.get("vectorId")
                field_name = id_to_field.get(vector_id)
                if not field_name:
                    continue

                data_points = obj.get("vectorDataPoint", [])
                for dp in data_points:
                    ref_per = dp.get("refPer")
                    value = dp.get("value")
                    if ref_per and value is not None:
                        # refPer is "YYYY-MM-DD" format
                        result[field_name][ref_per] = float(value)

                print(f"[CaCpiServiceRent] Loaded {len(data_points)} data points for {field_name} (vector {vector_id})")

            return result

        except Exception as e:
            print(f"[CaCpiServiceRent] Error fetching vector data: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _calculate_yoy(self, index_data: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
        """
        インデックスデータから全フィールドのYoY（前年比）を計算

        Args:
            index_data: {"all_items": {"2020-01-01": 136.8, ...}, ...}

        Returns:
            [{"date": "2020-01-01", "all_items": 1.95, "services": 2.10, ...}, ...]
        """
        # 全日付を収集
        all_dates: set = set()
        for field_data in index_data.values():
            all_dates.update(field_data.keys())

        # 2001年以降のみ（YoY計算に12ヶ月前が必要）
        filtered_dates = sorted([d for d in all_dates if d >= "2001-01-01"])

        result = []
        for date_str in filtered_dates:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                prev_year_date = f"{dt.year - 1:04d}-{dt.month:02d}-{dt.day:02d}"
            except ValueError:
                continue

            item: Dict[str, Any] = {"date": date_str}
            has_value = False

            for field_name, field_data in index_data.items():
                current_val = field_data.get(date_str)
                prev_val = field_data.get(prev_year_date)

                if current_val is not None and prev_val is not None and prev_val > 0:
                    yoy = ((current_val - prev_val) / prev_val) * 100
                    item[field_name] = round(yoy, 2)
                    has_value = True
                else:
                    item[field_name] = None

            if has_value:
                result.append(item)

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            return should_refresh_by_pattern(FMP_CPI_PATTERN, last_updated_str, country="CA")
        except Exception:
            try:
                last_updated = datetime.fromisoformat(last_updated_str)
                if last_updated.tzinfo is None:
                    last_updated = last_updated.replace(tzinfo=JST)
                now = datetime.now(JST)
                age = now - last_updated
                return age.total_seconds() > 86400
            except Exception:
                return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CaCpiServiceRent] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaCpiServiceRent] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Canada CPI Service / Rent (Sticky CPI)",
            "source": "Statistics Canada",
            "table": "18-10-0004-01",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": cached_data.get("next_release") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ca_cpi_service_rent_service = CaCpiServiceRentService()
