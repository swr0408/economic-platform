"""
スイス経済ダッシュボードローダー
GDP成長率などを一括取得

キャッシュ更新判定: FMP発表日時ベース判定
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class SwitzerlandEconomyLoader(BaseDashboardLoader):
    """
    スイス経済ダッシュボード用データローダー

    取得データ:
    - ch_growth_rate: GDP成長率（QoQ, YoY, 年率）

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "switzerland"
    CATEGORY_CODE = "economy"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "ch_growth_rate",
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
            print(f"[SwitzerlandEconomy] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全経済データを並列で取得

        Returns:
            {
                "ch_growth_rate": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.switzerland.ch_growth_rate_service import ch_growth_rate_service

        result = {
            "ch_growth_rate": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=1) as executor:
            futures = {
                executor.submit(self._get_growth_rate, ch_growth_rate_service): "ch_growth_rate",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"[SwitzerlandEconomy] Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_growth_rate(self, service) -> dict:
        """GDP成長率データを取得"""
        try:
            force_refresh = self._should_force_refresh("ch_growth_rate")
            response = service.get_ch_growth_rate_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[SwitzerlandEconomy] Error getting GDP Growth Rate: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}
