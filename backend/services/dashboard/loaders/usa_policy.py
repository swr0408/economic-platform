"""
米国金融政策ダッシュボードローダー
政策金利、タームプレミアム、FedWatch、FOMC関連データを一括取得

キャッシュ更新判定: 発表日時ベース方式
- 政策金利: FOMC発表後（14:00 ET = 翌4:00 JST）
- タームプレミアム: 毎日更新（6:00 JST、NY Fed更新後）
- FedWatch: 毎日更新（6:00 JST） + 手動更新可能
- SEP日程: FOMC発表日ベース
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader
from core.redis_client import redis_client


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")


class USAPolicyLoader(BaseDashboardLoader):
    """
    米国金融政策ダッシュボード用データローダー

    取得データ:
    - policy_rate: 政策金利（FRED DFEDTARU）
    - term_premium: タームプレミアム（NY Fed ACM）
    - kw_term_premium: KWタームプレミアム（FRED THREEFYTP10）
    - sep_dates: SEP発表日リスト
    - fedwatch_screenshot_url: FedWatchスクリーンショットURL

    キャッシュ方式: 発表日時ベース判定
    - FOMC発表: 14:00 ET（声明文発表）= 翌4:00 JST（冬時間）/ 翌3:00 JST（夏時間）
    - タームプレミアム: 毎日6:00 JST頃（NY Fed更新後）
    - FedWatch: 毎日6:00 JST + 手動更新API（/api/fedwatch/refresh）
    - SEP日程: FOMC発表日（has_sep=Trueの会合日）
    - 発表日時を過ぎた指標は個別サービスもforce_refreshで再取得
    """

    COUNTRY_CODE = "usa"
    CATEGORY_CODE = "policy"

    def __init__(self):
        super().__init__()
        # 発表日時を過ぎた指標のセット（load_all実行時に判定）
        self._stale_indicators: set = set()

    # FOMC声明発表時刻（ET）
    FOMC_RELEASE_HOUR_ET = 14
    FOMC_RELEASE_MINUTE_ET = 0

    # タームプレミアム・FedWatch更新時刻（JST）- NY Fedの更新を考慮して6:00 JST
    DAILY_UPDATE_HOUR_JST = 6
    DAILY_UPDATE_MINUTE_JST = 0

    # ON RRP・SOFR更新時刻（JST）- NY Fed RRPオペ終了後（13:15 ET = 翌3:15 JST）を考慮して4:00 JST
    ON_RRP_UPDATE_HOUR_JST = 4
    ON_RRP_UPDATE_MINUTE_JST = 0

    # MTS発表時刻（ET 2:00pm = JST翌日4:00）
    MTS_RELEASE_HOUR_ET = 14
    MTS_RELEASE_MINUTE_ET = 0

    # CBO Outlook発表時刻（ET 10:00am = JST翌日0:00）
    # 通常は2月と8月に発表（年2回）
    CBO_RELEASE_HOUR_ET = 10
    CBO_RELEASE_MINUTE_ET = 0

    def get_release_datetimes(self) -> List[Optional[datetime]]:
        """
        各指標の発表日時リストを返す

        Returns:
            - FOMC発表日時（次回FOMC会合日の14:00 ET）
            - タームプレミアム更新日時（毎日6:00 JST）
            - FedWatch更新日時（毎日6:00 JST）
            - SEP発表日時（FOMC発表日と同時）
            - ON RRP・SOFR更新日時（毎日4:00 JST）
        """
        release_times = []

        # 1. FOMC発表日時（政策金利の更新タイミング）
        fomc_release = self._get_fomc_release_datetime()
        if fomc_release:
            release_times.append(fomc_release)

        # 2. 日次更新（タームプレミアム、FedWatch）- 毎日6:00 JST
        daily_release = self._get_daily_release_datetime()
        if daily_release:
            release_times.append(daily_release)

        # 3. SEP発表日時（has_sep=TrueのFOMC会合日）
        sep_release = self._get_sep_release_datetime()
        if sep_release:
            release_times.append(sep_release)

        # 4. ON RRP・SOFR更新日時 - 毎日4:00 JST
        on_rrp_release = self._get_on_rrp_release_datetime()
        if on_rrp_release:
            release_times.append(on_rrp_release)

        # 5. MTS発表日時（連邦財政収支）- 翌月第8営業日 2:00pm ET
        mts_release = self._get_mts_release_datetime()
        if mts_release:
            release_times.append(mts_release)

        # 6. CBO Outlook発表日時 - 年2回（2月・8月）10:00am ET
        cbo_release = self._get_cbo_release_datetime()
        if cbo_release:
            release_times.append(cbo_release)

        # 7. CREローン延滞率発表日時 - 四半期（2月・5月・8月・11月）
        cre_release = self._get_cre_loan_delinquency_release_datetime()
        if cre_release:
            release_times.append(cre_release)

        return release_times

    def _get_fomc_release_datetime(self) -> Optional[datetime]:
        """
        次回FOMC発表日時を取得（キャッシュから軽量に取得）

        Returns:
            FOMC発表日時（JST）、取得できない場合はNone
        """
        try:
            from services.usa.fomc_schedule_service import fomc_schedule_service

            upcoming = fomc_schedule_service.get_upcoming_fomc_dates(count=1)
            if not upcoming:
                return None

            next_fomc = upcoming[0]
            date_str = next_fomc.get("date", "")

            if len(date_str) != 8:
                return None

            # YYYYMMDD形式をパース
            year = int(date_str[:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])

            # FOMC発表時刻（14:00 ET）をJSTに変換
            fomc_et = datetime(year, month, day,
                              self.FOMC_RELEASE_HOUR_ET,
                              self.FOMC_RELEASE_MINUTE_ET,
                              tzinfo=ET)
            fomc_jst = fomc_et.astimezone(JST)

            return fomc_jst

        except Exception as e:
            print(f"Error getting FOMC release datetime: {e}")
            return None

    def _get_daily_release_datetime(self) -> Optional[datetime]:
        """
        日次更新データの発表日時を取得（今日または昨日の6:00 JST）

        タームプレミアム、FedWatchは毎営業日更新されるため、
        今日の6:00 JSTを発表日時として返す。
        現在時刻が6:00より前なら昨日の6:00を返す。

        Returns:
            日次更新日時（JST）
        """
        try:
            now = datetime.now(JST)
            today_update = datetime(
                now.year, now.month, now.day,
                self.DAILY_UPDATE_HOUR_JST,
                self.DAILY_UPDATE_MINUTE_JST,
                tzinfo=JST
            )

            # 現在時刻が今日の更新時刻より前なら、昨日の更新時刻を返す
            if now < today_update:
                return today_update - timedelta(days=1)

            return today_update

        except Exception as e:
            print(f"Error getting daily release datetime: {e}")
            return None

    def _get_on_rrp_release_datetime(self) -> Optional[datetime]:
        """
        ON RRP・SOFR更新日時を取得（今日または昨日の4:00 JST）

        NY Fed RRPオペは毎営業日 12:45-13:15 ET に実施。
        日本時間では翌3:15 JST頃に結果が確定するため、4:00 JSTに更新。

        Returns:
            ON RRP更新日時（JST）
        """
        try:
            now = datetime.now(JST)
            today_update = datetime(
                now.year, now.month, now.day,
                self.ON_RRP_UPDATE_HOUR_JST,
                self.ON_RRP_UPDATE_MINUTE_JST,
                tzinfo=JST
            )

            # 現在時刻が今日の更新時刻より前なら、昨日の更新時刻を返す
            if now < today_update:
                return today_update - timedelta(days=1)

            return today_update

        except Exception as e:
            print(f"Error getting ON RRP release datetime: {e}")
            return None

    def _get_mts_release_datetime(self) -> Optional[datetime]:
        """
        MTS（Monthly Treasury Statement）発表日時を取得

        MTSは毎月「翌月の第8営業日」に発表される。
        発表時刻は 2:00pm ET（= JST翌日4:00目安）

        Returns:
            MTS発表日時（JST）、取得できない場合はNone
        """
        try:
            from services.usa.federal_budget_service import federal_budget_service

            next_release = federal_budget_service.get_next_release_date()
            if not next_release:
                return None

            date_str = next_release.get("date")
            if not date_str:
                return None

            # YYYY-MM-DD形式をパース
            base_date = datetime.strptime(date_str, "%Y-%m-%d")

            # 発表時刻（14:00 ET）をJSTに変換
            mts_et = datetime(
                base_date.year, base_date.month, base_date.day,
                self.MTS_RELEASE_HOUR_ET, self.MTS_RELEASE_MINUTE_ET,
                tzinfo=ET
            )
            return mts_et.astimezone(JST)

        except Exception as e:
            print(f"Error getting MTS release datetime: {e}")
            return None

    def _get_cbo_release_datetime(self) -> Optional[datetime]:
        """
        CBO Outlook発表日時を取得

        CBOの「Budget and Economic Outlook」は通常：
        - 2月（年初見通し）
        - 8月（中間更新）
        の年2回発表される。発表時刻は 10:00am ET。

        2026年は 2/11 10:00am ET に発表予定。
        （日本時間 2/12 0:00 JST）

        Returns:
            CBO発表日時（JST）、取得できない場合はNone
        """
        try:
            now = datetime.now(ET)
            cbo_release_dates = self._cbo_release_dates_et()

            # 次回の発表日時を返す
            for release_date in cbo_release_dates:
                if release_date > now:
                    return release_date.astimezone(JST)

            # 過去の発表日のみの場合は最新のものを返す
            if cbo_release_dates:
                return cbo_release_dates[-1].astimezone(JST)

            return None

        except Exception as e:
            print(f"Error getting CBO release datetime: {e}")
            return None

    def _get_cre_loan_delinquency_release_datetime(self) -> Optional[datetime]:
        """
        CREローン延滞率発表日時を取得

        FRB Charge-Off and Delinquency Rates:
        - 四半期ごと（2月・5月・8月・11月）の21日頃に発表
        - 発表時刻は明確でないため、10:00 ET（翌日0:00 JST）と想定

        Returns:
            CREローン延滞率発表日時（JST）、取得できない場合はNone
        """
        try:
            now = datetime.now(ET)

            # 発表月と大体の発表日
            release_months = [2, 5, 8, 11]
            release_day_approx = 21
            release_hour_et = 10

            # 次回発表日を見つける
            for month in release_months:
                if month > now.month or (month == now.month and now.day < release_day_approx):
                    next_date = datetime(
                        now.year, month, release_day_approx,
                        release_hour_et, 0, tzinfo=ET
                    )
                    return next_date.astimezone(JST)

            # 来年の2月
            next_date = datetime(
                now.year + 1, 2, release_day_approx,
                release_hour_et, 0, tzinfo=ET
            )
            return next_date.astimezone(JST)

        except Exception as e:
            print(f"Error getting CRE Loan Delinquency release datetime: {e}")
            return None

    def _get_sep_release_datetime(self) -> Optional[datetime]:
        """
        次回SEP発表日時を取得

        SEPはFOMC会合のうちhas_sep=Trueの会合で発表される。
        FOMC声明と同時（14:00 ET）に発表。

        Returns:
            SEP発表日時（JST）、取得できない場合はNone
        """
        try:
            from services.usa.fomc_schedule_service import fomc_schedule_service

            # 次回SEP付きFOMC会合を取得
            upcoming = fomc_schedule_service.get_upcoming_fomc_dates(count=4)
            if not upcoming:
                return None

            # has_sep=Trueの会合を探す
            for meeting in upcoming:
                if meeting.get("has_sep", False):
                    date_str = meeting.get("date", "")
                    if len(date_str) != 8:
                        continue

                    # YYYYMMDD形式をパース
                    year = int(date_str[:4])
                    month = int(date_str[4:6])
                    day = int(date_str[6:8])

                    # SEP発表時刻（14:00 ET）をJSTに変換
                    sep_et = datetime(year, month, day,
                                      self.FOMC_RELEASE_HOUR_ET,
                                      self.FOMC_RELEASE_MINUTE_ET,
                                      tzinfo=ET)
                    sep_jst = sep_et.astimezone(JST)

                    return sep_jst

            return None

        except Exception as e:
            print(f"Error getting SEP release datetime: {e}")
            return None

    # =========================================================================
    # 「直近に過ぎた発表日時」を返すヘルパー群
    #   stale判定は「次回（未来）の発表日」ではなく「直近に過ぎた発表日」と
    #   比較しなければ発火しない（旧実装は未来日と比較しており永久に不発だった）。
    # =========================================================================

    def _nth_weekday_of_month(self, year: int, month: int, n: int) -> datetime:
        """その月のn番目の平日（営業日近似、米国の祝日は考慮しない）を返す"""
        from calendar import monthrange
        _, last_day = monthrange(year, month)
        count = 0
        for day in range(1, last_day + 1):
            d = datetime(year, month, day)
            if d.weekday() < 5:  # 平日
                count += 1
                if count == n:
                    return d
        return datetime(year, month, last_day)

    def _expected_latest_budget_month(self, now_et: datetime) -> tuple:
        """
        現時点で公表済みであるべきMTSデータの対象月 (year, month) を返す。

        MTSは「翌月の第8営業日 14:00 ET」に前月分を公表。
        祝日で実際の発表が1日ほど後ろにずれ得るため、発表予定日に1日の猶予を加える。
        """
        eighth = self._nth_weekday_of_month(now_et.year, now_et.month, 8)
        release_due = datetime(
            eighth.year, eighth.month, eighth.day,
            self.MTS_RELEASE_HOUR_ET, self.MTS_RELEASE_MINUTE_ET, tzinfo=ET
        ) + timedelta(days=1)  # 祝日ズレ吸収

        if now_et >= release_due:
            # 当月分は公表済み → 前月が最新
            y, m = now_et.year, now_et.month - 1
        else:
            # 当月分は未公表 → 前々月が最新
            y, m = now_et.year, now_et.month - 2

        while m <= 0:
            m += 12
            y -= 1
        return (y, m)

    def _federal_budget_is_behind(self) -> bool:
        """
        federal_budgetのキャッシュ最新月が、現時点で公表済みであるべき月に
        追いついていなければTrue（祝日ズレに強く、データが進むまで再取得を促す）。
        """
        try:
            from services.usa.federal_budget_service import federal_budget_service

            cached = redis_client.get(federal_budget_service.CACHE_KEY)
            if not cached:
                # キャッシュ未生成は通常ロードに任せる（force不要）
                return False
            latest = cached.get("latest") or {}
            date_str = latest.get("date")
            if not date_str or len(date_str) < 7:
                return False

            cur = (int(date_str[:4]), int(date_str[5:7]))
            exp = self._expected_latest_budget_month(datetime.now(ET))
            return cur < exp
        except Exception as e:
            print(f"Error checking federal_budget freshness: {e}")
            return False

    def _get_last_fomc_release_datetime(self) -> Optional[datetime]:
        """直近に過ぎたFOMC会合の発表日時（14:00 ET → JST）を返す"""
        try:
            from services.usa.fomc_schedule_service import fomc_schedule_service

            schedule = fomc_schedule_service.get_schedule()
            now = datetime.now(JST)
            last_dt = None
            for _year, meetings in schedule.items():
                for meeting in meetings:
                    date_str = meeting.get("date", "")
                    if len(date_str) != 8:
                        continue
                    dt = datetime(
                        int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]),
                        self.FOMC_RELEASE_HOUR_ET, self.FOMC_RELEASE_MINUTE_ET, tzinfo=ET
                    ).astimezone(JST)
                    if dt <= now and (last_dt is None or dt > last_dt):
                        last_dt = dt
            return last_dt
        except Exception as e:
            print(f"Error getting last FOMC release datetime: {e}")
            return None

    def _get_last_sep_release_datetime(self) -> Optional[datetime]:
        """直近に過ぎたSEP付きFOMC会合の発表日時（14:00 ET → JST）を返す"""
        try:
            from services.usa.fomc_schedule_service import fomc_schedule_service

            schedule = fomc_schedule_service.get_schedule()
            now = datetime.now(JST)
            last_dt = None
            for _year, meetings in schedule.items():
                for meeting in meetings:
                    if not meeting.get("has_sep", False):
                        continue
                    date_str = meeting.get("date", "")
                    if len(date_str) != 8:
                        continue
                    dt = datetime(
                        int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]),
                        self.FOMC_RELEASE_HOUR_ET, self.FOMC_RELEASE_MINUTE_ET, tzinfo=ET
                    ).astimezone(JST)
                    if dt <= now and (last_dt is None or dt > last_dt):
                        last_dt = dt
            return last_dt
        except Exception as e:
            print(f"Error getting last SEP release datetime: {e}")
            return None

    def _cbo_release_dates_et(self) -> List[datetime]:
        """CBO Budget and Economic Outlook の発表予定日（ET、昇順）"""
        return [
            # 2026年（年初見通し）
            datetime(2026, 2, 11, self.CBO_RELEASE_HOUR_ET, self.CBO_RELEASE_MINUTE_ET, tzinfo=ET),
            # 2026年8月（中間更新、通常8月下旬）
            datetime(2026, 8, 20, self.CBO_RELEASE_HOUR_ET, self.CBO_RELEASE_MINUTE_ET, tzinfo=ET),
            # 2027年2月（予定）
            datetime(2027, 2, 10, self.CBO_RELEASE_HOUR_ET, self.CBO_RELEASE_MINUTE_ET, tzinfo=ET),
        ]

    def _get_last_cbo_release_datetime(self) -> Optional[datetime]:
        """直近に過ぎたCBO発表日時（JST）を返す"""
        try:
            now = datetime.now(ET)
            past = [d for d in self._cbo_release_dates_et() if d <= now]
            if not past:
                return None
            return max(past).astimezone(JST)
        except Exception as e:
            print(f"Error getting last CBO release datetime: {e}")
            return None

    def _get_last_cre_loan_delinquency_release_datetime(self) -> Optional[datetime]:
        """直近に過ぎたCREローン延滞率発表日時（四半期・21日頃 10:00 ET → JST）を返す"""
        try:
            now = datetime.now(ET)
            release_months = [2, 5, 8, 11]
            release_day_approx = 21
            release_hour_et = 10

            candidates = []
            for year in (now.year - 1, now.year):
                for month in release_months:
                    d = datetime(year, month, release_day_approx, release_hour_et, 0, tzinfo=ET)
                    if d <= now:
                        candidates.append(d)
            if not candidates:
                return None
            return max(candidates).astimezone(JST)
        except Exception as e:
            print(f"Error getting last CRE Loan Delinquency release datetime: {e}")
            return None

    def _detect_stale_indicators(self, last_updated: Optional[str]) -> set:
        """
        発表日時を過ぎた指標を検出

        Args:
            last_updated: ダッシュボードキャッシュのlast_updated（ISO形式）

        Returns:
            発表日時を過ぎた指標名のセット
        """
        stale = set()

        if last_updated is None:
            return set()

        try:
            last_updated_dt = datetime.fromisoformat(last_updated)
            if last_updated_dt.tzinfo is None:
                last_updated_dt = last_updated_dt.replace(tzinfo=JST)

            now = datetime.now(JST)

            # FOMC発表（政策金利）- 直近に過ぎた会合と比較
            last_fomc = self._get_last_fomc_release_datetime()
            if last_fomc and last_updated_dt < last_fomc <= now:
                stale.add("policy_rate")
                print(f"[stale] FOMC release detected: {last_fomc.isoformat()}")

            # SEP発表 - 直近に過ぎたSEP付き会合と比較
            last_sep = self._get_last_sep_release_datetime()
            if last_sep and last_updated_dt < last_sep <= now:
                stale.add("sep")
                print(f"[stale] SEP release detected: {last_sep.isoformat()}")

            # 日次更新（タームプレミアム、FedWatch）- 6:00 JST
            daily_release = self._get_daily_release_datetime()
            if daily_release and last_updated_dt < daily_release <= now:
                stale.add("term_premium")
                stale.add("kw_term_premium")
                print(f"[stale] Daily update detected: {daily_release.isoformat()}")

            # ON RRP・SOFR更新 - 4:00 JST
            on_rrp_release = self._get_on_rrp_release_datetime()
            if on_rrp_release and last_updated_dt < on_rrp_release <= now:
                stale.add("on_rrp")
                stale.add("sofr_volatility")
                print(f"[stale] ON RRP/SOFR update detected: {on_rrp_release.isoformat()}")

            # MTS発表（連邦財政収支）- 公表済みであるべき月にキャッシュが追いついて
            # いなければstale。旧実装は next_release（未来の発表日）と比較しており
            # 条件が永久に不成立で発火しなかった（祝日ズレにも強いデータ基準に変更）。
            if self._federal_budget_is_behind():
                stale.add("federal_budget")
                print("[stale] Federal budget cache behind latest expected month")

            # CBO Outlook発表 - 直近に過ぎた発表日と比較
            last_cbo = self._get_last_cbo_release_datetime()
            if last_cbo and last_updated_dt < last_cbo <= now:
                stale.add("cbo_projections")
                print(f"[stale] CBO Outlook release detected: {last_cbo.isoformat()}")

            # CREローン延滞率発表 - 直近に過ぎた発表日と比較
            last_cre = self._get_last_cre_loan_delinquency_release_datetime()
            if last_cre and last_updated_dt < last_cre <= now:
                stale.add("cre_loan_delinquency")
                print(f"[stale] CRE Loan Delinquency release detected: {last_cre.isoformat()}")

        except Exception as e:
            print(f"Error detecting stale indicators: {e}")
            # エラー時に {"all"} を返すと、エラーが続く限り毎リクエストで全指標の
            # 外部API一斉取得が走りイベントループ/executorを圧迫する (2026-06-13 障害)。
            # 判定不能時はキャッシュ継続に倒す (各サービスのスケジューラが個別に更新する)。
            return set()

        return stale

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
        全金融政策データを並列で取得

        Returns:
            {
                "policy_rate": [...],
                "term_premium": [...],
                "kw_term_premium": [...],
                "sep_dates": [...],
                "fedwatch_screenshot_url": str
            }
        """
        # 遅延インポート（循環参照回避）
        from services.usa.fed_h15_service import fed_h15_service
        from services.usa.nyfed_service import nyfed_term_premium_service
        from services.usa.sofr_volatility_service import sofr_volatility_service
        from services.usa.on_rrp_service import on_rrp_service
        from services.usa.fred_service import fred_service
        from services.usa.fomc_schedule_service import fomc_schedule_service
        from services.usa.frb_total_assets_service import frb_total_assets_service
        from services.usa.reserve_balances_service import reserve_balances_service
        from services.usa.tga_service import tga_service
        from services.usa.oas_service import oas_service
        from services.usa.federal_budget_service import federal_budget_service
        from services.usa.cbo_projections_service import cbo_projections_service
        from services.usa.cre_loan_delinquency_service import cre_loan_delinquency_service

        result = {
            "policy_rate": None,
            "term_premium": None,
            "kw_term_premium": None,
            "sofr_volatility": None,
            "on_rrp": None,
            "frb_total_assets": None,
            "reserve_balances": None,
            "tga": None,
            "oas": None,
            "federal_budget": None,
            "cbo_projections": None,
            "cre_loan_delinquency": None,
            "sep_dates": None,
            "fedwatch_screenshot_url": None,
            "next_fomc": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=12) as executor:
            futures = {
                executor.submit(self._get_policy_rate, fed_h15_service): "policy_rate",
                executor.submit(self._get_term_premium, nyfed_term_premium_service): "term_premium",
                executor.submit(self._get_kw_term_premium, fred_service): "kw_term_premium",
                executor.submit(self._get_sofr_volatility, sofr_volatility_service): "sofr_volatility",
                executor.submit(self._get_on_rrp, on_rrp_service): "on_rrp",
                executor.submit(self._get_frb_total_assets, frb_total_assets_service): "frb_total_assets",
                executor.submit(self._get_reserve_balances, reserve_balances_service): "reserve_balances",
                executor.submit(self._get_tga, tga_service): "tga",
                executor.submit(self._get_oas, oas_service): "oas",
                executor.submit(self._get_federal_budget, federal_budget_service): "federal_budget",
                executor.submit(self._get_cbo_projections, cbo_projections_service): "cbo_projections",
                executor.submit(self._get_cre_loan_delinquency, cre_loan_delinquency_service): "cre_loan_delinquency",
                executor.submit(self._get_sep_dates, fomc_schedule_service): "sep_dates",
                executor.submit(self._get_fedwatch_url): "fedwatch_screenshot_url",
                executor.submit(self._get_next_fomc, fomc_schedule_service): "next_fomc",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_policy_rate(self, service) -> list:
        """政策金利データを取得。

        政策金利は次の FOMC 変更まで据え置き(階段状)。最終データ点が過去の変更日のままだと
        「いつ時点の現行金利か」が分かりにくいため、最終点を最新営業日まで**値据え置きで延長**する。
        FOMC での変更は従来どおり stale 検知 → force_refresh で反映されるため、
        変更を取りこぼして古い値を延長することはない。
        """
        try:
            force_refresh = self._should_force_refresh("policy_rate")
            response = service.get_policy_rate(force_refresh=force_refresh)
            return self._extend_to_latest_business_day(response.get("data", []), value_key="rate")
        except Exception as e:
            print(f"Error getting policy rate: {e}")
            return []

    def _extend_to_latest_business_day(self, data: list, value_key: str = "rate") -> list:
        """据え置き系列(政策金利等)の最終点を最新営業日まで値据え置きで延長する。

        - 既に最新営業日まで点がある場合は何もしない(冪等)。
        - 米国金利のため ET 基準の最新営業日(土日はスキップ)を採用。
        - 元データは破壊せず新リストを返す。値は最後の点の値をそのまま複製(延長)。
        """
        if not data:
            return data
        try:
            last = data[-1]
            last_date = datetime.strptime(last["date"], "%Y-%m-%d").date()
        except (KeyError, ValueError, TypeError):
            return data
        et_today = datetime.now(ZoneInfo("America/New_York")).date()
        latest_bday = et_today
        while latest_bday.weekday() >= 5:  # 5=土, 6=日
            latest_bday -= timedelta(days=1)
        if latest_bday <= last_date:
            return data
        return list(data) + [{"date": latest_bday.isoformat(), value_key: last.get(value_key)}]

    def _get_term_premium(self, service) -> list:
        """タームプレミアムデータを取得"""
        try:
            force_refresh = self._should_force_refresh("term_premium")
            response = service.get_term_premium_data(force_refresh=force_refresh)
            return response.get("data", [])
        except Exception as e:
            print(f"Error getting term premium: {e}")
            return []

    def _get_kw_term_premium(self, service) -> list:
        """KWタームプレミアムデータを取得"""
        try:
            force_refresh = self._should_force_refresh("kw_term_premium")
            response = service.get_kw_term_premium(force_refresh=force_refresh)
            return response.get("data", [])
        except Exception as e:
            print(f"Error getting KW term premium: {e}")
            return []

    def _get_sofr_volatility(self, service) -> dict:
        """SOFRボラティリティデータを取得"""
        try:
            force_refresh = self._should_force_refresh("sofr_volatility")
            response = service.get_sofr_volatility_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
            }
        except Exception as e:
            print(f"Error getting SOFR volatility: {e}")
            return {"data": [], "latest": None, "metadata": {}}

    def _get_on_rrp(self, service) -> dict:
        """ON RRP（Overnight Reverse Repo）データを取得"""
        try:
            force_refresh = self._should_force_refresh("on_rrp")
            response = service.get_on_rrp_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
            }
        except Exception as e:
            print(f"Error getting ON RRP: {e}")
            return {"data": [], "latest": None, "metadata": {}}

    def _get_frb_total_assets(self, service) -> list:
        """FRB総資産データを取得"""
        try:
            force_refresh = self._should_force_refresh("frb_total_assets")
            response = service.get_data(force_refresh=force_refresh)
            return response.get("data", [])
        except Exception as e:
            print(f"Error getting FRB total assets: {e}")
            return []

    def _get_reserve_balances(self, service) -> list:
        """準備預金残高データを取得"""
        try:
            force_refresh = self._should_force_refresh("reserve_balances")
            response = service.get_data(force_refresh=force_refresh)
            return response.get("data", [])
        except Exception as e:
            print(f"Error getting reserve balances: {e}")
            return []

    def _get_tga(self, service) -> list:
        """TGA（財務省一般勘定残高）データを取得"""
        try:
            force_refresh = self._should_force_refresh("tga")
            response = service.get_data(force_refresh=force_refresh)
            return response.get("data", [])
        except Exception as e:
            print(f"Error getting TGA: {e}")
            return []

    def _get_oas(self, service) -> dict:
        """OAS（Option-Adjusted Spread）データを取得"""
        try:
            force_refresh = self._should_force_refresh("oas")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "hy_spread": response.get("hy_spread", []),
                "ig_spread": response.get("ig_spread", []),
                "hy_yield": response.get("hy_yield", []),
            }
        except Exception as e:
            print(f"Error getting OAS: {e}")
            return {"hy_spread": [], "ig_spread": [], "hy_yield": []}

    def _get_federal_budget(self, service) -> dict:
        """連邦財政収支データを取得"""
        try:
            force_refresh = self._should_force_refresh("federal_budget")
            response = service.get_federal_budget_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": service.get_next_release_date(),
            }
        except Exception as e:
            print(f"Error getting Federal Budget: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_cbo_projections(self, service) -> dict:
        """CBO財政見通しデータを取得"""
        try:
            force_refresh = self._should_force_refresh("cbo_projections")
            response = service.get_cbo_projections_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", {}),
                "latest_baseline_date": response.get("latest_baseline_date"),
                "projection_years": response.get("projection_years", []),
                "metadata": response.get("metadata", {}),
            }
        except Exception as e:
            print(f"Error getting CBO Projections: {e}")
            return {"data": {}, "latest_baseline_date": None, "projection_years": [], "metadata": {}}

    def _get_cre_loan_delinquency(self, service) -> dict:
        """CREローン延滞率データを取得"""
        try:
            response = service.get_cre_delinquency_data()
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting CRE Loan Delinquency: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_sep_dates(self, service) -> list:
        """SEP発表日リストを取得（過去の公開済み日付のみ）"""
        try:
            return service.get_sep_dates(count=4, include_future=False)
        except Exception as e:
            print(f"Error getting SEP dates: {e}")
            return []

    def _get_fedwatch_url(self) -> str:
        """FedWatchスクリーンショットのURLを取得"""
        # 静的ファイルとして配信されるURLを返す
        return "/api/fedwatch/image"

    def _get_next_fomc(self, service) -> dict:
        """次回FOMC会合情報を取得"""
        try:
            upcoming = service.get_upcoming_fomc_dates(count=1)
            if upcoming and len(upcoming) > 0:
                next_meeting = upcoming[0]
                # 日付をフォーマット（YYYYMMDD -> YYYY/MM/DD）
                date_str = next_meeting.get("date", "")
                if len(date_str) == 8:
                    formatted_date = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:8]}"
                else:
                    formatted_date = date_str
                return {
                    "date": formatted_date,
                    "label": next_meeting.get("label", ""),
                    "has_sep": next_meeting.get("has_sep", False),
                }
            return None
        except Exception as e:
            print(f"Error getting next FOMC: {e}")
            return None
