"""
オーストラリア住宅ダッシュボードローダー
住宅価格など住宅関連指標を一括取得

キャッシュ更新判定: ファイルベース判定（手動更新Excelファイル）
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
SYDNEY = ZoneInfo("Australia/Sydney")


class AustraliaHousingLoader(BaseDashboardLoader):
    """
    オーストラリア住宅ダッシュボード用データローダー

    取得データ:
    - au_cotality_home_prices: Cotality住宅価格指数（日次/月次）
    - au_number_of_building_permits: 建築許可件数（月次）

    キャッシュ方式: ファイルベース判定 + FMP発表日判定
    """

    COUNTRY_CODE = "australia"
    CATEGORY_CODE = "housing"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "au_cotality_home_prices",
        "au_number_of_building_permits",
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
            return set()

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
            print(f"[AustraliaHousing] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全住宅データを取得

        Returns:
            {
                "au_cotality_home_prices": {...},
                "au_number_of_building_permits": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.australia.au_cotality_home_prices_service import au_cotality_home_prices_service
        from services.australia.au_number_of_building_permits_service import au_number_of_building_permits_service

        result = {
            "au_cotality_home_prices": None,
            "au_number_of_building_permits": None,
        }

        # データを取得
        result["au_cotality_home_prices"] = self._get_cotality_home_prices(au_cotality_home_prices_service)
        result["au_number_of_building_permits"] = self._get_building_permits(au_number_of_building_permits_service)

        return result

    def _get_cotality_home_prices(self, service) -> dict:
        """Cotality住宅価格指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_cotality_home_prices")
            response = service.get_au_cotality_home_prices_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "monthly_data": response.get("monthly_data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaHousing] Error getting Cotality Home Prices: {e}")
            return {"data": [], "monthly_data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_building_permits(self, service) -> dict:
        """建築許可件数データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_number_of_building_permits")
            response = service.get_au_number_of_building_permits_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaHousing] Error getting Building Permits: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

