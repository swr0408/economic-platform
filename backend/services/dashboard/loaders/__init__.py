"""
ダッシュボードローダー
各国・カテゴリ別のデータ取得ロジック
"""
from services.dashboard.loaders.base import BaseDashboardLoader
from services.dashboard.loaders.usa_policy import USAPolicyLoader
from services.dashboard.loaders.usa_economy import USAEconomyLoader
from services.dashboard.loaders.usa_consumer import USAConsumerLoader
from services.dashboard.loaders.usa_housing import USAHousingLoader

__all__ = [
    "BaseDashboardLoader",
    "USAPolicyLoader",
    "USAEconomyLoader",
    "USAConsumerLoader",
    "USAHousingLoader",
]
