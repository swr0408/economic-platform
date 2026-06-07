"""
GDP構成要素ルーター
民間最終消費支出・民間企業設備の前期比データを提供

エンドポイント:
    GET /api/japan/gdp-components       - GDP構成要素データ取得
    GET /api/japan/gdp-components/table - テーブル表示用データ取得
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

try:
    from services.japan.gdp_components_service import gdp_components_service
except ImportError:
    from backend.services.japan.gdp_components_service import gdp_components_service

router = APIRouter(prefix="/api/japan", tags=["Japan GDP Components"])


@router.get("/gdp-components")
def get_gdp_components_data(
    force_refresh: bool = Query(False, description="キャッシュを無視して強制取得")
) -> Dict[str, Any]:
    """
    GDP構成要素（前期比）データを取得

    Returns:
        {
            "series": [
                {
                    "name": "民間最終消費支出",
                    "code": "12",
                    "data": [{"date": "2024-Q1", "value": 0.5}, ...]
                },
                {
                    "name": "民間企業設備",
                    "code": "16",
                    "data": [{"date": "2024-Q1", "value": 1.2}, ...]
                }
            ],
            "latest": {...},
            "next_release": "2024-01-15T08:50:00+09:00",
            "cached": true/false,
            "source": "redis/e-stat/file",
            "last_updated": "2024-01-01T00:00:00+09:00"
        }
    """
    return gdp_components_service.get_gdp_components_data(force_refresh=force_refresh)


@router.get("/gdp-components/table")
def get_gdp_components_table_data() -> Dict[str, Any]:
    """
    テーブル表示用のGDP構成要素データを取得

    Returns:
        {
            "columns": [
                {"key": "date", "label": "四半期", "type": "string"},
                {"key": "民間最終消費支出", "label": "民間最終消費支出 (%)", "type": "number"},
                {"key": "民間企業設備", "label": "民間企業設備 (%)", "type": "number"}
            ],
            "rows": [
                {"date": "2024-Q3", "民間最終消費支出": 0.5, "民間企業設備": 1.2},
                ...
            ],
            "metadata": {...}
        }
    """
    return gdp_components_service.get_gdp_components_table_data()


@router.get("/gdp-components/cache-status")
def get_cache_status() -> Dict[str, Any]:
    """キャッシュ状態を取得"""
    return gdp_components_service.get_cache_status()
