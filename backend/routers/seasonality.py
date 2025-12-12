"""
Seasonality API のルータ。
"""

from fastapi import APIRouter, HTTPException
from pathlib import Path

try:
    from backend.config import SEASONALITY_DIR
    from backend.services.seasonality_service import build_index, build_manifest
except ImportError:
    from config import SEASONALITY_DIR
    from services.seasonality_service import build_index, build_manifest


router = APIRouter()


@router.get("/api/seasonality/index")
def api_seasonality_index():
    """カテゴリ別の銘柄インデックスを返す。"""
    try:
        return build_index()
    except Exception as e:
        print("api_seasonality_index error:", repr(e))
        return {"categories": {}}


@router.get("/api/seasonality/{symbol}/manifest")
def api_seasonality_manifest(symbol: str):
    """指定シンボルのマニフェストを返す。存在しなければ 404。"""
    sym_dir: Path = SEASONALITY_DIR / symbol
    if not sym_dir.exists():
        raise HTTPException(status_code=404, detail="symbol not found")
    return build_manifest(symbol)
