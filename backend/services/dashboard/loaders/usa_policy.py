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
    """

    COUNTRY_CODE = "usa"
    CATEGORY_CODE = "policy"

    # FOMC声明発表時刻（ET）
    FOMC_RELEASE_HOUR_ET = 14
    FOMC_RELEASE_MINUTE_ET = 0

    # タームプレミアム・FedWatch更新時刻（JST）- NY Fedの更新を考慮して6:00 JST
    DAILY_UPDATE_HOUR_JST = 6
    DAILY_UPDATE_MINUTE_JST = 0

    def get_release_datetimes(self) -> List[Optional[datetime]]:
        """
        各指標の発表日時リストを返す

        Returns:
            - FOMC発表日時（次回FOMC会合日の14:00 ET）
            - タームプレミアム更新日時（毎日6:00 JST）
            - FedWatch更新日時（毎日6:00 JST）
            - SEP発表日時（FOMC発表日と同時）
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
        from services.usa.fred_service import fred_service
        from services.usa.fomc_schedule_service import fomc_schedule_service

        result = {
            "policy_rate": None,
            "term_premium": None,
            "kw_term_premium": None,
            "sep_dates": None,
            "fedwatch_screenshot_url": None,
            "next_fomc": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self._get_policy_rate, fed_h15_service): "policy_rate",
                executor.submit(self._get_term_premium, nyfed_term_premium_service): "term_premium",
                executor.submit(self._get_kw_term_premium, fred_service): "kw_term_premium",
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
        """政策金利データを取得"""
        try:
            response = service.get_policy_rate()
            return response.get("data", [])
        except Exception as e:
            print(f"Error getting policy rate: {e}")
            return []

    def _get_term_premium(self, service) -> list:
        """タームプレミアムデータを取得"""
        try:
            response = service.get_term_premium_data()
            return response.get("data", [])
        except Exception as e:
            print(f"Error getting term premium: {e}")
            return []

    def _get_kw_term_premium(self, service) -> list:
        """KWタームプレミアムデータを取得"""
        try:
            response = service.get_kw_term_premium()
            return response.get("data", [])
        except Exception as e:
            print(f"Error getting KW term premium: {e}")
            return []

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
