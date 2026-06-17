"""
カナダ物価ダッシュボードローダー
CPI（消費者物価指数）などを一括取得

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
FMP_PATTERN_CPI = "CPI"


class CanadaInflationLoader(BaseDashboardLoader):
    """
    カナダ物価ダッシュボード用データローダー

    取得データ:
    - ca_cpi: 消費者物価指数（CPI）

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "canada"
    CATEGORY_CODE = "inflation"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "ca_cpi",
        "ca_ippi",
        "ca_inflation_expectations",
        "ca_cpi_service_rent",
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
            # エラー時に {"all"} を返すと、エラーが続く限り毎リクエストで全指標の
            # 外部API一斉取得が走りイベントループ/executorを圧迫する (2026-06-13 障害)。
            # 判定不能時はキャッシュ継続に倒す (各サービスのスケジューラが個別に更新する)。
            return set()

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
            print(f"[CanadaInflation] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全物価データを並列で取得

        Returns:
            {
                "ca_cpi": {...},
                "ca_ippi": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.canada.ca_cpi_service import ca_cpi_service
        from services.canada.ca_ippi_service import ca_ippi_service
        from services.canada.ca_inflation_expectations_service import ca_inflation_expectations_service
        from services.canada.ca_cpi_service_rent_service import ca_cpi_service_rent_service

        result = {
            "ca_cpi": None,
            "ca_ippi": None,
            "ca_inflation_expectations": None,
            "ca_cpi_service_rent": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self._get_ca_cpi, ca_cpi_service): "ca_cpi",
                executor.submit(self._get_ca_ippi, ca_ippi_service): "ca_ippi",
                executor.submit(self._get_ca_inflation_expectations, ca_inflation_expectations_service): "ca_inflation_expectations",
                executor.submit(self._get_ca_cpi_service_rent, ca_cpi_service_rent_service): "ca_cpi_service_rent",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"[CanadaInflation] Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_ca_cpi(self, service) -> dict:
        """カナダCPIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_cpi")
            response = service.get_ca_cpi_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaInflation] Error getting CPI: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ca_ippi(self, service) -> dict:
        """カナダIPPIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_ippi")
            response = service.get_ca_ippi_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaInflation] Error getting IPPI: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ca_inflation_expectations(self, service) -> dict:
        """カナダインフレ期待データを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_inflation_expectations")
            response = service.get_ca_inflation_expectations_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaInflation] Error getting Inflation Expectations: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ca_cpi_service_rent(self, service) -> dict:
        """カナダCPI サービス/家賃データを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_cpi_service_rent")
            response = service.get_ca_cpi_service_rent_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaInflation] Error getting CPI Service/Rent: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}
