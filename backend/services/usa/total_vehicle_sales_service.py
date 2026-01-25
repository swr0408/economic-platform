"""
自動車販売台数サービス
FRED APIからTotal Vehicle Sales（TOTALSA）データを取得

シリーズID:
- TOTALSA: Total Vehicle Sales (Seasonally Adjusted Annual Rate, Millions of Units)

発表スケジュール:
- BEA (Bureau of Economic Analysis) により毎月発表
- FMPスケジュールで管理

キャッシュ方式: 発表日時ベース判定方式

リファクタリング: fred_utils.BaseSingleSeriesService を使用
"""
from pathlib import Path

from services.usa.fred_utils import BaseSingleSeriesService


# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "consumer"


class TotalVehicleSalesService(BaseSingleSeriesService):
    """自動車販売台数サービス"""

    # 必須設定
    SERIES_ID = "TOTALSA"
    REDIS_KEY = "fred:series:total_vehicle_sales"
    ECONALPHA_ID = "total_vehicle_sales"
    CACHE_FILE = CACHE_DIR / "total_vehicle_sales_cache.json"
    INDICATOR_NAME = "Total Vehicle Sales"

    # オプション設定
    DEFAULT_START_DATE = "1990-01-01"
    VALUE_ROUND_DIGITS = 2
    USE_DIFF_CHANGES = False  # 変化率（%）で計算

    def get_total_vehicle_sales_data(self, start_date=None, force_refresh=False):
        """
        自動車販売台数データを取得（既存APIとの互換性維持）

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            統一されたAPIレスポンス形式
        """
        return self.get_data(start_date=start_date, force_refresh=force_refresh)


# シングルトンインスタンス
total_vehicle_sales_service = TotalVehicleSalesService()
