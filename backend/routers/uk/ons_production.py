"""
ONS Production Industries（鉱工業生産）Router
Office for National Statistics鉱工業生産データのAPIエンドポイント

エンドポイント:
- GET /api/uk/ons-production: 全データ取得（ED2T、ECYZ、メタデータ、次回発表日）
- GET /api/uk/ons-production/ed2t: ED2Tデータ（YoY、データ比較機能用）
- GET /api/uk/ons-production/ed2t-chart: ED2Tチャート表示用データ（YoY変化率）
- GET /api/uk/ons-production/ecyz: ECYZデータ（MoM、データ比較機能用）
- GET /api/uk/ons-production/ecyz-table: ECYZテーブル表示用データ（MoM変化率）
- POST /api/uk/ons-production/refresh: キャッシュを強制更新
"""
from fastapi import APIRouter, HTTPException, Response
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/uk/ons-production")
async def get_ons_production(response: Response) -> Dict[str, Any]:
    """
    ONS Production Industries（鉱工業生産）データを取得

    Returns:
        Dict containing:
        - ed2t: ED2T（YoY成長率）データ
        - ecyz: ECYZ（MoM成長率）データ
        - metadata: ソース情報
        - next_release: 次回発表日
        - last_updated: 最終更新日時
    """
    try:
        from services.uk.ons_production_service import ons_production_service
        data = ons_production_service.get_ons_production_data()

        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return data

    except Exception as e:
        logger.error(f"Error fetching ONS Production data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/uk/ons-production/ed2t")
async def get_ons_production_ed2t(response: Response) -> Dict[str, Any]:
    """
    ONS Production ED2Tデータを取得（データ比較機能用、YoY成長率）

    Returns:
        Dict containing:
        - data: ED2Tデータ（昇順）
        - metadata: ソース情報
        - next_release: 次回発表日
    """
    try:
        from services.uk.ons_production_service import ons_production_service
        data = ons_production_service.get_ons_production_data()

        if not data or "ed2t" not in data or not data["ed2t"]:
            raise HTTPException(status_code=500, detail="Failed to fetch ONS Production ED2T data")

        ed2t_data = data.get("ed2t", {}).get("data", [])

        # 日付昇順でソート
        sorted_data = sorted(ed2t_data, key=lambda x: x["date"])

        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return {
            "data": sorted_data,
            "metadata": data.get("ed2t", {}).get("metadata", {}),
            "next_release": data.get("next_release"),
            "last_updated": data.get("last_updated", ""),
            "source": "Office for National Statistics",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ONS Production ED2T endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/uk/ons-production/ed2t-chart")
async def get_ons_production_ed2t_chart(response: Response) -> Dict[str, Any]:
    """
    ONS Production ED2Tチャート表示用データを取得（YoY変化率）

    Returns:
        Dict containing:
        - dates: 日付配列
        - periods: 期間表記配列
        - values: YoY変化率配列
        - metadata: ソース情報
        - next_release: 次回発表日
    """
    try:
        from services.uk.ons_production_service import ons_production_service
        data = ons_production_service.get_ons_production_data()

        if not data or "ed2t" not in data or not data["ed2t"]:
            raise HTTPException(status_code=500, detail="Failed to fetch ONS Production ED2T data")

        ed2t_data = data.get("ed2t", {}).get("data", [])

        # 日付昇順でソート
        sorted_data = sorted(ed2t_data, key=lambda x: x["date"])

        chart_data = {
            "dates": [point["date"] for point in sorted_data],
            "periods": [point["period"] for point in sorted_data],
            "values": [point["value"] for point in sorted_data],
            "metadata": data.get("ed2t", {}).get("metadata", {}),
            "next_release": data.get("next_release"),
            "last_updated": data.get("last_updated", ""),
            "source": "Office for National Statistics",
        }

        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return chart_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ONS Production ED2T chart endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/uk/ons-production/ecyz")
async def get_ons_production_ecyz(response: Response) -> Dict[str, Any]:
    """
    ONS Production ECYZデータを取得（データ比較機能用、MoM成長率）

    Returns:
        Dict containing:
        - data: ECYZデータ（昇順）
        - metadata: ソース情報
        - next_release: 次回発表日
    """
    try:
        from services.uk.ons_production_service import ons_production_service
        data = ons_production_service.get_ons_production_data()

        if not data or "ecyz" not in data or not data["ecyz"]:
            raise HTTPException(status_code=500, detail="Failed to fetch ONS Production ECYZ data")

        ecyz_data = data.get("ecyz", {}).get("data", [])

        # 日付昇順でソート
        sorted_data = sorted(ecyz_data, key=lambda x: x["date"])

        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return {
            "data": sorted_data,
            "metadata": data.get("ecyz", {}).get("metadata", {}),
            "next_release": data.get("next_release"),
            "last_updated": data.get("last_updated", ""),
            "source": "Office for National Statistics",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ONS Production ECYZ endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/uk/ons-production/ecyz-table")
async def get_ons_production_ecyz_table(response: Response) -> Dict[str, Any]:
    """
    ONS Production ECYZテーブル表示用データを取得（MoM変化率）

    Returns:
        Dict containing:
        - data: MoM変化率データ（降順）
        - metadata: ソース情報
        - next_release: 次回発表日
    """
    try:
        from services.uk.ons_production_service import ons_production_service
        data = ons_production_service.get_ons_production_data()

        if not data or "ecyz" not in data or not data["ecyz"]:
            raise HTTPException(status_code=500, detail="Failed to fetch ONS Production ECYZ data")

        ecyz_data = data.get("ecyz", {}).get("data", [])

        # 日付降順でソート
        table_data = sorted(ecyz_data, key=lambda x: x["date"], reverse=True)

        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return {
            "data": table_data,
            "metadata": data.get("ecyz", {}).get("metadata", {}),
            "next_release": data.get("next_release"),
            "last_updated": data.get("last_updated", ""),
            "source": "Office for National Statistics",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ONS Production ECYZ table endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/uk/ons-production/refresh")
async def refresh_ons_production() -> Dict[str, Any]:
    """
    ONS Production Industriesデータを強制更新

    Returns:
        Dict containing status and last_updated
    """
    try:
        from services.uk.ons_production_service import ons_production_service
        data = ons_production_service.get_ons_production_data(force_refresh=True)

        if not data:
            raise HTTPException(status_code=500, detail="Failed to refresh ONS Production data")

        return {
            "status": "success",
            "message": "ONS Production data refreshed",
            "last_updated": data.get("last_updated", ""),
            "ed2t_count": len(data.get("ed2t", {}).get("data", [])),
            "ecyz_count": len(data.get("ecyz", {}).get("data", [])),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ONS Production refresh endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/uk/ons-production/cache-status")
async def get_ons_production_cache_status() -> Dict[str, Any]:
    """
    ONS Productionキャッシュ状態を取得

    Returns:
        Dict containing cache status information
    """
    try:
        from services.uk.ons_production_service import ons_production_service
        return ons_production_service.get_cache_status()

    except Exception as e:
        logger.error(f"Error getting ONS Production cache status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
