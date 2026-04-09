"""
Seasonality API のルータ。
"""

import json
from fastapi import APIRouter, HTTPException
from pathlib import Path

try:
    from backend.config import SEASONALITY_DIR, SEASONALITY_STATS_DIR
    from backend.services.seasonality_service import build_index, build_manifest
except ImportError:
    from config import SEASONALITY_DIR, SEASONALITY_STATS_DIR
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


def _load_stats_json(symbol: str, filename: str) -> dict:
    """手動更新の統計JSONを読み込む。存在しなければ 404。"""
    path: Path = SEASONALITY_STATS_DIR / symbol / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{filename} not found for {symbol}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"_load_stats_json error ({symbol}/{filename}):", repr(e))
        raise HTTPException(status_code=500, detail="failed to load stats json")


@router.get("/api/seasonality/{symbol}/monthly-stats")
def api_seasonality_monthly_stats(symbol: str):
    """月別統計（n, mean, median, std, CI95, neg_rate, diff）を返す。"""
    return _load_stats_json(symbol, "monthly_stats.json")


@router.get("/api/seasonality/{symbol}/intramonth-path")
def api_seasonality_intramonth_path(symbol: str):
    """月内累積平均パスを返す。"""
    return _load_stats_json(symbol, "intramonth_path.json")


@router.get("/api/seasonality/{symbol}/daily-stats")
def api_seasonality_daily_stats(symbol: str):
    """日別統計（月×営業日インデックスの平均/n/下落率）を返す。"""
    return _load_stats_json(symbol, "daily_stats.json")
