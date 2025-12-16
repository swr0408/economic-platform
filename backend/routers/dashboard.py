"""
ダッシュボードAPI
国・カテゴリ別のバッチデータ取得エンドポイント

使用例:
    GET /api/usa/policy/dashboard  → 米国金融政策データを一括取得
    GET /api/japan/policy/dashboard → 日本金融政策データを一括取得
"""
import time
from fastapi import APIRouter, Path, HTTPException
from fastapi.responses import JSONResponse
from typing import Literal

try:
    from backend.services.dashboard.registry import (
        get_dashboard_loader,
        get_available_dashboards,
        is_dashboard_available,
        AVAILABLE_COUNTRIES,
        AVAILABLE_CATEGORIES,
    )
except ImportError:
    from services.dashboard.registry import (
        get_dashboard_loader,
        get_available_dashboards,
        is_dashboard_available,
        AVAILABLE_COUNTRIES,
        AVAILABLE_CATEGORIES,
    )

router = APIRouter(prefix="/api", tags=["Dashboard"])

# 型定義（OpenAPI用）
CountryCode = Literal["usa", "japan", "eurozone", "uk", "china", "australia", "newzealand", "canada", "switzerland"]
CategoryCode = Literal["policy", "economy", "consumer", "employment", "inflation", "housing"]


@router.get("/{country}/{category}/dashboard")
async def get_dashboard(
    country: str = Path(..., description="国コード（例: usa, japan）"),
    category: str = Path(..., description="カテゴリコード（例: policy, economy）"),
):
    """
    ダッシュボードデータを一括取得

    ページ読み込み高速化のためのバッチAPI。
    Redis キャッシュ → DB の順でデータを取得し、外部APIは叩かない。

    Args:
        country: 国コード
        category: カテゴリコード

    Returns:
        {
            "data": {
                "policy_rate": [...],
                "term_premium": [...],
                ...
            },
            "cached": bool,
            "last_updated": str,
            "response_time_ms": float
        }

    Raises:
        404: 指定された国・カテゴリのダッシュボードが存在しない
    """
    start_time = time.time()

    # ローダーを取得（存在しない場合は404）
    loader = get_dashboard_loader(country, category)

    # データを取得（非同期）
    result = await loader.get_data_async()

    response_time_ms = (time.time() - start_time) * 1000

    return JSONResponse(
        content={
            "data": result.get("data", {}),
            "cached": result.get("cached", False),
            "last_updated": result.get("last_updated"),
            "response_time_ms": round(response_time_ms, 2),
            "country": country,
            "category": category,
        },
        headers={
            "X-Cache": "HIT" if result.get("cached") else "MISS",
            "X-Response-Time": f"{response_time_ms:.2f}ms",
        }
    )


@router.get("/dashboards/available")
async def get_available_dashboard_list():
    """
    利用可能なダッシュボードの一覧を取得

    Returns:
        {
            "dashboards": [
                {"country": "usa", "category": "policy", ...},
                ...
            ],
            "countries": {...},
            "categories": {...}
        }
    """
    return {
        "dashboards": get_available_dashboards(),
        "countries": AVAILABLE_COUNTRIES,
        "categories": AVAILABLE_CATEGORIES,
    }


@router.get("/{country}/{category}/dashboard/status")
async def get_dashboard_status(
    country: str = Path(..., description="国コード"),
    category: str = Path(..., description="カテゴリコード"),
):
    """
    ダッシュボードキャッシュの状態を取得

    Returns:
        {
            "available": bool,
            "cache_key": str,
            "cached": bool,
            "ttl_seconds": int
        }
    """
    available = is_dashboard_available(country, category)

    if not available:
        return {
            "available": False,
            "country": country,
            "category": category,
            "message": "Dashboard not yet available",
        }

    loader = get_dashboard_loader(country, category)
    cached = loader.get_cached()

    from core.redis_client import redis_client

    return {
        "available": True,
        "country": country,
        "category": category,
        "cache_key": loader.cache_key,
        "cached": cached is not None,
        "ttl_seconds": redis_client.ttl(loader.cache_key) if cached else -1,
        "last_updated": cached.get("last_updated") if cached else None,
    }


@router.post("/{country}/{category}/dashboard/refresh")
async def refresh_dashboard_cache(
    country: str = Path(..., description="国コード"),
    category: str = Path(..., description="カテゴリコード"),
):
    """
    ダッシュボードキャッシュを強制更新

    管理用エンドポイント。通常はCeleryスケジューラーが自動更新する。

    Returns:
        {
            "success": bool,
            "message": str,
            "response_time_ms": float
        }
    """
    start_time = time.time()

    loader = get_dashboard_loader(country, category)

    # キャッシュを無効化
    loader.invalidate_cache()

    # 再取得（これにより新しいデータがキャッシュされる）
    result = await loader.get_data_async()

    response_time_ms = (time.time() - start_time) * 1000

    return {
        "success": True,
        "message": f"Dashboard cache refreshed for {country}/{category}",
        "response_time_ms": round(response_time_ms, 2),
        "data_keys": list(result.get("data", {}).keys()),
    }


@router.delete("/{country}/{category}/dashboard/cache")
async def invalidate_dashboard_cache(
    country: str = Path(..., description="国コード"),
    category: str = Path(..., description="カテゴリコード"),
):
    """
    ダッシュボードキャッシュを削除

    Returns:
        {
            "success": bool,
            "message": str
        }
    """
    loader = get_dashboard_loader(country, category)
    success = loader.invalidate_cache()

    return {
        "success": success,
        "message": f"Cache invalidated for {country}/{category}" if success else "Failed to invalidate cache",
    }
