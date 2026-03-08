"""
中国国家統計局（NBS）関連 APIルーター

エンドポイント:
- GET /api/china/nbs/commercial-residential-sales - 商業住宅販売データ
- GET /api/china/nbs/commercial-residential-sales/cache - キャッシュ状態
- DELETE /api/china/nbs/commercial-residential-sales/cache - キャッシュ無効化
- GET /api/china/nbs/house-price-index - 住宅価格指数データ
- GET /api/china/nbs/house-price-index/cache - キャッシュ状態
- DELETE /api/china/nbs/house-price-index/cache - キャッシュ無効化
- GET /api/china/nbs/ppi - PPIデータ
- GET /api/china/nbs/ppi/cache - キャッシュ状態
- DELETE /api/china/nbs/ppi/cache - キャッシュ無効化
- GET /api/china/nbs/retail-sales - 小売売上高データ
- GET /api/china/nbs/retail-sales/cache - キャッシュ状態
- DELETE /api/china/nbs/retail-sales/cache - キャッシュ無効化
- GET /api/china/nbs/gdp-growth-rate - GDP成長率データ
- GET /api/china/nbs/gdp-growth-rate/cache - キャッシュ状態
- DELETE /api/china/nbs/gdp-growth-rate/cache - キャッシュ無効化
- GET /api/china/nbs/unemployment-rate - 失業率データ
- GET /api/china/nbs/unemployment-rate/cache - キャッシュ状態
- DELETE /api/china/nbs/unemployment-rate/cache - キャッシュ無効化
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.china.cn_cpi_service import cn_cpi_service
from services.china.cn_commercial_residential_sales_service import (
    cn_commercial_residential_sales_service,
)
from services.china.cn_house_price_index_service import (
    cn_house_price_index_service,
)
from services.china.cn_ppi_service import cn_ppi_service
from services.china.cn_retail_sales_service import cn_retail_sales_service
from services.china.cn_gdp_growth_rate_service import cn_gdp_growth_rate_service
from services.china.cn_industrial_production_service import cn_industrial_production_service
from services.china.cn_fixed_asset_investment_service import cn_fixed_asset_investment_service
from services.china.cn_unemployment_rate_service import cn_unemployment_rate_service
from services.china.cn_beijing_pm25_service import cn_beijing_pm25_service
from services.china.cn_pmi_service import cn_pmi_service
from services.china.cn_caixin_pmi_service import cn_caixin_pmi_service
from services.china.cn_trade_balance_service import cn_trade_balance_service
from services.china.cn_integrated_circuit_manufacturing_service import cn_integrated_circuit_manufacturing_service
from services.china.cn_electronics_stock_service import cn_electronics_stock_service

router = APIRouter(
    prefix="/api/china/nbs",
    tags=["china", "nbs"]
)


# -------------------------------------------------------------------------
# CPI（Consumer Price Index）
# -------------------------------------------------------------------------

@router.get("/cpi")
async def get_cpi(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """CPI（前年比・前月比 / 食品・非食品）データを返す"""
    return cn_cpi_service.get_data(force_refresh=force_refresh)


@router.get("/cpi/cache")
async def get_cpi_cache_status() -> Dict[str, Any]:
    """CPIのキャッシュ状態を返す"""
    return cn_cpi_service.get_cache_status()


@router.delete("/cpi/cache")
async def invalidate_cpi_cache() -> Dict[str, Any]:
    """CPIのキャッシュを無効化"""
    return cn_cpi_service.invalidate_cache()


# -------------------------------------------------------------------------
# 商業住宅販売（Commercial Residential Sales）
# -------------------------------------------------------------------------

@router.get("/commercial-residential-sales")
async def get_commercial_residential_sales(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """商業住宅販売（3系列 累積YoY）データを返す"""
    return cn_commercial_residential_sales_service.get_data(force_refresh=force_refresh)


@router.get("/commercial-residential-sales/cache")
async def get_commercial_residential_sales_cache_status() -> Dict[str, Any]:
    """商業住宅販売のキャッシュ状態を返す"""
    return cn_commercial_residential_sales_service.get_cache_status()


@router.delete("/commercial-residential-sales/cache")
async def invalidate_commercial_residential_sales_cache() -> Dict[str, Any]:
    """商業住宅販売のキャッシュを無効化"""
    return cn_commercial_residential_sales_service.invalidate_cache()


# -------------------------------------------------------------------------
# 住宅価格指数（House Price Index YoY）
# -------------------------------------------------------------------------

@router.get("/house-price-index")
async def get_house_price_index(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """住宅価格指数（YoY）データを返す"""
    return cn_house_price_index_service.get_data(force_refresh=force_refresh)


@router.get("/house-price-index/cache")
async def get_house_price_index_cache_status() -> Dict[str, Any]:
    """住宅価格指数のキャッシュ状態を返す"""
    return cn_house_price_index_service.get_cache_status()


@router.delete("/house-price-index/cache")
async def invalidate_house_price_index_cache() -> Dict[str, Any]:
    """住宅価格指数のキャッシュを無効化"""
    return cn_house_price_index_service.invalidate_cache()


# -------------------------------------------------------------------------
# 小売売上高（Retail Sales）
# -------------------------------------------------------------------------

@router.get("/retail-sales")
async def get_retail_sales(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """小売売上高（前年比）データを返す"""
    return cn_retail_sales_service.get_data(force_refresh=force_refresh)


@router.get("/retail-sales/cache")
async def get_retail_sales_cache_status() -> Dict[str, Any]:
    """小売売上高のキャッシュ状態を返す"""
    return cn_retail_sales_service.get_cache_status()


@router.delete("/retail-sales/cache")
async def invalidate_retail_sales_cache() -> Dict[str, Any]:
    """小売売上高のキャッシュを無効化"""
    return cn_retail_sales_service.invalidate_cache()


# -------------------------------------------------------------------------
# PPI（Producer Price Index）
# -------------------------------------------------------------------------

@router.get("/ppi")
async def get_ppi(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """PPI（前年比・前月比）データを返す"""
    return cn_ppi_service.get_data(force_refresh=force_refresh)


@router.get("/ppi/cache")
async def get_ppi_cache_status() -> Dict[str, Any]:
    """PPIのキャッシュ状態を返す"""
    return cn_ppi_service.get_cache_status()


@router.delete("/ppi/cache")
async def invalidate_ppi_cache() -> Dict[str, Any]:
    """PPIのキャッシュを無効化"""
    return cn_ppi_service.invalidate_cache()


# -------------------------------------------------------------------------
# 失業率（Unemployment Rate）
# -------------------------------------------------------------------------

@router.get("/unemployment-rate")
async def get_unemployment_rate(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """失業率（全国・若年層）データを返す"""
    return cn_unemployment_rate_service.get_data(force_refresh=force_refresh)


@router.get("/unemployment-rate/cache")
async def get_unemployment_rate_cache_status() -> Dict[str, Any]:
    """失業率のキャッシュ状態を返す"""
    return cn_unemployment_rate_service.get_cache_status()


@router.delete("/unemployment-rate/cache")
async def invalidate_unemployment_rate_cache() -> Dict[str, Any]:
    """失業率のキャッシュを無効化"""
    return cn_unemployment_rate_service.invalidate_cache()


# -------------------------------------------------------------------------
# GDP成長率（GDP Growth Rate）
# -------------------------------------------------------------------------

@router.get("/gdp-growth-rate")
async def get_gdp_growth_rate(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """GDP成長率（前年比・前期比）データを返す"""
    return cn_gdp_growth_rate_service.get_data(force_refresh=force_refresh)


@router.get("/gdp-growth-rate/cache")
async def get_gdp_growth_rate_cache_status() -> Dict[str, Any]:
    """GDP成長率のキャッシュ状態を返す"""
    return cn_gdp_growth_rate_service.get_cache_status()


@router.delete("/gdp-growth-rate/cache")
async def invalidate_gdp_growth_rate_cache() -> Dict[str, Any]:
    """GDP成長率のキャッシュを無効化"""
    return cn_gdp_growth_rate_service.invalidate_cache()


# -------------------------------------------------------------------------
# 鉱工業生産（Industrial Production）
# -------------------------------------------------------------------------

@router.get("/industrial-production")
async def get_industrial_production(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """鉱工業生産（前年比）データを返す"""
    return cn_industrial_production_service.get_data(force_refresh=force_refresh)


@router.get("/industrial-production/cache")
async def get_industrial_production_cache_status() -> Dict[str, Any]:
    """鉱工業生産のキャッシュ状態を返す"""
    return cn_industrial_production_service.get_cache_status()


@router.delete("/industrial-production/cache")
async def invalidate_industrial_production_cache() -> Dict[str, Any]:
    """鉱工業生産のキャッシュを無効化"""
    return cn_industrial_production_service.invalidate_cache()


# -------------------------------------------------------------------------
# 固定資産投資（Fixed Asset Investment）
# -------------------------------------------------------------------------

@router.get("/fixed-asset-investment")
async def get_fixed_asset_investment(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """固定資産投資（累計前年比）データを返す"""
    return cn_fixed_asset_investment_service.get_data(force_refresh=force_refresh)


@router.get("/fixed-asset-investment/cache")
async def get_fixed_asset_investment_cache_status() -> Dict[str, Any]:
    """固定資産投資のキャッシュ状態を返す"""
    return cn_fixed_asset_investment_service.get_cache_status()


@router.delete("/fixed-asset-investment/cache")
async def invalidate_fixed_asset_investment_cache() -> Dict[str, Any]:
    """固定資産投資のキャッシュを無効化"""
    return cn_fixed_asset_investment_service.invalidate_cache()


# -------------------------------------------------------------------------
# 北京PM2.5（Beijing PM2.5 Concentration）
# -------------------------------------------------------------------------

@router.get("/beijing-pm25")
async def get_beijing_pm25(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """北京PM2.5濃度（日次・月平均・30日移動平均）データを返す"""
    return cn_beijing_pm25_service.get_data(force_refresh=force_refresh)


@router.get("/beijing-pm25/cache")
async def get_beijing_pm25_cache_status() -> Dict[str, Any]:
    """北京PM2.5のキャッシュ状態を返す"""
    return cn_beijing_pm25_service.get_cache_status()


@router.delete("/beijing-pm25/cache")
async def invalidate_beijing_pm25_cache() -> Dict[str, Any]:
    """北京PM2.5のキャッシュを無効化"""
    return cn_beijing_pm25_service.invalidate_cache()


# -------------------------------------------------------------------------
# PMI（購買担当者景況指数）
# -------------------------------------------------------------------------

@router.get("/pmi")
async def get_pmi(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """NBS PMI（ヘッドライン + 製造業サブ + 非製造業サブ）データを返す"""
    return cn_pmi_service.get_data(force_refresh=force_refresh)


@router.get("/pmi/cache")
async def get_pmi_cache_status() -> Dict[str, Any]:
    """PMIのキャッシュ状態を返す"""
    return cn_pmi_service.get_cache_status()


@router.delete("/pmi/cache")
async def invalidate_pmi_cache() -> Dict[str, Any]:
    """PMIのキャッシュを無効化"""
    return cn_pmi_service.invalidate_cache()


# -------------------------------------------------------------------------
# Caixin PMI（財新PMI）
# -------------------------------------------------------------------------

@router.get("/caixin-pmi")
async def get_caixin_pmi(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """Caixin PMI（製造業 + サービス業）データを返す"""
    return cn_caixin_pmi_service.get_data(force_refresh=force_refresh)


@router.get("/caixin-pmi/cache")
async def get_caixin_pmi_cache_status() -> Dict[str, Any]:
    """Caixin PMIのキャッシュ状態を返す"""
    return cn_caixin_pmi_service.get_cache_status()


@router.delete("/caixin-pmi/cache")
async def invalidate_caixin_pmi_cache() -> Dict[str, Any]:
    """Caixin PMIのキャッシュを無効化"""
    return cn_caixin_pmi_service.invalidate_cache()


# -------------------------------------------------------------------------
# 貿易収支（Trade Balance）
# -------------------------------------------------------------------------

@router.get("/trade-balance")
async def get_trade_balance(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """貿易収支（収支 + 輸出 + 輸入 + YoY）データを返す"""
    return cn_trade_balance_service.get_data(force_refresh=force_refresh)


@router.get("/trade-balance/cache")
async def get_trade_balance_cache_status() -> Dict[str, Any]:
    """貿易収支のキャッシュ状態を返す"""
    return cn_trade_balance_service.get_cache_status()


@router.delete("/trade-balance/cache")
async def invalidate_trade_balance_cache() -> Dict[str, Any]:
    """貿易収支のキャッシュを無効化"""
    return cn_trade_balance_service.invalidate_cache()


# -------------------------------------------------------------------------
# 集積回路生産（Integrated Circuit Manufacturing）
# -------------------------------------------------------------------------

@router.get("/integrated-circuit-manufacturing")
async def get_integrated_circuit_manufacturing(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """集積回路生産（当期値・前年比・前月比）データを返す"""
    return cn_integrated_circuit_manufacturing_service.get_data(force_refresh=force_refresh)


@router.get("/integrated-circuit-manufacturing/cache")
async def get_integrated_circuit_manufacturing_cache_status() -> Dict[str, Any]:
    """集積回路生産のキャッシュ状態を返す"""
    return cn_integrated_circuit_manufacturing_service.get_cache_status()


@router.delete("/integrated-circuit-manufacturing/cache")
async def invalidate_integrated_circuit_manufacturing_cache() -> Dict[str, Any]:
    """集積回路生産のキャッシュを無効化"""
    return cn_integrated_circuit_manufacturing_service.invalidate_cache()


# -------------------------------------------------------------------------
# 電気機器在庫（Electronics Stock）
# -------------------------------------------------------------------------

@router.get("/electronics-stock")
async def get_electronics_stock(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """電気機器在庫（YoY + SOX指数先行）データを返す"""
    return cn_electronics_stock_service.get_data(force_refresh=force_refresh)


@router.get("/electronics-stock/cache")
async def get_electronics_stock_cache_status() -> Dict[str, Any]:
    """電気機器在庫のキャッシュ状態を返す"""
    return cn_electronics_stock_service.get_cache_status()


@router.delete("/electronics-stock/cache")
async def invalidate_electronics_stock_cache() -> Dict[str, Any]:
    """電気機器在庫のキャッシュを無効化"""
    return cn_electronics_stock_service.invalidate_cache()
