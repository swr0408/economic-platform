"""
ダッシュボードサービス
ページ単位のバッチAPIでデータを一括取得
"""
from services.dashboard.loaders.base import BaseDashboardLoader
from services.dashboard.registry import get_dashboard_loader, DASHBOARD_LOADERS

__all__ = [
    "BaseDashboardLoader",
    "get_dashboard_loader",
    "DASHBOARD_LOADERS",
]
