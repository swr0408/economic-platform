"""
BOE DMP Survey (意思決定者パネル調査) ルーター
BOE DMPサーベイエンドポイント
"""
from fastapi import APIRouter, Query

from services.uk.boe_dmp_survey_service import boe_dmp_survey_service

router = APIRouter(
    prefix="/api/uk",
    tags=["uk", "dmp_survey"]
)


@router.get("/boe-dmp-survey")
def get_boe_dmp_survey(force_refresh: bool = Query(False, description="強制更新フラグ")):
    """
    BOE DMP Survey（意思決定者パネル調査）データを取得

    Returns:
        DMPサーベイデータ（CPIインフレ期待、価格成長、賃金成長、雇用成長）
    """
    return boe_dmp_survey_service.fetch_data(force_refresh=force_refresh)


@router.post("/boe-dmp-survey/refresh")
def refresh_boe_dmp_survey():
    """
    BOE DMP Surveyデータを強制更新

    Returns:
        更新されたDMPサーベイデータ
    """
    return boe_dmp_survey_service.fetch_data(force_refresh=True)


@router.delete("/boe-dmp-survey/cache")
def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    result = boe_dmp_survey_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated" if result else "Cache not found"}
