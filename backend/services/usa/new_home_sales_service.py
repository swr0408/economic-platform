"""
新築住宅販売戸数サービス

FREDから新築一戸建て住宅販売戸数 (HSN1F) を取得

指標:
- 新築一戸建て住宅販売戸数（季節調整済み年率換算、千戸）

データソース:
- FRED: HSN1F (New One Family Houses Sold)

発表スケジュール:
- 月次（毎月下旬、通常24-26日頃 10:00 ET）

キャッシュ方式: FMP発表日時ベース判定方式
"""
from datetime import datetime
from typing import Dict, List, Any
from zoneinfo import ZoneInfo
from pathlib import Path

from services.usa.base_fred_service import BaseFREDService
from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import get_next_release_from_fmp


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "housing"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class NewHomeSalesService(BaseFREDService):
    """新築住宅販売戸数サービス"""

    SERIES_ID = "HSN1F"
    DATA_CACHE_KEY = "housing:new_home_sales:data"
    DATA_CACHE_FILE = CACHE_DIR / "new_home_sales_cache.json"

    # FMPマッピング用ID
    ECONALPHA_ID = "new_home_sales"

    # デフォルトの開始日
    DEFAULT_START_DATE = "2000-01-01"

    def __init__(self):
        super().__init__()

    def get_new_home_sales_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        新築住宅販売戸数データを取得

        Args:
            force_refresh: 強制更新フラグ

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float, "mom": float, "yoy": float}, ...],
                "latest": {"date": str, "value": float, "mom": float, "yoy": float},
                "next_release": {"date": str, "datetime_jst": str, "label": str} | None,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        result = self.get_data(force_refresh=force_refresh)

        # next_releaseを追加
        if self.ECONALPHA_ID:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
            result["next_release"] = next_release

        return result

    def _calculate_changes(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        前月比・前年比を計算

        HSN1Fは千戸単位の年率換算値なので、
        変化率を%で計算して返す
        """
        result = []
        for i, item in enumerate(raw_data):
            entry = {
                "date": item["date"],
                "value": item["value"],  # 原数値（千戸）
                "mom": None,
                "yoy": None
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

        return result

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "New Home Sales",
            "source": "FRED",
            "series_id": self.SERIES_ID,
            "cache_method": "FMP発表日時ベース判定",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID) if self.ECONALPHA_ID else None,
            "file_cache_exists": self.DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
new_home_sales_service = NewHomeSalesService()
