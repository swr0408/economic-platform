"""
オーストラリア物価ダッシュボードローダー
ABS月次CPIなどインフレ関連指標を一括取得

キャッシュ更新判定: FMP発表日時ベース判定
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
SYDNEY = ZoneInfo("Australia/Sydney")


class AustraliaInflationLoader(BaseDashboardLoader):
    """
    オーストラリア物価ダッシュボード用データローダー

    取得データ:
    - au_monthly_cpi: ABS月次CPI（総合・トリム平均・加重中央値）
    - au_cpi_categories: ABS CPIカテゴリ別（財・サービス・電力・家賃・新築住宅・食品）
    - au_quarterly_cpi: ABS四半期CPI（QoQ・YoY・SA YoY・トリム平均・加重中央値）
    - au_quarterly_ppi: ABS四半期PPI（QoQ・YoY）
    - au_inflation_expectations: インフレ期待（Melbourne Institute）
    - au_nab_cost_price: NAB企業調査 コスト・価格チャート（PDFスクリーンショット）

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "australia"
    CATEGORY_CODE = "inflation"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "au_monthly_cpi",
        "au_cpi_categories",
        "au_quarterly_cpi",
        "au_quarterly_ppi",
        "au_inflation_expectations",
        "au_nab_cost_price",
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
            print(f"[AustraliaInflation] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全物価データを取得

        Returns:
            {
                "au_monthly_cpi": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.australia.abs_monthly_cpi_service import abs_monthly_cpi_service
        from services.australia.abs_cpi_categories_service import abs_cpi_categories_service
        from services.australia.abs_quarterly_cpi_service import abs_quarterly_cpi_service
        from services.australia.abs_quarterly_ppi_service import abs_quarterly_ppi_service
        from services.australia.au_inflation_expectations_service import au_inflation_expectations_service
        from services.australia.nab_business_survey_cost_price_service import nab_business_survey_cost_price_service

        result = {
            "au_monthly_cpi": None,
            "au_cpi_categories": None,
            "au_quarterly_cpi": None,
            "au_quarterly_ppi": None,
            "au_inflation_expectations": None,
            "au_nab_cost_price": None,
        }

        # データを取得
        result["au_monthly_cpi"] = self._get_monthly_cpi(abs_monthly_cpi_service)
        result["au_cpi_categories"] = self._get_cpi_categories(abs_cpi_categories_service)
        result["au_quarterly_cpi"] = self._get_quarterly_cpi(abs_quarterly_cpi_service)
        result["au_quarterly_ppi"] = self._get_quarterly_ppi(abs_quarterly_ppi_service)
        result["au_inflation_expectations"] = self._get_inflation_expectations(au_inflation_expectations_service)
        result["au_nab_cost_price"] = self._get_nab_cost_price(nab_business_survey_cost_price_service)

        return result

    def _get_monthly_cpi(self, service) -> dict:
        """ABS月次CPIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("au_monthly_cpi")
            response = service.get_monthly_cpi_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaInflation] Error getting Monthly CPI: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_cpi_categories(self, service) -> dict:
        """ABS CPIカテゴリ別データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_cpi_categories")
            response = service.get_cpi_categories_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaInflation] Error getting CPI Categories: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_quarterly_cpi(self, service) -> dict:
        """ABS四半期CPIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("au_quarterly_cpi")
            response = service.get_quarterly_cpi_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaInflation] Error getting Quarterly CPI: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_quarterly_ppi(self, service) -> dict:
        """ABS四半期PPIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("au_quarterly_ppi")
            response = service.get_quarterly_ppi_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaInflation] Error getting Quarterly PPI: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_inflation_expectations(self, service) -> dict:
        """インフレ期待データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_inflation_expectations")
            response = service.get_au_inflation_expectations_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaInflation] Error getting Inflation Expectations: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_nab_cost_price(self, service) -> dict:
        """NAB企業調査 コスト・価格チャートスクリーンショットを取得"""
        try:
            return service.get_screenshot_urls()
        except Exception as e:
            print(f"[AustraliaInflation] Error getting NAB Cost/Price: {e}")
            return {"screenshots": [], "last_updated": None, "next_release": None}
