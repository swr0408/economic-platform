"""
BFS（スイス連邦統計局）関連 APIルーター

提供データ:
- Unemployment Rate（失業率）
- Retail Trade（小売売上高）
- Industrial Production（鉱工業生産）
"""
from fastapi import APIRouter, Query

router = APIRouter(
    prefix="/api/switzerland/bfs",
    tags=["switzerland", "employment"]
)


@router.get("/")
def bfs_root():
    """BFS APIルート"""
    return {
        "message": "BFS (Federal Statistical Office) API",
        "status": "Active",
        "available_endpoints": [
            "/unemployment-rate - Unemployment Rate",
            "/retail-trade - Retail Trade (小売売上高)",
            "/industrial-production - Industrial Production (鉱工業生産)",
            "/nominal-wage-growth - Nominal Wage Growth (名目賃金上昇率)",
            "/housing-prices - Housing Prices (住宅価格指数)",
        ]
    }


@router.get("/unemployment-rate")
def get_unemployment_rate(
    force_refresh: bool = Query(False, description="強制的にキャッシュを更新")
):
    """
    スイス失業率データを取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...}
        }
    """
    from services.switzerland.ch_unemployment_rate_service import ch_unemployment_rate_service

    return ch_unemployment_rate_service.get_unemployment_rate_data(force_refresh=force_refresh)


@router.get("/unemployment-rate/latest")
def get_unemployment_rate_latest():
    """
    スイス失業率 最新データを取得

    Returns:
        最新のスイス失業率データ
    """
    from services.switzerland.ch_unemployment_rate_service import ch_unemployment_rate_service

    result = ch_unemployment_rate_service.get_unemployment_rate_data()
    return {
        "latest": result.get("latest"),
        "next_release": result.get("next_release"),
    }


@router.get("/unemployment-rate/cache/status")
def get_unemployment_rate_cache_status():
    """スイス失業率 キャッシュ状態を取得"""
    from services.switzerland.ch_unemployment_rate_service import ch_unemployment_rate_service

    return ch_unemployment_rate_service.get_cache_status()


@router.delete("/unemployment-rate/cache")
def invalidate_unemployment_rate_cache():
    """スイス失業率 キャッシュを無効化"""
    from services.switzerland.ch_unemployment_rate_service import ch_unemployment_rate_service

    success = ch_unemployment_rate_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }


# =============================================================================
# 小売売上高（Retail Trade）
# =============================================================================

@router.get("/retail-trade")
def get_retail_trade(
    force_refresh: bool = Query(False, description="強制的にキャッシュを更新")
):
    """
    スイス小売売上高データを取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...}
        }
    """
    from services.switzerland.ch_retail_trade_service import ch_retail_trade_service

    return ch_retail_trade_service.get_ch_retail_trade_data(force_refresh=force_refresh)


@router.get("/retail-trade/latest")
def get_retail_trade_latest():
    """
    スイス小売売上高 最新データを取得

    Returns:
        最新のスイス小売売上高データ
    """
    from services.switzerland.ch_retail_trade_service import ch_retail_trade_service

    result = ch_retail_trade_service.get_ch_retail_trade_data()
    return {
        "latest": result.get("latest"),
        "next_release": result.get("next_release"),
    }


@router.get("/retail-trade/cache/status")
def get_retail_trade_cache_status():
    """スイス小売売上高 キャッシュ状態を取得"""
    from services.switzerland.ch_retail_trade_service import ch_retail_trade_service

    return ch_retail_trade_service.get_cache_status()


@router.delete("/retail-trade/cache")
def invalidate_retail_trade_cache():
    """スイス小売売上高 キャッシュを無効化"""
    from services.switzerland.ch_retail_trade_service import ch_retail_trade_service

    success = ch_retail_trade_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }


# =============================================================================
# 鉱工業生産（Industrial Production）
# =============================================================================

@router.get("/industrial-production")
def get_industrial_production(
    force_refresh: bool = Query(False, description="強制的にキャッシュを更新")
):
    """
    スイス鉱工業生産データを取得

    Returns:
        {
            "monthly_data": [...],
            "quarterly_data": [...],
            "latest_monthly": {...},
            "latest_quarterly": {...},
            "metadata": {...},
            "next_release": {...}
        }
    """
    from services.switzerland.ch_industrial_production_service import ch_industrial_production_service

    return ch_industrial_production_service.get_ch_industrial_production_data(force_refresh=force_refresh)


@router.get("/industrial-production/latest")
def get_industrial_production_latest():
    """
    スイス鉱工業生産 最新データを取得

    Returns:
        最新のスイス鉱工業生産データ
    """
    from services.switzerland.ch_industrial_production_service import ch_industrial_production_service

    result = ch_industrial_production_service.get_ch_industrial_production_data()
    return {
        "latest_monthly": result.get("latest_monthly"),
        "latest_quarterly": result.get("latest_quarterly"),
        "next_release": result.get("next_release"),
    }


@router.get("/industrial-production/cache/status")
def get_industrial_production_cache_status():
    """スイス鉱工業生産 キャッシュ状態を取得"""
    from services.switzerland.ch_industrial_production_service import ch_industrial_production_service

    return ch_industrial_production_service.get_cache_status()


@router.delete("/industrial-production/cache")
def invalidate_industrial_production_cache():
    """スイス鉱工業生産 キャッシュを無効化"""
    from services.switzerland.ch_industrial_production_service import ch_industrial_production_service

    success = ch_industrial_production_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }


# =============================================================================
# 名目賃金上昇率（Nominal Wage Growth）
# =============================================================================

@router.get("/nominal-wage-growth")
def get_nominal_wage_growth(
    force_refresh: bool = Query(False, description="強制的にキャッシュを更新")
):
    """
    スイス名目賃金上昇率データを取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...}
        }
    """
    from services.switzerland.ch_nominal_wage_growth_service import ch_nominal_wage_growth_service

    return ch_nominal_wage_growth_service.get_nominal_wage_growth_data(force_refresh=force_refresh)


@router.get("/nominal-wage-growth/latest")
def get_nominal_wage_growth_latest():
    """
    スイス名目賃金上昇率 最新データを取得

    Returns:
        最新のスイス名目賃金上昇率データ
    """
    from services.switzerland.ch_nominal_wage_growth_service import ch_nominal_wage_growth_service

    result = ch_nominal_wage_growth_service.get_nominal_wage_growth_data()
    return {
        "latest": result.get("latest"),
        "next_release": result.get("next_release"),
    }


@router.get("/nominal-wage-growth/cache/status")
def get_nominal_wage_growth_cache_status():
    """スイス名目賃金上昇率 キャッシュ状態を取得"""
    from services.switzerland.ch_nominal_wage_growth_service import ch_nominal_wage_growth_service

    return ch_nominal_wage_growth_service.get_cache_status()


@router.delete("/nominal-wage-growth/cache")
def invalidate_nominal_wage_growth_cache():
    """スイス名目賃金上昇率 キャッシュを無効化"""
    from services.switzerland.ch_nominal_wage_growth_service import ch_nominal_wage_growth_service

    success = ch_nominal_wage_growth_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }


# =============================================================================
# 住宅価格指数（Housing Prices）
# =============================================================================

@router.get("/housing-prices")
def get_housing_prices(
    force_refresh: bool = Query(False, description="強制的にキャッシュを更新")
):
    """
    スイス住宅価格指数データを取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...}
        }
    """
    from services.switzerland.ch_housing_prices_service import ch_housing_prices_service

    return ch_housing_prices_service.get_housing_prices_data(force_refresh=force_refresh)


@router.get("/housing-prices/latest")
def get_housing_prices_latest():
    """
    スイス住宅価格指数 最新データを取得

    Returns:
        最新のスイス住宅価格指数データ
    """
    from services.switzerland.ch_housing_prices_service import ch_housing_prices_service

    result = ch_housing_prices_service.get_housing_prices_data()
    return {
        "latest": result.get("latest"),
        "next_release": result.get("next_release"),
    }


@router.get("/housing-prices/cache/status")
def get_housing_prices_cache_status():
    """スイス住宅価格指数 キャッシュ状態を取得"""
    from services.switzerland.ch_housing_prices_service import ch_housing_prices_service

    return ch_housing_prices_service.get_cache_status()


@router.delete("/housing-prices/cache")
def invalidate_housing_prices_cache():
    """スイス住宅価格指数 キャッシュを無効化"""
    from services.switzerland.ch_housing_prices_service import ch_housing_prices_service

    success = ch_housing_prices_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }
