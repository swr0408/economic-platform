"""
ONS GDP Router
Office for National Statistics イギリス実質GDPデータのAPIエンドポイント

エンドポイント:
- GET /api/uk/ons-gdp: 全データ取得（QoQ、YoY、メタデータ、次回発表日）
- GET /api/uk/ons-gdp/chart: チャート表示用データ（YoY変化率）
- GET /api/uk/ons-gdp/table: テーブル表示用データ（QoQ変化率）
- POST /api/uk/ons-gdp/refresh: キャッシュを強制更新
"""
from fastapi import APIRouter, HTTPException, Response
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/uk/ons-gdp")
def get_ons_gdp(response: Response) -> Dict[str, Any]:
    """
    ONS GDPデータを取得

    Returns:
        Dict containing:
        - qoq: 前期比変化率データ
        - yoy: 前年同期比変化率データ
        - quarterly_data: 四半期GDPデータ
        - metadata: ソース情報
        - next_release: 次回発表日
        - last_updated: 最終更新日時
    """
    try:
        from services.uk.ons_gdp_service import ons_gdp_service
        data = ons_gdp_service.get_ons_gdp_data()

        # キャッシュ制御ヘッダー
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return data

    except Exception as e:
        logger.error(f"Error fetching ONS GDP data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/uk/ons-gdp/chart")
def get_ons_gdp_chart(response: Response) -> Dict[str, Any]:
    """
    ONS GDPチャート表示用データを取得（YoY変化率）

    Returns:
        Dict containing:
        - dates: 日付配列
        - periods: 期間表記配列
        - values: GDP値配列
        - yoy_changes: YoY変化率配列
        - metadata: ソース情報
        - next_release: 次回発表日
    """
    try:
        from services.uk.ons_gdp_service import ons_gdp_service
        data = ons_gdp_service.get_ons_gdp_data()

        if not data or "yoy" not in data:
            raise HTTPException(status_code=500, detail="Failed to fetch ONS GDP chart data")

        yoy_data = data.get("yoy", [])

        chart_data = {
            "dates": [point["date"] for point in yoy_data],
            "periods": [point["period"] for point in yoy_data],
            "values": [point["value"] for point in yoy_data],
            "yoy_changes": [point["yoy_change"] for point in yoy_data],
            "metadata": data.get("metadata", {}),
            "next_release": data.get("next_release"),
            "last_updated": data.get("last_updated", ""),
            "source": data.get("metadata", {}).get("source", "Office for National Statistics"),
        }

        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return chart_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ONS GDP chart endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/uk/ons-gdp/table")
def get_ons_gdp_table(response: Response) -> Dict[str, Any]:
    """
    ONS GDPテーブル表示用データを取得（QoQ変化率）

    Returns:
        Dict containing:
        - data: QoQ変化率データ（降順）
        - metadata: ソース情報
        - next_release: 次回発表日
    """
    try:
        from services.uk.ons_gdp_service import ons_gdp_service
        data = ons_gdp_service.get_ons_gdp_data()

        if not data or "qoq" not in data:
            raise HTTPException(status_code=500, detail="Failed to fetch ONS GDP table data")

        qoq_data = data.get("qoq", [])

        # 日付降順でソート（最新のデータを先頭に）
        table_data = sorted(qoq_data, key=lambda x: x["date"], reverse=True)

        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return {
            "data": table_data,
            "metadata": data.get("metadata", {}),
            "next_release": data.get("next_release"),
            "last_updated": data.get("last_updated", ""),
            "source": data.get("metadata", {}).get("source", "Office for National Statistics"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ONS GDP table endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/uk/ons-gdp/refresh")
def refresh_ons_gdp() -> Dict[str, Any]:
    """
    ONS GDPデータを強制更新

    Returns:
        Dict containing status and last_updated
    """
    try:
        from services.uk.ons_gdp_service import ons_gdp_service
        data = ons_gdp_service.get_ons_gdp_data(force_refresh=True)

        if not data:
            raise HTTPException(status_code=500, detail="Failed to refresh ONS GDP data")

        return {
            "status": "success",
            "message": "ONS GDP data refreshed",
            "last_updated": data.get("last_updated", ""),
            "qoq_count": len(data.get("qoq", [])),
            "yoy_count": len(data.get("yoy", [])),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ONS GDP refresh endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/uk/ons-gdp/cache-status")
def get_ons_gdp_cache_status() -> Dict[str, Any]:
    """
    ONS GDPキャッシュ状態を取得

    Returns:
        Dict containing cache status information
    """
    try:
        from services.uk.ons_gdp_service import ons_gdp_service
        return ons_gdp_service.get_cache_status()

    except Exception as e:
        logger.error(f"Error getting ONS GDP cache status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
