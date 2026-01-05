"""
新規失業保険申請件数（UI Initial Claims）サービス
FRED APIから新規失業保険申請件数データを取得

指標:
- ICSA: Initial Claims, Weekly, Seasonally Adjusted
- IC4WSA: 4-Week Moving Average of Initial Claims, Weekly, Seasonally Adjusted

データソース:
- FRED: https://fred.stlouisfed.org/series/ICSA

発表スケジュール:
- 毎週木曜日 8:30 AM ET

キャッシュ方式: FMP発表日時ベース判定方式

リファクタリング: fred_utils.BaseMultiSeriesService を使用
"""
from pathlib import Path

from services.usa.fred_utils import BaseMultiSeriesService


# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"


class InitialClaimsService(BaseMultiSeriesService):
    """新規失業保険申請件数サービス"""

    # 必須設定
    SERIES_CONFIG = {
        "icsa": "ICSA",         # 新規失業保険申請件数
        "ic4wsa": "IC4WSA"      # 4週移動平均
    }
    REDIS_KEY = "fred:initial_claims:data"
    ECONALPHA_ID = "initial_claims"
    CACHE_FILE = CACHE_DIR / "initial_claims_cache.json"
    INDICATOR_NAME = "Initial Claims"

    # オプション設定
    PRIMARY_SERIES = "icsa"
    VALUE_ROUND_DIGITS = 0  # 件数は整数

    def get_initial_claims_data(self, start_date=None, force_refresh=False):
        """
        新規失業保険申請件数データを取得（既存APIとの互換性維持）

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            統一されたAPIレスポンス形式
        """
        return self.get_data(start_date=start_date, force_refresh=force_refresh)


# シングルトンインスタンス
initial_claims_service = InitialClaimsService()
