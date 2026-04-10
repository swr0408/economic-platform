"""
イギリス経済ダッシュボードローダー
ONS GDP、ONS GVA（月間GDP）、ONS Production Industries（鉱工業生産）、CBI製造業受注指数、UK PMIを一括取得

キャッシュ更新判定: FMP発表日時ベース更新
- ONS GDP: FMP GDP発表日時ベース更新
- ONS GVA: FMP GDP MoM/YoY発表日時ベース更新
- ONS Production: FMP Industrial Production MoM/YoY発表日時ベース更新
- CBI Industrial Trends: FMP CBI Industrial Trends Orders発表日時ベース更新
- UK PMI: FMP S&P Global PMI発表日時ベース更新
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class UKEconomyLoader(BaseDashboardLoader):
    """
    イギリス経済ダッシュボード用データローダー

    取得データ:
    - ons_gdp: ONS GDP成長率（前期比・前年比）
    - ons_gva: ONS GVA 月間GDP（ED3H: 3m on 3m、ECY2: 月次指数）
    - ons_production: ONS Production Industries 鉱工業生産（ED2T: YoY、ECYZ: MoM）
    - cbi_industrial_trends: CBI製造業受注指数
    - uk_pmi: UK S&P Global PMI（製造業・サービス業・総合）

    キャッシュ方式: FMP発表日時ベース更新
    """

    COUNTRY_CODE = "uk"
    CATEGORY_CODE = "economy"

    def __init__(self):
        super().__init__()
        self._stale_indicators: set = set()

    def get_expected_keys(self) -> List[str]:
        """
        期待されるデータキーのリストを返す
        キャッシュに含まれていなければ自動的に再取得する
        """
        return ["ons_gdp", "ons_gva", "ons_production", "cbi_industrial_trends", "uk_pmi", "uk_trade_balance", "uk_current_account", "uk_government_debt_to_gdp_ratio"]


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
        """
        データ再取得の前処理
        """
        self._stale_indicators = self._detect_stale_indicators(last_updated)
        if self._stale_indicators:
            print(f"Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全経済データを並列で取得

        Returns:
            {
                "ons_gdp": {...},
                "ons_gva": {...},
                "ons_production": {...},
                "cbi_industrial_trends": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.uk.ons_gdp_service import ons_gdp_service
        from services.uk.ons_gva_service import ons_gva_service
        from services.uk.ons_production_service import ons_production_service
        from services.uk.cbi_industrial_trends_service import cbi_industrial_trends_service
        from services.uk.uk_pmi_service import uk_pmi_service
        from services.uk.uk_trade_balance_service import uk_trade_balance_service
        from services.uk.uk_current_account_service import uk_current_account_service
        from services.uk.uk_government_debt_to_gdp_ratio_service import uk_government_debt_to_gdp_ratio_service

        result = {
            "ons_gdp": None,
            "ons_gva": None,
            "ons_production": None,
            "cbi_industrial_trends": None,
            "uk_pmi": None,
            "uk_trade_balance": None,
            "uk_current_account": None,
            "uk_government_debt_to_gdp_ratio": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(self._get_ons_gdp, ons_gdp_service): "ons_gdp",
                executor.submit(self._get_ons_gva, ons_gva_service): "ons_gva",
                executor.submit(self._get_ons_production, ons_production_service): "ons_production",
                executor.submit(self._get_cbi_industrial_trends, cbi_industrial_trends_service): "cbi_industrial_trends",
                executor.submit(self._get_uk_pmi, uk_pmi_service): "uk_pmi",
                executor.submit(self._get_uk_trade_balance, uk_trade_balance_service): "uk_trade_balance",
                executor.submit(self._get_uk_current_account, uk_current_account_service): "uk_current_account",
                executor.submit(self._get_uk_government_debt_to_gdp_ratio, uk_government_debt_to_gdp_ratio_service): "uk_government_debt_to_gdp_ratio",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_ons_gdp(self, service) -> dict:
        """ONS GDPデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ons_gdp")
            response = service.get_ons_gdp_data(force_refresh=force_refresh)
            return {
                "qoq": response.get("qoq", []),
                "yoy": response.get("yoy", []),
                "quarterly_data": response.get("quarterly_data", []),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ONS GDP: {e}")
            return {"qoq": [], "yoy": [], "quarterly_data": [], "metadata": {}, "next_release": None}

    def _get_ons_gva(self, service) -> dict:
        """ONS GVA（月間GDP）データを取得"""
        try:
            force_refresh = self._should_force_refresh("ons_gva")
            response = service.get_ons_gva_data(force_refresh=force_refresh)
            return {
                "ed3h": response.get("ed3h", {}),
                "ecy2": response.get("ecy2", {}),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ONS GVA: {e}")
            return {"ed3h": {}, "ecy2": {}, "metadata": {}, "next_release": None}

    def _get_ons_production(self, service) -> dict:
        """ONS Production Industries（鉱工業生産）データを取得"""
        try:
            force_refresh = self._should_force_refresh("ons_production")
            response = service.get_ons_production_data(force_refresh=force_refresh)
            return {
                "ed2t": response.get("ed2t", {}),
                "ecyz": response.get("ecyz", {}),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ONS Production: {e}")
            return {"ed2t": {}, "ecyz": {}, "metadata": {}, "next_release": None}

    def _get_cbi_industrial_trends(self, service) -> dict:
        """CBI製造業受注指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("cbi_industrial_trends")
            response = service.get_cbi_industrial_trends_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting CBI Industrial Trends: {e}")
            return {"data": [], "latest": None, "next_release": None}

    def _get_uk_pmi(self, service) -> dict:
        """UK PMIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("uk_pmi")
            response = service.get_uk_pmi_data(force_refresh=force_refresh)
            return {
                "manufacturing": response.get("manufacturing", []),
                "services": response.get("services", []),
                "composite": response.get("composite", []),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting UK PMI: {e}")
            return {"manufacturing": [], "services": [], "composite": [], "next_release": None}

    def _get_uk_current_account(self, service) -> dict:
        """UK経常収支データを取得"""
        try:
            force_refresh = self._should_force_refresh("uk_current_account")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "qoq_change": response.get("qoq_change", []),
                "gdp_ratio": response.get("gdp_ratio", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting UK Current Account: {e}")
            return {"data": [], "qoq_change": [], "gdp_ratio": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_uk_trade_balance(self, service) -> dict:
        """UK貿易収支データを取得"""
        try:
            force_refresh = self._should_force_refresh("uk_trade_balance")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "mom_change": response.get("mom_change", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting UK Trade Balance: {e}")
            return {"data": [], "mom_change": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_uk_government_debt_to_gdp_ratio(self, service) -> dict:
        """UK政府債務残高対GDP比データを取得"""
        try:
            force_refresh = self._should_force_refresh("uk_government_debt_to_gdp_ratio")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "mom_change": response.get("mom_change", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting UK Government Debt to GDP Ratio: {e}")
            return {"data": [], "mom_change": [], "latest": None, "metadata": {}, "next_release": None}
