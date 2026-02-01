"""
スイス金融政策ダッシュボードローダー
SNB政策金利、CPI、インフレ見通しなどを一括取得

キャッシュ更新判定: FMP発表日時ベース判定
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader
from services.switzerland.fmp_next_release_utils import get_next_release_by_pattern


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# FMP Event Patterns
FMP_PATTERN_SNB_RATE = "SNB Interest Rate Decision"


class SwitzerlandPolicyLoader(BaseDashboardLoader):
    """
    スイス金融政策ダッシュボード用データローダー

    取得データ:
    - ch_snb_rate: SNB政策金利（Policy Rate）
    - ch_inflation_forecast: SNBインフレ見通し
    - ch_cpi: 消費者物価指数（CPI）

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "switzerland"
    CATEGORY_CODE = "policy"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "ch_snb_rate",
        "ch_inflation_forecast",
        "ch_cpi",
        "snb_balance_sheet",
        "snb_sight_deposits",
        "foreign_currency_reserves",
        "monetary_base",
        "monetary_aggregate_m2",
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
            return {"all"}

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
            print(f"[SwitzerlandPolicy] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全金融政策データを並列で取得

        Returns:
            {
                "ch_snb_rate": {...},
                "ch_inflation_forecast": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.switzerland.ch_snb_rate_service import ch_snb_rate_service
        from services.switzerland.ch_inflation_forecast_service import ch_inflation_forecast_service
        from services.switzerland.ch_cpi_service import ch_cpi_service
        from services.switzerland.snb_balance_sheet_service import snb_balance_sheet_service
        from services.switzerland.snb_sight_deposits_service import snb_sight_deposits_service
        from services.switzerland.foreign_currency_reserves_service import foreign_currency_reserves_service
        from services.switzerland.monetary_base_service import monetary_base_service
        from services.switzerland.monetary_aggregate_m2_service import monetary_aggregate_m2_service

        result = {
            "ch_snb_rate": None,
            "ch_inflation_forecast": None,
            "ch_cpi": None,
            "snb_balance_sheet": None,
            "snb_sight_deposits": None,
            "foreign_currency_reserves": None,
            "monetary_base": None,
            "monetary_aggregate_m2": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(self._get_ch_snb_rate, ch_snb_rate_service): "ch_snb_rate",
                executor.submit(self._get_ch_inflation_forecast, ch_inflation_forecast_service): "ch_inflation_forecast",
                executor.submit(self._get_ch_cpi, ch_cpi_service): "ch_cpi",
                executor.submit(self._get_snb_balance_sheet, snb_balance_sheet_service): "snb_balance_sheet",
                executor.submit(self._get_snb_sight_deposits, snb_sight_deposits_service): "snb_sight_deposits",
                executor.submit(self._get_foreign_currency_reserves, foreign_currency_reserves_service): "foreign_currency_reserves",
                executor.submit(self._get_monetary_base, monetary_base_service): "monetary_base",
                executor.submit(self._get_monetary_aggregate_m2, monetary_aggregate_m2_service): "monetary_aggregate_m2",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"[SwitzerlandPolicy] Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_ch_snb_rate(self, service) -> dict:
        """SNB政策金利データを取得"""
        try:
            force_refresh = self._should_force_refresh("ch_snb_rate")
            response = service.get_ch_snb_rate_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[SwitzerlandPolicy] Error getting SNB Rate: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ch_inflation_forecast(self, service) -> dict:
        """SNBインフレ見通しデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ch_inflation_forecast")
            response = service.get_inflation_forecast_data(force_refresh=force_refresh)
            return {
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[SwitzerlandPolicy] Error getting Inflation Forecast: {e}")
            return {"latest": None, "metadata": {}, "next_release": None}

    def _get_ch_cpi(self, service) -> dict:
        """スイスCPIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ch_cpi")
            response = service.get_ch_cpi_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[SwitzerlandPolicy] Error getting CPI: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_snb_balance_sheet(self, service) -> dict:
        """SNBバランスシートデータを取得"""
        try:
            force_refresh = self._should_force_refresh("snb_balance_sheet")
            response = service.get_balance_sheet_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[SwitzerlandPolicy] Error getting SNB Balance Sheet: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_snb_sight_deposits(self, service) -> dict:
        """SNB当座預金データを取得"""
        try:
            force_refresh = self._should_force_refresh("snb_sight_deposits")
            response = service.get_sight_deposits_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
                "last_publishing_date": response.get("last_publishing_date"),
            }
        except Exception as e:
            print(f"[SwitzerlandPolicy] Error getting SNB Sight Deposits: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None, "last_publishing_date": None}

    def _get_foreign_currency_reserves(self, service) -> dict:
        """外貨準備データを取得"""
        try:
            force_refresh = self._should_force_refresh("foreign_currency_reserves")
            response = service.get_foreign_currency_reserves_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
                "last_publishing_date": response.get("last_publishing_date"),
            }
        except Exception as e:
            print(f"[SwitzerlandPolicy] Error getting Foreign Currency Reserves: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None, "last_publishing_date": None}

    def _get_monetary_base(self, service) -> dict:
        """マネタリーベースデータを取得"""
        try:
            force_refresh = self._should_force_refresh("monetary_base")
            response = service.get_monetary_base_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
                "last_publishing_date": response.get("last_publishing_date"),
            }
        except Exception as e:
            print(f"[SwitzerlandPolicy] Error getting Monetary Base: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None, "last_publishing_date": None}

    def _get_monetary_aggregate_m2(self, service) -> dict:
        """貨幣総量M2データを取得"""
        try:
            force_refresh = self._should_force_refresh("monetary_aggregate_m2")
            response = service.get_monetary_aggregate_m2_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
                "last_publishing_date": response.get("last_publishing_date"),
            }
        except Exception as e:
            print(f"[SwitzerlandPolicy] Error getting Monetary Aggregate M2: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None, "last_publishing_date": None}
