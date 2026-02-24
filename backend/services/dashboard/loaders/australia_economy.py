"""
オーストラリア経済ダッシュボードローダー
GDP成長率など経済関連指標を一括取得

キャッシュ更新判定: FMP発表日時ベース判定
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
SYDNEY = ZoneInfo("Australia/Sydney")


class AustraliaEconomyLoader(BaseDashboardLoader):
    """
    オーストラリア経済ダッシュボード用データローダー

    取得データ:
    - au_gdp_growth_rate: GDP成長率（QoQ/YoY）
    - au_gdp_price_related: GDP詳細（デフレーター/純輸出寄与/GFCF/消費）
    - au_private_new_capital_expenditure: 民間新規設備投資（QoQ/YoY）
    - au_international_trade: 国際貿易（貿易収支・輸出・輸入、月次）
    - au_current_account: 経常収支（四半期）
    - au_pmi: S&P Global PMI（製造業/サービス業/総合）
    - au_terms_of_trade: 交易条件（Index/QoQ%/YoY%）

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "australia"
    CATEGORY_CODE = "economy"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "au_gdp_growth_rate",
        "au_gdp_price_related",
        "au_private_new_capital_expenditure",
        "au_international_trade",
        "au_current_account",
        "au_current_account_gdp_ratio",
        "au_pmi",
        "au_terms_of_trade",
    ]

    def __init__(self):
        super().__init__()
        self._stale_indicators: set = set()

    def get_expected_keys(self) -> List[str]:
        """期待されるデータキーのリストを返す"""
        return self.EXPECTED_KEYS

    def get_release_datetimes(self) -> List[Optional[datetime]]:
        """各指標の発表日時リストを返す"""
        return []

    def _detect_stale_indicators(self, last_updated: Optional[str]) -> set:
        """発表日時を過ぎた指標を検出"""
        stale = set()

        if last_updated is None:
            return stale

        return stale

    def _should_force_refresh(self, indicator: str) -> bool:
        """指標が強制更新対象かどうかを判定"""
        if "all" in self._stale_indicators:
            return True
        return indicator in self._stale_indicators

    def _prepare_for_refresh(self, last_updated: Optional[str]) -> None:
        """データ再取得の前処理"""
        self._stale_indicators = self._detect_stale_indicators(last_updated)
        if self._stale_indicators:
            print(f"[AustraliaEconomy] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全経済データを取得

        Returns:
            {
                "au_gdp_growth_rate": {...},
                "au_gdp_price_related": {...},
                "au_private_new_capital_expenditure": {...},
                "au_international_trade": {...},
                "au_current_account": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.australia.au_gdp_growth_rate_service import au_gdp_growth_rate_service
        from services.australia.au_gdp_price_related_service import au_gdp_price_related_service
        from services.australia.au_private_new_capital_expenditure_service import au_private_new_capital_expenditure_service
        from services.australia.au_international_trade_service import au_international_trade_service
        from services.australia.au_current_account_service import au_current_account_service
        from services.australia.au_current_account_gdp_ratio_service import au_current_account_gdp_ratio_service
        from services.australia.au_pmi_service import au_pmi_service
        from services.australia.au_terms_of_trade_service import au_terms_of_trade_service

        result = {
            "au_gdp_growth_rate": None,
            "au_gdp_price_related": None,
            "au_private_new_capital_expenditure": None,
            "au_international_trade": None,
            "au_current_account": None,
            "au_current_account_gdp_ratio": None,
            "au_pmi": None,
            "au_terms_of_trade": None,
        }

        # データを取得
        result["au_gdp_growth_rate"] = self._get_gdp_growth_rate(au_gdp_growth_rate_service)
        result["au_gdp_price_related"] = self._get_gdp_price_related(au_gdp_price_related_service)
        result["au_private_new_capital_expenditure"] = self._get_private_capex(au_private_new_capital_expenditure_service)
        result["au_international_trade"] = self._get_international_trade(au_international_trade_service)
        result["au_current_account"] = self._get_current_account(au_current_account_service)
        result["au_current_account_gdp_ratio"] = self._get_current_account_gdp_ratio(au_current_account_gdp_ratio_service)
        result["au_pmi"] = self._get_pmi(au_pmi_service)
        result["au_terms_of_trade"] = self._get_terms_of_trade(au_terms_of_trade_service)

        return result

    def _get_gdp_growth_rate(self, service) -> dict:
        """GDP成長率データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_gdp_growth_rate")
            response = service.get_au_gdp_growth_rate_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaEconomy] Error getting GDP Growth Rate: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_gdp_price_related(self, service) -> dict:
        """GDP詳細データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_gdp_price_related")
            response = service.get_au_gdp_price_related_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaEconomy] Error getting GDP Detail: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_private_capex(self, service) -> dict:
        """民間新規設備投資データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_private_new_capital_expenditure")
            response = service.get_au_private_new_capital_expenditure_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaEconomy] Error getting Private CAPEX: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_international_trade(self, service) -> dict:
        """国際貿易データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_international_trade")
            response = service.get_au_international_trade_data(force_refresh=force_refresh)
            return {
                "balance": response.get("balance", []),
                "exports": response.get("exports", []),
                "imports": response.get("imports", []),
                "balance_mom_diff": response.get("balance_mom_diff", []),
                "exports_mom": response.get("exports_mom", []),
                "exports_yoy": response.get("exports_yoy", []),
                "imports_mom": response.get("imports_mom", []),
                "imports_yoy": response.get("imports_yoy", []),
                "latest_balance": response.get("latest_balance"),
                "latest_exports": response.get("latest_exports"),
                "latest_imports": response.get("latest_imports"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaEconomy] Error getting International Trade: {e}")
            return {
                "balance": [], "exports": [], "imports": [],
                "balance_mom_diff": [], "exports_mom": [], "exports_yoy": [],
                "imports_mom": [], "imports_yoy": [],
                "latest_balance": None, "latest_exports": None, "latest_imports": None,
                "metadata": {}, "next_release": None,
            }

    def _get_current_account(self, service) -> dict:
        """経常収支データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_current_account")
            response = service.get_au_current_account_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "qoq_diff": response.get("qoq_diff", []),
                "yoy_diff": response.get("yoy_diff", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaEconomy] Error getting Current Account: {e}")
            return {"data": [], "qoq_diff": [], "yoy_diff": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_current_account_gdp_ratio(self, service) -> dict:
        """経常収支対GDP比データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_current_account_gdp_ratio")
            response = service.get_au_current_account_gdp_ratio_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaEconomy] Error getting Current Account GDP Ratio: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_pmi(self, service) -> dict:
        """S&P Global PMIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("au_pmi")
            response = service.get_au_pmi_data(force_refresh=force_refresh)
            return {
                "manufacturing": response.get("manufacturing"),
                "services": response.get("services"),
                "composite": response.get("composite"),
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated"),
            }
        except Exception as e:
            print(f"[AustraliaEconomy] Error getting PMI: {e}")
            return {"manufacturing": None, "services": None, "composite": None, "next_release": None, "last_updated": None}

    def _get_terms_of_trade(self, service) -> dict:
        """交易条件データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_terms_of_trade")
            response = service.get_au_terms_of_trade_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaEconomy] Error getting Terms of Trade: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}
