"""
米国雇用ダッシュボードローダー
失業率 / 広義の失業率 / 失業率内訳 / CB雇用機会業況判断 / 非農業部門雇用者数 / フルタイム・パートタイム雇用者数 /
複数の仕事を持つ人 / 経済的理由によるパートタイム / JOLTS求人 / Indeed求人件数 / JOLTS採用数・解雇数 / 求人倍率 /
ADP雇用者数 / NER Pulse（週次雇用変動）/ 新規失業保険申請件数 / 継続失業保険申請件数 / Challenger人員削減数 /
平均時給 / 自発的離職率 / 労働参加率 / ADP賃金上昇率 / アトランタ連銀賃金トラッカー / Indeed賃金トラッカー / PCEデフレーター飲食宿泊・娯楽 /
雇用コスト指数 / 単位労働コスト・労働生産性 / NFIB人件費・雇用計画 / NFIB労働報酬・失業率 / 平均残業時間 / 平均週労働時間を一括取得

キャッシュ更新判定: 発表日時ベース方式
- 発表日: BLSから自動取得（毎月第1金曜日）
- 発表時刻: 8:30 ET（Employment Situation）
- CB雇用機会業況判断: 毎月最終火曜日 10:00 ET発表
- JOLTS: 毎月上旬 10:00 ET発表
- ADP雇用者数: 毎月第1水曜日 8:15 ET発表
- NER Pulse: 毎週火曜日 8:15 ET発表（月次NER発表週を除く）
- 新規失業保険申請件数: 毎週木曜日 8:30 ET発表（祝日による例外日あり）
- 継続失業保険申請件数: 毎週木曜日 8:30 ET発表（新規と同時発表）
- Challenger人員削減数: 毎月第1木曜日 7:30 ET発表
- 雇用コスト指数: 四半期ごと発表（1月、4月、7月、10月）8:30 ET
- 単位労働コスト・労働生産性: 四半期ごと発表（2月、3月、5月、6月、8月、9月、11月、12月）8:30 ET
- NFIB人件費・雇用計画: 毎月第2火曜日 6:00 ET発表
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
    - multiple_jobs_parttime: 複数の仕事を持つ人/経済的理由によるパートタイム - FRED LNS12026619/LNS12032194（毎月第1金曜日 8:30 ET）
    - jolts_indeed: JOLTS求人/Indeed求人件数 - FRED JTSJOL/IHLIDXUS（JOLTSは毎月上旬 10:00 ET）
    - jolts_hires_layoffs: JOLTS採用数/解雇数 - FRED JTSHIL/JTSLDL（JOLTSは毎月上旬 10:00 ET）
    - job_openings_per_unemployed: 求人倍率 - FRED JTSJOL/UNEMPLOY（JOLTSまたはEmpsit発表時に更新）
    - adp_employment: ADP雇用者数 - FRED ADPMNUSNERSA（毎月第1水曜日 8:15 ET）
    - ner_pulse: NER Pulse（週次雇用変動）- ADP Media Center（毎週火曜日 8:15 ET）
    - initial_claims: 新規失業保険申請件数 - FRED ICSA/IC4WSA（毎週木曜日 8:30 ET）
    - continued_claims: 継続失業保険申請件数 - FRED CCSA/CC4WSA（毎週木曜日 8:30 ET）
    - challenger_job_cuts: Challenger人員削減数 - DB/FMP（毎月第1木曜日 7:30 ET）
    - average_hourly_earnings: 平均時給/自発的離職率 - FRED CES0500000003/JTSQUR（毎月第1金曜日 8:30 ET）
    - labor_force_participation: 労働参加率 - FRED CIVPART（毎月第1金曜日 8:30 ET）
    - adp_wage_growth: ADP賃金上昇率中央値 - ADP Pay Insights（毎月第1水曜日 8:15 ET）
    - atlanta_fed_wage: アトランタ連銀賃金トラッカー - Atlanta Fed（毎月第2金曜日頃）
    - indeed_wage_tracker: Indeed賃金トラッカー - Indeed Hiring Lab（毎月15日以降）
    - pce_food_recreation: PCEデフレーター飲食宿泊・娯楽 - BEA NIPA T20404（毎月末 8:30 ET）
    - employment_cost_index: 雇用コスト指数 - FRED ECIALLCIV（四半期ごと 8:30 ET）
    - unit_labor_cost: 単位労働コスト/労働生産性 - FRED PRS85006112/PRS85006092（四半期ごと 8:30 ET）
    - nfib_compensation: NFIB人件費・雇用計画 - NFIB PDF（毎月第2火曜日 6:00 ET）
    - nfib_compensation_unemployment: NFIB労働報酬・失業率 - NFIB PDF + FRED UNRATE（NFIB: 毎月第2火曜日 6:00 ET / UNRATE: 毎月第1金曜日 8:30 ET）
    - overtime_hours: 平均残業時間 - FRED AWOTMAN（毎月第1金曜日 8:30 ET）
    - us_average_weekly_working_hours: 平均週労働時間 - FRED CES0500000002/CES3000000002（毎月第1金曜日 8:30 ET）

    キャッシュ方式: 発表日時ベース判定
    - Employment Situation発表: 毎月第1金曜日 8:30 ET
    - CB雇用機会業況判断: 毎月最終火曜日 10:00 ET
    - JOLTS: 毎月上旬 10:00 ET
    - ADP雇用者数: 毎月第1水曜日 8:15 ET
    - NER Pulse: 毎週火曜日 8:15 ET（月次NER発表週を除く）
    - 新規失業保険申請件数: 毎週木曜日 8:30 ET（祝日による例外日あり）
    - 継続失業保険申請件数: 毎週木曜日 8:30 ET（新規と同時発表）
    - Challenger人員削減数: 毎月第1木曜日 7:30 ET
    - 雇用コスト指数: 四半期ごと発表（1月、4月、7月、10月）8:30 ET
    - 単位労働コスト・労働生産性: 四半期ごと発表（2月、3月、5月、6月、8月、9月、11月、12月）8:30 ET
    - NFIB人件費・雇用計画: 毎月第2火曜日 6:00 ET発表
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
    JOLTS_RELEASE_HOUR_ET = 10
    JOLTS_RELEASE_MINUTE_ET = 0
    ADP_RELEASE_HOUR_ET = 8
    ADP_RELEASE_MINUTE_ET = 15
    NER_PULSE_RELEASE_HOUR_ET = 8
    NER_PULSE_RELEASE_MINUTE_ET = 15
    INITIAL_CLAIMS_RELEASE_HOUR_ET = 8
    INITIAL_CLAIMS_RELEASE_MINUTE_ET = 30
    CHALLENGER_RELEASE_HOUR_ET = 7
    CHALLENGER_RELEASE_MINUTE_ET = 30
    ECI_RELEASE_HOUR_ET = 8
    ECI_RELEASE_MINUTE_ET = 30
    ULC_RELEASE_HOUR_ET = 8
    ULC_RELEASE_MINUTE_ET = 30

    def get_release_datetimes(self) -> List[Optional[datetime]]:
        """
        各指標の発表日時リストを返す

        Returns:
            - Employment Situation発表日時（8:30 ET）
            - CB雇用機会業況判断発表日時（10:00 ET）
            - JOLTS発表日時（10:00 ET）
            - ADP雇用者数発表日時（8:15 ET）
            - NER Pulse発表日時（8:15 ET）
            - 新規失業保険申請件数発表日時（8:30 ET）
            - 雇用コスト指数発表日時（8:30 ET）
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

        # JOLTS発表日時
        jolts_release = self._get_jolts_release_datetime()
        if jolts_release:
            release_times.append(jolts_release)

        # ADP雇用者数発表日時
        adp_release = self._get_adp_release_datetime()
        if adp_release:
            release_times.append(adp_release)

        # NER Pulse発表日時
        ner_pulse_release = self._get_ner_pulse_release_datetime()
        if ner_pulse_release:
            release_times.append(ner_pulse_release)

        # 新規失業保険申請件数発表日時
        initial_claims_release = self._get_initial_claims_release_datetime()
        if initial_claims_release:
            release_times.append(initial_claims_release)

        # Challenger人員削減数発表日時
        challenger_release = self._get_challenger_release_datetime()
        if challenger_release:
            release_times.append(challenger_release)

        # 雇用コスト指数発表日時
        eci_release = self._get_eci_release_datetime()
        if eci_release:
            release_times.append(eci_release)

        # 単位労働コスト・労働生産性発表日時
        ulc_release = self._get_ulc_release_datetime()
        if ulc_release:
            release_times.append(ulc_release)

        # NFIB人件費・雇用計画発表日時
        nfib_release = self._get_nfib_release_datetime()
        if nfib_release:
            release_times.append(nfib_release)

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

    def _get_jolts_release_datetime(self) -> Optional[datetime]:
        """
        JOLTS発表日時を取得

        Returns:
            発表日時（JST）、取得できない場合はNone
        """
        try:
            from services.usa.jolts_indeed_service import jolts_indeed_service

            # サービスからnext_releaseを取得
            data = jolts_indeed_service.get_jolts_indeed_data()
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
                self.JOLTS_RELEASE_HOUR_ET,
                self.JOLTS_RELEASE_MINUTE_ET,
                tzinfo=ET
            )
            release_jst = release_et.astimezone(JST)

            return release_jst

        except Exception as e:
            print(f"Error getting JOLTS release datetime: {e}")
            return None

    def _get_adp_release_datetime(self) -> Optional[datetime]:
        """
        ADP雇用者数の発表日時を取得

        Returns:
            発表日時（JST）、取得できない場合はNone
        """
        try:
            from services.usa.adp_employment_service import adp_employment_service

            # サービスからnext_releaseを取得
            data = adp_employment_service.get_adp_employment_data()
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

            # 発表時刻（8:15 ET）をJSTに変換
            release_et = datetime(
                base_date.year, base_date.month, base_date.day,
                self.ADP_RELEASE_HOUR_ET,
                self.ADP_RELEASE_MINUTE_ET,
                tzinfo=ET
            )
            release_jst = release_et.astimezone(JST)

            return release_jst

        except Exception as e:
            print(f"Error getting ADP release datetime: {e}")
            return None

    def _get_ner_pulse_release_datetime(self) -> Optional[datetime]:
        """
        NER Pulse（週次雇用変動）の発表日時を取得

        Returns:
            発表日時（JST）、取得できない場合はNone
        """
        try:
            from services.usa.ner_pulse_service import ner_pulse_service

            # サービスからnext_releaseを取得
            data = ner_pulse_service.get_ner_pulse_data()
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

            # 発表時刻（8:15 ET）をJSTに変換
            release_et = datetime(
                base_date.year, base_date.month, base_date.day,
                self.NER_PULSE_RELEASE_HOUR_ET,
                self.NER_PULSE_RELEASE_MINUTE_ET,
                tzinfo=ET
            )
            release_jst = release_et.astimezone(JST)

            return release_jst

        except Exception as e:
            print(f"Error getting NER Pulse release datetime: {e}")
            return None

    def _get_initial_claims_release_datetime(self) -> Optional[datetime]:
        """
        新規失業保険申請件数の発表日時を取得

        Returns:
            発表日時（JST）、取得できない場合はNone
        """
        try:
            from services.usa.initial_claims_service import initial_claims_service

            # サービスからnext_releaseを取得
            data = initial_claims_service.get_initial_claims_data()
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
                self.INITIAL_CLAIMS_RELEASE_HOUR_ET,
                self.INITIAL_CLAIMS_RELEASE_MINUTE_ET,
                tzinfo=ET
            )
            release_jst = release_et.astimezone(JST)

            return release_jst

        except Exception as e:
            print(f"Error getting Initial Claims release datetime: {e}")
            return None

    def _get_challenger_release_datetime(self) -> Optional[datetime]:
        """
        Challenger人員削減数の発表日時を取得

        Returns:
            発表日時（JST）、取得できない場合はNone
        """
        try:
            from services.usa.challenger_job_cuts_service import challenger_job_cuts_service

            # サービスからnext_releaseを取得
            next_release = challenger_job_cuts_service._get_next_release()

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

            # 発表時刻（7:30 ET）をJSTに変換
            release_et = datetime(
                base_date.year, base_date.month, base_date.day,
                self.CHALLENGER_RELEASE_HOUR_ET,
                self.CHALLENGER_RELEASE_MINUTE_ET,
                tzinfo=ET
            )
            release_jst = release_et.astimezone(JST)

            return release_jst

        except Exception as e:
            print(f"Error getting Challenger release datetime: {e}")
            return None

    def _get_eci_release_datetime(self) -> Optional[datetime]:
        """
        雇用コスト指数の発表日時を取得

        Returns:
            発表日時（JST）、取得できない場合はNone
        """
        try:
            from services.usa.employment_cost_index_service import employment_cost_index_service

            # サービスからnext_releaseを取得
            data = employment_cost_index_service.get_employment_cost_index_data()
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
                self.ECI_RELEASE_HOUR_ET,
                self.ECI_RELEASE_MINUTE_ET,
                tzinfo=ET
            )
            release_jst = release_et.astimezone(JST)

            return release_jst

        except Exception as e:
            print(f"Error getting ECI release datetime: {e}")
            return None

    def _get_ulc_release_datetime(self) -> Optional[datetime]:
        """
        単位労働コスト・労働生産性の発表日時を取得

        Returns:
            発表日時（JST）、取得できない場合はNone
        """
        try:
            from services.usa.unit_labor_cost_service import unit_labor_cost_service

            # サービスからnext_releaseを取得
            data = unit_labor_cost_service.get_unit_labor_cost_data()
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
                self.ULC_RELEASE_HOUR_ET,
                self.ULC_RELEASE_MINUTE_ET,
                tzinfo=ET
            )
            release_jst = release_et.astimezone(JST)

            return release_jst

        except Exception as e:
            print(f"Error getting ULC release datetime: {e}")
            return None

    def _get_nfib_release_datetime(self) -> Optional[datetime]:
        """
        NFIB人件費・雇用計画の発表日時を取得

        NFIB楽観指数と同じ発表日時（毎月第2火曜日 6:00 ET）

        Returns:
            発表日時（JST）、取得できない場合はNone
        """
        try:
            from services.usa.nfib_service import nfib_service

            # NFIBサービスからnext_releaseを取得
            data = nfib_service.get_nfib_data()
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

            # 発表時刻（6:00 ET = 19:00/20:00 JST）
            # NFIBは夏時間考慮が必要だが、nfib_service内で処理済み
            release_et = datetime(
                base_date.year, base_date.month, base_date.day,
                6, 0, 0,
                tzinfo=ET
            )
            release_jst = release_et.astimezone(JST)

            return release_jst

        except Exception as e:
            print(f"Error getting NFIB release datetime: {e}")
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
            return set()

        try:
            last_updated_dt = datetime.fromisoformat(last_updated)
            if last_updated_dt.tzinfo is None:
                last_updated_dt = last_updated_dt.replace(tzinfo=JST)

            now = datetime.now(JST)
            stale = set()

            # Employment Situation発表（失業率・失業率内訳・非農業部門雇用者数・フルタイム/パートタイム・複数の仕事を持つ人/経済的理由によるパートタイム・求人倍率・平均残業時間）
            empsit_release = self._get_empsit_release_datetime()
            if empsit_release and last_updated_dt < empsit_release <= now:
                stale.add("unemployment_rate")
                stale.add("unemployment_by_reason")
                stale.add("nonfarm_payrolls")
                stale.add("fullpart_time_employment")
                stale.add("multiple_jobs_parttime")
                stale.add("job_openings_per_unemployed")  # 求人倍率（UNEMPLOY使用）
                stale.add("average_hourly_earnings")  # 平均時給
                stale.add("labor_force_participation")  # 労働参加率
                stale.add("overtime_hours")  # 平均残業時間
                stale.add("us_average_weekly_working_hours")  # 平均週労働時間
                print(f"[stale] Employment Situation release detected: {empsit_release.isoformat()}")

            # CB雇用機会業況判断発表
            cb_release = self._get_cb_jobs_labor_release_datetime()
            if cb_release and last_updated_dt < cb_release <= now:
                stale.add("cb_jobs_labor")
                print(f"[stale] CB Jobs Labor release detected: {cb_release.isoformat()}")

            # JOLTS発表
            jolts_release = self._get_jolts_release_datetime()
            if jolts_release and last_updated_dt < jolts_release <= now:
                stale.add("jolts_indeed")
                stale.add("jolts_hires_layoffs")
                stale.add("job_openings_per_unemployed")  # 求人倍率（JTSJOL使用）
                print(f"[stale] JOLTS release detected: {jolts_release.isoformat()}")

            # ADP雇用者数発表（賃金上昇率も同時発表）
            adp_release = self._get_adp_release_datetime()
            if adp_release and last_updated_dt < adp_release <= now:
                stale.add("adp_employment")
                stale.add("adp_wage_growth")  # ADP賃金上昇率も同時発表
                print(f"[stale] ADP release detected: {adp_release.isoformat()}")

            # NER Pulse発表
            ner_pulse_release = self._get_ner_pulse_release_datetime()
            if ner_pulse_release and last_updated_dt < ner_pulse_release <= now:
                stale.add("ner_pulse")
                print(f"[stale] NER Pulse release detected: {ner_pulse_release.isoformat()}")

            # 新規失業保険申請件数発表
            initial_claims_release = self._get_initial_claims_release_datetime()
            if initial_claims_release and last_updated_dt < initial_claims_release <= now:
                stale.add("initial_claims")
                stale.add("continued_claims")  # 継続失業保険申請件数も同時発表
                print(f"[stale] Initial Claims release detected: {initial_claims_release.isoformat()}")

            # Challenger人員削減数発表
            challenger_release = self._get_challenger_release_datetime()
            if challenger_release and last_updated_dt < challenger_release <= now:
                stale.add("challenger_job_cuts")
                print(f"[stale] Challenger release detected: {challenger_release.isoformat()}")

            # 雇用コスト指数発表
            eci_release = self._get_eci_release_datetime()
            if eci_release and last_updated_dt < eci_release <= now:
                stale.add("employment_cost_index")
                print(f"[stale] Employment Cost Index release detected: {eci_release.isoformat()}")

            # 単位労働コスト・労働生産性発表
            ulc_release = self._get_ulc_release_datetime()
            if ulc_release and last_updated_dt < ulc_release <= now:
                stale.add("unit_labor_cost")
                print(f"[stale] Unit Labor Cost release detected: {ulc_release.isoformat()}")

            # NFIB人件費・雇用計画発表
            nfib_release = self._get_nfib_release_datetime()
            if nfib_release and last_updated_dt < nfib_release <= now:
                stale.add("nfib_compensation")
                stale.add("nfib_compensation_unemployment")  # NFIB労働報酬・失業率も同時に更新
                print(f"[stale] NFIB Compensation release detected: {nfib_release.isoformat()}")

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
        from services.usa.multiple_jobs_parttime_service import multiple_jobs_parttime_service
        from services.usa.jolts_indeed_service import jolts_indeed_service
        from services.usa.jolts_hires_layoffs_service import jolts_hires_layoffs_service
        from services.usa.job_openings_per_unemployed_service import job_openings_per_unemployed_service
        from services.usa.adp_employment_service import adp_employment_service
        from services.usa.ner_pulse_service import ner_pulse_service
        from services.usa.initial_claims_service import initial_claims_service
        from services.usa.continued_claims_service import continued_claims_service
        from services.usa.challenger_job_cuts_service import challenger_job_cuts_service
        from services.usa.average_hourly_earnings_service import average_hourly_earnings_service
        from services.usa.labor_force_participation_service import labor_force_participation_service
        from services.usa.adp_wage_growth_service import adp_wage_growth_service
        from services.usa.atlanta_fed_wage_service import atlanta_fed_wage_service
        from services.usa.indeed_wage_tracker_service import indeed_wage_tracker_service
        from services.usa.pce_food_recreation_service import pce_food_recreation_service
        from services.usa.employment_cost_index_service import employment_cost_index_service
        from services.usa.unit_labor_cost_service import unit_labor_cost_service
        from services.usa.nfib_service import nfib_service
        from services.usa.overtime_hours_service import overtime_hours_service
        from services.usa.us_average_weekly_working_hours_service import us_average_weekly_working_hours_service
        from services.usa.sahm_rule_service import sahm_rule_service

        result = {
            "unemployment_rate": None,
            "unemployment_by_reason": None,
            "cb_jobs_labor": None,
            "nonfarm_payrolls": None,
            "fullpart_time_employment": None,
            "multiple_jobs_parttime": None,
            "jolts_indeed": None,
            "jolts_hires_layoffs": None,
            "job_openings_per_unemployed": None,
            "adp_employment": None,
            "ner_pulse": None,
            "initial_claims": None,
            "continued_claims": None,
            "challenger_job_cuts": None,
            "average_hourly_earnings": None,
            "labor_force_participation": None,
            "adp_wage_growth": None,
            "atlanta_fed_wage": None,
            "indeed_wage_tracker": None,
            "pce_food_recreation": None,
            "employment_cost_index": None,
            "unit_labor_cost": None,
            "nfib_compensation": None,
            "nfib_compensation_unemployment": None,
            "overtime_hours": None,
            "us_average_weekly_working_hours": None,
            "sahm_rule": None,
        }

        # 並列でデータを取得（25ワーカー）
        with ThreadPoolExecutor(max_workers=25) as executor:
            futures = {
                executor.submit(self._get_unemployment_rate, unemployment_rate_service): "unemployment_rate",
                executor.submit(self._get_unemployment_by_reason, unemployment_by_reason_service): "unemployment_by_reason",
                executor.submit(self._get_cb_jobs_labor, cb_jobs_labor_differential_service): "cb_jobs_labor",
                executor.submit(self._get_nonfarm_payrolls, nonfarm_payrolls_service): "nonfarm_payrolls",
                executor.submit(self._get_fullpart_time_employment, fullpart_time_employment_service): "fullpart_time_employment",
                executor.submit(self._get_multiple_jobs_parttime, multiple_jobs_parttime_service): "multiple_jobs_parttime",
                executor.submit(self._get_jolts_indeed, jolts_indeed_service): "jolts_indeed",
                executor.submit(self._get_jolts_hires_layoffs, jolts_hires_layoffs_service): "jolts_hires_layoffs",
                executor.submit(self._get_job_openings_per_unemployed, job_openings_per_unemployed_service): "job_openings_per_unemployed",
                executor.submit(self._get_adp_employment, adp_employment_service): "adp_employment",
                executor.submit(self._get_ner_pulse, ner_pulse_service): "ner_pulse",
                executor.submit(self._get_initial_claims, initial_claims_service): "initial_claims",
                executor.submit(self._get_continued_claims, continued_claims_service): "continued_claims",
                executor.submit(self._get_challenger_job_cuts, challenger_job_cuts_service): "challenger_job_cuts",
                executor.submit(self._get_average_hourly_earnings, average_hourly_earnings_service): "average_hourly_earnings",
                executor.submit(self._get_labor_force_participation, labor_force_participation_service): "labor_force_participation",
                executor.submit(self._get_adp_wage_growth, adp_wage_growth_service): "adp_wage_growth",
                executor.submit(self._get_atlanta_fed_wage, atlanta_fed_wage_service): "atlanta_fed_wage",
                executor.submit(self._get_indeed_wage_tracker, indeed_wage_tracker_service): "indeed_wage_tracker",
                executor.submit(self._get_pce_food_recreation, pce_food_recreation_service): "pce_food_recreation",
                executor.submit(self._get_employment_cost_index, employment_cost_index_service): "employment_cost_index",
                executor.submit(self._get_unit_labor_cost, unit_labor_cost_service): "unit_labor_cost",
                executor.submit(self._get_nfib_compensation, nfib_service): "nfib_compensation",
                executor.submit(self._get_nfib_compensation_unemployment, nfib_service, unemployment_rate_service): "nfib_compensation_unemployment",
                executor.submit(self._get_overtime_hours, overtime_hours_service): "overtime_hours",
                executor.submit(self._get_us_average_weekly_working_hours, us_average_weekly_working_hours_service): "us_average_weekly_working_hours",
                executor.submit(self._get_sahm_rule, sahm_rule_service): "sahm_rule",
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

    def _get_multiple_jobs_parttime(self, service) -> Optional[dict]:
        """複数の仕事を持つ人/経済的理由によるパートタイムデータを取得"""
        try:
            force_refresh = self._should_force_refresh("multiple_jobs_parttime")
            response = service.get_multiple_jobs_parttime_data(force_refresh=force_refresh)
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
            print(f"Error getting Multiple Jobs / Part-Time data: {e}")
            return None

    def _get_jolts_indeed(self, service) -> Optional[dict]:
        """JOLTS/Indeed求人データを取得"""
        try:
            force_refresh = self._should_force_refresh("jolts_indeed")
            response = service.get_jolts_indeed_data(force_refresh=force_refresh)
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
            print(f"Error getting JOLTS / Indeed data: {e}")
            return None

    def _get_jolts_hires_layoffs(self, service) -> Optional[dict]:
        """JOLTS採用数/解雇数データを取得"""
        try:
            force_refresh = self._should_force_refresh("jolts_hires_layoffs")
            response = service.get_hires_layoffs_data(force_refresh=force_refresh)
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
            print(f"Error getting JOLTS Hires / Layoffs data: {e}")
            return None

    def _get_job_openings_per_unemployed(self, service) -> Optional[dict]:
        """求人倍率データを取得"""
        try:
            force_refresh = self._should_force_refresh("job_openings_per_unemployed")
            response = service.get_job_openings_per_unemployed_data(force_refresh=force_refresh)
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
            print(f"Error getting Job Openings per Unemployed data: {e}")
            return None

    def _get_adp_employment(self, service) -> Optional[dict]:
        """ADP雇用者数データを取得"""
        try:
            force_refresh = self._should_force_refresh("adp_employment")
            response = service.get_adp_employment_data(force_refresh=force_refresh)
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
            print(f"Error getting ADP Employment data: {e}")
            return None

    def _get_ner_pulse(self, service) -> Optional[dict]:
        """NER Pulse（週次雇用変動）データを取得"""
        try:
            force_refresh = self._should_force_refresh("ner_pulse")
            response = service.get_ner_pulse_data(force_refresh=force_refresh)
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
            print(f"Error getting NER Pulse data: {e}")
            return None

    def _get_initial_claims(self, service) -> Optional[dict]:
        """新規失業保険申請件数データを取得"""
        try:
            force_refresh = self._should_force_refresh("initial_claims")
            response = service.get_initial_claims_data(force_refresh=force_refresh)
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
            print(f"Error getting Initial Claims data: {e}")
            return None

    def _get_continued_claims(self, service) -> Optional[dict]:
        """継続失業保険申請件数データを取得"""
        try:
            force_refresh = self._should_force_refresh("continued_claims")
            response = service.get_continued_claims_data(force_refresh=force_refresh)
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
            print(f"Error getting Continued Claims data: {e}")
            return None

    def _get_challenger_job_cuts(self, service) -> Optional[dict]:
        """Challenger人員削減数データを取得"""
        try:
            force_refresh = self._should_force_refresh("challenger_job_cuts")
            response = service.get_challenger_data(force_refresh=force_refresh)
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
            print(f"Error getting Challenger Job Cuts data: {e}")
            return None

    def _get_average_hourly_earnings(self, service) -> Optional[dict]:
        """平均時給/自発的離職率データを取得"""
        try:
            force_refresh = self._should_force_refresh("average_hourly_earnings")
            response = service.get_average_hourly_earnings_data(force_refresh=force_refresh)
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
            print(f"Error getting Average Hourly Earnings data: {e}")
            return None

    def _get_labor_force_participation(self, service) -> Optional[dict]:
        """労働参加率データを取得"""
        try:
            force_refresh = self._should_force_refresh("labor_force_participation")
            response = service.get_labor_force_participation_data(force_refresh=force_refresh)
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
            print(f"Error getting Labor Force Participation data: {e}")
            return None

    def _get_adp_wage_growth(self, service) -> Optional[dict]:
        """ADP賃金上昇率中央値データを取得"""
        try:
            force_refresh = self._should_force_refresh("adp_wage_growth")
            response = service.get_adp_wage_growth_data(force_refresh=force_refresh)
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
            print(f"Error getting ADP Wage Growth data: {e}")
            return None

    def _get_atlanta_fed_wage(self, service) -> Optional[dict]:
        """アトランタ連銀賃金トラッカーデータを取得"""
        try:
            force_refresh = self._should_force_refresh("atlanta_fed_wage")
            response = service.get_atlanta_fed_wage_data(force_refresh=force_refresh)
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
            print(f"Error getting Atlanta Fed Wage data: {e}")
            return None

    def _get_indeed_wage_tracker(self, service) -> Optional[dict]:
        """Indeed賃金トラッカーデータを取得"""
        try:
            force_refresh = self._should_force_refresh("indeed_wage_tracker")
            response = service.get_indeed_wage_data(force_refresh=force_refresh)
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
            print(f"Error getting Indeed Wage Tracker data: {e}")
            return None

    def _get_pce_food_recreation(self, service) -> Optional[dict]:
        """PCEデフレーター飲食宿泊・娯楽データを取得"""
        try:
            force_refresh = self._should_force_refresh("pce_food_recreation")
            response = service.get_pce_food_recreation_data(force_refresh=force_refresh)
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
            print(f"Error getting PCE Food Recreation data: {e}")
            return None

    def _get_employment_cost_index(self, service) -> Optional[dict]:
        """雇用コスト指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("employment_cost_index")
            response = service.get_employment_cost_index_data(force_refresh=force_refresh)
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
            print(f"Error getting Employment Cost Index data: {e}")
            return None

    def _get_unit_labor_cost(self, service) -> Optional[dict]:
        """単位労働コスト/労働生産性データを取得"""
        try:
            force_refresh = self._should_force_refresh("unit_labor_cost")
            response = service.get_unit_labor_cost_data(force_refresh=force_refresh)
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
            print(f"Error getting Unit Labor Cost data: {e}")
            return None

    def _get_nfib_compensation(self, service) -> Optional[dict]:
        """NFIB人件費・雇用計画データを取得"""
        try:
            force_refresh = self._should_force_refresh("nfib_compensation")
            response = service.get_compensation_data(force_refresh=force_refresh)
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
            print(f"Error getting NFIB Compensation data: {e}")
            return None

    def _get_nfib_compensation_unemployment(self, nfib_service, unemployment_service) -> Optional[dict]:
        """
        NFIB労働報酬・失業率データを取得

        NFIB Actual Compensation Changes + 失業率(UNRATE)を組み合わせたデータを返す
        """
        try:
            force_refresh = self._should_force_refresh("nfib_compensation_unemployment")

            # NFIB Actual Compensation Changes取得
            nfib_response = nfib_service.get_actual_compensation_data(force_refresh=force_refresh)
            nfib_data = nfib_response.get("data", [])

            # 失業率データ取得（UNRATEのみ使用）
            ur_response = unemployment_service.get_unemployment_rate_data(force_refresh=force_refresh)
            ur_data = ur_response.get("data", [])

            if not nfib_data and not ur_data:
                return None

            # データをマージ（日付をキーにして結合）
            date_map = {}

            # NFIB Actual Compensation
            for item in nfib_data:
                date_str = item.get("date")
                if date_str:
                    if date_str not in date_map:
                        date_map[date_str] = {"date": date_str}
                    date_map[date_str]["actual_compensation"] = item.get("value")

            # 失業率（UNRATE）
            for item in ur_data:
                date_str = item.get("date")
                if date_str:
                    if date_str not in date_map:
                        date_map[date_str] = {"date": date_str}
                    date_map[date_str]["unemployment_rate"] = item.get("unrate")

            # 日付順にソート
            merged_data = sorted(date_map.values(), key=lambda x: x["date"])

            # 最新値を取得
            latest = None
            if merged_data:
                # 両方のデータがある最新のポイントを探す
                for item in reversed(merged_data):
                    if item.get("actual_compensation") is not None:
                        latest = item
                        break

            return {
                "data": merged_data,
                "latest": latest,
                "next_release": nfib_response.get("next_release"),
                "last_updated": nfib_response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting NFIB Compensation Unemployment data: {e}")
            return None

    def _get_overtime_hours(self, service) -> Optional[dict]:
        """平均残業時間データを取得"""
        try:
            force_refresh = self._should_force_refresh("overtime_hours")
            response = service.get_overtime_hours_data(force_refresh=force_refresh)
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
            print(f"Error getting Overtime Hours data: {e}")
            return None

    def _get_us_average_weekly_working_hours(self, service) -> Optional[dict]:
        """平均週労働時間データを取得"""
        try:
            force_refresh = self._should_force_refresh("us_average_weekly_working_hours")
            response = service.get_us_average_weekly_working_hours_data(force_refresh=force_refresh)
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
            print(f"Error getting Average Weekly Working Hours data: {e}")
            return None

    def _get_sahm_rule(self, service) -> Optional[dict]:
        """サームルールデータを取得"""
        try:
            force_refresh = self._should_force_refresh("sahm_rule")
            response = service.get_data(force_refresh=force_refresh)
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
            print(f"Error getting Sahm Rule data: {e}")
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
        from services.usa.multiple_jobs_parttime_service import multiple_jobs_parttime_service
        from services.usa.jolts_indeed_service import jolts_indeed_service
        from services.usa.jolts_hires_layoffs_service import jolts_hires_layoffs_service
        from services.usa.job_openings_per_unemployed_service import job_openings_per_unemployed_service
        from services.usa.adp_employment_service import adp_employment_service
        from services.usa.ner_pulse_service import ner_pulse_service
        from services.usa.initial_claims_service import initial_claims_service
        from services.usa.continued_claims_service import continued_claims_service
        from services.usa.challenger_job_cuts_service import challenger_job_cuts_service
        from services.usa.average_hourly_earnings_service import average_hourly_earnings_service
        from services.usa.labor_force_participation_service import labor_force_participation_service
        from services.usa.adp_wage_growth_service import adp_wage_growth_service
        from services.usa.atlanta_fed_wage_service import atlanta_fed_wage_service
        from services.usa.indeed_wage_tracker_service import indeed_wage_tracker_service
        from services.usa.pce_food_recreation_service import pce_food_recreation_service
        from services.usa.employment_cost_index_service import employment_cost_index_service
        from services.usa.unit_labor_cost_service import unit_labor_cost_service
        from services.usa.nfib_service import nfib_service
        from services.usa.overtime_hours_service import overtime_hours_service
        from services.usa.us_average_weekly_working_hours_service import us_average_weekly_working_hours_service
        from services.usa.sahm_rule_service import sahm_rule_service

        # 全サービスのキャッシュを無効化
        services = [
            (unemployment_rate_service, "Unemployment Rate"),
            (unemployment_by_reason_service, "Unemployment by Reason"),
            (cb_jobs_labor_differential_service, "CB Jobs Labor Differential"),
            (nonfarm_payrolls_service, "Nonfarm Payrolls"),
            (fullpart_time_employment_service, "Full/Part-Time Employment"),
            (multiple_jobs_parttime_service, "Multiple Jobs / Part-Time"),
            (jolts_indeed_service, "JOLTS / Indeed"),
            (jolts_hires_layoffs_service, "JOLTS Hires / Layoffs"),
            (job_openings_per_unemployed_service, "Job Openings per Unemployed"),
            (adp_employment_service, "ADP Employment"),
            (ner_pulse_service, "NER Pulse"),
            (initial_claims_service, "Initial Claims"),
            (continued_claims_service, "Continued Claims"),
            (challenger_job_cuts_service, "Challenger Job Cuts"),
            (average_hourly_earnings_service, "Average Hourly Earnings"),
            (labor_force_participation_service, "Labor Force Participation"),
            (adp_wage_growth_service, "ADP Wage Growth"),
            (atlanta_fed_wage_service, "Atlanta Fed Wage"),
            (indeed_wage_tracker_service, "Indeed Wage Tracker"),
            (pce_food_recreation_service, "PCE Food Recreation"),
            (employment_cost_index_service, "Employment Cost Index"),
            (unit_labor_cost_service, "Unit Labor Cost"),
            (nfib_service, "NFIB Compensation"),
            (overtime_hours_service, "Overtime Hours"),
            (us_average_weekly_working_hours_service, "Average Weekly Working Hours"),
            (sahm_rule_service, "Sahm Rule"),
        ]
        self._invalidate_service_caches(services)

        # 親クラスのinvalidate_cacheを呼び出し
        return super().invalidate_cache()
