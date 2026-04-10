"""
中国住宅ダッシュボードローダー
商業住宅販売（累積前年比3系列）を一括取得

キャッシュ更新判定: NBS発表日時ベース
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo

from services.dashboard.loaders.base import BaseDashboardLoader


JST = ZoneInfo("Asia/Tokyo")
CST = ZoneInfo("Asia/Shanghai")


class ChinaHousingLoader(BaseDashboardLoader):
    """
    中国住宅ダッシュボード用データローダー

    取得データ:
    - cn_commercial_residential_sales: 商業住宅販売（3系列YoY）
    - cn_house_price_index: 住宅価格指数（YoY）
    """

    COUNTRY_CODE = "china"
    CATEGORY_CODE = "housing"

    EXPECTED_KEYS = [
        "cn_commercial_residential_sales",
        "cn_house_price_index",
    ]

    def __init__(self):
        super().__init__()
        self._stale_indicators: set = set()

    def get_expected_keys(self) -> List[str]:
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
        if "all" in self._stale_indicators:
            return True
        return indicator in self._stale_indicators

    def _prepare_for_refresh(self, last_updated: Optional[str]) -> None:
        self._stale_indicators = self._detect_stale_indicators(last_updated)
        if self._stale_indicators:
            print(f"[ChinaHousing] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        from services.china.cn_commercial_residential_sales_service import (
            cn_commercial_residential_sales_service,
        )
        from services.china.cn_house_price_index_service import (
            cn_house_price_index_service,
        )

        result = {
            "cn_commercial_residential_sales": None,
            "cn_house_price_index": None,
        }

        result["cn_commercial_residential_sales"] = self._get_generic_indicator(
            cn_commercial_residential_sales_service,
            "cn_commercial_residential_sales",
            "Commercial Residential Sales",
        )
        result["cn_house_price_index"] = self._get_generic_indicator(
            cn_house_price_index_service,
            "cn_house_price_index",
            "House Price Index",
        )

        return result

    def _get_generic_indicator(self, service, key: str, label: str) -> dict:
        try:
            force_refresh = self._should_force_refresh(key)
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[ChinaHousing] Error getting {label}: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}
