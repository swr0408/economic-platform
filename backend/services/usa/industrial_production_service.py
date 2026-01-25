"""
鉱工業生産（Industrial Production）サービス
FRED APIからINDPROデータを取得

シリーズID:
- INDPRO: Industrial Production: Total Index (Index 2017=100)

発表スケジュール:
- 毎月14〜18日頃の9:15 ET
- FMPスケジュールで管理

キャッシュ方式: 発表日時ベース判定方式

リファクタリング: fred_utils.BaseSingleSeriesService を使用
"""
from pathlib import Path

from services.usa.fred_utils import BaseSingleSeriesService


# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "economy"


class IndustrialProductionService(BaseSingleSeriesService):
    """鉱工業生産（Industrial Production）サービス"""

    # 必須設定
    SERIES_ID = "INDPRO"
    REDIS_KEY = "fred:series:indpro"
    ECONALPHA_ID = "industrial_production"
    CACHE_FILE = CACHE_DIR / "industrial_production_cache.json"
    INDICATOR_NAME = "Industrial Production"

    # オプション設定
    VALUE_ROUND_DIGITS = 2
    USE_DIFF_CHANGES = False  # 変化率（%）で計算

    def get_industrial_production_data(self, start_date=None, force_refresh=False):
        """
        鉱工業生産データを取得（既存APIとの互換性維持）

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            統一されたAPIレスポンス形式
        """
        return self.get_data(start_date=start_date, force_refresh=force_refresh)


# シングルトンインスタンス
industrial_production_service = IndustrialProductionService()
