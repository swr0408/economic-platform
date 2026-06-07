"""
NBS月次データ DB蓄積ユーティリティ

nbs_monthly_data テーブルへのCSVインポートとAPIデータ蓄積を共通化。
複数指標（PPI、失業率、商業住宅販売等）で共有。

テーブル構造:
    indicator VARCHAR(64)  -- 指標ID（例: cn_ppi_yoy, cn_unemployment_total）
    date      DATE         -- データ日付（YYYY-MM-01）
    value     DECIMAL      -- 値
    source    VARCHAR(16)  -- 'csv' or 'api'
    PRIMARY KEY (indicator, date)
"""
import logging
from datetime import date
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# DB indicator ID → (サービスパス, ダッシュボードカテゴリ)
# CSVインポート時にこのマップに従って関連サービスキャッシュ＋ダッシュボードキャッシュを無効化する。
# サービスを循環インポートで呼ばないよう、パス文字列で保持。
# ダッシュボードカテゴリは services/dashboard/loaders/china_<category>.py と一致。
_DB_INDICATOR_TO_SERVICE_MAP: Dict[str, Tuple[str, str]] = {
    # --- 経済（economy）---
    "cn_gdp_yoy": ("services.china.cn_gdp_growth_rate_service:cn_gdp_growth_rate_service", "economy"),
    "cn_gdp_qoq": ("services.china.cn_gdp_growth_rate_service:cn_gdp_growth_rate_service", "economy"),
    "cn_industrial_production_yoy": ("services.china.cn_industrial_production_service:cn_industrial_production_service", "economy"),
    "cn_fixed_asset_investment_ytd": ("services.china.cn_fixed_asset_investment_service:cn_fixed_asset_investment_service", "economy"),
    "cn_electronics_stock_yoy": ("services.china.cn_electronics_stock_service:cn_electronics_stock_service", "economy"),
    "cn_ic_raw": ("services.china.cn_integrated_circuit_manufacturing_service:cn_integrated_circuit_manufacturing_service", "economy"),
    "cn_ic_yoy": ("services.china.cn_integrated_circuit_manufacturing_service:cn_integrated_circuit_manufacturing_service", "economy"),
    # 貿易収支（cn_trade_balance_service, DB_INDICATORS）
    "cn_trade_balance": ("services.china.cn_trade_balance_service:cn_trade_balance_service", "economy"),
    "cn_exports": ("services.china.cn_trade_balance_service:cn_trade_balance_service", "economy"),
    "cn_imports": ("services.china.cn_trade_balance_service:cn_trade_balance_service", "economy"),
    "cn_exports_yoy": ("services.china.cn_trade_balance_service:cn_trade_balance_service", "economy"),
    "cn_imports_yoy": ("services.china.cn_trade_balance_service:cn_trade_balance_service", "economy"),
    # PMI系（cn_pmi_service, NBS_API_CODES → DB indicator）
    "cn_pmi_composite": ("services.china.cn_pmi_service:cn_pmi_service", "economy"),
    "cn_pmi_manufacturing": ("services.china.cn_pmi_service:cn_pmi_service", "economy"),
    "cn_pmi_non_manufacturing": ("services.china.cn_pmi_service:cn_pmi_service", "economy"),
    "cn_pmi_mfg_production": ("services.china.cn_pmi_service:cn_pmi_service", "economy"),
    "cn_pmi_mfg_new_orders": ("services.china.cn_pmi_service:cn_pmi_service", "economy"),
    "cn_pmi_mfg_new_export_orders": ("services.china.cn_pmi_service:cn_pmi_service", "economy"),
    "cn_pmi_mfg_in_hand_orders": ("services.china.cn_pmi_service:cn_pmi_service", "economy"),
    "cn_pmi_mfg_employment": ("services.china.cn_pmi_service:cn_pmi_service", "economy"),
    "cn_pmi_mfg_raw_material_price": ("services.china.cn_pmi_service:cn_pmi_service", "economy"),
    "cn_pmi_mfg_producer_prices": ("services.china.cn_pmi_service:cn_pmi_service", "economy"),
    "cn_pmi_mfg_supplier_delivery": ("services.china.cn_pmi_service:cn_pmi_service", "economy"),
    "cn_pmi_nmf_services": ("services.china.cn_pmi_service:cn_pmi_service", "economy"),
    "cn_pmi_nmf_construction": ("services.china.cn_pmi_service:cn_pmi_service", "economy"),
    "cn_pmi_nmf_new_orders": ("services.china.cn_pmi_service:cn_pmi_service", "economy"),
    "cn_pmi_nmf_export_new_orders": ("services.china.cn_pmi_service:cn_pmi_service", "economy"),
    "cn_pmi_nmf_in_hand_orders": ("services.china.cn_pmi_service:cn_pmi_service", "economy"),
    "cn_pmi_nmf_sale_price": ("services.china.cn_pmi_service:cn_pmi_service", "economy"),
    "cn_pmi_nmf_input_price": ("services.china.cn_pmi_service:cn_pmi_service", "economy"),
    "cn_pmi_nmf_supplier_delivery": ("services.china.cn_pmi_service:cn_pmi_service", "economy"),
    "cn_pmi_nmf_employment": ("services.china.cn_pmi_service:cn_pmi_service", "economy"),
    # --- 物価（inflation）---
    "cn_cpi_yoy": ("services.china.cn_cpi_service:cn_cpi_service", "inflation"),
    "cn_cpi_mom": ("services.china.cn_cpi_service:cn_cpi_service", "inflation"),
    "cn_cpi_food_yoy": ("services.china.cn_cpi_service:cn_cpi_service", "inflation"),
    "cn_cpi_food_mom": ("services.china.cn_cpi_service:cn_cpi_service", "inflation"),
    "cn_cpi_nonfood_yoy": ("services.china.cn_cpi_service:cn_cpi_service", "inflation"),
    "cn_cpi_nonfood_mom": ("services.china.cn_cpi_service:cn_cpi_service", "inflation"),
    "cn_cpi_core_yoy": ("services.china.cn_cpi_service:cn_cpi_service", "inflation"),
    "cn_cpi_core_mom": ("services.china.cn_cpi_service:cn_cpi_service", "inflation"),
    "cn_ppi_yoy": ("services.china.cn_ppi_service:cn_ppi_service", "inflation"),
    "cn_ppi_mom": ("services.china.cn_ppi_service:cn_ppi_service", "inflation"),
    "cn_export_prices_index": ("services.china.cn_export_prices_service:cn_export_prices_service", "inflation"),
    "cn_export_prices_yoy": ("services.china.cn_export_prices_service:cn_export_prices_service", "inflation"),
    # --- 雇用（employment）---
    "cn_unemployment_total": ("services.china.cn_unemployment_rate_service:cn_unemployment_rate_service", "employment"),
    "cn_unemployment_youth": ("services.china.cn_unemployment_rate_service:cn_unemployment_rate_service", "employment"),
    # --- 消費（consumer）---
    "cn_retail_sales_yoy": ("services.china.cn_retail_sales_service:cn_retail_sales_service", "consumer"),
    # --- 住宅（housing）---
    "cn_re_floor_started_yoy": ("services.china.cn_commercial_residential_sales_service:cn_commercial_residential_sales_service", "housing"),
    "cn_re_sales_yoy": ("services.china.cn_commercial_residential_sales_service:cn_commercial_residential_sales_service", "housing"),
    "cn_re_floor_sold_yoy": ("services.china.cn_commercial_residential_sales_service:cn_commercial_residential_sales_service", "housing"),
}


def _invalidate_related_caches(indicator: str) -> None:
    """DB指標IDに紐づくサービスキャッシュ＋ダッシュボードキャッシュを無効化

    CSVインポートで大量データを再取り込みしたときに、古い部分キャッシュが残らないよう、
    サービスキャッシュ（Redis + ファイル）と該当カテゴリのダッシュボードキャッシュをクリア。
    """
    mapping = _DB_INDICATOR_TO_SERVICE_MAP.get(indicator)
    if not mapping:
        logger.debug(f"[NBS-DB] No cache invalidation mapping for indicator '{indicator}'")
        return

    service_path, dashboard_category = mapping

    # 1. サービスキャッシュ無効化（Redis + ファイル）
    try:
        module_path, attr = service_path.split(":")
        import importlib
        module = importlib.import_module(module_path)
        service = getattr(module, attr)
        service.invalidate_cache()
        logger.info(f"[NBS-DB] Invalidated service cache for {indicator} → {attr}")
    except Exception as e:
        logger.warning(f"[NBS-DB] Failed to invalidate service cache for {service_path}: {e}")

    # 2. 該当カテゴリのダッシュボードキャッシュ無効化
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, db=0, socket_timeout=2)
        dashboard_keys = [
            f"china:{dashboard_category}:dashboard:v1",
            f"china:{dashboard_category}:dashboard:v1:light",
            f"china:{dashboard_category}:dashboard:v1:heavy",
        ]
        for key in dashboard_keys:
            if r.exists(key):
                r.delete(key)
                logger.info(f"[NBS-DB] Invalidated dashboard cache: {key}")
    except Exception as e:
        logger.warning(f"[NBS-DB] Failed to invalidate dashboard cache: {e}")


def upsert_nbs_data(
    indicator: str,
    data: Dict[str, float],
    source: str = "api",
) -> int:
    """NBS月次データをDBに一括UPSERT

    Args:
        indicator: 指標ID（例: 'cn_ppi_yoy'）
        data: {date_str: value, ...} e.g. {"2026-01-01": -1.4}
        source: データソース ('csv' or 'api')

    Returns:
        追加/更新件数
    """
    if not data:
        return 0

    try:
        from core.database import SessionLocal
        from sqlalchemy import text

        count = 0
        with SessionLocal() as session:
            for date_str, value in data.items():
                session.execute(text("""
                    INSERT INTO nbs_monthly_data (indicator, date, value, source, updated_at)
                    VALUES (:ind, :dt, :val, :src, CURRENT_TIMESTAMP)
                    ON CONFLICT (indicator, date)
                    DO UPDATE SET value = :val, source = :src, updated_at = CURRENT_TIMESTAMP
                """), {"ind": indicator, "dt": date_str, "val": value, "src": source})
                count += 1
            session.commit()
        logger.info(f"[NBS-DB] {indicator}: upserted {count} records (source={source})")

        # CSV インポート時は関連サービスキャッシュを無効化
        # （API取得経由の upsert は少量の最新データのみなのでキャッシュ無効化しない）
        if source == "csv" and count > 0:
            _invalidate_related_caches(indicator)

        return count
    except Exception as e:
        logger.warning(f"[NBS-DB] {indicator}: upsert failed: {e}")
        return 0


def load_nbs_data(indicator: str) -> Dict[str, float]:
    """DBから指標の全データを取得

    Args:
        indicator: 指標ID

    Returns:
        {date_str: value, ...} 日付昇順
    """
    try:
        from core.database import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as session:
            rows = session.execute(text("""
                SELECT date, value
                FROM nbs_monthly_data
                WHERE indicator = :ind
                ORDER BY date ASC
            """), {"ind": indicator}).fetchall()

        result = {}
        for row in rows:
            date_str = row[0].isoformat() if isinstance(row[0], date) else str(row[0])
            result[date_str] = float(row[1])
        return result
    except Exception as e:
        logger.warning(f"[NBS-DB] {indicator}: load failed: {e}")
        return {}


def load_nbs_multi(indicators: List[str]) -> Dict[str, Dict[str, float]]:
    """DBから複数指標のデータを一括取得

    Args:
        indicators: 指標IDリスト

    Returns:
        {indicator: {date_str: value, ...}, ...}
    """
    try:
        from core.database import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as session:
            # IN句で一括取得
            placeholders = ", ".join(f":ind{i}" for i in range(len(indicators)))
            params = {f"ind{i}": ind for i, ind in enumerate(indicators)}
            rows = session.execute(text(f"""
                SELECT indicator, date, value
                FROM nbs_monthly_data
                WHERE indicator IN ({placeholders})
                ORDER BY indicator, date ASC
            """), params).fetchall()

        result: Dict[str, Dict[str, float]] = {ind: {} for ind in indicators}
        for row in rows:
            ind = row[0]
            date_str = row[1].isoformat() if isinstance(row[1], date) else str(row[1])
            result[ind][date_str] = float(row[2])
        return result
    except Exception as e:
        logger.warning(f"[NBS-DB] multi load failed: {e}")
        return {ind: {} for ind in indicators}


def get_latest_date(indicator: str) -> Optional[str]:
    """指標のDB内最新日付を取得"""
    try:
        from core.database import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as session:
            row = session.execute(text("""
                SELECT MAX(date) FROM nbs_monthly_data WHERE indicator = :ind
            """), {"ind": indicator}).scalar()

        if row:
            return row.isoformat() if isinstance(row, date) else str(row)
        return None
    except Exception as e:
        logger.warning(f"[NBS-DB] {indicator}: get_latest_date failed: {e}")
        return None


def get_record_count(indicator: str) -> int:
    """指標のレコード数を取得"""
    try:
        from core.database import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as session:
            return session.execute(text("""
                SELECT COUNT(*) FROM nbs_monthly_data WHERE indicator = :ind
            """), {"ind": indicator}).scalar() or 0
    except Exception as e:
        return 0
