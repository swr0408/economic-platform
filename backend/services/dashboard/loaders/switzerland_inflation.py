"""
スイス物価ダッシュボードローダー
CPI、PPIなどを一括取得

キャッシュ更新判定: FMP発表日時ベース判定
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class SwitzerlandInflationLoader(BaseDashboardLoader):
    """
    スイス物価ダッシュボード用データローダー

    取得データ:
    - ch_cpi: 消費者物価指数（CPI）
    - ch_ppi: 生産者・輸入物価指数（PPI）

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "switzerland"
    CATEGORY_CODE = "inflation"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "ch_cpi",
        "ch_ppi",
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
            print(f"[SwitzerlandInflation] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全物価データを並列で取得

        Returns:
            {
                "ch_cpi": {...},
                "ch_ppi": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.switzerland.ch_cpi_service import ch_cpi_service
        from services.switzerland.ch_ppi_service import ch_ppi_service

        result = {
            "ch_cpi": None,
            "ch_ppi": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(self._get_ch_cpi, ch_cpi_service): "ch_cpi",
                executor.submit(self._get_ch_ppi, ch_ppi_service): "ch_ppi",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"[SwitzerlandInflation] Error fetching {key}: {e}")
                    result[key] = None

        return result

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
            print(f"[SwitzerlandInflation] Error getting CPI: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ch_ppi(self, service) -> dict:
        """スイスPPIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ch_ppi")
            response = service.get_ch_ppi_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[SwitzerlandInflation] Error getting PPI: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}
