"""
日本経済ダッシュボードローダー
GDP、鉱工業生産、第三次産業活動指数、機械受注、設備投資など経済指標を一括取得

キャッシュ更新判定: FMP発表日時ベース更新
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class JapanEconomyLoader(BaseDashboardLoader):
    """
    日本経済ダッシュボード用データローダー

    取得データ:
    - quarterly_gdp: 四半期GDP成長率（前期比・前期比年率・前年比）
    - iip: 鉱工業生産指数（前月比）
    - iip_yoy: 鉱工業生産指数（前年比）
    - tertiary_industry: 第三次産業活動指数（前月比・前年比）
    - machinery_orders: 機械受注
    - machine_tool_orders: 工作機械受注
    - capital_investment: 設備投資

    キャッシュ方式: FMP発表日時ベース更新
    """

    COUNTRY_CODE = "japan"
    CATEGORY_CODE = "economy"

    def __init__(self):
        super().__init__()
        self._stale_indicators: set = set()

    def get_expected_keys(self) -> List[str]:
        """
        期待されるデータキーのリストを返す
        """
        return [
            "quarterly_gdp",
            "iip",
            "iip_yoy",
            "tertiary_industry",
            "machinery_orders",
            "machine_tool_orders",
            "capital_investment",
            "current_account",
            "current_account_gdp_ratio",
            "balance_of_trade",
        ]


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
            # エラー時に {"all"} を返すと、エラーが続く限り毎リクエストで全指標の
            # 外部API一斉取得が走りイベントループ/executorを圧迫する (2026-06-13 障害)。
            # 判定不能時はキャッシュ継続に倒す (各サービスのスケジューラが個別に更新する)。
            return set()

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
                "quarterly_gdp": {...},
                "iip": {...},
                "iip_yoy": {...},
                "tertiary_industry": {...},
                "machinery_orders": {...},
                "machine_tool_orders": {...},
                "capital_investment": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.japan.quarterly_gdp_service import quarterly_gdp_service
        from services.japan.japan_iip_service import japan_iip_service
        from services.japan.japan_iip_yoy_service import japan_iip_yoy_service
        from services.japan.tertiary_industry_index_service import tertiary_industry_index_service
        from services.japan.machinery_orders_service import machinery_orders_service
        from services.japan.machine_tool_orders_service import machine_tool_orders_service
        from services.japan.capital_investment_service import capital_investment_service
        from services.japan.japan_current_account_service import japan_current_account_service
        from services.japan.japan_current_account_gdp_ratio_service import japan_current_account_gdp_ratio_service
        from services.japan.japan_balance_of_trade_service import japan_balance_of_trade_service

        result = {
            "quarterly_gdp": None,
            "iip": None,
            "iip_yoy": None,
            "tertiary_industry": None,
            "machinery_orders": None,
            "machine_tool_orders": None,
            "capital_investment": None,
            "current_account": None,
            "current_account_gdp_ratio": None,
            "balance_of_trade": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(self._get_quarterly_gdp, quarterly_gdp_service): "quarterly_gdp",
                executor.submit(self._get_iip, japan_iip_service): "iip",
                executor.submit(self._get_iip_yoy, japan_iip_yoy_service): "iip_yoy",
                executor.submit(self._get_tertiary_industry, tertiary_industry_index_service): "tertiary_industry",
                executor.submit(self._get_machinery_orders, machinery_orders_service): "machinery_orders",
                executor.submit(self._get_machine_tool_orders, machine_tool_orders_service): "machine_tool_orders",
                executor.submit(self._get_capital_investment, capital_investment_service): "capital_investment",
                executor.submit(self._get_current_account, japan_current_account_service): "current_account",
                executor.submit(self._get_current_account_gdp_ratio, japan_current_account_gdp_ratio_service): "current_account_gdp_ratio",
                executor.submit(self._get_balance_of_trade, japan_balance_of_trade_service): "balance_of_trade",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_quarterly_gdp(self, service) -> dict:
        """四半期GDPデータを取得"""
        try:
            force_refresh = self._should_force_refresh("quarterly_gdp")
            response = service.get_quarterly_gdp_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting Quarterly GDP: {e}")
            return {"data": [], "latest": None, "next_release": None}

    def _get_iip(self, service) -> dict:
        """鉱工業生産指数（前月比）データを取得"""
        try:
            force_refresh = self._should_force_refresh("iip")
            response = service.get_iip_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting IIP: {e}")
            return {"data": [], "latest": None, "next_release": None}

    def _get_iip_yoy(self, service) -> dict:
        """鉱工業生産指数（前年比）データを取得"""
        try:
            force_refresh = self._should_force_refresh("iip_yoy")
            response = service.get_iip_yoy_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting IIP YoY: {e}")
            return {"data": [], "latest": None, "next_release": None}

    def _get_tertiary_industry(self, service) -> dict:
        """第三次産業活動指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("tertiary_industry")
            response = service.get_tertiary_industry_index_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting Tertiary Industry Index: {e}")
            return {"data": [], "latest": None, "next_release": None}

    def _get_machinery_orders(self, service) -> dict:
        """機械受注データを取得"""
        try:
            force_refresh = self._should_force_refresh("machinery_orders")
            response = service.get_machinery_orders_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting Machinery Orders: {e}")
            return {"data": [], "latest": None, "next_release": None}

    def _get_machine_tool_orders(self, service) -> dict:
        """工作機械受注データを取得"""
        try:
            force_refresh = self._should_force_refresh("machine_tool_orders")
            response = service.get_machine_tool_orders_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting Machine Tool Orders: {e}")
            return {"data": [], "latest": None, "next_release": None}

    def _get_capital_investment(self, service) -> dict:
        """設備投資データを取得"""
        try:
            force_refresh = self._should_force_refresh("capital_investment")
            response = service.get_capital_investment_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting Capital Investment: {e}")
            return {"data": [], "latest": None, "next_release": None}

    def _get_current_account(self, service) -> dict:
        """経常収支データを取得"""
        try:
            force_refresh = self._should_force_refresh("current_account")
            response = service.get_current_account_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting Current Account: {e}")
            return {"data": [], "latest": None, "next_release": None}

    def _get_current_account_gdp_ratio(self, service) -> dict:
        """経常収支対GDP比データを取得"""
        try:
            force_refresh = self._should_force_refresh("current_account_gdp_ratio")
            response = service.get_current_account_gdp_ratio_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting Current Account GDP Ratio: {e}")
            return {"data": [], "latest": None, "next_release": None}

    def _get_balance_of_trade(self, service) -> dict:
        """貿易収支データを取得"""
        try:
            force_refresh = self._should_force_refresh("balance_of_trade")
            response = service.get_balance_of_trade_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting Balance of Trade: {e}")
            return {"data": [], "latest": None, "next_release": None}
