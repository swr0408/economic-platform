"""
ニュージーランド経済ダッシュボードローダー
GDP成長率等を一括取得

キャッシュ更新判定: FMP発表日時ベース判定
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
AUCKLAND = ZoneInfo("Pacific/Auckland")


class NewZealandEconomyLoader(BaseDashboardLoader):
    """
    ニュージーランド経済ダッシュボード用データローダー

    取得データ:
    - nz_gdp_growth_rate: GDP成長率（QoQ・YoY）
    - nz_gdp_item: GDP項目別（HCE, GFCF, 輸出, 輸入, 在庫変動）

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "newzealand"
    CATEGORY_CODE = "economy"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "nz_gdp_growth_rate",
        "nz_gdp_item",
        "nz_capacity_utilization",
        "nz_pmi",
        "nz_psi",
        "nz_pci",
        "nz_global_dairy_trade",
        "nz_terms_of_trade",
        "nz_trade_balance",
        "nz_current_account_balance",
        "nz_current_account_gdp_ratio",
    ]

    def __init__(self):
        super().__init__()
        self._stale_indicators: set = set()

    def get_expected_keys(self) -> List[str]:
        """期待されるデータキーのリストを返す"""
        return self.EXPECTED_KEYS


    def _detect_stale_indicators(self, last_updated: Optional[str]) -> set:
        """
        発表日時を過ぎた指標を検出（FMPカレンダー自動判定）
        """
        if last_updated is None:
            return set()

        try:
            last_updated_dt = datetime.fromisoformat(last_updated)
            if last_updated_dt.tzinfo is None:
                last_updated_dt = last_updated_dt.replace(tzinfo=JST)

            now = datetime.now(JST)
            release_datetimes = self.get_release_datetimes()

            for release_dt in release_datetimes:
                if release_dt and last_updated_dt < release_dt <= now:
                    return {"all"}

        except Exception as e:
            print(f"Error detecting stale indicators: {e}")
            return {"all"}

        return set()

    def _should_force_refresh(self, indicator: str) -> bool:
        """指標が強制更新対象かどうかを判定"""
        if "all" in self._stale_indicators:
            return True
        return indicator in self._stale_indicators

    def _prepare_for_refresh(self, last_updated: Optional[str]) -> None:
        """データ再取得の前処理"""
        self._stale_indicators = self._detect_stale_indicators(last_updated)
        if self._stale_indicators:
            print(f"[NewZealandEconomy] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全経済データを取得

        Returns:
            {
                "nz_gdp_growth_rate": {...},
                "nz_gdp_item": {...},
                "nz_capacity_utilization": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.newzealand.nz_gdp_growth_rate_service import nz_gdp_growth_rate_service
        from services.newzealand.nz_gdp_item_service import nz_gdp_item_service
        from services.newzealand.nz_capacity_utilization_service import nz_capacity_utilization_service
        from services.newzealand.nz_pmi_service import nz_pmi_service
        from services.newzealand.nz_global_dairy_trade_service import nz_global_dairy_trade_service
        from services.newzealand.nz_terms_of_trade_service import nz_terms_of_trade_service
        from services.newzealand.nz_trade_balance_service import nz_trade_balance_service
        from services.newzealand.nz_current_account_balance_service import nz_current_account_balance_service
        from services.newzealand.nz_current_account_gdp_ratio_service import nz_current_account_gdp_ratio_service

        result = {
            "nz_gdp_growth_rate": None,
            "nz_gdp_item": None,
            "nz_capacity_utilization": None,
            "nz_pmi": None,
            "nz_psi": None,
            "nz_pci": None,
            "nz_global_dairy_trade": None,
            "nz_terms_of_trade": None,
            "nz_trade_balance": None,
            "nz_current_account_balance": None,
            "nz_current_account_gdp_ratio": None,
        }

        # データを取得
        result["nz_gdp_growth_rate"] = self._get_indicator(
            nz_gdp_growth_rate_service, "nz_gdp_growth_rate", "GDP Growth Rate"
        )
        result["nz_gdp_item"] = self._get_indicator(
            nz_gdp_item_service, "nz_gdp_item", "GDP Items"
        )
        result["nz_capacity_utilization"] = self._get_indicator(
            nz_capacity_utilization_service, "nz_capacity_utilization", "Capacity Utilization"
        )
        result["nz_pmi"] = self._get_pmi_indicator(nz_pmi_service, "pmi", "PMI")
        result["nz_psi"] = self._get_pmi_indicator(nz_pmi_service, "psi", "PSI")
        result["nz_pci"] = self._get_pmi_indicator(nz_pmi_service, "pci", "PCI")
        result["nz_global_dairy_trade"] = self._get_indicator(
            nz_global_dairy_trade_service, "nz_global_dairy_trade", "Global Dairy Trade"
        )
        result["nz_terms_of_trade"] = self._get_indicator(
            nz_terms_of_trade_service, "nz_terms_of_trade", "Terms of Trade"
        )
        result["nz_trade_balance"] = self._get_indicator(
            nz_trade_balance_service, "nz_trade_balance", "Trade Balance"
        )
        result["nz_current_account_balance"] = self._get_indicator(
            nz_current_account_balance_service, "nz_current_account_balance", "Current Account Balance"
        )
        result["nz_current_account_gdp_ratio"] = self._get_indicator(
            nz_current_account_gdp_ratio_service, "nz_current_account_gdp_ratio", "Current Account / GDP Ratio"
        )

        return result

    def _get_pmi_indicator(self, service, kind: str, label: str) -> dict:
        """PMI/PSI/PCI指標データを取得"""
        try:
            force_refresh = self._should_force_refresh(f"nz_{kind}")
            method = getattr(service, f"get_{kind}_data")
            response = method(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[NewZealandEconomy] Error getting {label}: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_indicator(self, service, indicator_key: str, label: str) -> dict:
        """指標データを取得"""
        try:
            force_refresh = self._should_force_refresh(indicator_key)
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[NewZealandEconomy] Error getting {label}: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}
