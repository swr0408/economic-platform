"""
UK雇用ダッシュボードローダー
失業率などの雇用関連指標を一括取得

キャッシュ更新判定: FMP発表日時ベース方式
- ONS Unemployment Rate: FMP発表日時ベース更新（"Unemployment Rate"パターン）
- ONS Claimant Count: FMP発表日時ベース更新（"Claimant Count Change"パターン）
- ONS Wages: FMP発表日時ベース更新（"Average Earnings"パターン）
- ONS Real Wages: FMP発表日時ベース更新（"Average Earnings"パターン）
- ONS Employment: FMP発表日時ベース更新（"Employment Change"パターン）
- ONS Economic Activity: FMP発表日時ベース更新（"Unemployment Rate"パターン）
- ONS Productivity: FMP発表日時ベース更新（"Labour Productivity QoQ"パターン）
- Indeed Wage Tracker: 毎月15日以降に1日1回チェック
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class UKEmploymentLoader(BaseDashboardLoader):
    """
    UK雇用ダッシュボード用データローダー

    取得データ:
    - ons_unemployment: ONS失業率
    - ons_claimant_count: ONS失業給付申請件数
    - ons_wages: ONS平均賃金
    - ons_real_wages: ONS実質平均賃金
    - ons_employment: ONS雇用者数変化
    - ons_economic_activity: ONS経済活動率
    - ons_productivity: ONS労働生産性
    - indeed_wage_tracker: Indeed賃金トラッカー

    キャッシュ方式: FMP発表日時ベース判定
    - ONS Unemployment Rate: FMP発表日時ベース更新
    - ONS Claimant Count: FMP発表日時ベース更新
    - ONS Wages: FMP発表日時ベース更新
    - ONS Real Wages: FMP発表日時ベース更新
    - ONS Employment: FMP発表日時ベース更新
    - ONS Economic Activity: FMP発表日時ベース更新
    - ONS Productivity: FMP発表日時ベース更新
    - Indeed Wage Tracker: 毎月15日以降に1日1回チェック
    """

    COUNTRY_CODE = "uk"
    CATEGORY_CODE = "employment"

    def __init__(self):
        super().__init__()
        self._stale_indicators: set = set()

    def get_expected_keys(self) -> List[str]:
        """期待されるデータキーのリスト"""
        return [
            "ons_unemployment",
            "ons_claimant_count",
            "ons_wages",
            "ons_real_wages",
            "ons_employment",
            "ons_economic_activity",
            "ons_productivity",
            "ons_unit_labour_costs",
            "indeed_wage_tracker",
        ]

    def get_release_datetimes(self) -> List[Optional[datetime]]:
        """
        各指標の発表日時リストを返す
        """
        return []

    def _detect_stale_indicators(self, last_updated: Optional[str]) -> set:
        """
        発表日時を過ぎた指標を検出
        """
        stale = set()

        if last_updated is None:
            return {"all"}

        try:
            last_updated_dt = datetime.fromisoformat(last_updated)
            if last_updated_dt.tzinfo is None:
                last_updated_dt = last_updated_dt.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 発表日時ベースの判定のみ
            # 各サービスが自身のキャッシュ判定を行う

        except Exception as e:
            print(f"Error detecting stale indicators: {e}")
            return {"all"}

        return stale

    def _should_force_refresh(self, indicator: str) -> bool:
        """指標が強制更新対象かどうかを判定"""
        if "all" in self._stale_indicators:
            return True
        return indicator in self._stale_indicators

    def _prepare_for_refresh(self, last_updated: Optional[str]) -> None:
        """
        データ再取得の前処理
        """
        self._stale_indicators = self._detect_stale_indicators(last_updated)
        if self._stale_indicators:
            print(f"Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全雇用データを並列で取得

        Returns:
            {
                "ons_unemployment": {...},
                "ons_claimant_count": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.uk.ons_unemployment_service import ons_unemployment_service
        from services.uk.ons_claimant_count_service import ons_claimant_count_service
        from services.uk.ons_wages_service import ons_wages_service
        from services.uk.ons_real_wages_service import ons_real_wages_service
        from services.uk.ons_employment_service import ons_employment_service
        from services.uk.ons_economic_activity_service import ons_economic_activity_service
        from services.uk.ons_productivity_service import ons_productivity_service
        from services.uk.ons_unit_labour_costs_service import ons_unit_labour_costs_service
        from services.uk.indeed_wage_tracker_service import indeed_wage_tracker_uk_service

        result = {
            "ons_unemployment": None,
            "ons_claimant_count": None,
            "ons_wages": None,
            "ons_real_wages": None,
            "ons_employment": None,
            "ons_economic_activity": None,
            "ons_productivity": None,
            "ons_unit_labour_costs": None,
            "indeed_wage_tracker": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(self._get_ons_unemployment, ons_unemployment_service): "ons_unemployment",
                executor.submit(self._get_ons_claimant_count, ons_claimant_count_service): "ons_claimant_count",
                executor.submit(self._get_ons_wages, ons_wages_service): "ons_wages",
                executor.submit(self._get_ons_real_wages, ons_real_wages_service): "ons_real_wages",
                executor.submit(self._get_ons_employment, ons_employment_service): "ons_employment",
                executor.submit(self._get_ons_economic_activity, ons_economic_activity_service): "ons_economic_activity",
                executor.submit(self._get_ons_productivity, ons_productivity_service): "ons_productivity",
                executor.submit(self._get_ons_unit_labour_costs, ons_unit_labour_costs_service): "ons_unit_labour_costs",
                executor.submit(self._get_indeed_wage_tracker, indeed_wage_tracker_uk_service): "indeed_wage_tracker",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_ons_unemployment(self, service) -> dict:
        """ONS失業率データを取得"""
        try:
            force_refresh = self._should_force_refresh("ons_unemployment")
            response = service.get_ons_unemployment_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ONS Unemployment: {e}")
            return {"data": [], "latest": None, "next_release": None}

    def _get_ons_claimant_count(self, service) -> dict:
        """ONS失業給付申請件数データを取得"""
        try:
            force_refresh = self._should_force_refresh("ons_claimant_count")
            response = service.get_ons_claimant_count_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ONS Claimant Count: {e}")
            return {"data": [], "latest": None, "next_release": None}

    def _get_ons_wages(self, service) -> dict:
        """ONS平均賃金データを取得"""
        try:
            force_refresh = self._should_force_refresh("ons_wages")
            response = service.get_ons_wages_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ONS Wages: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ons_real_wages(self, service) -> dict:
        """ONS実質平均賃金データを取得"""
        try:
            force_refresh = self._should_force_refresh("ons_real_wages")
            response = service.get_ons_real_wages_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ONS Real Wages: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ons_employment(self, service) -> dict:
        """ONS雇用者数データを取得"""
        try:
            force_refresh = self._should_force_refresh("ons_employment")
            response = service.get_ons_employment_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ONS Employment: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ons_economic_activity(self, service) -> dict:
        """ONS経済活動率データを取得"""
        try:
            force_refresh = self._should_force_refresh("ons_economic_activity")
            response = service.get_ons_economic_activity_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ONS Economic Activity: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ons_productivity(self, service) -> dict:
        """ONS労働生産性データを取得"""
        try:
            force_refresh = self._should_force_refresh("ons_productivity")
            response = service.get_ons_productivity_data(force_refresh=force_refresh)
            return {
                "lzvb": response.get("lzvb", {}),
                "a4ym": response.get("a4ym", {}),
                "dmwo": response.get("dmwo", {}),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ONS Productivity: {e}")
            return {"lzvb": {}, "a4ym": {}, "dmwo": {}, "latest": None, "metadata": {}, "next_release": None}

    def _get_ons_unit_labour_costs(self, service) -> dict:
        """ONS単位労働コストデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ons_unit_labour_costs")
            response = service.get_ons_unit_labour_costs_data(force_refresh=force_refresh)
            return {
                "yoy": response.get("yoy", {}),
                "qoq": response.get("qoq", {}),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ONS Unit Labour Costs: {e}")
            return {"yoy": {}, "qoq": {}, "latest": None, "metadata": {}, "next_release": None}

    def _get_indeed_wage_tracker(self, service) -> dict:
        """Indeed賃金トラッカーデータを取得"""
        try:
            force_refresh = self._should_force_refresh("indeed_wage_tracker")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
            }
        except Exception as e:
            print(f"Error getting Indeed Wage Tracker: {e}")
            return {"data": [], "latest": None, "metadata": {}}
