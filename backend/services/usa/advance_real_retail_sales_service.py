"""
Advance Real Retail and Food Services Sales サービス
FRED RRSFS シリーズからデータを取得

指標:
- 実質小売売上高（2017年ドルベース、季節調整済み）
- 前月比・前年比を計算（日付ベースで正確に計算）

データソース:
- FRED: https://fred.stlouisfed.org/series/RRSFS

発表スケジュール:
- 小売売上高発表と同日（毎月中旬 8:30 ET）

キャッシュ方式: FMP発表日時ベース判定方式（retail_sales）
"""
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

from services.usa.base_fred_service import BaseFREDService
from services.usa.fmp_next_release_utils import get_next_release_from_fmp


# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class AdvanceRealRetailSalesService(BaseFREDService):
    """
    Advance Real Retail and Food Services Sales サービス

    FRED RRSFS シリーズ:
    - 実質小売売上高（2017年ドルベース、季節調整済み）
    - 単位: Millions of Chained 2017 Dollars
    """

    SERIES_ID = "RRSFS"
    DATA_CACHE_KEY = "consumer:advance_real_retail_sales:data"
    DATA_CACHE_FILE = CACHE_DIR / "advance_real_retail_sales_cache.json"
    ECONALPHA_ID = "retail_sales"  # 小売売上高と同時発表

    DEFAULT_START_DATE = "2000-01-01"

    def _calculate_changes(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        前月比・前年比を日付ベースで正確に計算

        RRSFSシリーズは一部の月が欠落している可能性があるため、
        インデックスベースではなく日付ベースで計算する
        """
        # 日付→値のマッピングを作成
        date_value_map = {item["date"]: item["value"] for item in raw_data}

        result = []
        for item in raw_data:
            entry = {
                "date": item["date"],
                "value": item["value"],
                "mom": None,
                "yoy": None
            }

            try:
                current_date = datetime.strptime(item["date"], "%Y-%m-%d")

                # 前月比: 1ヶ月前のデータと比較
                prev_month_date = current_date - relativedelta(months=1)
                prev_month_str = prev_month_date.strftime("%Y-%m-%d")
                if prev_month_str in date_value_map:
                    prev_value = date_value_map[prev_month_str]
                    if prev_value and prev_value != 0:
                        entry["mom"] = round(((item["value"] - prev_value) / prev_value) * 100, 2)

                # 前年比: 12ヶ月前のデータと比較
                year_ago_date = current_date - relativedelta(months=12)
                year_ago_str = year_ago_date.strftime("%Y-%m-%d")
                if year_ago_str in date_value_map:
                    year_ago_value = date_value_map[year_ago_str]
                    if year_ago_value and year_ago_value != 0:
                        entry["yoy"] = round(((item["value"] - year_ago_value) / year_ago_value) * 100, 2)

            except (ValueError, TypeError):
                pass

            result.append(entry)

        return result

    def get_advance_real_retail_sales_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        実質小売売上高データを取得

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{
                    "date": str,
                    "value": float,  # 実質小売売上高（百万ドル、2017年基準）
                    "mom": float | null,  # 前月比（%）
                    "yoy": float | null,  # 前年比（%）
                }, ...],
                "latest": {...},
                "next_release": {...} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        result = self.get_data(start_date=start_date, force_refresh=force_refresh)

        # next_releaseを追加
        result["next_release"] = get_next_release_from_fmp(self.ECONALPHA_ID)

        return result


# シングルトンインスタンス
advance_real_retail_sales_service = AdvanceRealRetailSalesService()
