"""
雇用コスト指数（Employment Cost Index）サービス
FRED APIからECIALLCIV（Total Compensation）データを取得

指標:
- ECIALLCIV: Employment Cost Index: Total Compensation: All Civilian Workers

データソース:
- FRED: https://fred.stlouisfed.org/series/ECIALLCIV

発表スケジュール:
- BLS Employment Cost Index
- 四半期ごと発表（1月、4月、7月、10月）

キャッシュ方式: 発表日時ベース判定方式

リファクタリング: fred_utils.BaseSingleSeriesService を使用
"""
import os
from typing import Dict, List, Any, Optional
from pathlib import Path

import requests

from services.usa.fred_utils import BaseSingleSeriesService, FRED_BASE_URL


# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "employment"


class EmploymentCostIndexService(BaseSingleSeriesService):
    """雇用コスト指数サービス"""

    # 必須設定
    SERIES_ID = "ECIALLCIV"
    REDIS_KEY = "fred:employment_cost_index:data"
    ECONALPHA_ID = "employment_cost_index"
    CACHE_FILE = CACHE_DIR / "employment_cost_index_cache.json"
    INDICATOR_NAME = "Employment Cost Index"

    # オプション設定
    VALUE_ROUND_DIGITS = 2
    SKIP_CHANGES = True  # FREDから前期比を直接取得するため

    def _fetch_raw_data(self, start_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        FRED APIから前期比（pch）として取得

        ECIは四半期データで、FREDのunits=pchパラメータを使用して
        前期比を直接取得する
        """
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            url = f"{FRED_BASE_URL}/series/observations"
            params = {
                "series_id": self.SERIES_ID,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date or self.DEFAULT_START_DATE,
                "sort_order": "asc",
                "units": "pch"  # 前期比
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
                    pch = float(value_str)
                    result.append({
                        "date": obs["date"],
                        "pch": round(pch, self.VALUE_ROUND_DIGITS)
                    })
                except (ValueError, KeyError):
                    continue

            return result

        except Exception as e:
            print(f"Error fetching {self.INDICATOR_NAME}: {e}")
            return []

    def get_employment_cost_index_data(self, start_date=None, force_refresh=False):
        """
        雇用コスト指数データを取得（既存APIとの互換性維持）

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            統一されたAPIレスポンス形式
        """
        return self.get_data(start_date=start_date, force_refresh=force_refresh)


# シングルトンインスタンス
employment_cost_index_service = EmploymentCostIndexService()
