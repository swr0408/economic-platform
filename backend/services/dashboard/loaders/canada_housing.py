"""
カナダ住宅ダッシュボードローダー
住宅着工件数などを一括取得

キャッシュ更新判定: FMP発表日時ベース判定
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError

from services.dashboard.loaders.base import BaseDashboardLoader
from services.canada.fmp_next_release_utils import get_next_release_by_pattern


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
TORONTO = ZoneInfo("America/Toronto")

# FMP Event Patterns
FMP_PATTERN_HOUSING_STARTS = "Housing Starts"
FMP_PATTERN_BUILDING_PERMITS = "Building Permits"


class CanadaHousingLoader(BaseDashboardLoader):
    """
    カナダ住宅ダッシュボード用データローダー

    取得データ:
    - ca_housing_starts: 住宅着工件数
    - ca_building_permits: 建築許可

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "canada"
    CATEGORY_CODE = "housing"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "ca_housing_starts",
        "ca_building_permits",
        "ca_new_housing_price_index",
        "ca_debt_service_ratio",
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
            print(f"[CanadaHousing] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全住宅データを並列で取得

        Returns:
            {
                "ca_housing_starts": {...},
                "ca_building_permits": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.canada.ca_housing_starts_service import ca_housing_starts_service
        from services.canada.ca_building_permits_service import ca_building_permits_service
        from services.canada.ca_new_housing_price_index_service import ca_new_housing_price_index_service
        from services.canada.ca_debt_service_ratio_service import ca_debt_service_ratio_service

        result = {
            "ca_housing_starts": None,
            "ca_building_permits": None,
            "ca_new_housing_price_index": None,
            "ca_debt_service_ratio": None,
        }

        # Housing Starts, Building Permits, NHPI, DSR を並列取得
        FETCH_TIMEOUT = 30
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self._get_ca_housing_starts, ca_housing_starts_service): "ca_housing_starts",
                executor.submit(self._get_ca_building_permits, ca_building_permits_service): "ca_building_permits",
                executor.submit(self._get_ca_new_housing_price_index, ca_new_housing_price_index_service): "ca_new_housing_price_index",
                executor.submit(self._get_ca_debt_service_ratio, ca_debt_service_ratio_service): "ca_debt_service_ratio",
            }

            try:
                for future in as_completed(futures, timeout=FETCH_TIMEOUT * 2):
                    key = futures[future]
                    try:
                        result[key] = future.result(timeout=FETCH_TIMEOUT)
                    except FuturesTimeoutError:
                        print(f"[CanadaHousing] Timeout fetching {key}")
                        result[key] = {"data": [], "latest": None, "metadata": {}, "next_release": None}
                    except Exception as e:
                        print(f"[CanadaHousing] Error fetching {key}: {e}")
                        result[key] = {"data": [], "latest": None, "metadata": {}, "next_release": None}
            except FuturesTimeoutError:
                print("[CanadaHousing] Overall timeout - some tasks did not complete")
                for key in result:
                    if result[key] is None:
                        result[key] = {"data": [], "latest": None, "metadata": {}, "next_release": None}

        return result

    def _get_ca_housing_starts(self, service) -> dict:
        """カナダ住宅着工件数データを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_housing_starts")
            response = service.get_ca_housing_starts_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaHousing] Error getting Housing Starts: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ca_building_permits(self, service) -> dict:
        """カナダ建築許可データを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_building_permits")
            response = service.get_ca_building_permits_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaHousing] Error getting Building Permits: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ca_new_housing_price_index(self, service) -> dict:
        """カナダ新築住宅価格指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_new_housing_price_index")
            response = service.get_ca_new_housing_price_index_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaHousing] Error getting New Housing Price Index: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ca_debt_service_ratio(self, service) -> dict:
        """カナダ家計DSRデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_debt_service_ratio")
            response = service.get_ca_debt_service_ratio_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaHousing] Error getting Debt Service Ratio: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}
