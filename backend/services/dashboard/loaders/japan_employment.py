"""
日本雇用ダッシュボードローダー
所定内給与など雇用関連指標を一括取得

キャッシュ更新判定: FMP発表日時ベース方式
- 所定内給与: 毎月上旬発表（FMPカレンダーから取得）
- 雇用形態別D.I.: 四半期発表（3,6,9,12月）
- 失業率: 毎月末発表（FMPカレンダーから取得）
- 有効求人倍率: 毎月末発表（FMPカレンダーから取得）

取得データ:
- scheduled_wage: 所定内給与（e-Stat版）
- scheduled_wage_common: 所定内給与（共通事業所版）
- employment_type: 雇用形態別労働者過不足判断D.I.
- unemployment: 完全失業率（季節調整値）
- job_offers_ratio: 有効求人倍率（季節調整値）
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class JapanEmploymentLoader(BaseDashboardLoader):
    """
    日本雇用ダッシュボード用データローダー

    取得データ:
    - scheduled_wage: 所定内給与（e-Stat版）
    - scheduled_wage_common: 所定内給与（共通事業所版）
    - employment_type: 雇用形態別労働者過不足判断D.I.
    - unemployment: 完全失業率（季節調整値）
    - job_offers_ratio: 有効求人倍率（季節調整値）

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "japan"
    CATEGORY_CODE = "employment"

    def __init__(self):
        super().__init__()
        self._stale_indicators: set = set()

    def get_release_datetimes(self) -> List[Optional[datetime]]:
        """
        各指標の発表日時リストを返す
        """
        release_times = []

        # 所定内給与発表日時
        scheduled_wage_release = self._get_scheduled_wage_release_datetime()
        if scheduled_wage_release:
            release_times.append(scheduled_wage_release)

        # 失業率発表日時
        unemployment_release = self._get_unemployment_release_datetime()
        if unemployment_release:
            release_times.append(unemployment_release)

        # 有効求人倍率発表日時
        job_offers_ratio_release = self._get_job_offers_ratio_release_datetime()
        if job_offers_ratio_release:
            release_times.append(job_offers_ratio_release)

        return release_times

    def _get_scheduled_wage_release_datetime(self) -> Optional[datetime]:
        """
        次回所定内給与発表日時を取得
        """
        try:
            from services.japan.fmp_next_release_utils import get_next_release_from_fmp

            next_release = get_next_release_from_fmp("jp_average_cash_earnings_yoy")
            if not next_release:
                return None

            datetime_jst_str = next_release.get("datetime_jst")
            if not datetime_jst_str:
                return None

            return datetime.fromisoformat(datetime_jst_str)

        except Exception as e:
            print(f"Error getting scheduled wage release datetime: {e}")
            return None

    def _get_unemployment_release_datetime(self) -> Optional[datetime]:
        """
        次回失業率発表日時を取得
        """
        try:
            from services.japan.japan_unemployment_service import japan_unemployment_service

            next_release = japan_unemployment_service._get_next_release_from_fmp()
            if not next_release:
                return None

            datetime_jst_str = next_release.get("datetime_jst")
            if not datetime_jst_str:
                return None

            return datetime.fromisoformat(datetime_jst_str)

        except Exception as e:
            print(f"Error getting unemployment release datetime: {e}")
            return None

    def _get_job_offers_ratio_release_datetime(self) -> Optional[datetime]:
        """
        次回有効求人倍率発表日時を取得
        """
        try:
            from services.japan.fmp_next_release_utils import get_next_release_from_fmp

            next_release = get_next_release_from_fmp("jp_job_offers_ratio")
            if not next_release:
                return None

            datetime_jst_str = next_release.get("datetime_jst")
            if not datetime_jst_str:
                return None

            return datetime.fromisoformat(datetime_jst_str)

        except Exception as e:
            print(f"Error getting job offers ratio release datetime: {e}")
            return None

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

            # 所定内給与発表
            scheduled_wage_release = self._get_scheduled_wage_release_datetime()
            if scheduled_wage_release and last_updated_dt < scheduled_wage_release <= now:
                stale.add("scheduled_wage")
                print(f"[stale] Scheduled wage release detected: {scheduled_wage_release.isoformat()}")

            # 失業率発表
            unemployment_release = self._get_unemployment_release_datetime()
            if unemployment_release and last_updated_dt < unemployment_release <= now:
                stale.add("unemployment")
                print(f"[stale] Unemployment release detected: {unemployment_release.isoformat()}")

            # 有効求人倍率発表
            job_offers_ratio_release = self._get_job_offers_ratio_release_datetime()
            if job_offers_ratio_release and last_updated_dt < job_offers_ratio_release <= now:
                stale.add("job_offers_ratio")
                print(f"[stale] Job offers ratio release detected: {job_offers_ratio_release.isoformat()}")

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
                "scheduled_wage": {...},  # e-Stat版
                "scheduled_wage_common": {...},  # 共通事業所版
                "employment_type": {...},  # 雇用形態別D.I.
            }
        """
        # 遅延インポート（循環参照回避）
        from services.japan.scheduled_wage_service import scheduled_wage_service
        from services.japan.scheduled_wage_common_service import scheduled_wage_common_service
        from services.japan.employment_type_service import employment_type_service
        from services.japan.japan_unemployment_service import japan_unemployment_service
        from services.japan.job_offers_ratio_service import job_offers_ratio_service

        result = {
            "scheduled_wage": None,
            "scheduled_wage_common": None,
            "employment_type": None,
            "unemployment": None,
            "job_offers_ratio": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(self._get_scheduled_wage, scheduled_wage_service): "scheduled_wage",
                executor.submit(self._get_scheduled_wage_common, scheduled_wage_common_service): "scheduled_wage_common",
                executor.submit(self._get_employment_type, employment_type_service): "employment_type",
                executor.submit(self._get_unemployment, japan_unemployment_service): "unemployment",
                executor.submit(self._get_job_offers_ratio, job_offers_ratio_service): "job_offers_ratio",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_scheduled_wage(self, service) -> dict:
        """所定内給与データを取得（e-Stat版）"""
        try:
            force_refresh = self._should_force_refresh("scheduled_wage")
            response = service.get_scheduled_wage_data(force_refresh=force_refresh)
            return {
                "scheduled_wage": response.get("scheduled_wage"),
                "general": response.get("general"),
                "part_time": response.get("part_time"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting scheduled wage (e-Stat): {e}")
            return {"scheduled_wage": None, "general": None, "part_time": None, "next_release": None}

    def _get_scheduled_wage_common(self, service) -> dict:
        """所定内給与データを取得（共通事業所版）"""
        try:
            force_refresh = self._should_force_refresh("scheduled_wage")
            response = service.get_scheduled_wage_data(force_refresh=force_refresh)
            return {
                "scheduled_wage": response.get("scheduled_wage"),
                "general": response.get("general"),
                "part_time": response.get("part_time"),
                "next_release": response.get("next_release"),
                "data_type": response.get("data_type"),
            }
        except Exception as e:
            print(f"Error getting scheduled wage (common): {e}")
            return {"scheduled_wage": None, "general": None, "part_time": None, "next_release": None, "data_type": None}

    def _get_employment_type(self, service) -> dict:
        """雇用形態別労働者過不足判断D.I.データを取得"""
        try:
            force_refresh = self._should_force_refresh("employment_type")
            response = service.get_employment_type_data(force_refresh=force_refresh)
            return {
                "regular_employee": response.get("regular_employee"),
                "part_time": response.get("part_time"),
            }
        except Exception as e:
            print(f"Error getting employment type D.I.: {e}")
            return {"regular_employee": None, "part_time": None}

    def _get_unemployment(self, service) -> dict:
        """失業率データを取得"""
        try:
            force_refresh = self._should_force_refresh("unemployment")
            response = service.get_unemployment_data(force_refresh=force_refresh)
            return {
                "unemployment_rate": response.get("unemployment_rate"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting unemployment rate: {e}")
            return {"unemployment_rate": None, "next_release": None}

    def _get_job_offers_ratio(self, service) -> dict:
        """有効求人倍率データを取得"""
        try:
            force_refresh = self._should_force_refresh("job_offers_ratio")
            response = service.get_job_offers_ratio_data(force_refresh=force_refresh)
            return {
                "job_offers_ratio": response.get("data"),
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting job offers ratio: {e}")
            return {"job_offers_ratio": None, "latest": None, "next_release": None}
