"""
オーストラリア統計局（ABS）雇用関連 APIルーター

エンドポイント:
- GET /api/australia/abs/unemployment-rate - 失業率データ
- GET /api/australia/abs/unemployment-rate/cache - キャッシュ状態
- DELETE /api/australia/abs/unemployment-rate/cache - キャッシュ無効化
- GET /api/australia/abs/employed-persons - 雇用者数データ
- GET /api/australia/abs/employed-persons/cache - キャッシュ状態
- DELETE /api/australia/abs/employed-persons/cache - キャッシュ無効化
- GET /api/australia/abs/fulltime-parttime - フルタイム/パートタイム雇用者数データ
- GET /api/australia/abs/fulltime-parttime/cache - キャッシュ状態
- DELETE /api/australia/abs/fulltime-parttime/cache - キャッシュ無効化
- GET /api/australia/abs/wage-price-index - 賃金物価指数データ
- GET /api/australia/abs/wage-price-index/cache - キャッシュ状態
- DELETE /api/australia/abs/wage-price-index/cache - キャッシュ無効化
- GET /api/australia/abs/job-vacancies - 求人件数データ
- GET /api/australia/abs/job-vacancies/cache - キャッシュ状態
- DELETE /api/australia/abs/job-vacancies/cache - キャッシュ無効化
- GET /api/australia/abs/anz-job-advertisements - ANZ求人広告データ
- GET /api/australia/abs/anz-job-advertisements/cache - キャッシュ状態
- DELETE /api/australia/abs/anz-job-advertisements/cache - キャッシュ無効化
- GET /api/australia/abs/underutilization - アンダー・ユーティライゼーション
- GET /api/australia/abs/underutilization/cache - キャッシュ状態
- DELETE /api/australia/abs/underutilization/cache - キャッシュ無効化
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.australia.au_unemployment_rate_service import au_unemployment_rate_service
from services.australia.au_employed_persons_service import au_employed_persons_service
from services.australia.au_fulltime_parttime_service import au_fulltime_parttime_service
from services.australia.au_participation_rate_service import au_participation_rate_service
from services.australia.au_wage_price_index_service import au_wage_price_index_service
from services.australia.au_job_vacancies_service import au_job_vacancies_service
from services.australia.au_anz_job_advertisements_service import au_anz_job_advertisements_service
from services.australia.au_underutilization_service import au_underutilization_service

router = APIRouter(
    prefix="/api/australia/abs",
    tags=["australia", "employment"]
)


@router.get("/unemployment-rate")
def get_unemployment_rate(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    ABS 失業率データを取得

    1系列:
    - Unemployment Rate (季節調整済み) - %
    """
    return au_unemployment_rate_service.get_au_unemployment_rate_data(force_refresh=force_refresh)


@router.get("/unemployment-rate/cache")
def get_unemployment_rate_cache_status() -> Dict[str, Any]:
    """失業率のキャッシュ状態を取得"""
    return au_unemployment_rate_service.get_cache_status()


@router.delete("/unemployment-rate/cache")
def invalidate_unemployment_rate_cache() -> Dict[str, bool]:
    """失業率のキャッシュを無効化"""
    success = au_unemployment_rate_service.invalidate_cache()
    return {"success": success}


# =====================================================================
# Employed Persons（雇用者数）
# =====================================================================


@router.get("/employed-persons")
def get_employed_persons(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    ABS 雇用者数データを取得

    3系列:
    - Employed Persons (季節調整済み) - 千人
    - 前月増減（千人）
    - 前年比（%）
    """
    return au_employed_persons_service.get_au_employed_persons_data(force_refresh=force_refresh)


@router.get("/employed-persons/cache")
def get_employed_persons_cache_status() -> Dict[str, Any]:
    """雇用者数のキャッシュ状態を取得"""
    return au_employed_persons_service.get_cache_status()


@router.delete("/employed-persons/cache")
def invalidate_employed_persons_cache() -> Dict[str, bool]:
    """雇用者数のキャッシュを無効化"""
    success = au_employed_persons_service.invalidate_cache()
    return {"success": success}


# =====================================================================
# Full-time/Part-time（フルタイム/パートタイム雇用者数）
# =====================================================================


@router.get("/fulltime-parttime")
def get_fulltime_parttime(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    ABS フルタイム/パートタイム雇用者数データを取得

    6系列:
    - Full-time (千人) / Part-time (千人)
    - Full-time MoM change (千人) / Part-time MoM change (千人)
    - Full-time YoY (%) / Part-time YoY (%)
    """
    return au_fulltime_parttime_service.get_au_fulltime_parttime_data(force_refresh=force_refresh)


@router.get("/fulltime-parttime/cache")
def get_fulltime_parttime_cache_status() -> Dict[str, Any]:
    """フルタイム/パートタイムのキャッシュ状態を取得"""
    return au_fulltime_parttime_service.get_cache_status()


@router.delete("/fulltime-parttime/cache")
def invalidate_fulltime_parttime_cache() -> Dict[str, bool]:
    """フルタイム/パートタイムのキャッシュを無効化"""
    success = au_fulltime_parttime_service.invalidate_cache()
    return {"success": success}


# =====================================================================
# Participation Rate（労働参加率）
# =====================================================================


@router.get("/participation-rate")
def get_participation_rate(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    ABS 労働参加率データを取得

    1系列:
    - Participation Rate (季節調整済み) - %
    """
    return au_participation_rate_service.get_au_participation_rate_data(force_refresh=force_refresh)


@router.get("/participation-rate/cache")
def get_participation_rate_cache_status() -> Dict[str, Any]:
    """労働参加率のキャッシュ状態を取得"""
    return au_participation_rate_service.get_cache_status()


@router.delete("/participation-rate/cache")
def invalidate_participation_rate_cache() -> Dict[str, bool]:
    """労働参加率のキャッシュを無効化"""
    success = au_participation_rate_service.invalidate_cache()
    return {"success": success}


# =====================================================================
# Wage Price Index（賃金物価指数）
# =====================================================================


@router.get("/wage-price-index")
def get_wage_price_index(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    ABS 賃金物価指数データを取得

    2系列:
    - QoQ (%) - 前期比
    - YoY (%) - 前年比
    """
    return au_wage_price_index_service.get_au_wage_price_index_data(force_refresh=force_refresh)


@router.get("/wage-price-index/cache")
def get_wage_price_index_cache_status() -> Dict[str, Any]:
    """賃金物価指数のキャッシュ状態を取得"""
    return au_wage_price_index_service.get_cache_status()


@router.delete("/wage-price-index/cache")
def invalidate_wage_price_index_cache() -> Dict[str, bool]:
    """賃金物価指数のキャッシュを無効化"""
    success = au_wage_price_index_service.invalidate_cache()
    return {"success": success}


# =====================================================================
# Job Vacancies（求人件数）
# =====================================================================


@router.get("/job-vacancies")
def get_job_vacancies(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    ABS 求人件数データを取得

    1系列:
    - Job Vacancies (季節調整済み) - 千件
    """
    return au_job_vacancies_service.get_au_job_vacancies_data(force_refresh=force_refresh)


@router.get("/job-vacancies/cache")
def get_job_vacancies_cache_status() -> Dict[str, Any]:
    """求人件数のキャッシュ状態を取得"""
    return au_job_vacancies_service.get_cache_status()


@router.delete("/job-vacancies/cache")
def invalidate_job_vacancies_cache() -> Dict[str, bool]:
    """求人件数のキャッシュを無効化"""
    success = au_job_vacancies_service.invalidate_cache()
    return {"success": success}


# =====================================================================
# ANZ Job Advertisements（ANZ求人広告）
# =====================================================================


@router.get("/anz-job-advertisements")
def get_anz_job_advertisements(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    ANZ-Indeed 求人広告データを取得

    1系列:
    - Job Advertisements Index (季節調整済み) - Index (2019=100)
    """
    return au_anz_job_advertisements_service.get_au_anz_job_advertisements_data(force_refresh=force_refresh)


@router.get("/anz-job-advertisements/cache")
def get_anz_job_advertisements_cache_status() -> Dict[str, Any]:
    """ANZ求人広告のキャッシュ状態を取得"""
    return au_anz_job_advertisements_service.get_cache_status()


@router.delete("/anz-job-advertisements/cache")
def invalidate_anz_job_advertisements_cache() -> Dict[str, bool]:
    """ANZ求人広告のキャッシュを無効化"""
    success = au_anz_job_advertisements_service.invalidate_cache()
    return {"success": success}


# =====================================================================
# Underutilization（アンダー・ユーティライゼーション）
# =====================================================================


@router.get("/underutilization")
def get_underutilization(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    アンダー・ユーティライゼーションデータを取得

    ABS 6202.0 Table 23:
    - underutilisation: 不完全利用率 (%, SA)
    - underemployment: 不完全雇用率 (%, SA)
    - unemployment: 失業率 (%, SA)
    """
    return au_underutilization_service.get_au_underutilization_data(force_refresh=force_refresh)


@router.get("/underutilization/cache")
def get_underutilization_cache_status() -> Dict[str, Any]:
    """アンダー・ユーティライゼーションのキャッシュ状態を取得"""
    return au_underutilization_service.get_cache_status()


@router.delete("/underutilization/cache")
def invalidate_underutilization_cache() -> Dict[str, bool]:
    """アンダー・ユーティライゼーションのキャッシュを無効化"""
    success = au_underutilization_service.invalidate_cache()
    return {"success": success}
