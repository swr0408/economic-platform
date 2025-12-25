"""
米国雇用ダッシュボードローダー
失業率 / 広義の失業率 / 失業率内訳 / CB雇用機会業況判断 / 非農業部門雇用者数 / フルタイム・パートタイム雇用者数を一括取得

キャッシュ更新判定: 発表日時ベース方式
- 発表日: BLSから自動取得（毎月第1金曜日）
- 発表時刻: 8:30 ET（Employment Situation）
- CB雇用機会業況判断: 毎月最終火曜日 10:00 ET発表
- 発表日時を過ぎた指標は個別サービスもforce_refreshで再取得
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")


class USAEmploymentLoader(BaseDashboardLoader):
    """
    米国雇用ダッシュボード用データローダー

    取得データ:
    - unemployment_rate: 失業率 / 広義の失業率 - FRED UNRATE, U6RATE（毎月第1金曜日 8:30 ET）
    - unemployment_by_reason: 失業率内訳 - FRED LNS13023653 等（毎月第1金曜日 8:30 ET）
    - cb_jobs_labor: CB雇用機会業況判断 - Conference Board公式ページ（毎月最終火曜日 10:00 ET）
    - nonfarm_payrolls: 非農業部門雇用者数 - FRED PAYEMS 等（毎月第1金曜日 8:30 ET）
    - fullpart_time_employment: フルタイム/パートタイム雇用者数 - FRED LNS12500000/LNS12600000（毎月第1金曜日 8:30 ET）

    キャッシュ方式: 発表日時ベース判定
    - Employment Situation発表: 毎月第1金曜日 8:30 ET
    - CB雇用機会業況判断: 毎月最終火曜日 10:00 ET
    - 発表日時を過ぎた指標は個別サービスもforce_refreshで再取得
    """

    COUNTRY_CODE = "usa"
    CATEGORY_CODE = "employment"

    def __init__(self):
        super().__init__()
        # 発表日時を過ぎた指標のセット（load_all実行時に判定）
        self._stale_indicators: set = set()

    # 発表時刻設定（ET）
    EMPSIT_RELEASE_HOUR_ET = 8
    EMPSIT_RELEASE_MINUTE_ET = 30
    CB_RELEASE_HOUR_ET = 10
    CB_RELEASE_MINUTE_ET = 0

    def get_release_datetimes(self) -> List[Optional[datetime]]:
        """
        各指標の発表日時リストを返す

        Returns:
            - Employment Situation発表日時（8:30 ET）
            - CB雇用機会業況判断発表日時（10:00 ET）
        """
        release_times = []

        # Employment Situation発表日時（失業率の更新タイミング）
        empsit_release = self._get_empsit_release_datetime()
        if empsit_release:
            release_times.append(empsit_release)

        # CB雇用機会業況判断発表日時
        cb_release = self._get_cb_jobs_labor_release_datetime()
        if cb_release:
            release_times.append(cb_release)

        return release_times

    def _get_cb_jobs_labor_release_datetime(self) -> Optional[datetime]:
        """
        CB雇用機会業況判断の発表日時を取得

        Returns:
            発表日時（JST）、取得できない場合はNone
        """
        try:
            from services.usa.cb_jobs_labor_differential_service import cb_jobs_labor_differential_service

            # サービスからnext_releaseを取得
            data = cb_jobs_labor_differential_service.get_jobs_labor_data()
            next_release = data.get("next_release")

            if not next_release:
                return None

            date_str = next_release.get("date")
            if not date_str:
                return None

            # YYYY-MM-DD形式をパース
            try:
                base_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                return None

            # 発表時刻（10:00 ET）をJSTに変換
            release_et = datetime(
                base_date.year, base_date.month, base_date.day,
                self.CB_RELEASE_HOUR_ET,
                self.CB_RELEASE_MINUTE_ET,
                tzinfo=ET
            )
            release_jst = release_et.astimezone(JST)

            return release_jst

        except Exception as e:
            print(f"Error getting CB Jobs Labor release datetime: {e}")
            return None

    def _get_empsit_release_datetime(self) -> Optional[datetime]:
        """
        Employment Situation発表日時を取得

        Returns:
            発表日時（JST）、取得できない場合はNone
        """
        try:
            from services.usa.unemployment_rate_service import unemployment_rate_service

            # サービスからnext_releaseを取得（キャッシュから軽量に取得）
            data = unemployment_rate_service.get_unemployment_rate_data()
            next_release = data.get("next_release")

            if not next_release:
                return None

            date_str = next_release.get("date")
            if not date_str:
                return None

            # YYYY-MM-DD形式をパース
            try:
                base_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                return None

            # 発表時刻（8:30 ET）をJSTに変換
            release_et = datetime(
                base_date.year, base_date.month, base_date.day,
                self.EMPSIT_RELEASE_HOUR_ET,
                self.EMPSIT_RELEASE_MINUTE_ET,
                tzinfo=ET
            )
            release_jst = release_et.astimezone(JST)

            return release_jst

        except Exception as e:
            print(f"Error getting Employment Situation release datetime: {e}")
            return None

    def _detect_stale_indicators(self, last_updated: Optional[str]) -> set:
        """
        発表日時を過ぎた指標を検出

        Args:
            last_updated: ダッシュボードキャッシュのlast_updated（ISO形式）

        Returns:
            発表日時を過ぎた指標名のセット
        """
        if last_updated is None:
            return {"all"}

        try:
            last_updated_dt = datetime.fromisoformat(last_updated)
            if last_updated_dt.tzinfo is None:
                last_updated_dt = last_updated_dt.replace(tzinfo=JST)

            now = datetime.now(JST)
            stale = set()

            # Employment Situation発表（失業率・失業率内訳・非農業部門雇用者数・フルタイム/パートタイム）
            empsit_release = self._get_empsit_release_datetime()
            if empsit_release and last_updated_dt < empsit_release <= now:
                stale.add("unemployment_rate")
                stale.add("unemployment_by_reason")
                stale.add("nonfarm_payrolls")
                stale.add("fullpart_time_employment")
                print(f"[stale] Employment Situation release detected: {empsit_release.isoformat()}")

            # CB雇用機会業況判断発表
            cb_release = self._get_cb_jobs_labor_release_datetime()
            if cb_release and last_updated_dt < cb_release <= now:
                stale.add("cb_jobs_labor")
                print(f"[stale] CB Jobs Labor release detected: {cb_release.isoformat()}")

            return stale

        except Exception as e:
            print(f"Error detecting stale indicators: {e}")
            return {"all"}

    def _should_force_refresh(self, indicator: str) -> bool:
        """指標が強制更新対象かどうかを判定"""
        if "all" in self._stale_indicators:
            return True
        return indicator in self._stale_indicators

    def _prepare_for_refresh(self, last_updated: Optional[str]) -> None:
        """
        データ再取得の前処理

        発表日時を過ぎた指標を検出し、force_refresh対象を設定する。
        """
        self._stale_indicators = self._detect_stale_indicators(last_updated)
        if self._stale_indicators:
            print(f"Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全雇用データを並列で取得

        Returns:
            {
                "unemployment_rate": {...},
                "unemployment_by_reason": {...},
                "cb_jobs_labor": {...},
                "nonfarm_payrolls": {...},
                "fullpart_time_employment": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.usa.unemployment_rate_service import unemployment_rate_service
        from services.usa.unemployment_by_reason_service import unemployment_by_reason_service
        from services.usa.cb_jobs_labor_differential_service import cb_jobs_labor_differential_service
        from services.usa.nonfarm_payrolls_service import nonfarm_payrolls_service
        from services.usa.fullpart_time_employment_service import fullpart_time_employment_service

        result = {
            "unemployment_rate": None,
            "unemployment_by_reason": None,
            "cb_jobs_labor": None,
            "nonfarm_payrolls": None,
            "fullpart_time_employment": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(self._get_unemployment_rate, unemployment_rate_service): "unemployment_rate",
                executor.submit(self._get_unemployment_by_reason, unemployment_by_reason_service): "unemployment_by_reason",
                executor.submit(self._get_cb_jobs_labor, cb_jobs_labor_differential_service): "cb_jobs_labor",
                executor.submit(self._get_nonfarm_payrolls, nonfarm_payrolls_service): "nonfarm_payrolls",
                executor.submit(self._get_fullpart_time_employment, fullpart_time_employment_service): "fullpart_time_employment",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_unemployment_rate(self, service) -> Optional[dict]:
        """失業率データを取得"""
        try:
            force_refresh = self._should_force_refresh("unemployment_rate")
            response = service.get_unemployment_rate_data(force_refresh=force_refresh)
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting Unemployment Rate data: {e}")
            return None

    def _get_unemployment_by_reason(self, service) -> Optional[dict]:
        """失業率内訳データを取得"""
        try:
            force_refresh = self._should_force_refresh("unemployment_by_reason")
            response = service.get_unemployment_by_reason_data(force_refresh=force_refresh)
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "series_config": response.get("series_config"),
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting Unemployment by Reason data: {e}")
            return None

    def _get_cb_jobs_labor(self, service) -> Optional[dict]:
        """CB雇用機会業況判断データを取得"""
        try:
            force_refresh = self._should_force_refresh("cb_jobs_labor")
            response = service.get_jobs_labor_data(force_refresh=force_refresh)
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting CB Jobs Labor data: {e}")
            return None

    def _get_nonfarm_payrolls(self, service) -> Optional[dict]:
        """非農業部門雇用者数データを取得"""
        try:
            force_refresh = self._should_force_refresh("nonfarm_payrolls")
            response = service.get_nonfarm_payrolls_data(force_refresh=force_refresh)
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "series_config": response.get("series_config"),
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting Nonfarm Payrolls data: {e}")
            return None

    def _get_fullpart_time_employment(self, service) -> Optional[dict]:
        """フルタイム/パートタイム雇用者数データを取得"""
        try:
            force_refresh = self._should_force_refresh("fullpart_time_employment")
            response = service.get_fullpart_time_employment_data(force_refresh=force_refresh)
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "series_config": response.get("series_config"),
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting Full/Part-Time Employment data: {e}")
            return None

    def invalidate_cache(self) -> bool:
        """
        キャッシュを無効化（ダッシュボード + 個別サービス）
        """
        from services.usa.unemployment_rate_service import unemployment_rate_service
        from services.usa.unemployment_by_reason_service import unemployment_by_reason_service
        from services.usa.cb_jobs_labor_differential_service import cb_jobs_labor_differential_service
        from services.usa.nonfarm_payrolls_service import nonfarm_payrolls_service
        from services.usa.fullpart_time_employment_service import fullpart_time_employment_service

        # 全サービスのキャッシュを無効化
        services = [
            (unemployment_rate_service, "Unemployment Rate"),
            (unemployment_by_reason_service, "Unemployment by Reason"),
            (cb_jobs_labor_differential_service, "CB Jobs Labor Differential"),
            (nonfarm_payrolls_service, "Nonfarm Payrolls"),
            (fullpart_time_employment_service, "Full/Part-Time Employment"),
        ]
        self._invalidate_service_caches(services)

        # 親クラスのinvalidate_cacheを呼び出し
        return super().invalidate_cache()
