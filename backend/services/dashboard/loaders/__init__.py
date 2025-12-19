"""
ダッシュボードローダー
各国・カテゴリ別のデータ取得ロジック
"""
from services.dashboard.loaders.base import BaseDashboardLoader
from services.dashboard.loaders.usa_policy import USAPolicyLoader
from services.dashboard.loaders.usa_economy import USAEconomyLoader

__all__ = [
    "BaseDashboardLoader",
    "USAPolicyLoader",
    "USAEconomyLoader",
]
