"""
中国インフレーションダッシュボードローダー
CPI（前年比・前月比・食品・非食品）+ PPI（前年比・前月比）を一括取得

キャッシュ更新判定: NBS発表日時ベース
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo

from services.dashboard.loaders.base import BaseDashboardLoader


JST = ZoneInfo("Asia/Tokyo")
CST = ZoneInfo("Asia/Shanghai")


class ChinaInflationLoader(BaseDashboardLoader):
    """
    中国インフレーションダッシュボード用データローダー

    取得データ:
    - cn_cpi: CPI（前年比・前月比・食品・非食品）
    - cn_ppi: PPI（前年比・前月比）
    """

    COUNTRY_CODE = "china"
    CATEGORY_CODE = "inflation"

    EXPECTED_KEYS = [
        "cn_cpi",
        "cn_ppi",
    ]

    def __init__(self):
        super().__init__()
        self._stale_indicators: set = set()

    def get_expected_keys(self) -> List[str]:
        return self.EXPECTED_KEYS

    def get_release_datetimes(self) -> List[Optional[datetime]]:
        return []

    def _detect_stale_indicators(self, last_updated: Optional[str]) -> set:
        stale = set()
        if last_updated is None:
            return stale
        return stale

    def _should_force_refresh(self, indicator: str) -> bool:
        if "all" in self._stale_indicators:
            return True
        return indicator in self._stale_indicators

    def _prepare_for_refresh(self, last_updated: Optional[str]) -> None:
        self._stale_indicators = self._detect_stale_indicators(last_updated)
        if self._stale_indicators:
            print(f"[ChinaInflation] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        from services.china.cn_cpi_service import cn_cpi_service
        from services.china.cn_ppi_service import cn_ppi_service

        result = {
            "cn_cpi": None,
            "cn_ppi": None,
        }

        result["cn_cpi"] = self._get_generic_indicator(
            cn_cpi_service,
            "cn_cpi",
            "CPI",
        )

        result["cn_ppi"] = self._get_generic_indicator(
            cn_ppi_service,
            "cn_ppi",
            "PPI",
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
            print(f"[ChinaInflation] Error getting {label}: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}
