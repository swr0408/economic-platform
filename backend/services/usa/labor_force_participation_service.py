"""
労働参加率サービス
FRED APIからCIVPARTデータを取得

指標:
- CIVPART: 労働参加率（Civilian Labor Force Participation Rate）

データソース:
- FRED: https://fred.stlouisfed.org/series/CIVPART

発表スケジュール:
- BLS Employment Situation（雇用統計）毎月第1金曜日 8:30 AM ET
- 失業率の次回発表日を参照（Employment Situation発表時に更新されるため）

キャッシュ方式: 発表日時ベース判定方式

リファクタリング: fred_utils.BaseSingleSeriesService を使用
"""
from pathlib import Path

from services.usa.fred_utils import BaseSingleSeriesService


# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"


class LaborForceParticipationService(BaseSingleSeriesService):
    """労働参加率サービス"""

    # 必須設定
    SERIES_ID = "CIVPART"
    REDIS_KEY = "fred:labor_force_participation:data"
    ECONALPHA_ID = "labor_force_participation"
    CACHE_FILE = CACHE_DIR / "labor_force_participation_cache.json"
    INDICATOR_NAME = "Labor Force Participation Rate"

    # オプション設定
    VALUE_ROUND_DIGITS = 1  # 小数1桁
    SKIP_CHANGES = True  # 水準値のみ（変化率計算なし）

    def get_labor_force_participation_data(self, start_date=None, force_refresh=False):
        """
        労働参加率データを取得（既存APIとの互換性維持）

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            統一されたAPIレスポンス形式
        """
        return self.get_data(start_date=start_date, force_refresh=force_refresh)


# シングルトンインスタンス
labor_force_participation_service = LaborForceParticipationService()
