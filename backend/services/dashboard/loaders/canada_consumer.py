"""
カナダ消費者ダッシュボードローダー
小売売上高などを一括取得

キャッシュ更新判定: FMP発表日時ベース判定
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader
from services.canada.fmp_next_release_utils import get_next_release_by_pattern


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
TORONTO = ZoneInfo("America/Toronto")

# FMP Event Patterns
FMP_PATTERN_RETAIL_SALES = "Retail Sales"


class CanadaConsumerLoader(BaseDashboardLoader):
    """
    カナダ消費者ダッシュボード用データローダー

    取得データ:
    - ca_retail_sales: 小売売上高

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "canada"
    CATEGORY_CODE = "consumer"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "ca_retail_sales",
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
            print(f"[CanadaConsumer] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全消費者データを並列で取得

        Returns:
            {
                "ca_retail_sales": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.canada.ca_retail_sales_service import ca_retail_sales_service

        result = {
            "ca_retail_sales": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self._get_ca_retail_sales, ca_retail_sales_service): "ca_retail_sales",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"[CanadaConsumer] Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_ca_retail_sales(self, service) -> dict:
        """カナダ小売売上高データを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_retail_sales")
            response = service.get_ca_retail_sales_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaConsumer] Error getting Retail Sales: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

