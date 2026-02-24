"""
ニュージーランド金融政策ダッシュボードローダー
RBNZ政策金利・MPS経済見通しなどを一括取得

キャッシュ更新判定: FMP発表日時ベース判定
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
AUCKLAND = ZoneInfo("Pacific/Auckland")


class NewZealandPolicyLoader(BaseDashboardLoader):
    """
    ニュージーランド金融政策ダッシュボード用データローダー

    取得データ:
    - nz_rbnz_rate: RBNZ政策金利（OCR）
    - nz_economic_forecast: RBNZ MPS経済見通し

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "newzealand"
    CATEGORY_CODE = "policy"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "nz_rbnz_rate",
        "nz_economic_forecast",
        "nz_central_bank_balance_sheet",
        "nz_bank_balance_sheet",
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
            print(f"[NewZealandPolicy] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全金融政策データを取得

        Returns:
            {
                "nz_rbnz_rate": {...},
                "nz_economic_forecast": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.newzealand.rbnz_policy_rate_service import rbnz_policy_rate_service
        from services.newzealand.rbnz_mps_forecast_service import rbnz_mps_forecast_service
        from services.newzealand.nz_central_bank_balance_sheet_service import nz_central_bank_balance_sheet_service
        from services.newzealand.nz_bank_balance_sheet_service import nz_bank_balance_sheet_service

        result = {
            "nz_rbnz_rate": None,
            "nz_economic_forecast": None,
            "nz_central_bank_balance_sheet": None,
            "nz_bank_balance_sheet": None,
        }

        # データを取得
        result["nz_rbnz_rate"] = self._get_rbnz_rate(rbnz_policy_rate_service)
        result["nz_economic_forecast"] = self._get_economic_forecast(rbnz_mps_forecast_service)
        result["nz_central_bank_balance_sheet"] = self._get_balance_sheet(nz_central_bank_balance_sheet_service)
        result["nz_bank_balance_sheet"] = self._get_bank_balance_sheet(nz_bank_balance_sheet_service)

        return result

    def _get_rbnz_rate(self, service) -> dict:
        """RBNZ政策金利データを取得"""
        try:
            force_refresh = self._should_force_refresh("nz_rbnz_rate")
            response = service.get_nz_rbnz_rate_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[NewZealandPolicy] Error getting RBNZ Rate: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_economic_forecast(self, service) -> dict:
        """RBNZ MPS経済見通しデータを取得"""
        try:
            force_refresh = self._should_force_refresh("nz_economic_forecast")
            response = service.get_nz_economic_forecast_data(force_refresh=force_refresh)
            return {
                "indicators": response.get("indicators", {}),
                "metadata": response.get("metadata", {}),
            }
        except Exception as e:
            print(f"[NewZealandPolicy] Error getting MPS Forecast: {e}")
            return {"indicators": {}, "metadata": {}}

    def _get_balance_sheet(self, service) -> dict:
        """RBNZ中央銀行バランスシートデータを取得"""
        try:
            force_refresh = self._should_force_refresh("nz_central_bank_balance_sheet")
            response = service.get_nz_central_bank_balance_sheet_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[NewZealandPolicy] Error getting Balance Sheet: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_bank_balance_sheet(self, service) -> dict:
        """NZ銀行バランスシートデータを取得"""
        try:
            force_refresh = self._should_force_refresh("nz_bank_balance_sheet")
            response = service.get_nz_bank_balance_sheet_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[NewZealandPolicy] Error getting Bank Balance Sheet: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}
