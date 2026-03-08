"""
中国人民銀行（PBOC）関連 APIルーター

エンドポイント:
- GET /api/china/pboc/lpr-1y - ローンプライムレート（1Y）データ
- GET /api/china/pboc/lpr-5y - ローンプライムレート（5Y）データ
- GET /api/china/pboc/lpr - 1Y + 5Y 両方まとめて取得
- GET /api/china/pboc/lpr/cache - キャッシュ状態
- DELETE /api/china/pboc/lpr/cache - キャッシュ無効化
- GET /api/china/pboc/reverse-repo-rate - 逆回購金利データ
- GET /api/china/pboc/reverse-repo-rate/cache - キャッシュ状態
- DELETE /api/china/pboc/reverse-repo-rate/cache - キャッシュ無効化
- POST /api/china/pboc/reverse-repo-rate/fetch - 最新データを今すぐ取得
- GET /api/china/pboc/rrr - 預金準備率データ
- GET /api/china/pboc/rrr/cache - キャッシュ状態
- DELETE /api/china/pboc/rrr/cache - キャッシュ無効化
- POST /api/china/pboc/rrr/fetch - 最新データを今すぐ取得
- GET /api/china/pboc/balance-sheet - 中銀バランスシート（総資産）データ
- GET /api/china/pboc/balance-sheet/cache - キャッシュ状態
- DELETE /api/china/pboc/balance-sheet/cache - キャッシュ無効化
- POST /api/china/pboc/balance-sheet/fetch - 最新年データを今すぐ取得
- POST /api/china/pboc/balance-sheet/fetch-all - 全年データを取得（初回用）
- GET /api/china/pboc/fixing-repo-rate - Fixing Repo Rate (FR/FDR) 時系列データ
- GET /api/china/pboc/fixing-repo-rate/cache - キャッシュ状態
- DELETE /api/china/pboc/fixing-repo-rate/cache - キャッシュを無効化
- POST /api/china/pboc/fixing-repo-rate/fetch - 最新データを差分更新
- GET /api/china/pboc/shibor - SHIBOR 時系列データ
- GET /api/china/pboc/shibor/cache - キャッシュ状態
- DELETE /api/china/pboc/shibor/cache - キャッシュを無効化
- POST /api/china/pboc/shibor/fetch - 最新データを差分更新
- GET /api/china/pboc/m1-m2 - M1/M2 貨幣供応量 時系列データ
- GET /api/china/pboc/m1-m2/cache - キャッシュ状態
- DELETE /api/china/pboc/m1-m2/cache - キャッシュを無効化
- POST /api/china/pboc/m1-m2/fetch - 最新データを差分更新
- POST /api/china/pboc/m1-m2/fetch-all - 全年データを取得（初回用）
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.china.cn_lpr_service import cn_lpr_service
from services.china.ch_reverse_repo_rate_service import (
    ch_reverse_repo_rate_service,
    fetch_and_store_latest,
)
from services.china.ch_rrr_service import (
    ch_rrr_service,
    fetch_and_store_latest as rrr_fetch_and_store_latest,
)
from services.china.ch_central_bank_balance_sheet_service import (
    ch_central_bank_balance_sheet_service,
    fetch_latest as cbs_fetch_latest,
    fetch_all_years as cbs_fetch_all_years,
)
from services.china.cn_fixing_repo_rate_screenshot_service import (
    cn_fixing_repo_rate_service,
)
from services.china.cn_shibor_service import cn_shibor_service
from services.china.ch_m1_m2_service import ch_m1_m2_service
from services.china.cn_aggregate_financing_service import cn_aggregate_financing_service
from services.china.cn_new_rmb_loans_service import cn_new_rmb_loans_service
from services.china.cn_foreign_exchange_reserves_service import cn_foreign_exchange_reserves_service

router = APIRouter(
    prefix="/api/china/pboc",
    tags=["china", "policy"]
)


@router.get("/lpr-1y")
async def get_lpr_1y(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """中国ローンプライムレート（1年）データを取得"""
    return cn_lpr_service.get_lpr_1y_data(force_refresh=force_refresh)


@router.get("/lpr-5y")
async def get_lpr_5y(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """中国ローンプライムレート（5年）データを取得"""
    return cn_lpr_service.get_lpr_5y_data(force_refresh=force_refresh)


@router.get("/lpr")
async def get_lpr(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """中国ローンプライムレート（1Y + 5Y）データをまとめて取得"""
    return cn_lpr_service.get_data(force_refresh=force_refresh)


@router.get("/lpr/cache")
async def get_lpr_cache_status() -> Dict[str, Any]:
    """ローンプライムレートのキャッシュ状態を取得"""
    return cn_lpr_service.get_cache_status()


@router.delete("/lpr/cache")
async def invalidate_lpr_cache() -> Dict[str, Any]:
    """ローンプライムレートのキャッシュを無効化"""
    return cn_lpr_service.invalidate_cache()


# =============================================================================
# 逆回購金利
# =============================================================================

@router.get("/reverse-repo-rate")
async def get_reverse_repo_rate(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """中国逆回購金利（7日物）データを取得"""
    return ch_reverse_repo_rate_service.get_data(force_refresh=force_refresh)


@router.get("/reverse-repo-rate/cache")
async def get_reverse_repo_cache_status() -> Dict[str, Any]:
    """逆回購金利のキャッシュ状態を取得"""
    return ch_reverse_repo_rate_service.get_cache_status()


@router.delete("/reverse-repo-rate/cache")
async def invalidate_reverse_repo_cache() -> Dict[str, Any]:
    """逆回購金利のキャッシュを無効化"""
    return ch_reverse_repo_rate_service.invalidate_cache()


@router.post("/reverse-repo-rate/fetch")
async def fetch_reverse_repo_now() -> Dict[str, Any]:
    """PBOCウェブサイトから最新データを今すぐ取得してDBに追加"""
    try:
        count = fetch_and_store_latest()
        return {"success": True, "new_records": count}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# 預金準備率（RRR）
# =============================================================================

@router.get("/rrr")
async def get_rrr(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """中国預金準備率（Large Bank）データを取得"""
    return ch_rrr_service.get_data(force_refresh=force_refresh)


@router.get("/rrr/cache")
async def get_rrr_cache_status() -> Dict[str, Any]:
    """預金準備率のキャッシュ状態を取得"""
    return ch_rrr_service.get_cache_status()


@router.delete("/rrr/cache")
async def invalidate_rrr_cache() -> Dict[str, Any]:
    """預金準備率のキャッシュを無効化"""
    return ch_rrr_service.invalidate_cache()


@router.post("/rrr/fetch")
async def fetch_rrr_now() -> Dict[str, Any]:
    """PBOCウェブサイトから最新のRRR発表を今すぐ取得してDBに追加"""
    try:
        count = rrr_fetch_and_store_latest()
        if count > 0:
            ch_rrr_service.invalidate_cache()
        return {"success": True, "new_announcements": count}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# 中銀バランスシート（総資産）
# =============================================================================

@router.get("/balance-sheet")
async def get_balance_sheet(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """中国人民銀行バランスシート（総資産）データを取得"""
    return ch_central_bank_balance_sheet_service.get_data(force_refresh=force_refresh)


@router.get("/balance-sheet/cache")
async def get_balance_sheet_cache_status() -> Dict[str, Any]:
    """バランスシートのキャッシュ状態を取得"""
    return ch_central_bank_balance_sheet_service.get_cache_status()


@router.delete("/balance-sheet/cache")
async def invalidate_balance_sheet_cache() -> Dict[str, Any]:
    """バランスシートのキャッシュを無効化"""
    return ch_central_bank_balance_sheet_service.invalidate_cache()


@router.post("/balance-sheet/fetch")
async def fetch_balance_sheet_latest() -> Dict[str, Any]:
    """当年・前年のデータを今すぐ取得してDBに追加（月次更新用）"""
    try:
        count = cbs_fetch_latest()
        if count > 0:
            ch_central_bank_balance_sheet_service.invalidate_cache()
        return {"success": True, "updated_records": count}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/balance-sheet/fetch-all")
async def fetch_balance_sheet_all() -> Dict[str, Any]:
    """全年データを取得してDBに追加（初回セットアップ用）"""
    try:
        count = cbs_fetch_all_years()
        if count > 0:
            ch_central_bank_balance_sheet_service.invalidate_cache()
        return {"success": True, "inserted_records": count}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Fixing Repo Rate (chinamoney.com.cn API)
# =============================================================================

@router.get("/fixing-repo-rate")
async def get_fixing_repo_rate(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    Fixing Repo Rate (FR001/FR007/FR014/FDR001/FDR007/FDR014) 時系列データを返す

    データソース: chinamoney.com.cn 内部 API
    """
    return cn_fixing_repo_rate_service.get_data(force_refresh=force_refresh)


@router.get("/fixing-repo-rate/cache")
async def get_fixing_repo_rate_cache_status() -> Dict[str, Any]:
    """Fixing Repo Rate のキャッシュ状態を返す"""
    return cn_fixing_repo_rate_service.get_cache_status()


@router.delete("/fixing-repo-rate/cache")
async def invalidate_fixing_repo_rate_cache() -> Dict[str, Any]:
    """Fixing Repo Rate のキャッシュを無効化"""
    return cn_fixing_repo_rate_service.invalidate_cache()


@router.post("/fixing-repo-rate/fetch")
async def fetch_fixing_repo_rate_latest() -> Dict[str, Any]:
    """当年データを API 取得して Excel 上書き → キャッシュ再構築（毎日14:00 CST以降に実行）"""
    try:
        result = cn_fixing_repo_rate_service.update_current_year()
        latest = result.get("latest") or {}
        return {
            "success": True,
            "total_records": result.get("metadata", {}).get("total_records", 0),
            "latest_date": latest.get("date"),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# SHIBOR (shibor.org API)
# =============================================================================

@router.get("/shibor")
async def get_shibor(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """SHIBOR (O/N, 1W, 2W, 1M, 3M, 6M, 9M, 1Y) 時系列データを返す"""
    return cn_shibor_service.get_data(force_refresh=force_refresh)


@router.get("/shibor/cache")
async def get_shibor_cache_status() -> Dict[str, Any]:
    """SHIBOR のキャッシュ状態を返す"""
    return cn_shibor_service.get_cache_status()


@router.delete("/shibor/cache")
async def invalidate_shibor_cache() -> Dict[str, Any]:
    """SHIBOR のキャッシュを無効化"""
    return cn_shibor_service.invalidate_cache()


@router.post("/shibor/fetch")
async def fetch_shibor_latest() -> Dict[str, Any]:
    """当年データを API 取得して Excel 上書き → キャッシュ再構築（毎日14:00 CST以降に実行）"""
    try:
        result = cn_shibor_service.update_current_year()
        latest = result.get("latest") or {}
        return {
            "success": True,
            "total_records": result.get("metadata", {}).get("total_records", 0),
            "latest_date": latest.get("date"),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# M1/M2 貨幣供応量
# =============================================================================

@router.get("/m1-m2")
async def get_m1_m2(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """M1/M2 貨幣供応量 時系列データを返す（単位: 億元、前年比: %）"""
    return ch_m1_m2_service.get_data(force_refresh=force_refresh)


@router.get("/m1-m2/cache")
async def get_m1_m2_cache_status() -> Dict[str, Any]:
    """M1/M2 のキャッシュ状態を返す"""
    return ch_m1_m2_service.get_cache_status()


@router.delete("/m1-m2/cache")
async def invalidate_m1_m2_cache() -> Dict[str, Any]:
    """M1/M2 のキャッシュを無効化"""
    return ch_m1_m2_service.invalidate_cache()


@router.post("/m1-m2/fetch")
async def fetch_m1_m2_latest() -> Dict[str, Any]:
    """当年データを取得してキャッシュ再構築（月次スケジューラー用）"""
    try:
        result = ch_m1_m2_service.update_latest()
        latest = result.get("latest") or {}
        return {
            "success": True,
            "total_records": result.get("metadata", {}).get("total_records", 0),
            "latest_date": latest.get("date"),
            "latest_m2": latest.get("m2"),
            "latest_m1": latest.get("m1"),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/m1-m2/fetch-all")
async def fetch_m1_m2_all() -> Dict[str, Any]:
    """全年データを取得してキャッシュ再構築（初回セットアップ用）"""
    try:
        result = ch_m1_m2_service.get_data(force_refresh=True)
        latest = result.get("latest") or {}
        return {
            "success": True,
            "total_records": result.get("metadata", {}).get("total_records", 0),
            "latest_date": latest.get("date"),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# 社会融資総量（Aggregate Financing to the Real Economy）
# =============================================================================

@router.get("/aggregate-financing")
async def get_aggregate_financing(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """社会融資総量（Flow + Stock + YoY）データを返す"""
    return cn_aggregate_financing_service.get_data(force_refresh=force_refresh)


@router.get("/aggregate-financing/cache")
async def get_aggregate_financing_cache_status() -> Dict[str, Any]:
    """社会融資総量のキャッシュ状態を返す"""
    return cn_aggregate_financing_service.get_cache_status()


@router.delete("/aggregate-financing/cache")
async def invalidate_aggregate_financing_cache() -> Dict[str, Any]:
    """社会融資総量のキャッシュを無効化"""
    return cn_aggregate_financing_service.invalidate_cache()


@router.post("/aggregate-financing/fetch")
async def fetch_aggregate_financing_latest() -> Dict[str, Any]:
    """当年データを取得してキャッシュ再構築（月次スケジューラー用）"""
    try:
        result = cn_aggregate_financing_service.update_latest()
        latest = result.get("latest") or {}
        return {
            "success": True,
            "total_records": result.get("metadata", {}).get("total_records", 0),
            "latest_date": latest.get("date"),
            "latest_flow": latest.get("flow"),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/aggregate-financing/fetch-all")
async def fetch_aggregate_financing_all() -> Dict[str, Any]:
    """全年データを取得してキャッシュ再構築（初回セットアップ用）"""
    try:
        result = cn_aggregate_financing_service.get_data(force_refresh=True)
        latest = result.get("latest") or {}
        return {
            "success": True,
            "total_records": result.get("metadata", {}).get("total_records", 0),
            "latest_date": latest.get("date"),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# 新規人民元貸出（New RMB Loans）
# =============================================================================

@router.get("/new-rmb-loans")
async def get_new_rmb_loans(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """新規人民元貸出（Stock + Flow + YoY）データを返す"""
    return cn_new_rmb_loans_service.get_data(force_refresh=force_refresh)


@router.get("/new-rmb-loans/cache")
async def get_new_rmb_loans_cache_status() -> Dict[str, Any]:
    """新規人民元貸出のキャッシュ状態を返す"""
    return cn_new_rmb_loans_service.get_cache_status()


@router.delete("/new-rmb-loans/cache")
async def invalidate_new_rmb_loans_cache() -> Dict[str, Any]:
    """新規人民元貸出のキャッシュを無効化"""
    return cn_new_rmb_loans_service.invalidate_cache()


# =============================================================================
# 外貨準備（Foreign Exchange Reserves）
# =============================================================================

@router.get("/forex-reserves")
async def get_forex_reserves(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """外貨準備（Foreign Exchange Reserves）データを返す"""
    return cn_foreign_exchange_reserves_service.get_data(force_refresh=force_refresh)


@router.get("/forex-reserves/cache")
async def get_forex_reserves_cache_status() -> Dict[str, Any]:
    """外貨準備のキャッシュ状態を返す"""
    return cn_foreign_exchange_reserves_service.get_cache_status()


@router.delete("/forex-reserves/cache")
async def invalidate_forex_reserves_cache() -> Dict[str, Any]:
    """外貨準備のキャッシュを無効化"""
    return cn_foreign_exchange_reserves_service.invalidate_cache()


# =============================================================================
# Central Parity Rate（基準値・Fixing）
# =============================================================================

@router.get("/central-parity")
async def get_central_parity(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """Central Parity Rate（USD/CNY基準値）+ スポットレートを返す"""
    try:
        from services.china.cn_central_parity_service import cn_central_parity_service
    except ImportError:
        from backend.services.china.cn_central_parity_service import cn_central_parity_service
    return cn_central_parity_service.get_data(force_refresh=force_refresh)


@router.get("/central-parity/cache")
async def get_central_parity_cache_status() -> Dict[str, Any]:
    """Central Parityのキャッシュ状態を返す"""
    try:
        from services.china.cn_central_parity_service import cn_central_parity_service
    except ImportError:
        from backend.services.china.cn_central_parity_service import cn_central_parity_service
    return cn_central_parity_service.get_cache_status()


@router.delete("/central-parity/cache")
async def invalidate_central_parity_cache() -> Dict[str, Any]:
    """Central Parityのキャッシュを無効化"""
    try:
        from services.china.cn_central_parity_service import cn_central_parity_service
    except ImportError:
        from backend.services.china.cn_central_parity_service import cn_central_parity_service
    return cn_central_parity_service.invalidate_cache()


@router.post("/central-parity/fetch")
async def fetch_central_parity() -> Dict[str, Any]:
    """Central Parityの当年データを手動で取得・更新"""
    try:
        from services.china.cn_central_parity_service import cn_central_parity_service
    except ImportError:
        from backend.services.china.cn_central_parity_service import cn_central_parity_service
    return cn_central_parity_service.update_current_year()
