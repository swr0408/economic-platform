"""
継続失業保険申請件数（UI Continued Claims）サービス
FRED APIから継続失業保険申請件数データを取得

指標:
- CCSA: Continued Claims, Weekly, Seasonally Adjusted
- CC4WSA: 4-Week Moving Average of Continued Claims, Weekly, Seasonally Adjusted

データソース:
- FRED: https://fred.stlouisfed.org/series/CCSA

発表スケジュール:
- 毎週木曜日 8:30 AM ET（新規失業保険申請件数と同時発表）

キャッシュ方式: FMP発表日時ベース判定方式

リファクタリング: fred_utils.BaseMultiSeriesService を使用
"""
from pathlib import Path

from services.usa.fred_utils import BaseMultiSeriesService


# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "employment"


class ContinuedClaimsService(BaseMultiSeriesService):
    """継続失業保険申請件数サービス"""

    # 必須設定
    SERIES_CONFIG = {
        "ccsa": "CCSA",         # 継続失業保険申請件数
        "cc4wsa": "CC4WSA"      # 4週移動平均
    }
    REDIS_KEY = "fred:continued_claims:data"
    ECONALPHA_ID = "continued_claims"
    CACHE_FILE = CACHE_DIR / "continued_claims_cache.json"
    INDICATOR_NAME = "Continued Claims"

    # オプション設定
    PRIMARY_SERIES = "ccsa"
    VALUE_ROUND_DIGITS = 0  # 件数は整数

    def get_continued_claims_data(self, start_date=None, force_refresh=False):
        """
        継続失業保険申請件数データを取得（既存APIとの互換性維持）

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            統一されたAPIレスポンス形式
        """
        return self.get_data(start_date=start_date, force_refresh=force_refresh)


# シングルトンインスタンス
continued_claims_service = ContinuedClaimsService()
