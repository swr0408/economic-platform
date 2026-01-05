"""
失業率 / 広義の失業率サービス
FRED APIからUNRATE & U6RATEデータを取得

指標:
- UNRATE: Unemployment Rate（失業率）
- U6RATE: Total Unemployed Plus All Persons Marginally Attached to the Labor Force
         Plus Total Employed Part Time for Economic Reasons（広義の失業率）

データソース:
- FRED: https://fred.stlouisfed.org/series/UNRATE
- FRED: https://fred.stlouisfed.org/series/U6RATE

発表スケジュール:
- BLS Employment Situation（雇用統計）
- 毎月第1金曜日 8:30 AM ET
- 発表時刻: 21:30 (夏) / 22:30 (冬) JST

キャッシュ方式: FMP 3分方式（発表時刻から3分間は毎分更新チェック）

リファクタリング: fred_utils.BaseMultiSeriesService を使用
"""
from pathlib import Path

from services.usa.fred_utils import BaseMultiSeriesService


# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"


class UnemploymentRateService(BaseMultiSeriesService):
    """失業率 / 広義の失業率サービス"""

    # 必須設定
    SERIES_CONFIG = {
        "unrate": "UNRATE",     # 失業率
        "u6rate": "U6RATE"      # 広義の失業率（U-6）
    }
    REDIS_KEY = "fred:unemployment_rate:data"
    ECONALPHA_ID = "unemployment_rate"
    CACHE_FILE = CACHE_DIR / "unemployment_rate_cache.json"
    INDICATOR_NAME = "Unemployment Rate"

    # オプション設定
    PRIMARY_SERIES = "unrate"
    VALUE_ROUND_DIGITS = 1  # 失業率は小数点1桁

    def get_unemployment_rate_data(self, start_date=None, force_refresh=False):
        """
        失業率データを取得（既存APIとの互換性維持）

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            統一されたAPIレスポンス形式
        """
        return self.get_data(start_date=start_date, force_refresh=force_refresh)


# シングルトンインスタンス
unemployment_rate_service = UnemploymentRateService()
