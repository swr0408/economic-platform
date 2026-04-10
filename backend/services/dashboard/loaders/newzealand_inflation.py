"""
ニュージーランド物価ダッシュボードローダー
PPI等を一括取得

キャッシュ更新判定: FMP発表日時ベース判定
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
AUCKLAND = ZoneInfo("Pacific/Auckland")


class NewZealandInflationLoader(BaseDashboardLoader):
    """
    ニュージーランド物価ダッシュボード用データローダー

    取得データ:
    - nz_cpi: 消費者物価指数（CPI）
    - nz_cpi_item: CPI項目別
    - nz_traded_nontraded: 貿易財/非貿易財
    - nz_ppi: 生産者物価指数（PPI）
    - nz_inflation_expectations: インフレ期待
    - nz_anz_business_outlook_price: ANZ企業景況感物価関連（PDFスクリーンショット）

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "newzealand"
    CATEGORY_CODE = "inflation"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "nz_cpi",
        "nz_cpi_item",
        "nz_traded_nontraded",
        "nz_ppi",
        "nz_inflation_expectations",
        "nz_anz_business_outlook_price",
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
            print(f"[NewZealandInflation] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全物価データを取得

        Returns:
            {
                "nz_cpi": {...},
                "nz_cpi_item": {...},
                "nz_traded_nontraded": {...},
                "nz_ppi": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.newzealand.nz_cpi_service import nz_cpi_service
        from services.newzealand.nz_cpi_item_service import nz_cpi_item_service
        from services.newzealand.nz_traded_nontraded_service import nz_traded_nontraded_service
        from services.newzealand.nz_ppi_service import nz_ppi_service
        from services.newzealand.nz_inflation_expectations_service import nz_inflation_expectations_service
        from services.newzealand.nz_anz_business_outlook_price_service import nz_anz_business_outlook_price_service

        result = {
            "nz_cpi": None,
            "nz_cpi_item": None,
            "nz_traded_nontraded": None,
            "nz_ppi": None,
            "nz_inflation_expectations": None,
            "nz_anz_business_outlook_price": None,
        }

        # データを取得
        result["nz_cpi"] = self._get_cpi(nz_cpi_service)
        result["nz_cpi_item"] = self._get_cpi_item(nz_cpi_item_service)
        result["nz_traded_nontraded"] = self._get_traded_nontraded(nz_traded_nontraded_service)
        result["nz_ppi"] = self._get_ppi(nz_ppi_service)
        result["nz_inflation_expectations"] = self._get_inflation_expectations(nz_inflation_expectations_service)
        result["nz_anz_business_outlook_price"] = self._get_anz_business_outlook_price(nz_anz_business_outlook_price_service)

        return result

    def _get_cpi(self, service) -> dict:
        """NZ CPIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("nz_cpi")
            response = service.get_nz_cpi_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[NewZealandInflation] Error getting CPI: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_cpi_item(self, service) -> dict:
        """NZ CPI項目別データを取得"""
        try:
            force_refresh = self._should_force_refresh("nz_cpi_item")
            response = service.get_nz_cpi_item_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[NewZealandInflation] Error getting CPI Item: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_traded_nontraded(self, service) -> dict:
        """NZ 貿易財/非貿易財データを取得"""
        try:
            force_refresh = self._should_force_refresh("nz_traded_nontraded")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[NewZealandInflation] Error getting Traded/Non-Traded: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ppi(self, service) -> dict:
        """NZ PPIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("nz_ppi")
            response = service.get_nz_ppi_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[NewZealandInflation] Error getting PPI: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_inflation_expectations(self, service) -> dict:
        """NZ インフレ期待データを取得"""
        try:
            force_refresh = self._should_force_refresh("nz_inflation_expectations")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[NewZealandInflation] Error getting Inflation Expectations: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_anz_business_outlook_price(self, service) -> dict:
        """ANZ企業景況感物価関連スクリーンショットを取得"""
        try:
            return service.get_screenshot_data()
        except Exception as e:
            print(f"[NewZealandInflation] Error getting ANZ Business Outlook Price: {e}")
            return {"page2_exists": False, "last_updated": None, "pdf_date": None, "next_release": None}
