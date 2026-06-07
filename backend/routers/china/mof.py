"""
中国 財政部（MOF）関連 APIルーター

エンドポイント:
- GET /api/china/mof/land-sales-income - 土地売却収入データ
- GET /api/china/mof/land-sales-income/cache - キャッシュ状態
- DELETE /api/china/mof/land-sales-income/cache - キャッシュ無効化
- GET /api/china/mof/local-bonds - 地方政府債券データ
- GET /api/china/mof/local-bonds/cache - キャッシュ状態
- DELETE /api/china/mof/local-bonds/cache - キャッシュ無効化
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.china.cn_land_sales_income_service import cn_land_sales_income_service
from services.china.cn_local_bonds_service import cn_local_bonds_service

router = APIRouter(
    prefix="/api/china/mof",
    tags=["china", "mof"]
)


# -------------------------------------------------------------------------
# 土地売却収入（Land Sales Income）
# -------------------------------------------------------------------------

@router.get("/land-sales-income")
def get_land_sales_income(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """土地売却収入（累計、亿元）データを返す"""
    return cn_land_sales_income_service.get_data(force_refresh=force_refresh)


@router.get("/land-sales-income/cache")
def get_land_sales_income_cache_status() -> Dict[str, Any]:
    """土地売却収入のキャッシュ状態を返す"""
    return cn_land_sales_income_service.get_cache_status()


@router.delete("/land-sales-income/cache")
def invalidate_land_sales_income_cache() -> Dict[str, Any]:
    """土地売却収入のキャッシュを無効化"""
    return cn_land_sales_income_service.invalidate_cache()


# -------------------------------------------------------------------------
# 地方政府債券（Local Government Bonds）
# -------------------------------------------------------------------------

@router.get("/local-bonds")
def get_local_bonds(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """地方政府債券データ（新規比率・専項比率・枠余地・コスト）を返す"""
    return cn_local_bonds_service.get_data(force_refresh=force_refresh)


@router.get("/local-bonds/cache")
def get_local_bonds_cache_status() -> Dict[str, Any]:
    """地方政府債券のキャッシュ状態を返す"""
    return cn_local_bonds_service.get_cache_status()


@router.delete("/local-bonds/cache")
def invalidate_local_bonds_cache() -> Dict[str, Any]:
    """地方政府債券のキャッシュを無効化"""
    return cn_local_bonds_service.invalidate_cache()


# -------------------------------------------------------------------------
# 国債発行（Government Bond Issuance）
# -------------------------------------------------------------------------

@router.get("/bond-issuance")
def get_bond_issuance(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """国債発行データ（入札予定・結果・月次供給量）を返す"""
    from services.china.cn_government_bond_issuance_service import cn_government_bond_issuance_service
    return cn_government_bond_issuance_service.get_data(force_refresh=force_refresh)


@router.get("/bond-issuance/cache")
def get_bond_issuance_cache_status() -> Dict[str, Any]:
    """国債発行のキャッシュ状態を返す"""
    from services.china.cn_government_bond_issuance_service import cn_government_bond_issuance_service
    return cn_government_bond_issuance_service.get_cache_status()


@router.delete("/bond-issuance/cache")
def invalidate_bond_issuance_cache() -> Dict[str, Any]:
    """国債発行のキャッシュを無効化"""
    from services.china.cn_government_bond_issuance_service import cn_government_bond_issuance_service
    return cn_government_bond_issuance_service.invalidate_cache()


@router.post("/bond-issuance/fetch")
def fetch_bond_issuance() -> Dict[str, Any]:
    """国債発行の新規データを手動で取得・更新"""
    from services.china.cn_government_bond_issuance_service import cn_government_bond_issuance_service
    return cn_government_bond_issuance_service.update_latest()


@router.post("/bond-issuance/initial-scrape")
def initial_scrape_bond_issuance(
    max_pages: int = Query(15, description="スクレイピングするページ数")
) -> Dict[str, Any]:
    """国債発行の初回全ページスクレイピング"""
    from services.china.cn_government_bond_issuance_service import cn_government_bond_issuance_service
    return cn_government_bond_issuance_service.initial_scrape(max_pages=max_pages)
