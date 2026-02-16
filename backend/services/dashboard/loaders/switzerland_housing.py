"""
スイス住宅ダッシュボードローダー
住宅ローン金利などを一括取得

キャッシュ更新判定: ICSカレンダーベース判定
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class SwitzerlandHousingLoader(BaseDashboardLoader):
    """
    スイス住宅ダッシュボード用データローダー

    取得データ:
    - ch_mortgage_rates: 住宅ローン金利（新規契約）

    キャッシュ方式: ICSカレンダーベース判定
    """

    COUNTRY_CODE = "switzerland"
    CATEGORY_CODE = "housing"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "ch_mortgage_rates",
        "ch_mortgage_balance",
        "ch_new_mortgage_loans",
        "ch_housing_prices",
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
            print(f"[SwitzerlandHousing] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全住宅データを並列で取得

        Returns:
            {
                "ch_mortgage_rates": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.switzerland.ch_mortgage_rates_service import ch_mortgage_rates_service
        from services.switzerland.ch_mortgage_balance_service import ch_mortgage_balance_service
        from services.switzerland.ch_new_mortgage_loans_service import ch_new_mortgage_loans_service
        from services.switzerland.ch_housing_prices_service import ch_housing_prices_service

        result = {
            "ch_mortgage_rates": None,
            "ch_mortgage_balance": None,
            "ch_new_mortgage_loans": None,
            "ch_housing_prices": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self._get_mortgage_rates, ch_mortgage_rates_service): "ch_mortgage_rates",
                executor.submit(self._get_mortgage_balance, ch_mortgage_balance_service): "ch_mortgage_balance",
                executor.submit(self._get_new_mortgage_loans, ch_new_mortgage_loans_service): "ch_new_mortgage_loans",
                executor.submit(self._get_housing_prices, ch_housing_prices_service): "ch_housing_prices",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"[SwitzerlandHousing] Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_mortgage_rates(self, service) -> dict:
        """住宅ローン金利データを取得"""
        try:
            force_refresh = self._should_force_refresh("ch_mortgage_rates")
            response = service.get_mortgage_rates_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[SwitzerlandHousing] Error getting Mortgage Rates: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_mortgage_balance(self, service) -> dict:
        """住宅ローン残高データを取得"""
        try:
            force_refresh = self._should_force_refresh("ch_mortgage_balance")
            response = service.get_mortgage_balance_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[SwitzerlandHousing] Error getting Mortgage Balance: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_new_mortgage_loans(self, service) -> dict:
        """新規住宅ローン融資額データを取得"""
        try:
            force_refresh = self._should_force_refresh("ch_new_mortgage_loans")
            response = service.get_new_mortgage_loans_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[SwitzerlandHousing] Error getting New Mortgage Loans: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_housing_prices(self, service) -> dict:
        """住宅価格指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("ch_housing_prices")
            response = service.get_housing_prices_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[SwitzerlandHousing] Error getting Housing Prices: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}
