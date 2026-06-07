"""
BOE MPC Voting API Router
BOE金融政策委員会メンバー投票履歴

エンドポイント:
    GET /api/uk/boe-mpc-voting          - MPC投票データ
    GET /api/uk/boe-mpc-voting/table    - テーブル表示用データ
"""
from fastapi import APIRouter, Query

from services.uk.boe_mpc_voting_service import boe_mpc_voting_service


router = APIRouter(
    prefix="/api/uk/boe-mpc-voting",
    tags=["uk", "monetary_policy"]
)


@router.get("")
def get_mpc_voting(
    force_refresh: bool = Query(False, description="強制更新")
):
    """
    BOE MPC投票データを取得

    Returns:
        {
            "data": [...],
            "members": [...],
            "latest": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return boe_mpc_voting_service.get_mpc_voting_data(force_refresh=force_refresh)


@router.get("/table")
def get_mpc_voting_table(
    force_refresh: bool = Query(False, description="強制更新"),
    limit: int = Query(20, ge=1, le=100, description="取得件数")
):
    """
    テーブル表示用のMPC投票データを取得

    Returns:
        {
            "members": [...],
            "data": [...],
            "next_release": {...},
            "last_updated": str,
            "source": str
        }
    """
    if force_refresh:
        boe_mpc_voting_service.get_mpc_voting_data(force_refresh=True)

    return boe_mpc_voting_service.get_table_data(limit=limit)


@router.get("/cache-status")
def get_cache_status():
    """キャッシュ状態を取得"""
    return boe_mpc_voting_service.get_cache_status()


@router.post("/invalidate-cache")
def invalidate_cache():
    """キャッシュを無効化"""
    success = boe_mpc_voting_service.invalidate_cache()
    return {"success": success}
