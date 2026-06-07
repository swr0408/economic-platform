"""
BusinessNZ APIルーター

エンドポイント:
- GET /api/newzealand/businessnz/pmi - 製造業PMIデータ
- GET /api/newzealand/businessnz/pmi/cache - キャッシュ状態
- DELETE /api/newzealand/businessnz/pmi/cache - キャッシュ無効化
- GET /api/newzealand/businessnz/psi - サービス業PSIデータ
- GET /api/newzealand/businessnz/psi/cache - キャッシュ状態
- DELETE /api/newzealand/businessnz/psi/cache - キャッシュ無効化
- GET /api/newzealand/businessnz/pci - 総合PCIデータ
- GET /api/newzealand/businessnz/pci/cache - キャッシュ状態
- DELETE /api/newzealand/businessnz/pci/cache - キャッシュ無効化
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.newzealand.nz_pmi_service import nz_pmi_service

router = APIRouter(
    prefix="/api/newzealand/businessnz",
    tags=["newzealand", "economy"]
)


# =============================================================================
# PMI（製造業PMI）
# =============================================================================

@router.get("/pmi")
def get_pmi(
    force_refresh: bool = Query(False, description="データを強制再取得"),
) -> Dict[str, Any]:
    """製造業PMIデータを取得"""
    return nz_pmi_service.get_pmi_data(force_refresh=force_refresh)


@router.get("/pmi/cache")
def get_pmi_cache_status() -> Dict[str, Any]:
    """製造業PMIのキャッシュ状態を取得"""
    return nz_pmi_service.get_pmi_cache_status()


@router.delete("/pmi/cache")
def invalidate_pmi_cache() -> Dict[str, Any]:
    """製造業PMIのキャッシュを無効化"""
    result = nz_pmi_service.invalidate_pmi_cache()
    return {"success": result, "message": "PMI cache invalidated"}


# =============================================================================
# PSI（サービス業PSI）
# =============================================================================

@router.get("/psi")
def get_psi(
    force_refresh: bool = Query(False, description="データを強制再取得"),
) -> Dict[str, Any]:
    """サービス業PSIデータを取得"""
    return nz_pmi_service.get_psi_data(force_refresh=force_refresh)


@router.get("/psi/cache")
def get_psi_cache_status() -> Dict[str, Any]:
    """サービス業PSIのキャッシュ状態を取得"""
    return nz_pmi_service.get_psi_cache_status()


@router.delete("/psi/cache")
def invalidate_psi_cache() -> Dict[str, Any]:
    """サービス業PSIのキャッシュを無効化"""
    result = nz_pmi_service.invalidate_psi_cache()
    return {"success": result, "message": "PSI cache invalidated"}


# =============================================================================
# PCI（総合PCI）
# =============================================================================

@router.get("/pci")
def get_pci(
    force_refresh: bool = Query(False, description="データを強制再取得"),
) -> Dict[str, Any]:
    """総合PCIデータを取得"""
    return nz_pmi_service.get_pci_data(force_refresh=force_refresh)


@router.get("/pci/cache")
def get_pci_cache_status() -> Dict[str, Any]:
    """総合PCIのキャッシュ状態を取得"""
    return nz_pmi_service.get_pci_cache_status()


@router.delete("/pci/cache")
def invalidate_pci_cache() -> Dict[str, Any]:
    """総合PCIのキャッシュを無効化"""
    result = nz_pmi_service.invalidate_pci_cache()
    return {"success": result, "message": "PCI cache invalidated"}
