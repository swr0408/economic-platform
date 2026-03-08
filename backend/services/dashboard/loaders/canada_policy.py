"""
カナダ金融政策ダッシュボードローダー
BOC政策金利などを一括取得

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
FMP_PATTERN_BOC_RATE = "BoC Interest Rate Decision"


class CanadaPolicyLoader(BaseDashboardLoader):
    """
    カナダ金融政策ダッシュボード用データローダー

    取得データ:
    - ca_boc_rate: BOC政策金利（オーバーナイトレート目標）

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "canada"
    CATEGORY_CODE = "policy"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "ca_boc_rate",
        "boc_mpr",
        "boc_balance_sheet",
        "canada_banks_balance_sheet",
        "ca_corra",
        "ca_settlement_balances",
        "ca_government_deposits",
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
            print(f"[CanadaPolicy] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全金融政策データを並列で取得

        Returns:
            {
                "ca_boc_rate": {...},
                "boc_mpr": {...},
                "boc_balance_sheet": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.canada.ca_boc_rate_service import ca_boc_rate_service
        from services.canada.boc_mpr_service import boc_mpr_service
        from services.canada.boc_balance_sheet_service import boc_balance_sheet_service
        from services.canada.canada_banks_balance_sheet_service import canada_banks_balance_sheet_service
        from services.canada.ca_corra_service import ca_corra_service
        from services.canada.ca_settlement_balances_service import ca_settlement_balances_service
        from services.canada.ca_government_deposits_service import ca_government_deposits_service

        result = {
            "ca_boc_rate": None,
            "boc_mpr": None,
            "boc_balance_sheet": None,
            "canada_banks_balance_sheet": None,
            "ca_corra": None,
            "ca_settlement_balances": None,
            "ca_government_deposits": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=7) as executor:
            futures = {
                executor.submit(self._get_ca_boc_rate, ca_boc_rate_service): "ca_boc_rate",
                executor.submit(self._get_boc_mpr, boc_mpr_service): "boc_mpr",
                executor.submit(self._get_boc_balance_sheet, boc_balance_sheet_service): "boc_balance_sheet",
                executor.submit(self._get_canada_banks_balance_sheet, canada_banks_balance_sheet_service): "canada_banks_balance_sheet",
                executor.submit(self._get_ca_corra, ca_corra_service): "ca_corra",
                executor.submit(self._get_ca_settlement_balances, ca_settlement_balances_service): "ca_settlement_balances",
                executor.submit(self._get_ca_government_deposits, ca_government_deposits_service): "ca_government_deposits",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"[CanadaPolicy] Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_ca_boc_rate(self, service) -> dict:
        """BOC政策金利データを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_boc_rate")
            response = service.get_ca_boc_rate_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaPolicy] Error getting BOC Rate: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_boc_mpr(self, service) -> dict:
        """BOC金融政策報告書データを取得"""
        try:
            force_refresh = self._should_force_refresh("boc_mpr")
            response = service.get_boc_mpr_data(force_refresh=force_refresh)
            return {
                "latest_report": response.get("latest_report"),
                "previous_report": response.get("previous_report"),
                "comparison": response.get("comparison"),
                "metadata": response.get("metadata", {}),
            }
        except Exception as e:
            print(f"[CanadaPolicy] Error getting BOC MPR: {e}")
            return {"latest_report": None, "previous_report": None, "comparison": None, "metadata": {}}

    def _get_boc_balance_sheet(self, service) -> dict:
        """BOCバランスシートデータを取得"""
        try:
            force_refresh = self._should_force_refresh("boc_balance_sheet")
            response = service.get_boc_balance_sheet_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
            }
        except Exception as e:
            print(f"[CanadaPolicy] Error getting BOC Balance Sheet: {e}")
            return {"data": [], "latest": None, "metadata": {}}

    def _get_canada_banks_balance_sheet(self, service) -> dict:
        """カナダ銀行バランスシート（チャータード銀行）データを取得"""
        try:
            force_refresh = self._should_force_refresh("canada_banks_balance_sheet")
            response = service.get_canada_banks_balance_sheet_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
            }
        except Exception as e:
            print(f"[CanadaPolicy] Error getting Canada Banks Balance Sheet: {e}")
            return {"data": [], "latest": None, "metadata": {}}

    def _get_ca_corra(self, service) -> dict:
        """CORRA（カナダ翌日物レポ平均金利）データを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_corra")
            response = service.get_ca_corra_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
            }
        except Exception as e:
            print(f"[CanadaPolicy] Error getting CORRA: {e}")
            return {"data": [], "latest": None, "metadata": {}}

    def _get_ca_settlement_balances(self, service) -> dict:
        """カナダ決済残高データを取得（日次・週次の両方）"""
        try:
            force_refresh = self._should_force_refresh("ca_settlement_balances")
            response = service.get_ca_settlement_balances_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "daily": response.get("daily", {"data": [], "latest": None, "metadata": {}}),
                "weekly": response.get("weekly", {"data": [], "latest": None, "metadata": {}}),
            }
        except Exception as e:
            print(f"[CanadaPolicy] Error getting Settlement Balances: {e}")
            return {
                "data": [],
                "latest": None,
                "metadata": {},
                "daily": {"data": [], "latest": None, "metadata": {}},
                "weekly": {"data": [], "latest": None, "metadata": {}},
            }

    def _get_ca_government_deposits(self, service) -> dict:
        """カナダ政府預金データを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_government_deposits")
            response = service.get_ca_government_deposits_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
            }
        except Exception as e:
            print(f"[CanadaPolicy] Error getting Government Deposits: {e}")
            return {"data": [], "latest": None, "metadata": {}}
