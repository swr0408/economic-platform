"""
ONS GVA（月間GDP）Router
Office for National Statistics GVAデータのAPIエンドポイント

エンドポイント:
- GET /api/uk/ons-gva: 全データ取得（ED3H、ECY2、メタデータ、次回発表日）
- GET /api/uk/ons-gva/ed3h-table: ED3Hテーブル表示用データ（3m on 3m）
- GET /api/uk/ons-gva/ecy2-chart: ECY2チャート表示用データ（YoY変化率）
- GET /api/uk/ons-gva/ecy2-table: ECY2テーブル表示用データ（MoM変化率）
- POST /api/uk/ons-gva/refresh: キャッシュを強制更新
"""
from fastapi import APIRouter, HTTPException, Response
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/uk/ons-gva")
def get_ons_gva(response: Response) -> Dict[str, Any]:
    """
    ONS GVA（月間GDP）データを取得

    Returns:
        Dict containing:
        - ed3h: ED3H（3m on 3m成長率）データ
        - ecy2: ECY2（月次指数）データ（YoY、MoM含む）
        - metadata: ソース情報
        - next_release: 次回発表日
        - last_updated: 最終更新日時
    """
    try:
        from services.uk.ons_gva_service import ons_gva_service
        data = ons_gva_service.get_ons_gva_data()

        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return data

    except Exception as e:
        logger.error(f"Error fetching ONS GVA data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/uk/ons-gva/ed3h")
def get_ons_gva_ed3h(response: Response) -> Dict[str, Any]:
    """
    ONS GVA ED3Hデータを取得（データ比較機能用、3m on 3m成長率）

    Returns:
        Dict containing:
        - data: ED3Hデータ（昇順）
        - metadata: ソース情報
        - next_release: 次回発表日
    """
    try:
        from services.uk.ons_gva_service import ons_gva_service
        data = ons_gva_service.get_ons_gva_data()

        if not data or "ed3h" not in data or not data["ed3h"]:
            raise HTTPException(status_code=500, detail="Failed to fetch ONS GVA ED3H data")

        ed3h_data = data.get("ed3h", {}).get("data", [])

        # 日付昇順でソート
        sorted_data = sorted(ed3h_data, key=lambda x: x["date"])

        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return {
            "data": sorted_data,
            "metadata": data.get("ed3h", {}).get("metadata", {}),
            "next_release": data.get("next_release"),
            "last_updated": data.get("last_updated", ""),
            "source": "Office for National Statistics",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ONS GVA ED3H endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/uk/ons-gva/ed3h-table")
def get_ons_gva_ed3h_table(response: Response) -> Dict[str, Any]:
    """
    ONS GVA ED3Hテーブル表示用データを取得（3m on 3m成長率）

    Returns:
        Dict containing:
        - data: ED3Hデータ（降順）
        - metadata: ソース情報
        - next_release: 次回発表日
    """
    try:
        from services.uk.ons_gva_service import ons_gva_service
        data = ons_gva_service.get_ons_gva_data()

        if not data or "ed3h" not in data or not data["ed3h"]:
            raise HTTPException(status_code=500, detail="Failed to fetch ONS GVA ED3H data")

        ed3h_data = data.get("ed3h", {}).get("data", [])

        # 日付降順でソート
        table_data = sorted(ed3h_data, key=lambda x: x["date"], reverse=True)

        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return {
            "data": table_data,
            "metadata": data.get("ed3h", {}).get("metadata", {}),
            "next_release": data.get("next_release"),
            "last_updated": data.get("last_updated", ""),
            "source": "Office for National Statistics",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ONS GVA ED3H table endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/uk/ons-gva/ecy2-3m-yoy")
def get_ons_gva_ecy2_3m_yoy(response: Response) -> Dict[str, Any]:
    """
    ONS GVA 3か月前年比データを取得（ECY2インデックスの3か月移動平均YoY）

    Returns:
        Dict containing:
        - data: 3か月移動平均のYoY変化率データ（昇順）
        - metadata: ソース情報
        - next_release: 次回発表日
    """
    try:
        from services.uk.ons_gva_service import ons_gva_service
        data = ons_gva_service.get_ons_gva_data()

        if not data or "ecy2" not in data or not data["ecy2"]:
            raise HTTPException(status_code=500, detail="Failed to fetch ONS GVA ECY2 data")

        yoy_3m_data = data.get("ecy2", {}).get("3m_yoy", [])

        # 日付昇順でソート
        sorted_data = sorted(yoy_3m_data, key=lambda x: x["date"])

        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return {
            "data": sorted_data,
            "metadata": data.get("ecy2", {}).get("metadata", {}),
            "next_release": data.get("next_release"),
            "last_updated": data.get("last_updated", ""),
            "source": "Office for National Statistics",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ONS GVA ECY2 3M YoY endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/uk/ons-gva/ecy2-chart")
def get_ons_gva_ecy2_chart(response: Response) -> Dict[str, Any]:
    """
    ONS GVA ECY2チャート表示用データを取得（YoY変化率）

    Returns:
        Dict containing:
        - dates: 日付配列
        - periods: 期間表記配列
        - values: 指数値配列
        - yoy_changes: YoY変化率配列
        - metadata: ソース情報
        - next_release: 次回発表日
    """
    try:
        from services.uk.ons_gva_service import ons_gva_service
        data = ons_gva_service.get_ons_gva_data()

        if not data or "ecy2" not in data or not data["ecy2"]:
            raise HTTPException(status_code=500, detail="Failed to fetch ONS GVA ECY2 data")

        yoy_data = data.get("ecy2", {}).get("yoy", [])

        chart_data = {
            "dates": [point["date"] for point in yoy_data],
            "periods": [point["period"] for point in yoy_data],
            "values": [point["value"] for point in yoy_data],
            "yoy_changes": [point["yoy_change"] for point in yoy_data],
            "metadata": data.get("ecy2", {}).get("metadata", {}),
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
        logger.error(f"Error in ONS GVA ECY2 chart endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/uk/ons-gva/ecy2-yoy")
def get_ons_gva_ecy2_yoy(response: Response) -> Dict[str, Any]:
    """
    ONS GVA ECY2 YoYデータを取得（データ比較機能用）

    Returns:
        Dict containing:
        - data: YoY変化率データ（オブジェクト配列）
        - metadata: ソース情報
        - next_release: 次回発表日
    """
    try:
        from services.uk.ons_gva_service import ons_gva_service
        data = ons_gva_service.get_ons_gva_data()

        if not data or "ecy2" not in data or not data["ecy2"]:
            raise HTTPException(status_code=500, detail="Failed to fetch ONS GVA ECY2 data")

        yoy_data = data.get("ecy2", {}).get("yoy", [])

        # 日付昇順でソート
        sorted_data = sorted(yoy_data, key=lambda x: x["date"])

        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return {
            "data": sorted_data,
            "metadata": data.get("ecy2", {}).get("metadata", {}),
            "next_release": data.get("next_release"),
            "last_updated": data.get("last_updated", ""),
            "source": "Office for National Statistics",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ONS GVA ECY2 YoY endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/uk/ons-gva/ecy2-table")
def get_ons_gva_ecy2_table(response: Response) -> Dict[str, Any]:
    """
    ONS GVA ECY2テーブル表示用データを取得（MoM変化率）

    Returns:
        Dict containing:
        - data: MoM変化率データ（降順）
        - metadata: ソース情報
        - next_release: 次回発表日
    """
    try:
        from services.uk.ons_gva_service import ons_gva_service
        data = ons_gva_service.get_ons_gva_data()

        if not data or "ecy2" not in data or not data["ecy2"]:
            raise HTTPException(status_code=500, detail="Failed to fetch ONS GVA ECY2 data")

        mom_data = data.get("ecy2", {}).get("mom", [])

        # 日付降順でソート
        table_data = sorted(mom_data, key=lambda x: x["date"], reverse=True)

        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return {
            "data": table_data,
            "metadata": data.get("ecy2", {}).get("metadata", {}),
            "next_release": data.get("next_release"),
            "last_updated": data.get("last_updated", ""),
            "source": "Office for National Statistics",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ONS GVA ECY2 table endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/uk/ons-gva/refresh")
def refresh_ons_gva() -> Dict[str, Any]:
    """
    ONS GVAデータを強制更新

    Returns:
        Dict containing status and last_updated
    """
    try:
        from services.uk.ons_gva_service import ons_gva_service
        data = ons_gva_service.get_ons_gva_data(force_refresh=True)

        if not data:
            raise HTTPException(status_code=500, detail="Failed to refresh ONS GVA data")

        return {
            "status": "success",
            "message": "ONS GVA data refreshed",
            "last_updated": data.get("last_updated", ""),
            "ed3h_count": len(data.get("ed3h", {}).get("data", [])),
            "ecy2_count": len(data.get("ecy2", {}).get("data", [])),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ONS GVA refresh endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/uk/ons-gva/cache-status")
def get_ons_gva_cache_status() -> Dict[str, Any]:
    """
    ONS GVAキャッシュ状態を取得

    Returns:
        Dict containing cache status information
    """
    try:
        from services.uk.ons_gva_service import ons_gva_service
        return ons_gva_service.get_cache_status()

    except Exception as e:
        logger.error(f"Error getting ONS GVA cache status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
