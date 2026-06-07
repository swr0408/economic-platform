"""
スイス連邦統計局（FSO/BFS）関連 APIルーター

提供データ:
- CPI (Consumer Price Index / Landesindex der Konsumentenpreise)
- PPI (Producer and Import Price Index / Produzenten- und Importpreisindex)
"""
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(
    prefix="/api/switzerland/fso",
    tags=["switzerland", "inflation"]
)


@router.get("/")
def fso_root():
    """FSO APIルート"""
    return {
        "message": "Swiss Federal Statistical Office (FSO/BFS) API",
        "status": "Active",
        "available_endpoints": [
            "/cpi - Consumer Price Index",
            "/ppi - Producer and Import Price Index"
        ]
    }


@router.get("/cpi")
def get_ch_cpi(
    force_refresh: bool = Query(False, description="強制的にキャッシュを更新")
):
    """
    スイスCPIデータを取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...}
        }
    """
    from services.switzerland.ch_cpi_service import ch_cpi_service

    return ch_cpi_service.get_ch_cpi_data(force_refresh=force_refresh)


@router.get("/cpi/latest")
def get_ch_cpi_latest():
    """
    スイスCPI最新データを取得

    Returns:
        最新のCPIデータ
    """
    from services.switzerland.ch_cpi_service import ch_cpi_service

    result = ch_cpi_service.get_ch_cpi_data()
    return {
        "latest": result.get("latest"),
        "next_release": result.get("next_release"),
    }


@router.get("/cpi/cache/status")
def get_ch_cpi_cache_status():
    """CPI キャッシュ状態を取得"""
    from services.switzerland.ch_cpi_service import ch_cpi_service

    return ch_cpi_service.get_cache_status()


@router.delete("/cpi/cache")
def invalidate_ch_cpi_cache():
    """CPI キャッシュを無効化"""
    from services.switzerland.ch_cpi_service import ch_cpi_service

    success = ch_cpi_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }


# =========================================================================
# PPI エンドポイント
# =========================================================================

@router.get("/ppi")
def get_ch_ppi(
    force_refresh: bool = Query(False, description="強制的にキャッシュを更新")
):
    """
    スイスPPI（生産者・輸入物価指数）データを取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...}
        }
    """
    from services.switzerland.ch_ppi_service import ch_ppi_service

    return ch_ppi_service.get_ch_ppi_data(force_refresh=force_refresh)


@router.get("/ppi/latest")
def get_ch_ppi_latest():
    """
    スイスPPI最新データを取得

    Returns:
        最新のPPIデータ
    """
    from services.switzerland.ch_ppi_service import ch_ppi_service

    result = ch_ppi_service.get_ch_ppi_data()
    return {
        "latest": result.get("latest"),
        "next_release": result.get("next_release"),
    }


@router.get("/ppi/cache/status")
def get_ch_ppi_cache_status():
    """PPI キャッシュ状態を取得"""
    from services.switzerland.ch_ppi_service import ch_ppi_service

    return ch_ppi_service.get_cache_status()


@router.delete("/ppi/cache")
def invalidate_ch_ppi_cache():
    """PPI キャッシュを無効化"""
    from services.switzerland.ch_ppi_service import ch_ppi_service

    success = ch_ppi_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }
