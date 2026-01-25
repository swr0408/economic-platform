"""
単位労働コスト / 労働生産性サービス
FRED APIからデータを取得

指標:
- PRS85006112: Nonfarm Business Sector: Unit Labor Costs (前期比)
- PRS85006092: Nonfarm Business Sector: Labor Productivity (前期比)

データソース:
- FRED: https://fred.stlouisfed.org/series/PRS85006112
- FRED: https://fred.stlouisfed.org/series/PRS85006092

発表スケジュール:
- BLS Productivity and Costs
- 四半期ごと発表（2月、3月、5月、6月、8月、9月、11月、12月）
- 発表期間: 毎月1〜15日
- 発表時刻: 21:30 (夏) / 22:30 (冬) JST

キャッシュ方式: FMP発表期間ベース判定方式

リファクタリング: fred_utils.BaseMultiSeriesService を使用
"""
from pathlib import Path

from services.usa.fred_utils import BaseMultiSeriesService


# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "employment"


class UnitLaborCostService(BaseMultiSeriesService):
    """単位労働コスト / 労働生産性サービス"""

    # 必須設定
    SERIES_CONFIG = {
        "ulc_pch": "PRS85006112",       # 単位労働コスト（前期比%）
        "productivity_pch": "PRS85006092"  # 労働生産性（前期比%）
    }
    REDIS_KEY = "fred:unit_labor_cost:data"
    ECONALPHA_ID = "unit_labor_cost"
    CACHE_FILE = CACHE_DIR / "unit_labor_cost_cache.json"
    INDICATOR_NAME = "Unit Labor Cost / Labor Productivity"

    # オプション設定
    PRIMARY_SERIES = "ulc_pch"
    VALUE_ROUND_DIGITS = 2
    # 注: PRS85006112/PRS85006092は既に前期比(%)なので追加計算不要

    def get_unit_labor_cost_data(self, start_date=None, force_refresh=False):
        """
        単位労働コスト / 労働生産性データを取得（既存APIとの互換性維持）

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            統一されたAPIレスポンス形式
        """
        return self.get_data(start_date=start_date, force_refresh=force_refresh)


# シングルトンインスタンス
unit_labor_cost_service = UnitLaborCostService()
