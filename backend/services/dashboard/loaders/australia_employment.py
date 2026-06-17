"""
オーストラリア雇用ダッシュボードローダー
ABS失業率など雇用関連指標を一括取得

キャッシュ更新判定: FMP発表日時ベース判定
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
SYDNEY = ZoneInfo("Australia/Sydney")


class AustraliaEmploymentLoader(BaseDashboardLoader):
    """
    オーストラリア雇用ダッシュボード用データローダー

    取得データ:
    - au_unemployment_rate: ABS失業率（季節調整済み）
    - au_employed_persons: ABS雇用者数（季節調整済み、千人）
    - au_fulltime_parttime: ABS雇用者数フルタイム/パートタイム（季節調整済み、千人）
    - au_participation_rate: ABS労働参加率（季節調整済み）
    - au_wage_price_index: ABS賃金物価指数（季節調整済み、QoQ/YoY）
    - au_job_vacancies: ABS求人件数（季節調整済み、千件）
    - au_underutilization: アンダー・ユーティライゼーション（不足雇用含む）

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "australia"
    CATEGORY_CODE = "employment"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "au_unemployment_rate",
        "au_employed_persons",
        "au_fulltime_parttime",
        "au_participation_rate",
        "au_wage_price_index",
        "au_job_vacancies",
        "au_anz_job_advertisements",
        "au_underutilization",
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
            print(f"[AustraliaEmployment] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全雇用データを取得

        Returns:
            {
                "au_unemployment_rate": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.australia.au_unemployment_rate_service import au_unemployment_rate_service
        from services.australia.au_employed_persons_service import au_employed_persons_service
        from services.australia.au_fulltime_parttime_service import au_fulltime_parttime_service
        from services.australia.au_participation_rate_service import au_participation_rate_service
        from services.australia.au_wage_price_index_service import au_wage_price_index_service
        from services.australia.au_job_vacancies_service import au_job_vacancies_service
        from services.australia.au_anz_job_advertisements_service import au_anz_job_advertisements_service
        from services.australia.au_underutilization_service import au_underutilization_service

        result = {
            "au_unemployment_rate": None,
            "au_employed_persons": None,
            "au_fulltime_parttime": None,
            "au_participation_rate": None,
            "au_wage_price_index": None,
            "au_job_vacancies": None,
            "au_anz_job_advertisements": None,
            "au_underutilization": None,
        }

        # データを取得
        result["au_unemployment_rate"] = self._get_unemployment_rate(au_unemployment_rate_service)
        result["au_employed_persons"] = self._get_employed_persons(au_employed_persons_service)
        result["au_fulltime_parttime"] = self._get_fulltime_parttime(au_fulltime_parttime_service)
        result["au_participation_rate"] = self._get_participation_rate(au_participation_rate_service)
        result["au_wage_price_index"] = self._get_wage_price_index(au_wage_price_index_service)
        result["au_job_vacancies"] = self._get_job_vacancies(au_job_vacancies_service)
        result["au_anz_job_advertisements"] = self._get_anz_job_advertisements(au_anz_job_advertisements_service)
        result["au_underutilization"] = self._get_underutilization(au_underutilization_service)

        return result

    def _get_unemployment_rate(self, service) -> dict:
        """ABS失業率データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_unemployment_rate")
            response = service.get_au_unemployment_rate_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaEmployment] Error getting Unemployment Rate: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_employed_persons(self, service) -> dict:
        """ABS雇用者数データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_employed_persons")
            response = service.get_au_employed_persons_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaEmployment] Error getting Employed Persons: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_fulltime_parttime(self, service) -> dict:
        """ABSフルタイム/パートタイム雇用者数データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_fulltime_parttime")
            response = service.get_au_fulltime_parttime_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaEmployment] Error getting Full-time/Part-time: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_participation_rate(self, service) -> dict:
        """ABS労働参加率データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_participation_rate")
            response = service.get_au_participation_rate_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaEmployment] Error getting Participation Rate: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_wage_price_index(self, service) -> dict:
        """ABS賃金物価指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_wage_price_index")
            response = service.get_au_wage_price_index_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaEmployment] Error getting Wage Price Index: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_job_vacancies(self, service) -> dict:
        """ABS求人件数データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_job_vacancies")
            response = service.get_au_job_vacancies_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaEmployment] Error getting Job Vacancies: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_anz_job_advertisements(self, service) -> dict:
        """ANZ求人広告データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_anz_job_advertisements")
            response = service.get_au_anz_job_advertisements_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaEmployment] Error getting ANZ Job Advertisements: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_underutilization(self, service) -> dict:
        """アンダー・ユーティライゼーションデータを取得"""
        try:
            force_refresh = self._should_force_refresh("au_underutilization")
            response = service.get_au_underutilization_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaEmployment] Error getting Underutilization: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}
