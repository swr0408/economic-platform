"""
S&P/ケースシラー住宅価格指数サービス

FREDからS&P/Case-Shiller 20-City Composite Home Price Index (SPCS20RSA)を取得
前年比を計算して提供

指標:
- S&P/ケースシラー住宅価格指数 (20都市複合)

データソース:
- FRED: SPCS20RSA

発表スケジュール:
- 月次（毎月最終火曜日 9:00 ET）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from services.usa.base_fred_service import BaseFREDService
from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "housing"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class CaseShillerService(BaseFREDService):
    """S&P/ケースシラー住宅価格指数サービス"""

    SERIES_ID = "SPCS20RSA"
    DATA_CACHE_KEY = "housing:case_shiller:data"
    DATA_CACHE_FILE = CACHE_DIR / "case_shiller_cache.json"

    # FMPマッピング用ID（S&P/Case-Shiller Home Price Indices）
    ECONALPHA_ID = "case_shiller"

    # デフォルトの開始日
    DEFAULT_START_DATE = "2000-01-01"

    def __init__(self):
        super().__init__()

    def get_case_shiller_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        ケースシラー住宅価格指数データを取得

        Args:
            force_refresh: 強制更新フラグ

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float, "yoy": float}, ...],
                "latest": {"date": str, "value": float, "yoy": float},
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
        前年比のみ計算（住宅価格指数は前年比が主な指標）

        原数値はインデックスなので、前年比を計算して返す
        """
        result = []
        for i, item in enumerate(raw_data):
            entry = {
                "date": item["date"],
                "value": item["value"],  # 原数値（インデックス）
                "yoy": None
            }

            # 前年比（12ヶ月前との比較）
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
            "indicator": "S&P/Case-Shiller Home Price Index",
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
case_shiller_service = CaseShillerService()
