"""
個人消費支出：サービス（Personal Consumption Expenditures: Services）サービス
FRED APIから PCES データを取得し、前月比（MoM%）・前年比（YoY%）を計算

指標:
- PCES: Personal Consumption Expenditures: Services（個人消費支出：サービス、
        10億ドル、季節調整済み年率換算）

データソース:
- FRED: https://fred.stlouisfed.org/series/PCES
- BEA:  https://www.bea.gov/data/consumer-spending/main

発表スケジュール:
- BEA Personal Income and Outlays レポート（個人所得・個人消費）
- 毎月末 8:30 AM ET
- 次回発表日は FMP（econalpha_id="personal_income" / "Personal Income MoM"）から取得

キャッシュ方式: FMPスケジュールベース判定（CacheManager）+ 週次フォールバック

リファクタリング: fred_utils.BaseSingleSeriesService を使用
"""
from pathlib import Path

from services.usa.fred_utils import BaseSingleSeriesService


# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "consumer"


class PersonalConsumptionExpendituresServicesService(BaseSingleSeriesService):
    """個人消費支出：サービス サービス"""

    # 必須設定
    SERIES_ID = "PCES"
    REDIS_KEY = "fred:personal_consumption_expenditures_services:data"
    # 次回発表日・FMPスケジュールは個人所得（個人所得・個人消費レポート）に連動
    ECONALPHA_ID = "personal_income"
    CACHE_FILE = CACHE_DIR / "personal_consumption_expenditures_services_cache.json"
    INDICATOR_NAME = "Personal Consumption Expenditures: Services"

    # オプション設定
    VALUE_ROUND_DIGITS = 1
    USE_DIFF_CHANGES = False  # 変化率（前月比%・前年比%）を計算（差分ではない）

    def get_personal_consumption_expenditures_services_data(self, start_date=None, force_refresh=False):
        """
        個人消費支出：サービス データを取得（前月比%・前年比%）

        Returns:
            統一されたAPIレスポンス形式
            data: [{"date": str, "value": float, "mom": float | None, "yoy": float | None}, ...]
        """
        return self.get_data(start_date=start_date, force_refresh=force_refresh)


# シングルトンインスタンス
personal_consumption_expenditures_services_service = PersonalConsumptionExpendituresServicesService()
