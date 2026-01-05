"""
クレジットカードローン残高サービス
FRED APIからConsumer Loans: Credit Cards and Other Revolving Plansデータを取得

シリーズID:
- CCLACBW027SBOG: Consumer Loans: Credit Cards and Other Revolving Plans, All Commercial Banks
  (週次、水曜日終了、季節調整済み、10億ドル単位)

データソース:
- FRB H.8 Assets and Liabilities of Commercial Banks in the United States
- https://www.federalreserve.gov/releases/h8/

発表スケジュール:
- 毎週金曜日 16:15 ET（米国東部時間）

キャッシュ方式: 発表日時ベース判定方式

リファクタリング: fred_utils.BaseSingleSeriesService を使用
"""
from typing import Dict, List, Any, Optional
from pathlib import Path

from services.usa.fred_utils import (
    BaseSingleSeriesService,
    fetch_fred_series,
    aggregate_weekly_to_monthly,
    calculate_changes,
)


# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "consumer"


class ConsumerCreditService(BaseSingleSeriesService):
    """クレジットカードローン残高サービス"""

    # 必須設定
    SERIES_ID = "CCLACBW027SBOG"
    REDIS_KEY = "fred:series:consumer_credit"
    ECONALPHA_ID = "consumer_credit"
    CACHE_FILE = CACHE_DIR / "consumer_credit_cache.json"
    INDICATOR_NAME = "Consumer Credit"

    # オプション設定
    VALUE_ROUND_DIGITS = 2
    USE_DIFF_CHANGES = False  # 変化率（%）で計算

    def _fetch_raw_data(self, start_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        週次データを取得して月次に集計

        週次データ（CCLACBW027SBOG）を月平均に変換
        """
        # 週次データを取得
        weekly_data = fetch_fred_series(
            series_id=self.SERIES_ID,
            start_date=start_date or self.DEFAULT_START_DATE,
            api_key=self.api_key,
            round_digits=self.VALUE_ROUND_DIGITS
        )

        if not weekly_data:
            return []

        # 月次に集計
        return aggregate_weekly_to_monthly(weekly_data, round_digits=self.VALUE_ROUND_DIGITS)

    def _process_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """変化率（%）を計算"""
        return calculate_changes(raw_data, include_value=True)

    def get_consumer_credit_data(self, start_date=None, force_refresh=False):
        """
        クレジットカードローン残高データを取得（既存APIとの互換性維持）

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            統一されたAPIレスポンス形式
        """
        return self.get_data(start_date=start_date, force_refresh=force_refresh)


# シングルトンインスタンス
consumer_credit_service = ConsumerCreditService()
