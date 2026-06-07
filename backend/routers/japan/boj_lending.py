"""
日銀貸出動向 API Router

エンドポイント:
- GET /api/japan/boj-lending - 貸出動向データ取得（生データ、単位: 億円）
- GET /api/japan/boj-lending/yoy - 貸出動向データ取得（前年比、単位: %）
- GET /api/japan/boj-lending/cache-status - キャッシュステータス取得
- POST /api/japan/boj-lending/refresh - データ強制更新
- DELETE /api/japan/boj-lending/cache - キャッシュ削除
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

try:
    from backend.services.japan.boj_lending_service import boj_lending_service
except ImportError:
    from services.japan.boj_lending_service import boj_lending_service

router = APIRouter(prefix="/api/japan/boj-lending", tags=["Japan - BOJ Lending"])


@router.get("")
def get_boj_lending_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """
    日銀貸出動向データを取得（生データ）

    Args:
        force_refresh: キャッシュを無視して強制更新

    Returns:
        貸出動向データ（月次、単位: 億円）
    """
    try:
        result = boj_lending_service.get_boj_lending_data(force_refresh=force_refresh)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/yoy")
def get_boj_lending_yoy_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """
    日銀貸出動向データを取得（前年比）

    Args:
        force_refresh: キャッシュを無視して強制更新

    Returns:
        貸出動向データ（月次、前年比 %）
    """
    try:
        result = boj_lending_service.get_boj_lending_yoy_data(force_refresh=force_refresh)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache-status")
def get_cache_status():
    """
    キャッシュステータスを取得

    Returns:
        キャッシュの状態情報
    """
    try:
        return boj_lending_service.get_cache_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
def refresh_data():
    """
    データを強制更新

    Returns:
        更新後のデータ
    """
    try:
        result = boj_lending_service.get_boj_lending_data(force_refresh=True)
        return {
            "status": "refreshed",
            "data_count": len(result.get("data", [])),
            "latest": result.get("latest"),
            "last_updated": result.get("last_updated")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache")
def invalidate_cache():
    """
    キャッシュを削除

    Returns:
        削除結果
    """
    try:
        success = boj_lending_service.invalidate_cache()
        return {
            "status": "success" if success else "no_cache",
            "message": "Cache invalidated" if success else "No cache to invalidate"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
