"""
設備投資 API Router

エンドポイント:
- GET /api/japan/capital-investment - 設備投資データ取得（生データ、単位: 百万円）
- GET /api/japan/capital-investment/yoy - 設備投資データ取得（前年比、単位: %）
- GET /api/japan/capital-investment/cache-status - キャッシュステータス取得
- POST /api/japan/capital-investment/refresh - データ強制更新
- DELETE /api/japan/capital-investment/cache - キャッシュ削除
"""

from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.japan.capital_investment_service import capital_investment_service
except ImportError:
    from services.japan.capital_investment_service import capital_investment_service

router = APIRouter(prefix="/api/japan/capital-investment", tags=["Japan - Capital Investment"])


@router.get("")
def get_capital_investment_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """
    設備投資データを取得（生データ）

    Args:
        force_refresh: キャッシュを無視して強制更新

    Returns:
        設備投資データ（四半期、単位: 百万円）
    """
    try:
        result = capital_investment_service.get_capital_investment_data(force_refresh=force_refresh)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/yoy")
def get_capital_investment_yoy_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """
    設備投資データを取得（前年比）

    Args:
        force_refresh: キャッシュを無視して強制更新

    Returns:
        設備投資データ（四半期、前年比 %）
    """
    try:
        result = capital_investment_service.get_yoy_data(force_refresh=force_refresh)
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
        return capital_investment_service.get_cache_status()
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
        result = capital_investment_service.get_capital_investment_data(force_refresh=True)
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
        success = capital_investment_service.invalidate_cache()
        return {
            "status": "success" if success else "no_cache",
            "message": "Cache invalidated" if success else "No cache to invalidate"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
