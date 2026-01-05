"""
設備稼働率（Capacity Utilization）サービス
FRED APIからTCUデータを取得

シリーズID:
- TCU: Capacity Utilization: Total Industry (Percent)

発表スケジュール:
- 毎月14〜18日頃の9:15 ET（Industrial Productionと同時発表）
- FMPスケジュールで管理

キャッシュ方式: 発表日時ベース判定方式

リファクタリング: fred_utils.BaseSingleSeriesService を使用
"""
from pathlib import Path

from services.usa.fred_utils import BaseSingleSeriesService


# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "economy"


class CapacityUtilizationService(BaseSingleSeriesService):
    """設備稼働率（Capacity Utilization）サービス"""

    # 必須設定
    SERIES_ID = "TCU"
    REDIS_KEY = "fred:series:tcu"
    ECONALPHA_ID = "capacity_utilization"
    CACHE_FILE = CACHE_DIR / "capacity_utilization_cache.json"
    INDICATOR_NAME = "Capacity Utilization"

    # オプション設定
    VALUE_ROUND_DIGITS = 2
    SKIP_CHANGES = True  # 水準値のみ（変化率計算なし）

    def get_capacity_utilization_data(self, start_date=None, force_refresh=False):
        """
        設備稼働率データを取得（既存APIとの互換性維持）

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            統一されたAPIレスポンス形式
        """
        return self.get_data(start_date=start_date, force_refresh=force_refresh)


# シングルトンインスタンス
capacity_utilization_service = CapacityUtilizationService()
