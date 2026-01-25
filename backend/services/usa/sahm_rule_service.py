"""
サームルール（Sahm Rule）サービス
FREDからSAHMCURRENTシリーズを取得

指標:
- Sahm Rule Recession Indicator（サームルール景気後退指標）

データソース:
- FRED: SAHMCURRENT

発表スケジュール:
- 月次: 雇用統計と同時発表

キャッシュ方式: FMP発表日時ベース判定方式（unemployment_rateと連動）
"""
from pathlib import Path

from services.usa.fred_utils import BaseSingleSeriesService


CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class SahmRuleService(BaseSingleSeriesService):
    """サームルールサービス（FRED SAHMCURRENT）"""

    SERIES_ID = "SAHMCURRENT"
    REDIS_KEY = "employment:sahm_rule:data"
    ECONALPHA_ID = "unemployment_rate"  # 失業率と同時発表
    CACHE_FILE = CACHE_DIR / "sahm_rule_cache.json"
    INDICATOR_NAME = "Sahm Rule"

    # 月次データ - 変化率計算をスキップ（水準値のみ）
    SKIP_CHANGES = True
    VALUE_ROUND_DIGITS = 2
    DEFAULT_START_DATE = "2000-01-01"


# シングルトンインスタンス
sahm_rule_service = SahmRuleService()
