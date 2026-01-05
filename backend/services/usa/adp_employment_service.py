"""
ADP雇用者数（ADP National Employment Report）サービス
FRED APIからADP雇用者数データを取得

指標:
- ADPMNUSNERSA: ADP National Employment Report, All Employees, Total Nonfarm, Monthly, Seasonally Adjusted

データソース:
- FRED: https://fred.stlouisfed.org/series/ADPMNUSNERSA

発表スケジュール:
- 毎月第1水曜日 8:15 AM ET（雇用統計の2日前）

キャッシュ方式: FMP発表日時ベース判定方式

リファクタリング: fred_utils.BaseSingleSeriesService を使用
"""
from typing import Dict, List, Any
from datetime import datetime
from pathlib import Path

from services.usa.fred_utils import BaseSingleSeriesService


# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"


class ADPEmploymentService(BaseSingleSeriesService):
    """ADP雇用者数サービス"""

    # 必須設定
    SERIES_ID = "ADPMNUSNERSA"
    REDIS_KEY = "fred:adp_employment:data"
    ECONALPHA_ID = "adp_employment"
    CACHE_FILE = CACHE_DIR / "adp_employment_cache.json"
    INDICATOR_NAME = "ADP Employment"

    # オプション設定
    VALUE_ROUND_DIGITS = 0  # 千人単位は整数
    SKIP_CHANGES = True  # カスタム変化率計算を使用

    def _process_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """前月比（増減数）・前年比（%）を計算"""
        data_by_date = {d["date"]: d["value"] for d in raw_data}
        result = []

        for item in raw_data:
            current_date = datetime.strptime(item["date"], "%Y-%m-%d")
            current_value = item["value"]

            # 前月の日付を計算
            if current_date.month == 1:
                prev_month_date = current_date.replace(year=current_date.year - 1, month=12, day=1)
            else:
                prev_month_date = current_date.replace(month=current_date.month - 1, day=1)
            prev_month_str = prev_month_date.strftime("%Y-%m-%d")

            # 前年同月の日付を計算
            prev_year_date = current_date.replace(year=current_date.year - 1)
            prev_year_str = prev_year_date.strftime("%Y-%m-%d")

            # 前月比（千人単位の増減）
            prev_month_value = data_by_date.get(prev_month_str)
            mom = None
            if prev_month_value is not None and current_value is not None:
                mom = round(current_value - prev_month_value, 0)

            # 前年比（%）
            prev_year_value = data_by_date.get(prev_year_str)
            yoy = None
            if prev_year_value is not None and prev_year_value != 0 and current_value is not None:
                yoy = round((current_value - prev_year_value) / prev_year_value * 100, 2)

            result.append({
                "date": item["date"],
                "value": current_value,
                "mom": mom,  # 前月比（千人）
                "yoy": yoy   # 前年比（%）
            })

        return result

    def get_adp_employment_data(self, start_date=None, force_refresh=False):
        """
        ADP雇用者数データを取得（既存APIとの互換性維持）

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            統一されたAPIレスポンス形式
        """
        return self.get_data(start_date=start_date, force_refresh=force_refresh)


# シングルトンインスタンス
adp_employment_service = ADPEmploymentService()
