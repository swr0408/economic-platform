"""
ニュージーランド雇用ダッシュボードローダー
雇用者数等を一括取得

キャッシュ更新判定: FMP発表日時ベース判定
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
AUCKLAND = ZoneInfo("Pacific/Auckland")


class NewZealandEmploymentLoader(BaseDashboardLoader):
    """
    ニュージーランド雇用ダッシュボード用データローダー

    取得データ:
    - nz_number_of_employees: 雇用者数（総雇用者数・フルタイム・パートタイム）
    - nz_unemployment_rate: 失業率（季節調整済み）
    - nz_wages: 賃金（全給与・賃金率指数 + 平均時給）
    - nz_labour_force_participation: 労働参加率
    - nz_labor_cost_index: 労働コスト指数

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "newzealand"
    CATEGORY_CODE = "employment"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "nz_number_of_employees",
        "nz_unemployment_rate",
        "nz_wages",
        "nz_labour_force_participation",
        "nz_labor_cost_index",
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
            print(f"[NewZealandEmployment] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全雇用データを取得

        Returns:
            {
                "nz_number_of_employees": {...},
                "nz_unemployment_rate": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.newzealand.nz_number_of_employees_service import nz_number_of_employees_service
        from services.newzealand.nz_unemployment_rate_service import nz_unemployment_rate_service
        from services.newzealand.nz_wages_service import nz_wages_service
        from services.newzealand.nz_labour_force_participation_service import nz_labour_force_participation_service
        from services.newzealand.nz_labor_cost_index_service import nz_labor_cost_index_service

        result = {
            "nz_number_of_employees": None,
            "nz_unemployment_rate": None,
            "nz_wages": None,
            "nz_labour_force_participation": None,
            "nz_labor_cost_index": None,
        }

        # データを取得
        result["nz_number_of_employees"] = self._get_indicator(
            nz_number_of_employees_service, "nz_number_of_employees", "Number of Employees"
        )
        result["nz_unemployment_rate"] = self._get_indicator(
            nz_unemployment_rate_service, "nz_unemployment_rate", "Unemployment Rate"
        )
        result["nz_wages"] = self._get_indicator(
            nz_wages_service, "nz_wages", "Wages (LCI + QES)"
        )
        result["nz_labour_force_participation"] = self._get_indicator(
            nz_labour_force_participation_service, "nz_labour_force_participation", "Labour Force Participation"
        )
        result["nz_labor_cost_index"] = self._get_indicator(
            nz_labor_cost_index_service, "nz_labor_cost_index", "Labor Cost Index"
        )

        return result

    def _get_indicator(self, service, indicator_key: str, label: str) -> dict:
        """指標データを取得"""
        try:
            force_refresh = self._should_force_refresh(indicator_key)
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[NewZealandEmployment] Error getting {label}: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}
