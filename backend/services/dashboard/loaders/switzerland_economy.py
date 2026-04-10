"""
スイス経済ダッシュボードローダー
GDP成長率、鉱工業生産などを一括取得

キャッシュ更新判定: FMP発表日時ベース判定
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class SwitzerlandEconomyLoader(BaseDashboardLoader):
    """
    スイス経済ダッシュボード用データローダー

    取得データ:
    - ch_growth_rate: GDP成長率（QoQ, YoY, 年率）
    - ch_industrial_production: 鉱工業生産（月次MoM/YoY、四半期QoQ/YoY）
    - ch_households_and_npish: 家計消費（QoQ, YoY）

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "switzerland"
    CATEGORY_CODE = "economy"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "ch_growth_rate",
        "ch_industrial_production",
        "ch_households_and_npish",
        "ch_pmi",
        "ch_balance_of_trade",
        "ch_current_account",
        "ch_current_account_gdp_ratio",
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
            print(f"[SwitzerlandEconomy] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全経済データを並列で取得

        Returns:
            {
                "ch_growth_rate": {...},
                "ch_industrial_production": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.switzerland.ch_growth_rate_service import ch_growth_rate_service
        from services.switzerland.ch_industrial_production_service import ch_industrial_production_service
        from services.switzerland.ch_households_and_npish_service import ch_households_and_npish_service
        from services.switzerland.ch_pmi_service import ch_pmi_service
        from services.switzerland.ch_balance_of_trade_service import ch_balance_of_trade_service
        from services.switzerland.ch_current_account_service import ch_current_account_service
        from services.switzerland.ch_current_account_gdp_ratio_service import ch_current_account_gdp_ratio_service

        result = {
            "ch_growth_rate": None,
            "ch_industrial_production": None,
            "ch_households_and_npish": None,
            "ch_pmi": None,
            "ch_balance_of_trade": None,
            "ch_current_account": None,
            "ch_current_account_gdp_ratio": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=7) as executor:
            futures = {
                executor.submit(self._get_growth_rate, ch_growth_rate_service): "ch_growth_rate",
                executor.submit(self._get_industrial_production, ch_industrial_production_service): "ch_industrial_production",
                executor.submit(self._get_households_and_npish, ch_households_and_npish_service): "ch_households_and_npish",
                executor.submit(self._get_pmi, ch_pmi_service): "ch_pmi",
                executor.submit(self._get_balance_of_trade, ch_balance_of_trade_service): "ch_balance_of_trade",
                executor.submit(self._get_current_account, ch_current_account_service): "ch_current_account",
                executor.submit(self._get_current_account_gdp_ratio, ch_current_account_gdp_ratio_service): "ch_current_account_gdp_ratio",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"[SwitzerlandEconomy] Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_growth_rate(self, service) -> dict:
        """GDP成長率データを取得"""
        try:
            force_refresh = self._should_force_refresh("ch_growth_rate")
            response = service.get_ch_growth_rate_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[SwitzerlandEconomy] Error getting GDP Growth Rate: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_industrial_production(self, service) -> dict:
        """鉱工業生産データを取得"""
        try:
            force_refresh = self._should_force_refresh("ch_industrial_production")
            response = service.get_ch_industrial_production_data(force_refresh=force_refresh)
            return {
                "monthly_data": response.get("monthly_data", []),
                "quarterly_data": response.get("quarterly_data", []),
                "latest_monthly": response.get("latest_monthly"),
                "latest_quarterly": response.get("latest_quarterly"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[SwitzerlandEconomy] Error getting Industrial Production: {e}")
            return {
                "monthly_data": [],
                "quarterly_data": [],
                "latest_monthly": None,
                "latest_quarterly": None,
                "metadata": {},
                "next_release": None,
            }

    def _get_households_and_npish(self, service) -> dict:
        """家計消費データを取得"""
        try:
            force_refresh = self._should_force_refresh("ch_households_and_npish")
            response = service.get_ch_households_and_npish_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[SwitzerlandEconomy] Error getting Households and NPISH: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_pmi(self, service) -> dict:
        """PMIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ch_pmi")
            response = service.get_pmi_data(force_refresh=force_refresh)
            return {
                "manufacturing_data": response.get("manufacturing_data", []),
                "services_data": response.get("services_data", []),
                "latest_manufacturing": response.get("latest_manufacturing"),
                "latest_services": response.get("latest_services"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[SwitzerlandEconomy] Error getting PMI: {e}")
            return {
                "manufacturing_data": [],
                "services_data": [],
                "latest_manufacturing": None,
                "latest_services": None,
                "metadata": {},
                "next_release": None,
            }

    def _get_balance_of_trade(self, service) -> dict:
        """貿易収支データを取得"""
        try:
            force_refresh = self._should_force_refresh("ch_balance_of_trade")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "mom_change": response.get("mom_change", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[SwitzerlandEconomy] Error getting Balance of Trade: {e}")
            return {"data": [], "mom_change": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_current_account(self, service) -> dict:
        """経常収支データを取得"""
        try:
            force_refresh = self._should_force_refresh("ch_current_account")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "qoq_change": response.get("qoq_change", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[SwitzerlandEconomy] Error getting Current Account: {e}")
            return {"data": [], "qoq_change": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_current_account_gdp_ratio(self, service) -> dict:
        """経常収支対GDP比データを取得"""
        try:
            force_refresh = self._should_force_refresh("ch_current_account_gdp_ratio")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[SwitzerlandEconomy] Error getting Current Account GDP Ratio: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}
