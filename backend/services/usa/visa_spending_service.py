"""
Visa支出モメンタム指数サービス
FRED APIからVisa Spending Momentum Indexデータを取得

シリーズID:
- VISASMIHSA: Visa Spending Momentum Index (Seasonally Adjusted)

発表スケジュール:
- 毎月更新（具体的な発表日は不定）
- FMPスケジュールで管理

キャッシュ方式: 発表日時ベース判定方式

リファクタリング: fred_utils.BaseSingleSeriesService を使用
"""
from pathlib import Path

from services.usa.fred_utils import BaseSingleSeriesService


# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "consumer"


class VisaSpendingService(BaseSingleSeriesService):
    """Visa支出モメンタム指数サービス"""

    # 必須設定
    SERIES_ID = "VISASMIHSA"
    REDIS_KEY = "fred:series:visa_spending"
    ECONALPHA_ID = "visa_spending"
    CACHE_FILE = CACHE_DIR / "visa_spending_cache.json"
    INDICATOR_NAME = "Visa Spending Momentum Index"

    # オプション設定
    DEFAULT_START_DATE = "2015-01-01"  # このシリーズは2015年から
    VALUE_ROUND_DIGITS = 2
    USE_DIFF_CHANGES = True  # ポイント差で計算（指数なので）

    def get_visa_spending_data(self, start_date=None, force_refresh=False):
        """
        Visa支出モメンタム指数データを取得（既存APIとの互換性維持）

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            統一されたAPIレスポンス形式
        """
        return self.get_data(start_date=start_date, force_refresh=force_refresh)


# シングルトンインスタンス
visa_spending_service = VisaSpendingService()
