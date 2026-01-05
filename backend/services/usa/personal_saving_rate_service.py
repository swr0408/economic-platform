"""
家計貯蓄率（Personal Saving Rate）サービス
FRED APIからPSAVERTデータを取得

指標:
- PSAVERT: Personal Saving Rate（個人貯蓄率）

データソース:
- FRED: https://fred.stlouisfed.org/series/PSAVERT
- BEA: https://www.bea.gov/data/income-saving/personal-income

発表スケジュール:
- BEA Personal Income and Outlays レポート
- 毎月末 8:30 AM ET
- BEAから次回発表日を自動取得

キャッシュ方式: 発表日時ベース判定方式

リファクタリング: fred_utils.BaseSingleSeriesService を使用
"""
from pathlib import Path

from services.usa.fred_utils import BaseSingleSeriesService


# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "consumer"


class PersonalSavingRateService(BaseSingleSeriesService):
    """家計貯蓄率（Personal Saving Rate）サービス"""

    # 必須設定
    SERIES_ID = "PSAVERT"
    REDIS_KEY = "fred:personal_saving_rate:data"
    ECONALPHA_ID = "personal_saving_rate"
    CACHE_FILE = CACHE_DIR / "personal_saving_rate_cache.json"
    INDICATOR_NAME = "Personal Saving Rate"

    # オプション設定
    VALUE_ROUND_DIGITS = 1  # 貯蓄率は小数1桁
    USE_DIFF_CHANGES = True  # ポイント差で計算

    def get_personal_saving_rate_data(self, start_date=None, force_refresh=False):
        """
        家計貯蓄率データを取得（既存APIとの互換性維持）

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            統一されたAPIレスポンス形式
        """
        return self.get_data(start_date=start_date, force_refresh=force_refresh)


# シングルトンインスタンス
personal_saving_rate_service = PersonalSavingRateService()
