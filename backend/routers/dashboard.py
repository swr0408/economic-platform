"""
ダッシュボードAPI
国・カテゴリ別のバッチデータ取得エンドポイント

使用例:
    GET /api/usa/policy/dashboard  → 米国金融政策データを一括取得
    GET /api/japan/policy/dashboard → 日本金融政策データを一括取得
"""
import asyncio
import logging
import time
from fastapi import APIRouter, Depends, Path, HTTPException
from fastapi.responses import JSONResponse
from typing import Literal

logger = logging.getLogger(__name__)

try:
    from backend.services.dashboard.registry import (
        get_dashboard_loader,
        get_available_dashboards,
        is_dashboard_available,
        AVAILABLE_COUNTRIES,
        AVAILABLE_CATEGORIES,
    )
    from backend.core.auth.dependencies import require_role
    from backend.core.auth.models import ROLE_MASTER
except ImportError:
    from services.dashboard.registry import (
        get_dashboard_loader,
        get_available_dashboards,
        is_dashboard_available,
        AVAILABLE_COUNTRIES,
        AVAILABLE_CATEGORIES,
    )
    from core.auth.dependencies import require_role
    from core.auth.models import ROLE_MASTER

# master ロール要求の依存オブジェクト (ファクトリを一度呼んで使い回す)
_require_master = require_role(ROLE_MASTER)

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

    30秒タイムアウト: 超過時はキャッシュデータで応答。

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
    DASHBOARD_TIMEOUT_SECONDS = 30

    start_time = time.time()

    # ローダーを取得（存在しない場合は404）
    loader = get_dashboard_loader(country, category)

    try:
        # データを取得（非同期 + タイムアウト）
        # 注: run_in_executor 内のスレッドはタイムアウト後も走り続け、
        # 結果は Redis キャッシュに書かれる（次回アクセスで反映される）
        result = await asyncio.wait_for(
            loader.get_data_async(),
            timeout=DASHBOARD_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        response_time_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"Dashboard timeout ({DASHBOARD_TIMEOUT_SECONDS}s) for {country}/{category}, "
            f"falling back to cache"
        )

        cached = loader.get_cached()
        if cached:
            return JSONResponse(
                content={
                    "data": cached.get("data", {}),
                    "cached": True,
                    "last_updated": cached.get("last_updated"),
                    "response_time_ms": round(response_time_ms, 2),
                    "country": country,
                    "category": category,
                    "timeout_fallback": True,
                },
                headers={
                    "X-Cache": "TIMEOUT-FALLBACK",
                    "X-Response-Time": f"{response_time_ms:.2f}ms",
                }
            )

        return JSONResponse(
            content={
                "data": {},
                "cached": False,
                "last_updated": None,
                "response_time_ms": round(response_time_ms, 2),
                "country": country,
                "category": category,
                "timeout_fallback": True,
            },
            headers={
                "X-Cache": "TIMEOUT-EMPTY",
                "X-Response-Time": f"{response_time_ms:.2f}ms",
            }
        )

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


@router.get("/{country}/{category}/dashboard/light")
async def get_dashboard_light(
    country: str = Path(..., description="国コード（例: usa, japan）"),
    category: str = Path(..., description="カテゴリコード（例: policy, economy）"),
):
    """
    軽量指標のみを取得（プログレッシブレンダリング用）

    重い指標（スクリーンショット取得、PDF解析等）を除外し、
    高速にレスポンスを返す。フロントエンドで先に表示するデータ用。

    Returns:
        {
            "data": {...},  # 軽量指標のみ
            "cached": bool,
            "last_updated": str,
            "partial": true,
            "response_time_ms": float
        }
    """
    LIGHT_TIMEOUT_SECONDS = 15

    start_time = time.time()

    loader = get_dashboard_loader(country, category)

    try:
        result = await asyncio.wait_for(
            loader.get_data_light_async(),
            timeout=LIGHT_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        response_time_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"Light dashboard timeout ({LIGHT_TIMEOUT_SECONDS}s) for {country}/{category}, "
            f"falling back to cache"
        )

        cached = loader.get_cached()
        if cached:
            return JSONResponse(
                content={
                    "data": cached.get("data", {}),
                    "cached": True,
                    "last_updated": cached.get("last_updated"),
                    "partial": True,
                    "response_time_ms": round(response_time_ms, 2),
                    "country": country,
                    "category": category,
                    "timeout_fallback": True,
                },
                headers={
                    "X-Cache": "TIMEOUT-FALLBACK",
                    "X-Response-Time": f"{response_time_ms:.2f}ms",
                    "X-Partial": "true",
                }
            )

        return JSONResponse(
            content={
                "data": {},
                "cached": False,
                "last_updated": None,
                "partial": True,
                "response_time_ms": round(response_time_ms, 2),
                "country": country,
                "category": category,
                "timeout_fallback": True,
            },
            headers={
                "X-Cache": "TIMEOUT-EMPTY",
                "X-Response-Time": f"{response_time_ms:.2f}ms",
                "X-Partial": "true",
            }
        )

    response_time_ms = (time.time() - start_time) * 1000

    return JSONResponse(
        content={
            "data": result.get("data", {}),
            "cached": result.get("cached", False),
            "last_updated": result.get("last_updated"),
            "partial": True,
            "response_time_ms": round(response_time_ms, 2),
            "country": country,
            "category": category,
        },
        headers={
            "X-Cache": "HIT" if result.get("cached") else "MISS",
            "X-Response-Time": f"{response_time_ms:.2f}ms",
            "X-Partial": "true",
        }
    )


@router.get("/{country}/{category}/dashboard/heavy")
async def get_dashboard_heavy(
    country: str = Path(..., description="国コード（例: usa, japan）"),
    category: str = Path(..., description="カテゴリコード（例: policy, economy）"),
):
    """
    重い指標のみを取得（プログレッシブレンダリング用）

    スクリーンショット取得、PDF解析等の重い処理を含む指標のみを取得。
    フロントエンドで遅延ロードするデータ用。

    45秒タイムアウト: 超過時はキャッシュデータで応答。
    キャッシュもなければ空データを返す（画面が固まるのを防ぐ）。

    Returns:
        {
            "data": {...},  # 重い指標のみ
            "cached": bool,
            "last_updated": str,
            "partial": true,
            "response_time_ms": float
        }
    """
    HEAVY_TIMEOUT_SECONDS = 45

    start_time = time.time()

    loader = get_dashboard_loader(country, category)

    try:
        result = await asyncio.wait_for(
            loader.get_data_heavy_async(),
            timeout=HEAVY_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        response_time_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"Heavy dashboard timeout ({HEAVY_TIMEOUT_SECONDS}s) for {country}/{category}, "
            f"falling back to cache"
        )

        # タイムアウト → キャッシュがあればそれを返す
        cached = loader.get_cached()
        if cached:
            return JSONResponse(
                content={
                    "data": cached.get("data", {}),
                    "cached": True,
                    "last_updated": cached.get("last_updated"),
                    "partial": True,
                    "response_time_ms": round(response_time_ms, 2),
                    "country": country,
                    "category": category,
                    "timeout_fallback": True,
                },
                headers={
                    "X-Cache": "TIMEOUT-FALLBACK",
                    "X-Response-Time": f"{response_time_ms:.2f}ms",
                    "X-Partial": "true",
                }
            )

        # キャッシュもない → 空データを返す（画面が止まるよりマシ）
        return JSONResponse(
            content={
                "data": {},
                "cached": False,
                "last_updated": None,
                "partial": True,
                "response_time_ms": round(response_time_ms, 2),
                "country": country,
                "category": category,
                "timeout_fallback": True,
            },
            headers={
                "X-Cache": "TIMEOUT-EMPTY",
                "X-Response-Time": f"{response_time_ms:.2f}ms",
                "X-Partial": "true",
            }
        )

    response_time_ms = (time.time() - start_time) * 1000

    return JSONResponse(
        content={
            "data": result.get("data", {}),
            "cached": result.get("cached", False),
            "last_updated": result.get("last_updated"),
            "partial": True,
            "response_time_ms": round(response_time_ms, 2),
            "country": country,
            "category": category,
        },
        headers={
            "X-Cache": "HIT" if result.get("cached") else "MISS",
            "X-Response-Time": f"{response_time_ms:.2f}ms",
            "X-Partial": "true",
        }
    )


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
    _master = Depends(_require_master),
):
    """
    ダッシュボードキャッシュを強制更新 (master 限定)

    管理用エンドポイント。発表日時ベースの自動判定により通常は手動更新不要。

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
    _master = Depends(_require_master),
):
    """
    ダッシュボードキャッシュを削除 (master 限定)

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
