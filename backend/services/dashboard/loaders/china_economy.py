"""
中国経済ダッシュボードローダー
GDP成長率（前年比・前期比）、鉱工業生産（前年比）、固定資産投資（累計前年比）を一括取得

キャッシュ更新判定: NBS発表日時ベース
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo

from services.dashboard.loaders.base import BaseDashboardLoader


JST = ZoneInfo("Asia/Tokyo")
CST = ZoneInfo("Asia/Shanghai")


class ChinaEconomyLoader(BaseDashboardLoader):
    """
    中国経済ダッシュボード用データローダー

    取得データ:
    - cn_gdp_growth_rate: GDP成長率（前年比・前期比）
    - cn_industrial_production: 鉱工業生産（前年比）
    - cn_fixed_asset_investment: 固定資産投資（累計前年比）
    """

    COUNTRY_CODE = "china"
    CATEGORY_CODE = "economy"

    EXPECTED_KEYS = [
        "cn_gdp_growth_rate",
        "cn_industrial_production",
        "cn_fixed_asset_investment",
        "cn_beijing_pm25",
        "cn_pmi",
        "cn_caixin_pmi",
        "cn_trade_balance",
        "cn_current_account",
        "cn_current_account_gdp_ratio",
        "cn_land_sales_income",
        "cn_integrated_circuit_manufacturing",
        "cn_electronics_stock",
    ]

    def __init__(self):
        super().__init__()
        self._stale_indicators: set = set()

    def get_expected_keys(self) -> List[str]:
        return self.EXPECTED_KEYS

    def get_release_datetimes(self) -> List[Optional[datetime]]:
        return []

    def _detect_stale_indicators(self, last_updated: Optional[str]) -> set:
        stale = set()
        if last_updated is None:
            return stale
        return stale

    def _should_force_refresh(self, indicator: str) -> bool:
        if "all" in self._stale_indicators:
            return True
        return indicator in self._stale_indicators

    def _prepare_for_refresh(self, last_updated: Optional[str]) -> None:
        self._stale_indicators = self._detect_stale_indicators(last_updated)
        if self._stale_indicators:
            print(f"[ChinaEconomy] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        from services.china.cn_gdp_growth_rate_service import cn_gdp_growth_rate_service
        from services.china.cn_industrial_production_service import cn_industrial_production_service
        from services.china.cn_fixed_asset_investment_service import cn_fixed_asset_investment_service
        from services.china.cn_beijing_pm25_service import cn_beijing_pm25_service
        from services.china.cn_pmi_service import cn_pmi_service
        from services.china.cn_caixin_pmi_service import cn_caixin_pmi_service
        from services.china.cn_trade_balance_service import cn_trade_balance_service
        from services.china.cn_current_account_service import cn_current_account_service
        from services.china.cn_current_account_gdp_ratio_service import cn_current_account_gdp_ratio_service
        from services.china.cn_land_sales_income_service import cn_land_sales_income_service
        from services.china.cn_integrated_circuit_manufacturing_service import cn_integrated_circuit_manufacturing_service
        from services.china.cn_electronics_stock_service import cn_electronics_stock_service

        result = {
            "cn_gdp_growth_rate": None,
            "cn_industrial_production": None,
            "cn_fixed_asset_investment": None,
            "cn_beijing_pm25": None,
            "cn_pmi": None,
            "cn_caixin_pmi": None,
            "cn_trade_balance": None,
            "cn_current_account": None,
            "cn_current_account_gdp_ratio": None,
            "cn_land_sales_income": None,
            "cn_integrated_circuit_manufacturing": None,
            "cn_electronics_stock": None,
        }

        result["cn_gdp_growth_rate"] = self._get_generic_indicator(
            cn_gdp_growth_rate_service,
            "cn_gdp_growth_rate",
            "GDP Growth Rate",
        )

        result["cn_industrial_production"] = self._get_generic_indicator(
            cn_industrial_production_service,
            "cn_industrial_production",
            "Industrial Production",
        )

        result["cn_fixed_asset_investment"] = self._get_generic_indicator(
            cn_fixed_asset_investment_service,
            "cn_fixed_asset_investment",
            "Fixed Asset Investment",
        )

        result["cn_beijing_pm25"] = self._get_beijing_pm25(cn_beijing_pm25_service)

        result["cn_pmi"] = self._get_pmi(cn_pmi_service)

        result["cn_caixin_pmi"] = self._get_caixin_pmi(cn_caixin_pmi_service)

        result["cn_trade_balance"] = self._get_trade_balance(cn_trade_balance_service)

        result["cn_current_account"] = self._get_current_account(cn_current_account_service)

        result["cn_current_account_gdp_ratio"] = self._get_ca_gdp_ratio(cn_current_account_gdp_ratio_service)

        result["cn_land_sales_income"] = self._get_generic_indicator(
            cn_land_sales_income_service,
            "cn_land_sales_income",
            "Land Sales Income",
        )

        result["cn_integrated_circuit_manufacturing"] = self._get_generic_indicator(
            cn_integrated_circuit_manufacturing_service,
            "cn_integrated_circuit_manufacturing",
            "Integrated Circuit Manufacturing",
        )

        result["cn_electronics_stock"] = self._get_electronics_stock(cn_electronics_stock_service)

        return result

    def _get_beijing_pm25(self, service) -> dict:
        try:
            force_refresh = self._should_force_refresh("cn_beijing_pm25")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "daily": response.get("daily", []),
                "monthly": response.get("monthly", []),
                "ma30": response.get("ma30", []),
                "latest": response.get("latest"),
                "latest_monthly": response.get("latest_monthly"),
                "metadata": response.get("metadata", {}),
            }
        except Exception as e:
            print(f"[ChinaEconomy] Error getting Beijing PM2.5: {e}")
            return {"daily": [], "monthly": [], "ma30": [], "latest": None, "latest_monthly": None, "metadata": {}}

    def _get_pmi(self, service) -> dict:
        try:
            force_refresh = self._should_force_refresh("cn_pmi")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "headline": response.get("headline"),
                "manufacturing_sub": response.get("manufacturing_sub"),
                "non_manufacturing_sub": response.get("non_manufacturing_sub"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[ChinaEconomy] Error getting PMI: {e}")
            return {
                "headline": None,
                "manufacturing_sub": None,
                "non_manufacturing_sub": None,
                "metadata": {},
                "next_release": None,
            }

    def _get_caixin_pmi(self, service) -> dict:
        try:
            force_refresh = self._should_force_refresh("cn_caixin_pmi")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "manufacturing": response.get("manufacturing"),
                "services": response.get("services"),
                "next_release_manufacturing": response.get("next_release_manufacturing"),
                "next_release_services": response.get("next_release_services"),
                "metadata": response.get("metadata", {}),
            }
        except Exception as e:
            print(f"[ChinaEconomy] Error getting Caixin PMI: {e}")
            return {
                "manufacturing": None,
                "services": None,
                "next_release_manufacturing": None,
                "next_release_services": None,
                "metadata": {},
            }

    def _get_generic_indicator(self, service, key: str, label: str) -> dict:
        try:
            force_refresh = self._should_force_refresh(key)
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[ChinaEconomy] Error getting {label}: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_trade_balance(self, service) -> dict:
        try:
            force_refresh = self._should_force_refresh("cn_trade_balance")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "balance": response.get("balance", []),
                "exports": response.get("exports", []),
                "imports": response.get("imports", []),
                "balance_yoy": response.get("balance_yoy", []),
                "exports_yoy": response.get("exports_yoy", []),
                "imports_yoy": response.get("imports_yoy", []),
                "balance_mom_diff": response.get("balance_mom_diff", []),
                "exports_mom_diff": response.get("exports_mom_diff", []),
                "imports_mom_diff": response.get("imports_mom_diff", []),
                "latest_balance": response.get("latest_balance"),
                "latest_exports": response.get("latest_exports"),
                "latest_imports": response.get("latest_imports"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[ChinaEconomy] Error getting Trade Balance: {e}")
            return {
                "balance": [], "exports": [], "imports": [],
                "balance_yoy": [], "exports_yoy": [], "imports_yoy": [],
                "balance_mom_diff": [], "exports_mom_diff": [], "imports_mom_diff": [],
                "latest_balance": None, "latest_exports": None, "latest_imports": None,
                "metadata": {}, "next_release": None,
            }

    def _get_current_account(self, service) -> dict:
        try:
            force_refresh = self._should_force_refresh("cn_current_account")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "qoq_diff": response.get("qoq_diff", []),
                "yoy_diff": response.get("yoy_diff", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[ChinaEconomy] Error getting Current Account: {e}")
            return {
                "data": [], "qoq_diff": [], "yoy_diff": [],
                "latest": None, "metadata": {}, "next_release": None,
            }

    def _get_electronics_stock(self, service) -> dict:
        try:
            force_refresh = self._should_force_refresh("cn_electronics_stock")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "sox_data": response.get("sox_data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[ChinaEconomy] Error getting Electronics Stock: {e}")
            return {"data": [], "sox_data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ca_gdp_ratio(self, service) -> dict:
        try:
            force_refresh = self._should_force_refresh("cn_current_account_gdp_ratio")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[ChinaEconomy] Error getting CA/GDP Ratio: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}
