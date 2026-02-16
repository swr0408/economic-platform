"""
カナダ新築住宅価格指数（NHPI）サービス

指標:
- 新築住宅価格指数（インデックス値、2016年12月=100）
- 前年比（YoY）
- 前月比（MoM）

データソース:
- Statistics Canada Table 18-10-0205-01
- New housing price index, monthly
- WDS API (vectorId: 111955442)

発表スケジュール:
- 月次
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

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "canada" / "housing"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ca_new_housing_price_index_cache.json"

# Statistics Canada WDS API
STATCAN_WDS_BASE = "https://www150.statcan.gc.ca/t1/wds/rest"

# Vector ID for: Canada, Total (house and land)
# Table 18-10-0205-01, Coordinate: 1.1.0.0.0.0.0.0.0.0
NHPI_VECTOR_ID = 111955442
NHPI_PRODUCT_ID = 18100205

# FMPイベントパターン
FMP_NHPI_MOM_PATTERN = "New Housing Price Index MoM"
FMP_NHPI_YOY_PATTERN = "New Housing Price Index YoY"
CA_NHPI_ECONALPHA_ID = "canada_new_housing_price_index"


class CaNewHousingPriceIndexService:
    """カナダ新築住宅価格指数サービス"""

    DATA_CACHE_KEY = "canada:ca_new_housing_price_index:data"
    CACHE_TTL = 86400  # 24時間

    def __init__(self):
        pass

    def get_ca_new_housing_price_index_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダ新築住宅価格指数データを取得"""
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
            # 最新値を取得
            latest = result[-1] if result else None
            next_release = get_next_release_by_pattern(FMP_NHPI_MOM_PATTERN, country="CA")

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Statistics Canada",
                    "table": "18-10-0205-01",
                    "indicator": "New Housing Price Index",
                    "description": "カナダ新築住宅価格指数",
                    "unit": "%",
                    "frequency": "monthly",
                    "base_period": "December 2016 = 100",
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
        """Statistics Canada WDS APIから新築住宅価格指数データを取得"""
        try:
            print(f"[CaNHPI] Fetching data from WDS API (vectorId: {NHPI_VECTOR_ID})")

            # WDS API: getDataFromVectorsAndLatestNPeriods
            # 過去300期間（約25年分）を取得
            payload = [{"vectorId": NHPI_VECTOR_ID, "latestN": 300}]
            resp = requests.post(
                f"{STATCAN_WDS_BASE}/getDataFromVectorsAndLatestNPeriods",
                json=payload,
                timeout=30
            )
            resp.raise_for_status()

            data = resp.json()
            if not data or len(data) == 0:
                print("[CaNHPI] Empty response from WDS API")
                return []

            result = data[0]
            if result.get("status") != "SUCCESS":
                print(f"[CaNHPI] WDS API error: {result.get('object')}")
                return []

            obj = result.get("object", {})
            vector_id = obj.get("vectorId")
            product_id = obj.get("productId")
            data_points = obj.get("vectorDataPoint", [])

            print(f"[CaNHPI] Retrieved vectorId={vector_id}, productId={product_id}")
            print(f"[CaNHPI] Data points: {len(data_points)}")

            # データポイントを辞書に変換（日付 -> インデックス値）
            index_map: Dict[str, float] = {}
            for point in data_points:
                ref_per = point.get("refPer")  # 形式: "2024-01-01"
                value = point.get("value")

                if ref_per and value is not None:
                    index_map[ref_per] = float(value)

            print(f"[CaNHPI] Extracted {len(index_map)} monthly index values")

            # インデックス値からMoMとYoYを計算
            result_list = self._calculate_growth_rates(index_map)

            print(f"[CaNHPI] Loaded {len(result_list)} monthly records")
            if result_list:
                print(f"[CaNHPI] Date range: {result_list[0]['date']} to {result_list[-1]['date']}")
                latest = result_list[-1]
                print(f"[CaNHPI] Latest: {latest['date']} mom={latest.get('mom')}% yoy={latest.get('yoy')}%")

            return result_list

        except Exception as e:
            print(f"[CaNHPI] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _calculate_growth_rates(self, index_map: Dict[str, float]) -> List[Dict[str, Any]]:
        """インデックス値からMoM（前月比）とYoY（前年比）を計算"""
        sorted_dates = sorted(index_map.keys())
        result = []

        for i, date_str in enumerate(sorted_dates):
            index_value = index_map[date_str]

            item: Dict[str, Any] = {
                "date": date_str,
            }

            # MoM（前月比）を計算
            if i > 0:
                prev_date = sorted_dates[i - 1]
                prev_index = index_map[prev_date]
                if prev_index > 0:
                    mom = ((index_value - prev_index) / prev_index) * 100
                    item["mom"] = round(mom, 2)

            # YoY（前年比）を計算
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            prev_year_date = f"{dt.year - 1}-{dt.month:02d}-01"

            if prev_year_date in index_map:
                prev_year_index = index_map[prev_year_date]
                if prev_year_index > 0:
                    yoy = ((index_value - prev_year_index) / prev_year_index) * 100
                    item["yoy"] = round(yoy, 2)

            result.append(item)

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            return should_refresh_by_pattern(FMP_NHPI_MOM_PATTERN, last_updated_str, country="CA")
        except Exception:
            # FMP判定失敗時は24時間経過でリフレッシュ
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
            print(f"[CaNHPI] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaNHPI] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Canada New Housing Price Index",
            "source": "Statistics Canada",
            "table": "18-10-0205-01",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(FMP_NHPI_MOM_PATTERN, country="CA"),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ca_new_housing_price_index_service = CaNewHousingPriceIndexService()
