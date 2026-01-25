"""
SONIA（Sterling Overnight Index Average）ルーター
SONIAデータエンドポイント
"""
from fastapi import APIRouter, Query

from services.uk.sonia_service import sonia_service

router = APIRouter(
    prefix="/api/uk",
    tags=["uk", "monetary_policy"]
)


@router.get("/sonia")
async def get_sonia(force_refresh: bool = Query(False, description="強制更新フラグ")):
    """
    SONIAデータを取得

    Returns:
        SONIAデータ（日次オーバーナイト金利）
    """
    return sonia_service.get_sonia_data(force_refresh=force_refresh)


@router.post("/sonia/refresh")
async def refresh_sonia():
    """
    SONIAデータを強制更新

    Returns:
        更新されたSONIAデータ
    """
    return sonia_service.get_sonia_data(force_refresh=True)


@router.get("/sonia/cache-status")
async def get_cache_status():
    """
    キャッシュ状態を取得

    Returns:
        キャッシュ状態情報
    """
    return sonia_service.get_cache_status()


@router.delete("/sonia/cache")
async def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    result = sonia_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated" if result else "Cache not found"}
