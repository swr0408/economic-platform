"""
UK QT（量的引締め）ルーター
APFギルト保有残高データエンドポイント
"""
from fastapi import APIRouter, Query

from services.uk.uk_qt_service import uk_qt_service

router = APIRouter(
    prefix="/api/uk",
    tags=["uk", "monetary_policy"]
)


@router.get("/uk-qt")
def get_uk_qt(force_refresh: bool = Query(False, description="強制更新フラグ")):
    """
    UK QT（APFギルト保有残高）データを取得

    Returns:
        APFギルト保有残高データ（週次、GBP billions）
    """
    return uk_qt_service.get_data(force_refresh=force_refresh)


@router.post("/uk-qt/refresh")
def refresh_uk_qt():
    """
    UK QTデータを強制更新

    Returns:
        更新されたUK QTデータ
    """
    return uk_qt_service.get_data(force_refresh=True)


@router.get("/uk-qt/cache-status")
def get_cache_status():
    """
    キャッシュ状態を取得

    Returns:
        キャッシュ状態情報
    """
    return uk_qt_service.get_cache_status()


@router.delete("/uk-qt/cache")
def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    result = uk_qt_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated" if result else "Cache not found"}
