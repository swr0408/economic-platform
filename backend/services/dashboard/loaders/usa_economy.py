"""
米国経済ダッシュボードローダー
GDP成長率、GDP寄与度、GDP項目別成長率、潜在成長率、銀行貸し出し態度、FCI-G、NFCI、GDPNow、
ISM製造業、ISMサブインデックス、ISM非製造業、ISM非製造業サブインデックス、
NY連銀製造業景気指数、フィラデルフィア連銀製造業景気指数、NFIB中小企業楽観指数、
NFIB中小企業設備投資計画、鉱工業生産、設備稼働率、耐久財受注、米国航空機便数、TSA旅客数、
OpenTableレストラン予約件数を一括取得

キャッシュ更新判定: 発表日時ベース方式
- 各指標の発表日時をチェックし、last_updatedより後に発表があれば再取得
"""
from typing import Dict, Any, Optional, List
from datetime import time, datetime, timedelta
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


class USAEconomyLoader(BaseDashboardLoader):
    """
    米国経済ダッシュボード用データローダー

    取得データ:
    - gdp_growth_rate: GDP成長率（前期比年率）- FRED A191RL1Q225SBEA
    - gdp_contributions: GDP寄与度（5項目）- FRED各シリーズ
    - gdp_components_growth: GDP項目別成長率 - BEA NIPA T10101
    - potential_gdp: 潜在成長率（名目/実質）- FRED GDPPOT, NGDPPOT
    - bank_lending: 銀行貸し出し態度（SLOOS）- FRED DRTSCILM
    - fci: FCI-G（金融情勢指数）- Federal Reserve CSV
    - nfci: シカゴ連銀金融環境指数 - FRED NFCI（毎週水曜日更新）
    - gdpnow: GDPNow（リアルタイムGDP予測）- Atlanta Fed（月6-7回更新）
    - ism_manufacturing: ISM製造業景況指数 - DB/FMP（毎月第1営業日 10:00 ET）
    - ism_components: ISM製造業サブインデックス - DBnomics（毎月第1営業日 10:00 ET）
    - ism_non_manufacturing: ISM非製造業景況指数 - DB/FMP（毎月第3営業日 10:00 ET）
    - ism_non_manufacturing_components: ISM非製造業サブインデックス - DBnomics（毎月第3営業日 10:00 ET）
    - sp_pmi: S&P Global PMI（製造業/サービス業/総合）- DB/FMP（速報値:毎月第3週、確報値:毎月第1週 9:45 ET）
    - empire_state: NY連銀製造業景気指数 - FRED（毎月15日付近 8:30 ET）
    - philadelphia_fed: フィラデルフィア連銀製造業景気指数 - FRED（毎月第3木曜日 8:30 ET）
    - nfib: NFIB中小企業楽観指数 - NFIB PDF（毎月第2火曜日 6:00 ET）
    - nfib_capex: NFIB中小企業設備投資計画 - NFIB PDF（毎月第2火曜日 6:00 ET）
    - industrial_production: 鉱工業生産 - FRED INDPRO（毎月14〜18日頃 9:15 ET）
    - capacity_utilization: 設備稼働率 - FRED TCU（毎月14〜18日頃 9:15 ET、鉱工業生産と同時）
    - durable_goods: 耐久財受注 - FRED DGORDER, ADXTNO（毎月下旬 8:30 ET）
    - us_flights: 米国航空機便数 - Airportia スクリーンショット（毎日 UTC 06:00 = JST 15:00）
    - tsa_checkpoint: TSA旅客数 - TSA公式サイト（毎日 EST 10:00頃）
    - opentable: OpenTableレストラン予約件数前年比 - OpenTable スクリーンショット（毎日 ET 10:00頃）
    - next_gdp_release: 次回GDP発表情報
    - next_ism_non_manufacturing_release: 次回ISM非製造業発表情報

    キャッシュ方式: 発表日時ベース判定
    - 各指標の発表日時をチェックし、last_updatedより後に発表があれば再取得
    - 発表日時を過ぎた指標は個別サービスもforce_refreshで再取得
    """

    COUNTRY_CODE = "usa"
    CATEGORY_CODE = "economy"

    def __init__(self):
        super().__init__()
        # 発表日時を過ぎた指標のセット（load_all実行時に判定）
        self._stale_indicators: set = set()

    # 発表時刻設定（ET）
    RELEASE_TIMES = {
        # 月次・四半期指標
        "gdp": {"hour": 8, "minute": 30},              # GDP: 8:30 ET
        "ism_manufacturing": {"hour": 10, "minute": 0}, # ISM製造業: 10:00 ET
        "ism_non_manufacturing": {"hour": 10, "minute": 0},  # ISM非製造業: 10:00 ET
        "sp_pmi": {"hour": 9, "minute": 45},           # S&P PMI: 9:45 ET
        "empire_state": {"hour": 8, "minute": 30},     # NY連銀: 8:30 ET
        "philadelphia_fed": {"hour": 8, "minute": 30}, # フィラデルフィア連銀: 8:30 ET
        "nfib": {"hour": 6, "minute": 0},              # NFIB: 6:00 ET
        "industrial_production": {"hour": 9, "minute": 15},  # 鉱工業生産: 9:15 ET
        "durable_goods": {"hour": 8, "minute": 30},    # 耐久財受注: 8:30 ET
        "bank_lending": {"hour": 14, "minute": 0},     # SLOOS: 14:00 ET（四半期）
        # 週次指標
        "nfci": {"hour": 8, "minute": 30},             # NFCI: 8:30 ET（毎週水曜日）
        # 日次指標
        "tsa_checkpoint": {"hour": 10, "minute": 0},   # TSA: 10:00 ET
        "opentable": {"hour": 10, "minute": 0},        # OpenTable: 10:00 ET
        "us_flights": {"hour": 6, "minute": 0, "tz": "UTC"},  # 航空便: 06:00 UTC
    }

    # 日次更新指標の更新時刻（JST）
    DAILY_UPDATE_TIMES = {
        "fci": {"hour": 6, "minute": 0},      # FCI-G: 6:00 JST（Fed更新後）
        "gdpnow": {"hour": 6, "minute": 0},   # GDPNow: 6:00 JST（Atlanta Fed更新後）
    }

    def get_release_datetimes(self) -> List[Optional[datetime]]:
        """
        各指標の発表日時リストを返す（並列実行）

        各サービスが持つnext_release情報から発表日時を取得し、
        発表日時リストを返す。
        """
        release_times = []

        # 並列で発表日時を取得
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(self._get_gdp_release_datetimes),
                executor.submit(self._get_ism_release_datetimes),
                executor.submit(self._get_regional_fed_release_datetimes),
                executor.submit(self._get_nfib_release_datetimes),
                executor.submit(self._get_industrial_release_datetimes),
                executor.submit(self._get_durable_goods_release_datetimes),
                executor.submit(self._get_bank_lending_release_datetimes),
                executor.submit(self._get_nfci_release_datetimes),
                executor.submit(self._get_fci_gdpnow_release_datetimes),
                executor.submit(self._get_daily_release_datetimes),
            ]

            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        release_times.extend(result)
                except Exception:
                    pass

        return release_times

    def _detect_stale_indicators(self, last_updated: Optional[str]) -> set:
        """
        発表日時を過ぎた指標を検出（並列実行）

        ダッシュボードキャッシュのlast_updatedと現在時刻を比較し、
        その間に発表があった指標を検出する。

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

            # 並列で発表日時を取得
            stale = set()
            check_results = {}

            with ThreadPoolExecutor(max_workers=12) as executor:
                futures = {
                    executor.submit(self._get_gdp_release_datetimes): "gdp",
                    executor.submit(self._get_ism_manufacturing_release_datetime): "ism_manufacturing",
                    executor.submit(self._get_ism_non_manufacturing_release_datetime): "ism_non_manufacturing",
                    executor.submit(self._get_empire_state_release_datetime): "empire_state",
                    executor.submit(self._get_philadelphia_fed_release_datetime): "philadelphia_fed",
                    executor.submit(self._get_nfib_release_datetimes): "nfib",
                    executor.submit(self._get_industrial_release_datetimes): "industrial",
                    executor.submit(self._get_durable_goods_release_datetimes): "durable_goods",
                    executor.submit(self._get_bank_lending_release_datetimes): "bank_lending",
                    executor.submit(self._get_nfci_release_datetimes): "nfci",
                    executor.submit(self._get_fci_gdpnow_release_datetimes): "fci_gdpnow",
                    executor.submit(self._get_daily_release_datetimes): "daily",
                }

                for future in as_completed(futures):
                    key = futures[future]
                    try:
                        check_results[key] = future.result()
                    except Exception:
                        check_results[key] = None

            # 結果を判定
            def is_stale(release_dt):
                return release_dt and last_updated_dt < release_dt <= now

            # GDP関連
            gdp_releases = check_results.get("gdp") or []
            for release_dt in (gdp_releases if isinstance(gdp_releases, list) else [gdp_releases]):
                if is_stale(release_dt):
                    stale.add("gdp")
                    break

            # ISM製造業
            if is_stale(check_results.get("ism_manufacturing")):
                stale.add("ism_manufacturing")

            # ISM非製造業
            if is_stale(check_results.get("ism_non_manufacturing")):
                stale.add("ism_non_manufacturing")

            # NY連銀
            if is_stale(check_results.get("empire_state")):
                stale.add("empire_state")

            # フィラデルフィア連銀
            if is_stale(check_results.get("philadelphia_fed")):
                stale.add("philadelphia_fed")

            # NFIB
            nfib_releases = check_results.get("nfib") or []
            for release_dt in (nfib_releases if isinstance(nfib_releases, list) else [nfib_releases]):
                if is_stale(release_dt):
                    stale.add("nfib")
                    break

            # 鉱工業生産・設備稼働率（同時発表）
            industrial_releases = check_results.get("industrial") or []
            for release_dt in (industrial_releases if isinstance(industrial_releases, list) else [industrial_releases]):
                if is_stale(release_dt):
                    stale.add("industrial_production")
                    stale.add("capacity_utilization")
                    break

            # 耐久財受注
            durable_releases = check_results.get("durable_goods") or []
            for release_dt in (durable_releases if isinstance(durable_releases, list) else [durable_releases]):
                if is_stale(release_dt):
                    stale.add("durable_goods")
                    break

            # 銀行貸し出し態度（SLOOS）
            bank_releases = check_results.get("bank_lending") or []
            for release_dt in (bank_releases if isinstance(bank_releases, list) else [bank_releases]):
                if is_stale(release_dt):
                    stale.add("bank_lending")
                    break

            # NFCI
            nfci_releases = check_results.get("nfci") or []
            for release_dt in (nfci_releases if isinstance(nfci_releases, list) else [nfci_releases]):
                if is_stale(release_dt):
                    stale.add("nfci")
                    break

            # FCI-G, GDPNow（日次）
            fci_releases = check_results.get("fci_gdpnow") or []
            for release_dt in (fci_releases if isinstance(fci_releases, list) else [fci_releases]):
                if is_stale(release_dt):
                    stale.add("fci")
                    stale.add("gdpnow")
                    break

            # 日次指標（TSA, OpenTable, 航空便）
            daily_releases = check_results.get("daily") or []
            for release_dt in (daily_releases if isinstance(daily_releases, list) else [daily_releases]):
                if is_stale(release_dt):
                    stale.add("tsa_checkpoint")
                    stale.add("opentable")
                    stale.add("us_flights")
                    break

            if stale:
                print(f"[stale] Detected stale indicators: {stale}")

            return stale

        except Exception as e:
            print(f"Error detecting stale indicators: {e}")
            # エラー時は全指標を更新対象とする
            return {"all"}

    def _get_ism_manufacturing_release_datetime(self) -> Optional[datetime]:
        """ISM製造業の発表日時を取得"""
        try:
            from services.usa.ism_manufacturing_service import ism_manufacturing_service
            mfg_data = ism_manufacturing_service.get_ism_manufacturing_data()
            next_release = mfg_data.get("next_release")
            if next_release:
                date_str = next_release.get("date")
                return self._make_release_datetime(date_str, "ism_manufacturing")
        except Exception:
            pass
        return None

    def _get_ism_non_manufacturing_release_datetime(self) -> Optional[datetime]:
        """ISM非製造業の発表日時を取得"""
        try:
            from services.usa.ism_non_manufacturing_service import ism_non_manufacturing_service
            non_mfg_data = ism_non_manufacturing_service.get_ism_non_manufacturing_data()
            next_release = non_mfg_data.get("next_release")
            if next_release:
                date_str = next_release.get("date")
                return self._make_release_datetime(date_str, "ism_non_manufacturing")
        except Exception:
            pass
        return None

    def _get_empire_state_release_datetime(self) -> Optional[datetime]:
        """NY連銀の発表日時を取得"""
        try:
            from services.usa.empire_state_service import empire_state_service
            data = empire_state_service.get_empire_state_data()
            next_release = data.get("next_release")
            if next_release:
                date_str = next_release.get("date")
                return self._make_release_datetime(date_str, "empire_state")
        except Exception:
            pass
        return None

    def _get_philadelphia_fed_release_datetime(self) -> Optional[datetime]:
        """フィラデルフィア連銀の発表日時を取得"""
        try:
            from services.usa.philadelphia_fed_service import philadelphia_fed_service
            data = philadelphia_fed_service.get_philadelphia_fed_data()
            next_release = data.get("next_release")
            if next_release:
                date_str = next_release.get("date")
                return self._make_release_datetime(date_str, "philadelphia_fed")
        except Exception:
            pass
        return None

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

    def _parse_date_string(self, date_str: str) -> Optional[datetime]:
        """日付文字列をパース（YYYY-MM-DD形式）"""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return None

    def _make_release_datetime(
        self,
        date_str: str,
        indicator: str
    ) -> Optional[datetime]:
        """
        日付文字列と指標名から発表日時（JST）を生成

        Args:
            date_str: 日付文字列（YYYY-MM-DD）
            indicator: 指標名（RELEASE_TIMESのキー）

        Returns:
            発表日時（JST）
        """
        base_date = self._parse_date_string(date_str)
        if not base_date:
            return None

        time_config = self.RELEASE_TIMES.get(indicator)
        if not time_config:
            return None

        # タイムゾーンの決定
        tz = UTC if time_config.get("tz") == "UTC" else ET

        release_dt = datetime(
            base_date.year, base_date.month, base_date.day,
            time_config["hour"], time_config["minute"],
            tzinfo=tz
        )

        # JSTに変換
        return release_dt.astimezone(JST)

    def _get_gdp_release_datetimes(self) -> List[Optional[datetime]]:
        """GDP発表日時を取得"""
        try:
            from services.usa.bea_schedule_service import bea_schedule_service

            next_release = bea_schedule_service.get_next_gdp_release()
            if not next_release:
                return []

            date_str = next_release.get("date")
            release_dt = self._make_release_datetime(date_str, "gdp")
            return [release_dt] if release_dt else []

        except Exception as e:
            print(f"Error getting GDP release datetime: {e}")
            return []

    def _get_ism_release_datetimes(self) -> List[Optional[datetime]]:
        """ISM製造業・非製造業の発表日時を取得"""
        release_times = []

        try:
            # ISM製造業
            from services.usa.ism_manufacturing_service import ism_manufacturing_service
            mfg_data = ism_manufacturing_service.get_ism_manufacturing_data()
            next_release = mfg_data.get("next_release")
            if next_release:
                date_str = next_release.get("date")
                release_dt = self._make_release_datetime(date_str, "ism_manufacturing")
                if release_dt:
                    release_times.append(release_dt)
        except Exception as e:
            print(f"Error getting ISM Manufacturing release datetime: {e}")

        try:
            # ISM非製造業
            from services.usa.ism_non_manufacturing_service import ism_non_manufacturing_service
            non_mfg_data = ism_non_manufacturing_service.get_ism_non_manufacturing_data()
            next_release = non_mfg_data.get("next_release")
            if next_release:
                date_str = next_release.get("date")
                release_dt = self._make_release_datetime(date_str, "ism_non_manufacturing")
                if release_dt:
                    release_times.append(release_dt)
        except Exception as e:
            print(f"Error getting ISM Non-Manufacturing release datetime: {e}")

        return release_times

    def _get_regional_fed_release_datetimes(self) -> List[Optional[datetime]]:
        """地区連銀指標の発表日時を取得"""
        release_times = []

        try:
            # NY連銀（Empire State）
            from services.usa.empire_state_service import empire_state_service
            data = empire_state_service.get_empire_state_data()
            next_release = data.get("next_release")
            if next_release:
                date_str = next_release.get("date")
                release_dt = self._make_release_datetime(date_str, "empire_state")
                if release_dt:
                    release_times.append(release_dt)
        except Exception as e:
            print(f"Error getting Empire State release datetime: {e}")

        try:
            # フィラデルフィア連銀
            from services.usa.philadelphia_fed_service import philadelphia_fed_service
            data = philadelphia_fed_service.get_philadelphia_fed_data()
            next_release = data.get("next_release")
            if next_release:
                date_str = next_release.get("date")
                release_dt = self._make_release_datetime(date_str, "philadelphia_fed")
                if release_dt:
                    release_times.append(release_dt)
        except Exception as e:
            print(f"Error getting Philadelphia Fed release datetime: {e}")

        return release_times

    def _get_nfib_release_datetimes(self) -> List[Optional[datetime]]:
        """NFIB発表日時を取得"""
        try:
            from services.usa.nfib_service import nfib_service
            data = nfib_service.get_nfib_data()
            next_release = data.get("next_release")
            if not next_release:
                return []

            date_str = next_release.get("date")
            release_dt = self._make_release_datetime(date_str, "nfib")
            return [release_dt] if release_dt else []

        except Exception as e:
            print(f"Error getting NFIB release datetime: {e}")
            return []

    def _get_industrial_release_datetimes(self) -> List[Optional[datetime]]:
        """鉱工業生産・設備稼働率の発表日時を取得（同時発表）"""
        try:
            from services.usa.industrial_production_service import industrial_production_service
            data = industrial_production_service.get_industrial_production_data()
            next_release = data.get("next_release")
            if not next_release:
                return []

            date_str = next_release.get("date")
            release_dt = self._make_release_datetime(date_str, "industrial_production")
            return [release_dt] if release_dt else []

        except Exception as e:
            print(f"Error getting Industrial Production release datetime: {e}")
            return []

    def _get_durable_goods_release_datetimes(self) -> List[Optional[datetime]]:
        """耐久財受注の発表日時を取得"""
        try:
            from services.usa.durable_goods_service import durable_goods_service
            data = durable_goods_service.get_durable_goods_data()
            next_release = data.get("next_release")
            if not next_release:
                return []

            date_str = next_release.get("date")
            release_dt = self._make_release_datetime(date_str, "durable_goods")
            return [release_dt] if release_dt else []

        except Exception as e:
            print(f"Error getting Durable Goods release datetime: {e}")
            return []

    def _get_bank_lending_release_datetimes(self) -> List[Optional[datetime]]:
        """銀行貸し出し態度（SLOOS）の発表日時を取得（四半期）"""
        try:
            from services.usa.bank_lending_service import bank_lending_service
            data = bank_lending_service.get_bank_lending_standards()
            next_release = data.get("next_release")
            if not next_release:
                return []

            date_str = next_release.get("date")
            release_dt = self._make_release_datetime(date_str, "bank_lending")
            return [release_dt] if release_dt else []

        except Exception as e:
            print(f"Error getting Bank Lending release datetime: {e}")
            return []

    def _get_nfci_release_datetimes(self) -> List[Optional[datetime]]:
        """NFCI（シカゴ連銀金融環境指数）の発表日時を取得（毎週水曜日）"""
        try:
            from services.usa.nfci_service import nfci_service
            next_release = nfci_service.get_next_release_date()
            if not next_release:
                return []

            date_str = next_release.get("date")
            release_dt = self._make_release_datetime(date_str, "nfci")
            return [release_dt] if release_dt else []

        except Exception as e:
            print(f"Error getting NFCI release datetime: {e}")
            return []

    def _get_fci_gdpnow_release_datetimes(self) -> List[Optional[datetime]]:
        """
        FCI-G、GDPNowの更新日時を取得（毎日6:00 JST）

        これらの指標は不定期更新だが、日次でチェックするため
        毎日6:00 JSTを更新時刻として返す。
        """
        release_times = []
        now = datetime.now(JST)

        # FCI-G（毎日6:00 JST）
        fci_time = self.DAILY_UPDATE_TIMES["fci"]
        fci_today = datetime(
            now.year, now.month, now.day,
            fci_time["hour"], fci_time["minute"],
            tzinfo=JST
        )
        if now < fci_today:
            fci_today = fci_today - timedelta(days=1)
        release_times.append(fci_today)

        # GDPNow（毎日6:00 JST）
        gdpnow_time = self.DAILY_UPDATE_TIMES["gdpnow"]
        gdpnow_today = datetime(
            now.year, now.month, now.day,
            gdpnow_time["hour"], gdpnow_time["minute"],
            tzinfo=JST
        )
        if now < gdpnow_today:
            gdpnow_today = gdpnow_today - timedelta(days=1)
        release_times.append(gdpnow_today)

        return release_times

    def _get_daily_release_datetimes(self) -> List[Optional[datetime]]:
        """
        日次指標（TSA、OpenTable、航空便数）の発表日時を取得

        日次指標は毎日更新されるため、今日または昨日の更新時刻を返す
        """
        release_times = []
        now = datetime.now(JST)

        # TSA旅客数（毎日10:00 ET）
        tsa_time = self.RELEASE_TIMES["tsa_checkpoint"]
        tsa_today = datetime(
            now.year, now.month, now.day,
            tsa_time["hour"], tsa_time["minute"],
            tzinfo=ET
        ).astimezone(JST)
        # 今日の更新時刻を過ぎていなければ昨日の時刻を使用
        if now < tsa_today:
            tsa_today = tsa_today - timedelta(days=1)
        release_times.append(tsa_today)

        # OpenTable（毎日10:00 ET）
        opentable_time = self.RELEASE_TIMES["opentable"]
        opentable_today = datetime(
            now.year, now.month, now.day,
            opentable_time["hour"], opentable_time["minute"],
            tzinfo=ET
        ).astimezone(JST)
        if now < opentable_today:
            opentable_today = opentable_today - timedelta(days=1)
        release_times.append(opentable_today)

        # 航空便数（毎日06:00 UTC = 15:00 JST）
        flights_time = self.RELEASE_TIMES["us_flights"]
        flights_today = datetime(
            now.year, now.month, now.day,
            flights_time["hour"], flights_time["minute"],
            tzinfo=UTC
        ).astimezone(JST)
        if now < flights_today:
            flights_today = flights_today - timedelta(days=1)
        release_times.append(flights_today)

        return release_times

    def load_all(self) -> Dict[str, Any]:
        """
        全経済データを並列で取得

        Returns:
            {
                "gdp_growth_rate": [...],
                "gdp_contributions": {"data": [...], "series_info": {...}},
                "gdp_components_growth": [...],
                "next_gdp_release": {...}
            }
        """
        # 遅延インポート（循環参照回避）
        from services.usa.gdp_service import gdp_service
        from services.usa.gdp_contributions_service import gdp_contributions_service
        from services.usa.bea_gdp_components_service import bea_gdp_components_service
        from services.usa.potential_gdp_service import potential_gdp_service
        from services.usa.bank_lending_service import bank_lending_service
        from services.usa.fci_service import fci_service
        from services.usa.nfci_service import nfci_service
        from services.usa.gdpnow_service import gdpnow_service
        from services.usa.ism_manufacturing_service import ism_manufacturing_service
        from services.usa.ism_components_service import ism_components_service
        from services.usa.ism_non_manufacturing_service import ism_non_manufacturing_service
        from services.usa.ism_non_manufacturing_components_service import ism_non_manufacturing_components_service
        from services.usa.sp_pmi_service import sp_pmi_service
        from services.usa.empire_state_service import empire_state_service
        from services.usa.philadelphia_fed_service import philadelphia_fed_service
        from services.usa.nfib_service import nfib_service
        from services.usa.industrial_production_service import industrial_production_service
        from services.usa.capacity_utilization_service import capacity_utilization_service
        from services.usa.durable_goods_service import durable_goods_service
        from services.usa.us_flights_service import us_flights_service
        from services.usa.tsa_checkpoint_service import tsa_checkpoint_service
        from services.usa.opentable_service import opentable_service
        from services.usa.bea_schedule_service import bea_schedule_service

        result = {
            "gdp_growth_rate": None,
            "gdp_contributions": None,
            "gdp_components_growth": None,
            "potential_gdp": None,
            "bank_lending": None,
            "fci": None,
            "nfci": None,
            "gdpnow": None,
            "ism_manufacturing": None,
            "ism_components": None,
            "ism_non_manufacturing": None,
            "ism_non_manufacturing_components": None,
            "sp_pmi": None,
            "empire_state": None,
            "philadelphia_fed": None,
            "nfib": None,
            "nfib_capex": None,
            "industrial_production": None,
            "capacity_utilization": None,
            "durable_goods": None,
            "us_flights": None,
            "tsa_checkpoint": None,
            "opentable": None,
            "next_gdp_release": None,
            "next_ism_non_manufacturing_release": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=25) as executor:
            futures = {
                executor.submit(self._get_gdp_growth_rate, gdp_service): "gdp_growth_rate",
                executor.submit(self._get_gdp_contributions, gdp_contributions_service): "gdp_contributions",
                executor.submit(self._get_gdp_components_growth, bea_gdp_components_service): "gdp_components_growth",
                executor.submit(self._get_potential_gdp, potential_gdp_service): "potential_gdp",
                executor.submit(self._get_bank_lending, bank_lending_service): "bank_lending",
                executor.submit(self._get_fci, fci_service): "fci",
                executor.submit(self._get_nfci, nfci_service): "nfci",
                executor.submit(self._get_gdpnow, gdpnow_service): "gdpnow",
                executor.submit(self._get_ism_manufacturing, ism_manufacturing_service): "ism_manufacturing",
                executor.submit(self._get_ism_components, ism_components_service): "ism_components",
                executor.submit(self._get_ism_non_manufacturing, ism_non_manufacturing_service): "ism_non_manufacturing",
                executor.submit(self._get_ism_non_manufacturing_components, ism_non_manufacturing_components_service): "ism_non_manufacturing_components",
                executor.submit(self._get_sp_pmi, sp_pmi_service): "sp_pmi",
                executor.submit(self._get_empire_state, empire_state_service): "empire_state",
                executor.submit(self._get_philadelphia_fed, philadelphia_fed_service): "philadelphia_fed",
                executor.submit(self._get_nfib, nfib_service): "nfib",
                executor.submit(self._get_nfib_capex, nfib_service): "nfib_capex",
                executor.submit(self._get_industrial_production, industrial_production_service): "industrial_production",
                executor.submit(self._get_capacity_utilization, capacity_utilization_service): "capacity_utilization",
                executor.submit(self._get_durable_goods, durable_goods_service): "durable_goods",
                executor.submit(self._get_us_flights, us_flights_service): "us_flights",
                executor.submit(self._get_tsa_checkpoint, tsa_checkpoint_service): "tsa_checkpoint",
                executor.submit(self._get_opentable, opentable_service): "opentable",
                executor.submit(self._get_next_gdp_release, bea_schedule_service): "next_gdp_release",
                executor.submit(self._get_next_ism_non_manufacturing_release, ism_non_manufacturing_service): "next_ism_non_manufacturing_release",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    # ==========================================================================
    # 軽量指標のみを取得（高速レスポンス用）
    # ==========================================================================

    # 重い指標のリスト（スクリーンショット、PDF解析、複雑な外部API）
    HEAVY_INDICATORS = {"us_flights", "opentable", "nfib", "nfib_capex", "tsa_checkpoint"}

    def load_light(self) -> Dict[str, Any]:
        """
        軽量指標のみを並列で取得（高速レスポンス用）

        重い指標（スクリーンショット、PDF解析等）を除外し、
        FRED/BEA等のAPIキャッシュされたデータのみを取得。

        Returns:
            軽量指標のデータ辞書
        """
        # 遅延インポート（循環参照回避）
        from services.usa.gdp_service import gdp_service
        from services.usa.gdp_contributions_service import gdp_contributions_service
        from services.usa.bea_gdp_components_service import bea_gdp_components_service
        from services.usa.potential_gdp_service import potential_gdp_service
        from services.usa.bank_lending_service import bank_lending_service
        from services.usa.fci_service import fci_service
        from services.usa.nfci_service import nfci_service
        from services.usa.gdpnow_service import gdpnow_service
        from services.usa.ism_manufacturing_service import ism_manufacturing_service
        from services.usa.ism_components_service import ism_components_service
        from services.usa.ism_non_manufacturing_service import ism_non_manufacturing_service
        from services.usa.ism_non_manufacturing_components_service import ism_non_manufacturing_components_service
        from services.usa.sp_pmi_service import sp_pmi_service
        from services.usa.empire_state_service import empire_state_service
        from services.usa.philadelphia_fed_service import philadelphia_fed_service
        from services.usa.industrial_production_service import industrial_production_service
        from services.usa.capacity_utilization_service import capacity_utilization_service
        from services.usa.durable_goods_service import durable_goods_service
        from services.usa.bea_schedule_service import bea_schedule_service

        result = {
            "gdp_growth_rate": None,
            "gdp_contributions": None,
            "gdp_components_growth": None,
            "potential_gdp": None,
            "bank_lending": None,
            "fci": None,
            "nfci": None,
            "gdpnow": None,
            "ism_manufacturing": None,
            "ism_components": None,
            "ism_non_manufacturing": None,
            "ism_non_manufacturing_components": None,
            "sp_pmi": None,
            "empire_state": None,
            "philadelphia_fed": None,
            "industrial_production": None,
            "capacity_utilization": None,
            "durable_goods": None,
            "next_gdp_release": None,
            "next_ism_non_manufacturing_release": None,
        }

        # 並列でデータを取得（軽量指標のみ、20個）
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {
                executor.submit(self._get_gdp_growth_rate, gdp_service): "gdp_growth_rate",
                executor.submit(self._get_gdp_contributions, gdp_contributions_service): "gdp_contributions",
                executor.submit(self._get_gdp_components_growth, bea_gdp_components_service): "gdp_components_growth",
                executor.submit(self._get_potential_gdp, potential_gdp_service): "potential_gdp",
                executor.submit(self._get_bank_lending, bank_lending_service): "bank_lending",
                executor.submit(self._get_fci, fci_service): "fci",
                executor.submit(self._get_nfci, nfci_service): "nfci",
                executor.submit(self._get_gdpnow, gdpnow_service): "gdpnow",
                executor.submit(self._get_ism_manufacturing, ism_manufacturing_service): "ism_manufacturing",
                executor.submit(self._get_ism_components, ism_components_service): "ism_components",
                executor.submit(self._get_ism_non_manufacturing, ism_non_manufacturing_service): "ism_non_manufacturing",
                executor.submit(self._get_ism_non_manufacturing_components, ism_non_manufacturing_components_service): "ism_non_manufacturing_components",
                executor.submit(self._get_sp_pmi, sp_pmi_service): "sp_pmi",
                executor.submit(self._get_empire_state, empire_state_service): "empire_state",
                executor.submit(self._get_philadelphia_fed, philadelphia_fed_service): "philadelphia_fed",
                executor.submit(self._get_industrial_production, industrial_production_service): "industrial_production",
                executor.submit(self._get_capacity_utilization, capacity_utilization_service): "capacity_utilization",
                executor.submit(self._get_durable_goods, durable_goods_service): "durable_goods",
                executor.submit(self._get_next_gdp_release, bea_schedule_service): "next_gdp_release",
                executor.submit(self._get_next_ism_non_manufacturing_release, ism_non_manufacturing_service): "next_ism_non_manufacturing_release",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def load_heavy(self) -> Dict[str, Any]:
        """
        重い指標のみを並列で取得

        スクリーンショット取得、PDF解析等の重い処理を含む指標のみを取得。
        フロントエンドで遅延ロードに使用。

        Returns:
            重い指標のデータ辞書
        """
        # 遅延インポート（循環参照回避）
        from services.usa.nfib_service import nfib_service
        from services.usa.us_flights_service import us_flights_service
        from services.usa.tsa_checkpoint_service import tsa_checkpoint_service
        from services.usa.opentable_service import opentable_service

        result = {
            "nfib": None,
            "nfib_capex": None,
            "us_flights": None,
            "tsa_checkpoint": None,
            "opentable": None,
        }

        # 並列でデータを取得（重い指標のみ、5個）
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self._get_nfib, nfib_service): "nfib",
                executor.submit(self._get_nfib_capex, nfib_service): "nfib_capex",
                executor.submit(self._get_us_flights, us_flights_service): "us_flights",
                executor.submit(self._get_tsa_checkpoint, tsa_checkpoint_service): "tsa_checkpoint",
                executor.submit(self._get_opentable, opentable_service): "opentable",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_gdp_growth_rate(self, service) -> list:
        """GDP成長率データを取得"""
        try:
            force_refresh = self._should_force_refresh("gdp")
            response = service.get_gdp_growth_rate(force_refresh=force_refresh)
            return response.get("data", [])
        except Exception as e:
            print(f"Error getting GDP growth rate: {e}")
            return []

    def _get_gdp_contributions(self, service) -> Optional[dict]:
        """GDP寄与度データを取得"""
        try:
            force_refresh = self._should_force_refresh("gdp")
            response = service.get_gdp_contributions(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "series_info": response.get("series_info", {})
            }
        except Exception as e:
            print(f"Error getting GDP contributions: {e}")
            return None

    def _get_gdp_components_growth(self, service) -> Optional[list]:
        """GDP項目別成長率データを取得"""
        try:
            force_refresh = self._should_force_refresh("gdp")
            response = service.get_gdp_components_growth(force_refresh=force_refresh)
            data = response.get("data", [])
            # データが空の場合はNoneを返す（フロントでloadingではなく「利用不可」表示になる）
            return data if data else None
        except Exception as e:
            print(f"Error getting GDP components growth: {e}")
            return None

    def _get_potential_gdp(self, service) -> Optional[dict]:
        """潜在成長率データを取得"""
        try:
            response = service.get_potential_gdp()
            real_data = response.get("real", [])
            nominal_data = response.get("nominal", [])
            # データが両方空の場合はNoneを返す
            if not real_data and not nominal_data:
                return None
            return {
                "real": real_data,
                "nominal": nominal_data
            }
        except Exception as e:
            print(f"Error getting potential GDP: {e}")
            return None

    def _get_bank_lending(self, service) -> Optional[dict]:
        """銀行貸し出し態度データを取得"""
        try:
            force_refresh = self._should_force_refresh("bank_lending")
            response = service.get_bank_lending_standards(force_refresh=force_refresh)
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "next_release": response.get("next_release")
            }
        except Exception as e:
            print(f"Error getting bank lending standards: {e}")
            return None

    def _get_next_gdp_release(self, service) -> Optional[dict]:
        """次回GDP発表情報を取得"""
        try:
            return service.get_next_gdp_release()
        except Exception as e:
            print(f"Error getting next GDP release: {e}")
            return None

    def _get_fci(self, service) -> Optional[dict]:
        """FCI-G（金融情勢指数）データを取得"""
        try:
            force_refresh = self._should_force_refresh("fci")
            response = service.get_fci_data(force_refresh=force_refresh)
            baseline = response.get("baseline", {})
            oneyear = response.get("oneyear", {})

            # データが両方空の場合はNoneを返す
            if not baseline.get("data") and not oneyear.get("data"):
                return None

            return {
                "baseline": {
                    "data": baseline.get("data", []),
                    "latest": baseline.get("latest")
                },
                "oneyear": {
                    "data": oneyear.get("data", []),
                    "latest": oneyear.get("latest")
                }
            }
        except Exception as e:
            print(f"Error getting FCI data: {e}")
            return None

    def _get_nfci(self, service) -> Optional[dict]:
        """シカゴ連銀金融環境指数（NFCI）データを取得"""
        try:
            force_refresh = self._should_force_refresh("nfci")
            response = service.get_nfci_data(force_refresh=force_refresh)
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest")
            }
        except Exception as e:
            print(f"Error getting NFCI data: {e}")
            return None

    def _get_gdpnow(self, service) -> Optional[dict]:
        """GDPNow（リアルタイムGDP予測）データを取得"""
        try:
            force_refresh = self._should_force_refresh("gdpnow")
            response = service.get_gdpnow_data(force_refresh=force_refresh)
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest")
            }
        except Exception as e:
            print(f"Error getting GDPNow data: {e}")
            return None

    def _get_ism_manufacturing(self, service) -> Optional[dict]:
        """ISM製造業景況指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("ism_manufacturing")
            response = service.get_ism_manufacturing_data(force_refresh=force_refresh)
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "next_release": response.get("next_release")
            }
        except Exception as e:
            print(f"Error getting ISM Manufacturing data: {e}")
            return None

    def _get_ism_components(self, service) -> Optional[dict]:
        """ISM製造業サブインデックスデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ism_manufacturing")
            response = service.get_ism_components_data(force_refresh=force_refresh)
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "next_release": response.get("next_release")
            }
        except Exception as e:
            print(f"Error getting ISM Components data: {e}")
            return None

    def _get_ism_non_manufacturing(self, service) -> Optional[dict]:
        """ISM非製造業景況指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("ism_non_manufacturing")
            response = service.get_ism_non_manufacturing_data(force_refresh=force_refresh)
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
            print(f"Error getting ISM Non-Manufacturing data: {e}")
            return None

    def _get_ism_non_manufacturing_components(self, service) -> Optional[dict]:
        """ISM非製造業サブインデックスデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ism_non_manufacturing")
            response = service.get_ism_non_manufacturing_components_data(force_refresh=force_refresh)
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
            print(f"Error getting ISM Non-Manufacturing Components data: {e}")
            return None

    def _get_next_ism_non_manufacturing_release(self, service) -> Optional[dict]:
        """次回ISM非製造業発表情報を取得（Investing.comから都度取得）"""
        try:
            # ISM非製造業サービスから次回発表情報を取得
            return service._get_next_release()
        except Exception as e:
            print(f"Error getting next ISM Non-Manufacturing release: {e}")
            return None

    def _get_sp_pmi(self, service) -> Optional[dict]:
        """S&P Global PMIデータを取得（製造業/サービス業/総合）"""
        try:
            force_refresh = self._should_force_refresh("sp_pmi")
            response = service.get_sp_pmi_data(force_refresh=force_refresh)

            # 3つの系列のいずれかにデータがあれば返す
            mfg = response.get("manufacturing")
            svc = response.get("services")
            cmp = response.get("composite")

            if not (mfg or svc or cmp):
                return None

            return {
                "manufacturing": mfg,
                "services": svc,
                "composite": cmp,
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting S&P PMI data: {e}")
            return None

    def _get_empire_state(self, service) -> Optional[dict]:
        """NY連銀製造業景気指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("empire_state")
            response = service.get_empire_state_data(force_refresh=force_refresh)
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
            print(f"Error getting Empire State data: {e}")
            return None

    def _get_philadelphia_fed(self, service) -> Optional[dict]:
        """フィラデルフィア連銀製造業景気指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("philadelphia_fed")
            response = service.get_philadelphia_fed_data(force_refresh=force_refresh)
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
                "series_config": response.get("series_config"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting Philadelphia Fed data: {e}")
            return None

    def _get_nfib(self, service) -> Optional[dict]:
        """NFIB中小企業楽観指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("nfib")
            response = service.get_nfib_data(force_refresh=force_refresh)
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
            print(f"Error getting NFIB data: {e}")
            return None

    def _get_nfib_capex(self, service) -> Optional[dict]:
        """NFIB中小企業設備投資計画データを取得"""
        try:
            force_refresh = self._should_force_refresh("nfib")
            response = service.get_capex_plans_data(force_refresh=force_refresh)
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
            print(f"Error getting NFIB CapEx data: {e}")
            return None

    def _get_industrial_production(self, service) -> Optional[dict]:
        """鉱工業生産データを取得"""
        try:
            force_refresh = self._should_force_refresh("industrial_production")
            response = service.get_industrial_production_data(force_refresh=force_refresh)
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
            print(f"Error getting Industrial Production data: {e}")
            return None

    def _get_capacity_utilization(self, service) -> Optional[dict]:
        """設備稼働率データを取得"""
        try:
            force_refresh = self._should_force_refresh("capacity_utilization")
            response = service.get_capacity_utilization_data(force_refresh=force_refresh)
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
            print(f"Error getting Capacity Utilization data: {e}")
            return None

    def _get_durable_goods(self, service) -> Optional[dict]:
        """耐久財受注データを取得"""
        try:
            force_refresh = self._should_force_refresh("durable_goods")
            response = service.get_durable_goods_data(force_refresh=force_refresh)
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
            print(f"Error getting Durable Goods data: {e}")
            return None

    def _get_us_flights(self, service) -> Optional[dict]:
        """米国航空機便数データを取得"""
        try:
            force_refresh = self._should_force_refresh("us_flights")
            response = service.get_flights_data(force_refresh=force_refresh)
            # image_urlがない場合はエラー
            if not response.get("image_url"):
                return None
            return {
                "image_url": response.get("image_url"),
                "latest": response.get("latest"),
                "next_update": response.get("next_update"),
                "last_updated": response.get("last_updated"),
                "source": response.get("source")
            }
        except Exception as e:
            print(f"Error getting US Flights data: {e}")
            return None

    def _get_tsa_checkpoint(self, service) -> Optional[dict]:
        """TSA旅客数データを取得"""
        try:
            force_refresh = self._should_force_refresh("tsa_checkpoint")
            response = service.get_tsa_checkpoint_data(force_refresh=force_refresh)
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting TSA Checkpoint data: {e}")
            return None

    def _get_opentable(self, service) -> Optional[dict]:
        """OpenTableレストラン予約件数データを取得"""
        try:
            force_refresh = self._should_force_refresh("opentable")
            response = service.get_opentable_data(force_refresh=force_refresh)
            return {
                "image_url": response.get("image_url"),
                "latest": response.get("latest"),
                "last_updated": response.get("last_updated"),
                "source": response.get("source")
            }
        except Exception as e:
            print(f"Error getting OpenTable data: {e}")
            return None

    def invalidate_cache(self) -> bool:
        """
        キャッシュを無効化（ダッシュボード + 個別サービス）
        TSA、OpenTableサービスのキャッシュも一緒に無効化する
        """
        from services.usa.tsa_checkpoint_service import tsa_checkpoint_service
        from services.usa.opentable_service import opentable_service
        from pathlib import Path

        # TSAサービスのRedisキャッシュを無効化
        try:
            tsa_checkpoint_service.invalidate_cache()
            print("TSA checkpoint Redis cache invalidated")
        except Exception as e:
            print(f"Error invalidating TSA cache: {e}")

        # TSAサービスのファイルキャッシュを削除
        try:
            cache_file = Path(__file__).parent.parent.parent.parent / "data" / "cache" / "usa" / "economy" / "tsa_checkpoint_data.json"
            if cache_file.exists():
                cache_file.unlink()
                print("TSA checkpoint file cache deleted")
        except Exception as e:
            print(f"Error deleting TSA file cache: {e}")

        # OpenTableサービスのRedisキャッシュを無効化
        try:
            opentable_service.invalidate_cache()
            print("OpenTable Redis cache invalidated")
        except Exception as e:
            print(f"Error invalidating OpenTable cache: {e}")

        # 親クラスのinvalidate_cacheを呼び出し
        return super().invalidate_cache()
