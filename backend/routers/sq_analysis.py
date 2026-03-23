"""SQ/MSQ 検証分析 API"""
from fastapi import APIRouter, Query

try:
    from services.market.sq_analysis_service import SqAnalysisService
except ImportError:
    from backend.services.market.sq_analysis_service import SqAnalysisService

router = APIRouter(prefix="/api/market", tags=["market"])

_service = SqAnalysisService()


@router.get("/sq-analysis")
async def get_sq_analysis(force_refresh: bool = Query(False)):
    """SQ/MSQ騰落率分析データを取得"""
    return _service.get_data(force_refresh=force_refresh)
