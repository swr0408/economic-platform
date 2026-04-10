"""
カナダ雇用ダッシュボードローダー
雇用者数などを一括取得

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
FMP_PATTERN_EMPLOYMENT = "Employment Change"


class CanadaEmploymentLoader(BaseDashboardLoader):
    """
    カナダ雇用ダッシュボード用データローダー

    取得データ:
    - ca_employment: 雇用者数

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "canada"
    CATEGORY_CODE = "employment"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "ca_employment",
        "ca_unemployment_rate",
        "ca_labor_force_participation_rate",
        "ca_average_hourly_wage",
        "ca_weekly_average_salary",
        "ca_job_vacancy_rate",
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
            return {"all"}

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
            print(f"[CanadaEmployment] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全雇用データを並列で取得

        Returns:
            {
                "ca_employment": {...},
                "ca_unemployment_rate": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.canada.ca_employment_service import ca_employment_service
        from services.canada.ca_unemployment_rate_service import ca_unemployment_rate_service
        from services.canada.ca_labor_force_participation_rate_service import ca_labor_force_participation_rate_service
        from services.canada.ca_average_hourly_wage_service import ca_average_hourly_wage_service
        from services.canada.ca_weekly_average_salary_service import ca_weekly_average_salary_service
        from services.canada.ca_job_vacancy_rate_service import ca_job_vacancy_rate_service

        result = {
            "ca_employment": None,
            "ca_unemployment_rate": None,
            "ca_labor_force_participation_rate": None,
            "ca_average_hourly_wage": None,
            "ca_weekly_average_salary": None,
            "ca_job_vacancy_rate": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(self._get_ca_employment, ca_employment_service): "ca_employment",
                executor.submit(self._get_ca_unemployment_rate, ca_unemployment_rate_service): "ca_unemployment_rate",
                executor.submit(self._get_ca_labor_force_participation_rate, ca_labor_force_participation_rate_service): "ca_labor_force_participation_rate",
                executor.submit(self._get_ca_average_hourly_wage, ca_average_hourly_wage_service): "ca_average_hourly_wage",
                executor.submit(self._get_ca_weekly_average_salary, ca_weekly_average_salary_service): "ca_weekly_average_salary",
                executor.submit(self._get_ca_job_vacancy_rate, ca_job_vacancy_rate_service): "ca_job_vacancy_rate",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"[CanadaEmployment] Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_ca_employment(self, service) -> dict:
        """カナダ雇用者数データを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_employment")
            response = service.get_ca_employment_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaEmployment] Error getting Employment: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ca_unemployment_rate(self, service) -> dict:
        """カナダ失業率データを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_unemployment_rate")
            response = service.get_ca_unemployment_rate_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaEmployment] Error getting Unemployment rate: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ca_labor_force_participation_rate(self, service) -> dict:
        """カナダ労働参加率データを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_labor_force_participation_rate")
            response = service.get_ca_labor_force_participation_rate_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaEmployment] Error getting Labor force participation rate: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ca_average_hourly_wage(self, service) -> dict:
        """カナダ平均時給データを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_average_hourly_wage")
            response = service.get_ca_average_hourly_wage_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaEmployment] Error getting Average hourly wage: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ca_weekly_average_salary(self, service) -> dict:
        """カナダ週間平均給与データを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_weekly_average_salary")
            response = service.get_ca_weekly_average_salary_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaEmployment] Error getting Weekly average salary: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ca_job_vacancy_rate(self, service) -> dict:
        """カナダ求人率データを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_job_vacancy_rate")
            response = service.get_ca_job_vacancy_rate_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaEmployment] Error getting Job vacancy rate: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}
