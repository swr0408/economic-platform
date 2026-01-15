"""
ユーロ圏雇用ダッシュボードローダー
失業率、雇用者数変化、労働生産性、労働コスト指数、賃金・給与、交渉妥結賃金、Indeed賃金トラッカーなどの雇用関連指標を一括取得

キャッシュ更新判定: FMP発表日時ベース方式
- ECB Unemployment: FMP発表日時ベース更新（"Unemployment Rate"パターン）
- ECB Employment: FMP発表日時ベース更新（"Employment Change"パターン）
- ECB Labor Productivity: FMP発表日時ベース更新（ecb_employmentと同じスケジュール）
- ECB Unit Labour Cost: FMP発表日時ベース更新（"Labour Cost Index YoY"パターン）
- Eurostat Wages: FMP発表日時ベース更新（"eu_wage_growth"パターン）
- ECB Negotiated Wages: FMP発表日時ベース更新（"Negotiated Wage Growth"パターン）
- Indeed Euro Wage: 独自更新判定（15日以降1日1回チェック、月1回更新）
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class EurozoneEmploymentLoader(BaseDashboardLoader):
    """
    ユーロ圏雇用ダッシュボード用データローダー

    取得データ:
    - ecb_unemployment: ECB失業率
    - ecb_employment: ECB雇用者数変化（QoQ/YoY）
    - ecb_labor_productivity: ECB労働生産性（時間あたり・就業者あたり）
    - ecb_unit_labour_cost: ECB労働コスト指数（指数・YoY・QoQ）
    - eurostat_wages: Eurostat賃金・給与（YoY）
    - ecb_negotiated_wages: ECB交渉妥結賃金（YoY）
    - indeed_euro_wage: Indeed賃金トラッカー（ドイツ/フランス/ユーロ圏）

    キャッシュ方式: FMP発表日時ベース判定
    - ECB Unemployment: FMP発表日時ベース更新
    - ECB Employment: FMP発表日時ベース更新
    - ECB Labor Productivity: FMP発表日時ベース更新（ecb_employmentと同じスケジュール）
    - ECB Unit Labour Cost: FMP発表日時ベース更新
    - Eurostat Wages: FMP発表日時ベース更新
    - ECB Negotiated Wages: FMP発表日時ベース更新
    - Indeed Euro Wage: 独自更新判定（15日以降1日1回チェック、月1回更新）
    """

    COUNTRY_CODE = "eurozone"
    CATEGORY_CODE = "employment"

    # 期待されるデータキー（新しい指標追加時に更新）
    EXPECTED_KEYS = [
        "ecb_unemployment",
        "ecb_employment",
        "ecb_labor_productivity",
        "ecb_unit_labour_cost",
        "eurostat_wages",
        "ecb_negotiated_wages",
        "indeed_euro_wage",
        "germany_unemployment",
    ]

    def __init__(self):
        super().__init__()
        self._stale_indicators: set = set()

    def get_expected_keys(self) -> List[str]:
        """期待されるデータキーのリストを返す"""
        return self.EXPECTED_KEYS

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
                "ecb_unemployment": {...},
                "ecb_employment": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.eurozone.ecb_unemployment_service import ecb_unemployment_service
        from services.eurozone.ecb_employment_service import ecb_employment_service
        from services.eurozone.ecb_labor_productivity_service import ecb_labor_productivity_service
        from services.eurozone.ecb_unit_labour_cost_service import ecb_unit_labour_cost_service
        from services.eurozone.eurostat_wages_service import eurostat_wages_service
        from services.eurozone.ecb_negotiated_wages_service import ecb_negotiated_wages_service
        from services.eurozone.indeed_euro_wage_service import indeed_euro_wage_service
        from services.eurozone.germany_unemployment_service import germany_unemployment_service

        result = {
            "ecb_unemployment": None,
            "ecb_employment": None,
            "ecb_labor_productivity": None,
            "ecb_unit_labour_cost": None,
            "eurostat_wages": None,
            "ecb_negotiated_wages": None,
            "indeed_euro_wage": None,
            "germany_unemployment": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=9) as executor:
            futures = {
                executor.submit(self._get_ecb_unemployment, ecb_unemployment_service): "ecb_unemployment",
                executor.submit(self._get_ecb_employment, ecb_employment_service): "ecb_employment",
                executor.submit(self._get_ecb_labor_productivity, ecb_labor_productivity_service): "ecb_labor_productivity",
                executor.submit(self._get_ecb_unit_labour_cost, ecb_unit_labour_cost_service): "ecb_unit_labour_cost",
                executor.submit(self._get_eurostat_wages, eurostat_wages_service): "eurostat_wages",
                executor.submit(self._get_ecb_negotiated_wages, ecb_negotiated_wages_service): "ecb_negotiated_wages",
                executor.submit(self._get_indeed_euro_wage, indeed_euro_wage_service): "indeed_euro_wage",
                executor.submit(self._get_germany_unemployment, germany_unemployment_service): "germany_unemployment",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_ecb_unemployment(self, service) -> dict:
        """ECB失業率データを取得"""
        try:
            force_refresh = self._should_force_refresh("ecb_unemployment")
            response = service.get_ecb_unemployment_data(force_refresh=force_refresh)
            return {
                "unemployment_rate": response.get("unemployment_rate", []),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ECB Unemployment: {e}")
            return {"unemployment_rate": [], "metadata": {}}

    def _get_ecb_employment(self, service) -> dict:
        """ECB雇用者数変化データを取得"""
        try:
            force_refresh = self._should_force_refresh("ecb_employment")
            response = service.get_ecb_employment_data(force_refresh=force_refresh)
            return {
                "employment_qoq": response.get("employment_qoq", []),
                "employment_yoy": response.get("employment_yoy", []),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ECB Employment: {e}")
            return {"employment_qoq": [], "employment_yoy": [], "metadata": {}}

    def _get_ecb_labor_productivity(self, service) -> dict:
        """ECB労働生産性データを取得"""
        try:
            force_refresh = self._should_force_refresh("ecb_labor_productivity")
            response = service.get_ecb_labor_productivity_data(force_refresh=force_refresh)
            return {
                "per_hour": response.get("per_hour", []),
                "per_person": response.get("per_person", []),
                "per_hour_yoy": response.get("per_hour_yoy", []),
                "per_person_yoy": response.get("per_person_yoy", []),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ECB Labor Productivity: {e}")
            return {"per_hour": [], "per_person": [], "per_hour_yoy": [], "per_person_yoy": [], "metadata": {}}

    def _get_ecb_unit_labour_cost(self, service) -> dict:
        """ECB労働コスト指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("ecb_unit_labour_cost")
            response = service.get_ecb_unit_labour_cost_data(force_refresh=force_refresh)
            return {
                "unit_labour_cost": response.get("unit_labour_cost", []),
                "unit_labour_cost_yoy": response.get("unit_labour_cost_yoy", []),
                "unit_labour_cost_qoq": response.get("unit_labour_cost_qoq", []),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ECB Unit Labour Cost: {e}")
            return {"unit_labour_cost": [], "unit_labour_cost_yoy": [], "unit_labour_cost_qoq": [], "metadata": {}}

    def _get_eurostat_wages(self, service) -> dict:
        """Eurostat賃金・給与データを取得"""
        try:
            force_refresh = self._should_force_refresh("eurostat_wages")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting Eurostat Wages: {e}")
            return {"data": [], "latest": None, "metadata": {}}

    def _get_ecb_negotiated_wages(self, service) -> dict:
        """ECB交渉妥結賃金データを取得"""
        try:
            force_refresh = self._should_force_refresh("ecb_negotiated_wages")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ECB Negotiated Wages: {e}")
            return {"data": [], "latest": None, "metadata": {}}

    def _get_indeed_euro_wage(self, service) -> dict:
        """Indeed賃金トラッカー（ユーロ圏）データを取得"""
        try:
            force_refresh = self._should_force_refresh("indeed_euro_wage")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "germany": response.get("germany", []),
                "france": response.get("france", []),
                "euro_area": response.get("euro_area", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
            }
        except Exception as e:
            print(f"Error getting Indeed Euro Wage: {e}")
            return {"germany": [], "france": [], "euro_area": [], "latest": None, "metadata": {}}

    def _get_germany_unemployment(self, service) -> dict:
        """ドイツ失業率データを取得"""
        try:
            force_refresh = self._should_force_refresh("germany_unemployment")
            response = service.get_germany_unemployment_data(force_refresh=force_refresh)
            return {
                "unemployment_rate": response.get("unemployment_rate", []),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting Germany Unemployment: {e}")
            return {"unemployment_rate": [], "metadata": {}}
