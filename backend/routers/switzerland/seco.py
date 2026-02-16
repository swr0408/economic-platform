"""
SECO（スイス連邦経済省経済事務局）関連 APIルーター

提供データ:
- Consumer Climate（消費者景況感）
- GDP Growth Rate（GDP成長率）
- Job Vacancies（求人情報）
- Households and NPISH（家計消費）
"""
from fastapi import APIRouter, Query

router = APIRouter(
    prefix="/api/switzerland/seco",
    tags=["switzerland", "consumer"]
)


@router.get("/")
async def seco_root():
    """SECO APIルート"""
    return {
        "message": "SECO (State Secretariat for Economic Affairs) API",
        "status": "Active",
        "available_endpoints": [
            "/consumer-sentiment - Consumer Climate",
            "/growth-rate - GDP Growth Rate",
            "/job-vacancies - Job Vacancies (求人情報)",
            "/households-and-npish - Households and NPISH (家計消費)",
            "/pmi - PMI (製造業・サービス業)",
        ]
    }


@router.get("/consumer-sentiment")
async def get_consumer_sentiment(
    force_refresh: bool = Query(False, description="強制的にキャッシュを更新")
):
    """
    SECO消費者景況感データを取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...}
        }
    """
    from services.switzerland.ch_consumer_sentiment_service import ch_consumer_sentiment_service

    return ch_consumer_sentiment_service.get_consumer_sentiment_data(force_refresh=force_refresh)


@router.get("/consumer-sentiment/latest")
async def get_consumer_sentiment_latest():
    """
    SECO消費者景況感 最新データを取得

    Returns:
        最新のSECO消費者景況感データ
    """
    from services.switzerland.ch_consumer_sentiment_service import ch_consumer_sentiment_service

    result = ch_consumer_sentiment_service.get_consumer_sentiment_data()
    return {
        "latest": result.get("latest"),
        "next_release": result.get("next_release"),
    }


@router.get("/consumer-sentiment/cache/status")
async def get_consumer_sentiment_cache_status():
    """SECO消費者景況感 キャッシュ状態を取得"""
    from services.switzerland.ch_consumer_sentiment_service import ch_consumer_sentiment_service

    return ch_consumer_sentiment_service.get_cache_status()


@router.delete("/consumer-sentiment/cache")
async def invalidate_consumer_sentiment_cache():
    """SECO消費者景況感 キャッシュを無効化"""
    from services.switzerland.ch_consumer_sentiment_service import ch_consumer_sentiment_service

    success = ch_consumer_sentiment_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }


# =============================================================================
# GDP成長率（Growth Rate）
# =============================================================================

@router.get("/growth-rate")
async def get_growth_rate(
    force_refresh: bool = Query(False, description="強制的にキャッシュを更新")
):
    """
    スイスGDP成長率データを取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...}
        }
    """
    from services.switzerland.ch_growth_rate_service import ch_growth_rate_service

    return ch_growth_rate_service.get_ch_growth_rate_data(force_refresh=force_refresh)


@router.get("/growth-rate/latest")
async def get_growth_rate_latest():
    """
    スイスGDP成長率 最新データを取得

    Returns:
        最新のスイスGDP成長率データ
    """
    from services.switzerland.ch_growth_rate_service import ch_growth_rate_service

    result = ch_growth_rate_service.get_ch_growth_rate_data()
    return {
        "latest": result.get("latest"),
        "next_release": result.get("next_release"),
    }


@router.get("/growth-rate/cache/status")
async def get_growth_rate_cache_status():
    """スイスGDP成長率 キャッシュ状態を取得"""
    from services.switzerland.ch_growth_rate_service import ch_growth_rate_service

    return ch_growth_rate_service.get_cache_status()


@router.delete("/growth-rate/cache")
async def invalidate_growth_rate_cache():
    """スイスGDP成長率 キャッシュを無効化"""
    from services.switzerland.ch_growth_rate_service import ch_growth_rate_service

    success = ch_growth_rate_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }


# =============================================================================
# 求人情報（Job Vacancies）
# =============================================================================

@router.get("/job-vacancies")
async def get_job_vacancies(
    force_refresh: bool = Query(False, description="強制的にキャッシュを更新")
):
    """
    スイス求人情報データを取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...}
        }
    """
    from services.switzerland.ch_job_vacancies_service import ch_job_vacancies_service

    return ch_job_vacancies_service.get_job_vacancies_data(force_refresh=force_refresh)


@router.get("/job-vacancies/latest")
async def get_job_vacancies_latest():
    """
    スイス求人情報 最新データを取得

    Returns:
        最新のスイス求人情報データ
    """
    from services.switzerland.ch_job_vacancies_service import ch_job_vacancies_service

    result = ch_job_vacancies_service.get_job_vacancies_data()
    return {
        "latest": result.get("latest"),
        "next_release": result.get("next_release"),
    }


@router.get("/job-vacancies/cache/status")
async def get_job_vacancies_cache_status():
    """スイス求人情報 キャッシュ状態を取得"""
    from services.switzerland.ch_job_vacancies_service import ch_job_vacancies_service

    return ch_job_vacancies_service.get_cache_status()


@router.delete("/job-vacancies/cache")
async def invalidate_job_vacancies_cache():
    """スイス求人情報 キャッシュを無効化"""
    from services.switzerland.ch_job_vacancies_service import ch_job_vacancies_service

    success = ch_job_vacancies_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }


# =============================================================================
# 家計消費（Households and NPISH）
# =============================================================================

@router.get("/households-and-npish")
async def get_households_and_npish(
    force_refresh: bool = Query(False, description="強制的にキャッシュを更新")
):
    """
    スイス家計消費（Households and NPISH）データを取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...}
        }
    """
    from services.switzerland.ch_households_and_npish_service import ch_households_and_npish_service

    return ch_households_and_npish_service.get_ch_households_and_npish_data(force_refresh=force_refresh)


@router.get("/households-and-npish/latest")
async def get_households_and_npish_latest():
    """
    スイス家計消費 最新データを取得

    Returns:
        最新のスイス家計消費データ
    """
    from services.switzerland.ch_households_and_npish_service import ch_households_and_npish_service

    result = ch_households_and_npish_service.get_ch_households_and_npish_data()
    return {
        "latest": result.get("latest"),
        "next_release": result.get("next_release"),
    }


@router.get("/households-and-npish/cache/status")
async def get_households_and_npish_cache_status():
    """スイス家計消費 キャッシュ状態を取得"""
    from services.switzerland.ch_households_and_npish_service import ch_households_and_npish_service

    return ch_households_and_npish_service.get_cache_status()


@router.delete("/households-and-npish/cache")
async def invalidate_households_and_npish_cache():
    """スイス家計消費 キャッシュを無効化"""
    from services.switzerland.ch_households_and_npish_service import ch_households_and_npish_service

    success = ch_households_and_npish_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }


# =============================================================================
# PMI（購買担当者景気指数）
# =============================================================================

@router.get("/pmi")
async def get_pmi(
    force_refresh: bool = Query(False, description="強制的にキャッシュを更新")
):
    """
    スイスPMI（購買担当者景気指数）データを取得

    Returns:
        {
            "manufacturing_data": [...],
            "services_data": [...],
            "latest_manufacturing": {...},
            "latest_services": {...},
            "metadata": {...},
            "next_release": {...}
        }
    """
    from services.switzerland.ch_pmi_service import ch_pmi_service

    return ch_pmi_service.get_pmi_data(force_refresh=force_refresh)


@router.get("/pmi/latest")
async def get_pmi_latest():
    """
    スイスPMI 最新データを取得

    Returns:
        最新のスイスPMIデータ
    """
    from services.switzerland.ch_pmi_service import ch_pmi_service

    result = ch_pmi_service.get_pmi_data()
    return {
        "latest_manufacturing": result.get("latest_manufacturing"),
        "latest_services": result.get("latest_services"),
        "next_release": result.get("next_release"),
    }


@router.get("/pmi/cache/status")
async def get_pmi_cache_status():
    """スイスPMI キャッシュ状態を取得"""
    from services.switzerland.ch_pmi_service import ch_pmi_service

    return ch_pmi_service.get_cache_status()


@router.delete("/pmi/cache")
async def invalidate_pmi_cache():
    """スイスPMI キャッシュを無効化"""
    from services.switzerland.ch_pmi_service import ch_pmi_service

    success = ch_pmi_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }
