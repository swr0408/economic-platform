"""
経済指標発表スケジュール判定ユーティリティ

発表期間ベースのキャッシュ更新判定を提供。
Investing.comへのアクセスを削減し、期間内のみ更新チェックを行う。

使用方法:
    from services.usa.release_schedule_utils import ReleaseScheduleChecker

    # パターン1: 日付範囲ベース（従来方式）
    checker = ReleaseScheduleChecker(
        release_days=(1, 15),           # 発表期間: 1〜15日
        release_hour_summer=21,         # 夏時間の発表時刻（時）
        release_minute=30,              # 発表時刻（分）
        release_hour_winter=22,         # 冬時間の発表時刻（時）
        release_months=None,            # 発表月（Noneなら毎月）
    )

    # パターン2: 週次（毎週X曜日）
    checker = ReleaseScheduleChecker(
        weekly_day_of_week=4,           # 金曜日 (0=月, 4=金, 6=日)
        release_hour_summer=5,
        release_minute=15,
        release_hour_winter=6,
    )

    # パターン3: 月内第N週のX曜日（複数対応）
    checker = ReleaseScheduleChecker(
        nth_week_patterns=[
            {"nth": 1, "day_of_week": 3},  # 第1木曜日
            {"nth": 2, "day_of_week": 4},  # 第2金曜日
        ],
        release_hour_summer=21,
        release_minute=30,
        release_hour_winter=22,
    )

    if checker.should_refresh(last_updated_str):
        # データ更新処理
"""
from datetime import datetime, timedelta, date
from typing import Optional, Tuple, List, Dict
from zoneinfo import ZoneInfo


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")


def is_dst(dt: datetime) -> bool:
    """
    米国東部時間がサマータイム中かどうかを判定

    Args:
        dt: 判定する日時（タイムゾーン情報付き）

    Returns:
        True: サマータイム中
        False: 標準時間
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)

    # ETに変換してDSTを確認
    dt_et = dt.astimezone(ET)
    # dstがNoneでなく、0より大きければサマータイム
    dst = dt_et.dst()
    return dst is not None and dst.total_seconds() > 0


class ReleaseScheduleChecker:
    """
    経済指標発表スケジュール判定クラス

    発表期間と発表時刻に基づいて、キャッシュ更新が必要かどうかを判定する。
    発表時刻から3分間は毎分更新チェックを行い、取りこぼしを防ぐ。

    3つのパターンに対応:
    1. 日付範囲ベース: release_days=(1, 15) で1〜15日の間をチェック
    2. 週次: weekly_day_of_week=4 で毎週金曜日をチェック
    3. 月内第N週: nth_week_patterns で第1木曜日、第2金曜日などをチェック
    """

    # 発表時刻後の更新チェック期間（分）
    UPDATE_WINDOW_MINUTES = 3

    def __init__(
        self,
        release_days: Optional[Tuple[int, int]] = None,
        release_hour_summer: int = 0,
        release_minute: int = 0,
        release_hour_winter: Optional[int] = None,
        release_months: Optional[List[int]] = None,
        cross_month: bool = False,
        weekly_day_of_week: Optional[int] = None,
        nth_week_patterns: Optional[List[Dict[str, int]]] = None,
    ):
        """
        Args:
            release_days: 発表期間（開始日, 終了日）。例: (1, 15) = 1〜15日
            release_hour_summer: 夏時間（サマータイム）の発表時刻（時、JST）
            release_minute: 発表時刻（分）
            release_hour_winter: 冬時間の発表時刻（時、JST）。Noneなら夏時間+1
            release_months: 発表月のリスト。Noneなら毎月
            cross_month: 月跨ぎの期間かどうか（例: 29日〜翌13日）
            weekly_day_of_week: 週次発表の曜日（0=月, 1=火, ..., 6=日）
            nth_week_patterns: 月内第N週パターンのリスト
                例: [{"nth": 1, "day_of_week": 3}, {"nth": 2, "day_of_week": 4}]
                    → 第1木曜日と第2金曜日
        """
        self.release_days = release_days
        self.release_hour_summer = release_hour_summer
        self.release_minute = release_minute
        self.release_hour_winter = release_hour_winter if release_hour_winter is not None else release_hour_summer + 1
        self.release_months = release_months
        self.cross_month = cross_month
        self.weekly_day_of_week = weekly_day_of_week
        self.nth_week_patterns = nth_week_patterns

    def should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        判定ロジック（パターン別）:
        1. weekly_day_of_week が設定されている場合 → 週次判定
        2. nth_week_patterns が設定されている場合 → 月内第N週判定
        3. release_days が設定されている場合 → 日付範囲判定（従来方式）

        Args:
            last_updated_str: 最終更新日時のISO文字列

        Returns:
            True: 更新が必要
            False: キャッシュ有効
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 発表月チェック（全パターン共通）
            if not self._in_release_month(now):
                return False

            # パターン1: 週次判定
            if self.weekly_day_of_week is not None:
                return self._should_refresh_weekly(now, last_updated)

            # パターン2: 月内第N週判定
            if self.nth_week_patterns is not None:
                return self._should_refresh_nth_week(now, last_updated)

            # パターン3: 日付範囲判定（従来方式）
            if self.release_days is not None:
                return self._should_refresh_date_range(now, last_updated)

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return False

    def _should_refresh_date_range(self, now: datetime, last_updated: datetime) -> bool:
        """
        日付範囲ベースの更新判定（従来方式）

        判定ロジック:
        1. 発表期間外ならスキップ
        2. 発表期間内で、発表時刻から3分以内なら、最終更新が発表時刻より前なら更新
        3. 発表期間内で、発表時刻を3分以上過ぎていて、まだ更新していなければ更新
        """
        # 発表期間チェック
        if not self._in_release_period(now):
            return False

        # 発表時刻を取得
        release_time = self._get_release_time(now)
        if release_time is None:
            return False

        # 発表時刻より前なら更新不要
        if now < release_time:
            return False

        # 最終更新が発表時刻より前なら更新が必要
        if last_updated < release_time:
            return True

        return False

    def _should_refresh_weekly(self, now: datetime, last_updated: datetime) -> bool:
        """
        週次パターンの更新判定（3分方式対応）

        判定ロジック:
        1. 直近の発表日時（過去で最も近いもの）を計算
        2. 発表時刻から3分以内なら、最終更新が発表時刻より前なら更新
        3. 発表時刻を3分以上過ぎていて、まだ更新していなければ更新
        """
        # 直近の発表日時を取得
        last_release = self._get_last_weekly_release(now)
        if last_release is None:
            return False

        # 現在時刻が発表時刻より前なら更新不要
        if now < last_release:
            return False

        # 発表時刻から3分以内かどうか
        update_window_end = last_release + timedelta(minutes=self.UPDATE_WINDOW_MINUTES)
        in_update_window = now <= update_window_end

        if in_update_window:
            # 3分以内: 最終更新が発表時刻より前なら更新
            if last_updated < last_release:
                return True
        else:
            # 3分経過後: 発表時刻以降に更新していなければ更新
            if last_updated < last_release:
                return True

        return False

    def _should_refresh_nth_week(self, now: datetime, last_updated: datetime) -> bool:
        """
        月内第N週パターンの更新判定（3分方式対応）

        判定ロジック:
        1. 今月と先月の発表日時を全て取得
        2. 直近の発表日時（現在以前で最も近いもの）を特定
        3. 発表時刻から3分以内なら、最終更新が発表時刻より前なら更新
        4. 発表時刻を3分以上過ぎていて、まだ更新していなければ更新
        """
        # 直近の発表日時を取得
        last_release = self._get_last_nth_week_release(now)
        if last_release is None:
            return False

        # 現在時刻が発表時刻より前なら更新不要
        if now < last_release:
            return False

        # 発表時刻から3分以内かどうか
        update_window_end = last_release + timedelta(minutes=self.UPDATE_WINDOW_MINUTES)
        in_update_window = now <= update_window_end

        if in_update_window:
            # 3分以内: 最終更新が発表時刻より前なら更新
            if last_updated < last_release:
                return True
        else:
            # 3分経過後: 発表時刻以降に更新していなければ更新
            if last_updated < last_release:
                return True

        return False

    def _get_last_weekly_release(self, now: datetime) -> Optional[datetime]:
        """
        直近の週次発表日時を取得（現在以前で最も近いもの）

        Args:
            now: 現在日時

        Returns:
            直近の発表日時（JST）
        """
        if self.weekly_day_of_week is None:
            return None

        today = now.date()
        current_weekday = today.weekday()  # 0=月, 6=日

        # 今週の対象曜日までの日数（負の値 = 過去）
        days_since_target = (current_weekday - self.weekly_day_of_week) % 7

        # 今週の対象曜日
        target_date = today - timedelta(days=days_since_target)

        # 発表時刻を構築
        release_time = self._build_release_datetime(target_date)

        # 今日が対象曜日で、まだ発表時刻前なら先週の発表日時を返す
        if days_since_target == 0 and now < release_time:
            target_date = today - timedelta(days=7)
            release_time = self._build_release_datetime(target_date)

        return release_time

    def _get_next_weekly_release(self, now: datetime) -> Optional[datetime]:
        """
        次の週次発表日時を取得

        Args:
            now: 現在日時

        Returns:
            次の発表日時（JST）
        """
        if self.weekly_day_of_week is None:
            return None

        today = now.date()
        current_weekday = today.weekday()

        # 次の対象曜日までの日数
        days_until_target = (self.weekly_day_of_week - current_weekday) % 7

        # 今日が対象曜日の場合
        if days_until_target == 0:
            release_time = self._build_release_datetime(today)
            if now >= release_time:
                # 発表時刻を過ぎているので来週
                days_until_target = 7

        target_date = today + timedelta(days=days_until_target)
        return self._build_release_datetime(target_date)

    def _get_last_nth_week_release(self, now: datetime) -> Optional[datetime]:
        """
        直近の月内第N週発表日時を取得（現在以前で最も近いもの）

        Args:
            now: 現在日時

        Returns:
            直近の発表日時（JST）
        """
        if not self.nth_week_patterns:
            return None

        # 今月と先月の発表日時を取得
        all_releases = []

        # 今月
        all_releases.extend(self._get_nth_week_release_dates(now.year, now.month))

        # 先月
        if now.month == 1:
            prev_year, prev_month = now.year - 1, 12
        else:
            prev_year, prev_month = now.year, now.month - 1
        all_releases.extend(self._get_nth_week_release_dates(prev_year, prev_month))

        # 現在以前の発表日時のうち、最も近いものを取得
        past_releases = [r for r in all_releases if r <= now]
        if not past_releases:
            return None

        return max(past_releases)

    def _get_next_nth_week_release(self, now: datetime) -> Optional[datetime]:
        """
        次の月内第N週発表日時を取得

        Args:
            now: 現在日時

        Returns:
            次の発表日時（JST）
        """
        if not self.nth_week_patterns:
            return None

        # 今月と来月の発表日時を取得
        all_releases = []

        # 今月
        all_releases.extend(self._get_nth_week_release_dates(now.year, now.month))

        # 来月
        if now.month == 12:
            next_year, next_month = now.year + 1, 1
        else:
            next_year, next_month = now.year, now.month + 1
        all_releases.extend(self._get_nth_week_release_dates(next_year, next_month))

        # 現在以降の発表日時のうち、最も近いものを取得
        future_releases = [r for r in all_releases if r > now]
        if not future_releases:
            return None

        return min(future_releases)

    def _get_nth_week_release_dates(self, year: int, month: int) -> List[datetime]:
        """
        指定月の第N週発表日時を全て取得

        Args:
            year: 年
            month: 月

        Returns:
            発表日時のリスト
        """
        if not self.nth_week_patterns:
            return []

        result = []

        for pattern in self.nth_week_patterns:
            nth = pattern["nth"]
            target_weekday = pattern["day_of_week"]

            # 月の第N週のX曜日を計算
            target_date = self._get_nth_weekday_of_month(year, month, nth, target_weekday)
            if target_date:
                release_time = self._build_release_datetime(target_date)
                result.append(release_time)

        return result

    def _get_nth_weekday_of_month(
        self,
        year: int,
        month: int,
        nth: int,
        weekday: int
    ) -> Optional[date]:
        """
        指定月の第N週のX曜日を取得

        Args:
            year: 年
            month: 月
            nth: 第何週（1-5）
            weekday: 曜日（0=月, 6=日）

        Returns:
            該当日付。月内に存在しない場合はNone
        """
        # 月初日
        first_day = date(year, month, 1)
        first_weekday = first_day.weekday()

        # 最初の対象曜日までの日数
        days_until_first = (weekday - first_weekday) % 7
        first_target = first_day + timedelta(days=days_until_first)

        # 第N週の対象曜日
        target = first_target + timedelta(weeks=nth - 1)

        # 月内に収まっているか確認
        if target.month != month:
            return None

        return target

    def _build_release_datetime(self, target_date: date) -> datetime:
        """
        日付と発表時刻からdatetimeを構築

        Args:
            target_date: 対象日付

        Returns:
            発表日時（JST）
        """
        # 一時的なdatetimeを作成してサマータイム判定
        temp_dt = datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            12, 0, 0,
            tzinfo=JST
        )

        if is_dst(temp_dt):
            release_hour = self.release_hour_summer
        else:
            release_hour = self.release_hour_winter

        return datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            release_hour,
            self.release_minute,
            0,
            tzinfo=JST
        )

    def _in_release_month(self, now: datetime) -> bool:
        """発表月かどうかを判定"""
        if self.release_months is None:
            return True
        return now.month in self.release_months

    def _in_release_period(self, now: datetime) -> bool:
        """発表期間内かどうかを判定"""
        start_day, end_day = self.release_days

        if self.cross_month:
            # 月跨ぎの場合（例: 29〜翌13日）
            # 29日以降 OR 13日以前
            return now.day >= start_day or now.day <= end_day
        else:
            # 通常の場合
            return start_day <= now.day <= end_day

    def _get_release_time(self, now: datetime) -> Optional[datetime]:
        """
        今日の発表時刻を取得

        Args:
            now: 現在日時

        Returns:
            発表時刻（JST）。発表期間外ならNone
        """
        try:
            # サマータイム判定
            if is_dst(now):
                release_hour = self.release_hour_summer
            else:
                release_hour = self.release_hour_winter

            # 今日の発表時刻を構築
            release_time = now.replace(
                hour=release_hour,
                minute=self.release_minute,
                second=0,
                microsecond=0
            )

            return release_time

        except Exception as e:
            print(f"Error getting release time: {e}")
            return None

    def get_period_start(self, now: datetime) -> datetime:
        """
        今月（または今期間）の発表期間開始日時を取得

        Args:
            now: 現在日時

        Returns:
            発表期間開始日時
        """
        start_day, _ = self.release_days

        if self.cross_month:
            # 月跨ぎの場合
            if now.day >= start_day:
                # 今月のstart_dayから
                period_start = now.replace(day=start_day, hour=0, minute=0, second=0, microsecond=0)
            else:
                # 先月のstart_dayから
                if now.month == 1:
                    prev_month = now.replace(year=now.year - 1, month=12, day=start_day)
                else:
                    prev_month = now.replace(month=now.month - 1, day=start_day)
                period_start = prev_month.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            # 通常の場合
            period_start = now.replace(day=start_day, hour=0, minute=0, second=0, microsecond=0)

        return period_start

    def get_status(self) -> dict:
        """現在のステータスを取得（デバッグ用）"""
        now = datetime.now(JST)

        status = {
            "now": now.isoformat(),
            "in_release_month": self._in_release_month(now),
            "is_dst": is_dst(now),
            "release_months": self.release_months,
        }

        # パターン別の情報を追加
        if self.weekly_day_of_week is not None:
            status["pattern"] = "weekly"
            status["weekly_day_of_week"] = self.weekly_day_of_week
            last_release = self._get_last_weekly_release(now)
            next_release = self._get_next_weekly_release(now)
            status["last_release"] = last_release.isoformat() if last_release else None
            status["next_release"] = next_release.isoformat() if next_release else None
        elif self.nth_week_patterns is not None:
            status["pattern"] = "nth_week"
            status["nth_week_patterns"] = self.nth_week_patterns
            last_release = self._get_last_nth_week_release(now)
            next_release = self._get_next_nth_week_release(now)
            status["last_release"] = last_release.isoformat() if last_release else None
            status["next_release"] = next_release.isoformat() if next_release else None
            # 今月の発表日一覧
            status["this_month_releases"] = [
                r.isoformat() for r in self._get_nth_week_release_dates(now.year, now.month)
            ]
        else:
            status["pattern"] = "date_range"
            status["release_days"] = self.release_days
            status["in_release_period"] = self._in_release_period(now)
            release_time = self._get_release_time(now)
            status["release_time"] = release_time.isoformat() if release_time else None

        return status


# ============================================================
# 各指標用のプリセット定義
# ============================================================

# ============================================================
# GDP関連
# ============================================================

# GDP成長率（前期比年率）・GDP項目別成長率・GDP成長率 寄与度
# 発表期間: 毎月19-31日
# 発表時刻: 21:30 (夏) / 22:30 (冬) JST
GDP_GROWTH_CHECKER = ReleaseScheduleChecker(
    release_days=(19, 31),
    release_hour_summer=21,
    release_minute=30,
    release_hour_winter=22,
    release_months=None,
)

# ============================================================
# 雇用関連
# ============================================================

# 失業率 / 広義の失業率・失業率内訳・非農業部門雇用者数・
# フルタイム / パートタイム雇用者数・複数の仕事を持つ人 / 経済的理由によるパートタイム・
# 労働参加率・平均時給（前年比）・平均残業時間（製造業）
# 発表期間: 毎月1-15日
# 発表時刻: 21:30 (夏) / 22:30 (冬) JST
UNEMPLOYMENT_RATE_CHECKER = ReleaseScheduleChecker(
    release_days=(1, 15),
    release_hour_summer=21,
    release_minute=30,
    release_hour_winter=22,
    release_months=None,  # 毎月
)

# 雇用コスト指数 (EMPLOYMENT_COST_INDEX)
# 発表期間: 毎月25-31日
# 発表時刻: 21:30 (夏) / 22:30 (冬) JST
# 発表月: 1月、4月、7月、10月（四半期）
EMPLOYMENT_COST_INDEX_CHECKER = ReleaseScheduleChecker(
    release_days=(25, 31),
    release_hour_summer=21,
    release_minute=30,
    release_hour_winter=22,
    release_months=[1, 4, 7, 10],
)

# JOLTS求人 / Indeed求人件数指数 / JOLTS採用数 / 解雇数
# 発表期間: 毎月29日～翌月44日（月跨ぎ、約6週間の範囲）
# 発表時刻: 23:00 (夏) / 0:00 (冬) JST
# ※ Indeed求人件数指数は毎日更新のため別途対応
JOLTS_OPENINGS_CHECKER = ReleaseScheduleChecker(
    release_days=(29, 14),  # 29日〜翌月14日（44日は不正確なため14日に修正）
    release_hour_summer=23,
    release_minute=0,
    release_hour_winter=0,
    release_months=None,  # 毎月
    cross_month=True,
)

# 単位労働コスト (UNIT_LABOR_COST)
# 発表期間: 毎月1-15日
# 発表時刻: 21:30 (夏) / 22:30 (冬) JST
# 発表月: 2月、3月、5月、6月、8月、9月、11月、12月（四半期末以外）
UNIT_LABOR_COST_CHECKER = ReleaseScheduleChecker(
    release_days=(1, 15),
    release_hour_summer=21,
    release_minute=30,
    release_hour_winter=22,
    release_months=[2, 3, 5, 6, 8, 9, 11, 12],
)

# Challenger人員削減 (CHALLENGER_LAYOFFS)
# 発表期間: 毎月31日～翌月9日（月跨ぎ）
# 発表時刻: 20:30 (夏) / 21:30 (冬) JST
CHALLENGER_LAYOFFS_CHECKER = ReleaseScheduleChecker(
    release_days=(31, 9),
    release_hour_summer=20,
    release_minute=30,
    release_hour_winter=21,
    release_months=None,  # 毎月
    cross_month=True,
)

# ============================================================
# ISM関連
# ============================================================

# ISM製造業景況指数 (ISM_MANUFACTURING)
# 発表期間: 毎月1-6日（第1営業日付近）
# 発表時刻: 23:00 (夏) / 0:00 (冬) JST
ISM_MANUFACTURING_CHECKER = ReleaseScheduleChecker(
    release_days=(1, 6),
    release_hour_summer=23,
    release_minute=0,
    release_hour_winter=0,
    release_months=None,
)

# ISM非製造業景況指数 (ISM_NON_MANUFACTURING)
# 発表期間: 毎月3-8日（第3営業日付近、製造業より2日遅い）
# 発表時刻: 23:00 (夏) / 0:00 (冬) JST
ISM_NON_MANUFACTURING_CHECKER = ReleaseScheduleChecker(
    release_days=(3, 8),
    release_hour_summer=23,
    release_minute=0,
    release_hour_winter=0,
    release_months=None,
)

# ============================================================
# ADP関連
# ============================================================

# ADP雇用者数・ADP賃金上昇率中央値 (ADP_EMPLOYMENT)
# 発表期間: 毎月30日～翌月9日（月跨ぎ、39日相当）
# 発表時刻: 21:15 (夏) / 22:15 (冬) JST (8:15 AM ET)
ADP_EMPLOYMENT_CHECKER = ReleaseScheduleChecker(
    release_days=(30, 9),
    release_hour_summer=21,
    release_minute=15,
    release_hour_winter=22,
    release_months=None,
    cross_month=True,
)

# ============================================================
# 消費者信頼感関連
# ============================================================

# CB消費者信頼感指数・CB雇用機会業況判断 (CB_CONSUMER_CONFIDENCE)
# 発表期間: 毎月21日～翌月2日（月跨ぎ、32日相当）
# 発表時刻: 23:00 (夏) / 0:00 (冬) JST (10:00 AM ET)
CB_CONSUMER_CONFIDENCE_CHECKER = ReleaseScheduleChecker(
    release_days=(21, 2),
    release_hour_summer=23,
    release_minute=0,
    release_hour_winter=0,
    release_months=None,
    cross_month=True,
)

# ミシガン大学消費者信頼感指数 (MICHIGAN_CONSUMER_SENTIMENT)
# 発表期間: 毎月1-31日（速報版：第2金曜日、確報版：最終金曜日）
# 発表時刻: 23:00 (夏) / 0:00 (冬) JST (10:00 AM ET)
MICHIGAN_CONSUMER_SENTIMENT_CHECKER = ReleaseScheduleChecker(
    release_days=(1, 31),
    release_hour_summer=23,
    release_minute=0,
    release_hour_winter=0,
    release_months=None,
)

# ============================================================
# 小売売上・PCE関連
# ============================================================

# 小売売上高 / Retail Control (RETAIL_SALES)
# 発表期間: 毎月11-18日
# 発表時刻: 21:30 (夏) / 22:30 (冬) JST (8:30 AM ET)
RETAIL_SALES_CHECKER = ReleaseScheduleChecker(
    release_days=(11, 18),
    release_hour_summer=21,
    release_minute=30,
    release_hour_winter=22,
    release_months=None,
)

# 家計貯蓄率・個人所得・可処分所得・個人消費支出（PCE）・
# PCEデフレーター飲食宿泊・娯楽
# 発表期間: 毎月20日～翌月8日（月跨ぎ）
# 発表時刻: 21:30 (夏) / 22:30 (冬) JST (8:30 AM ET)
# ※ まれに0:00もあるため冬時間のみ0:00もチェック推奨
PERSONAL_INCOME_CHECKER = ReleaseScheduleChecker(
    release_days=(20, 8),
    release_hour_summer=21,
    release_minute=30,
    release_hour_winter=22,
    release_months=None,
    cross_month=True,
)

# ============================================================
# 週次失業保険申請件数
# ============================================================

# 新規失業保険申請件数・継続失業保険申請件数 (INITIAL_CLAIMS)
# 発表期間: 毎週水曜日と木曜日
# 発表時刻: 21:30 (夏) / 22:30 (冬) JST (8:30 AM ET)
# ※ 水曜日（新規）と木曜日（継続）の両方をカバー
WEEKLY_CLAIMS_CHECKER = ReleaseScheduleChecker(
    weekly_day_of_week=3,  # 木曜日（メインの発表日）
    release_hour_summer=21,
    release_minute=30,
    release_hour_winter=22,
    release_months=None,
)

# 新規失業保険申請件数（水曜日発表分）
WEEKLY_CLAIMS_WEDNESDAY_CHECKER = ReleaseScheduleChecker(
    weekly_day_of_week=2,  # 水曜日
    release_hour_summer=21,
    release_minute=30,
    release_hour_winter=22,
    release_months=None,
)

# ============================================================
# 地区連銀調査
# ============================================================

# NY連銀製造業景気指数 (Empire State Manufacturing)
# 発表期間: 毎月15-18日
# 発表時刻: 21:30 (夏) / 22:30 (冬) JST (8:30 AM ET)
NY_FED_MANUFACTURING_CHECKER = ReleaseScheduleChecker(
    release_days=(15, 18),
    release_hour_summer=21,
    release_minute=30,
    release_hour_winter=22,
    release_months=None,
)

# フィラデルフィア連銀製造業景気指数 現況 / 期待（今後6か月）
# 発表期間: 毎月15-21日
# 発表時刻: 21:30 (夏) / 22:30 (冬) JST (8:30 AM ET)
PHILLY_FED_MANUFACTURING_CHECKER = ReleaseScheduleChecker(
    release_days=(15, 21),
    release_hour_summer=21,
    release_minute=30,
    release_hour_winter=22,
    release_months=None,
)

# 地区連銀共通チェッカー（NY連銀と同じスケジュール）
REGIONAL_FED_CHECKER = NY_FED_MANUFACTURING_CHECKER


# ============================================================
# 鉱工業生産関連
# ============================================================

# 鉱工業生産 / 設備稼働率 (INDUSTRIAL_PRODUCTION)
# 発表期間: 毎月14-18日
# 発表時刻: 22:15 (夏) / 23:15 (冬) JST (9:15 AM ET)
INDUSTRIAL_PRODUCTION_CHECKER = ReleaseScheduleChecker(
    release_days=(14, 18),
    release_hour_summer=22,
    release_minute=15,
    release_hour_winter=23,
    release_months=None,
)

# 設備稼働率 (CAPACITY_UTILIZATION) - 鉱工業生産と同時発表
CAPACITY_UTILIZATION_CHECKER = INDUSTRIAL_PRODUCTION_CHECKER

# 耐久財受注 (DURABLE_GOODS)
# 発表期間: 毎月21日～翌月20日（月跨ぎ、約50日相当）
# 発表時刻: 21:30 (夏) / 22:30 (冬) JST (8:30 AM ET)
DURABLE_GOODS_CHECKER = ReleaseScheduleChecker(
    release_days=(21, 20),
    release_hour_summer=21,
    release_minute=30,
    release_hour_winter=22,
    release_months=None,
    cross_month=True,
)

# ============================================================
# その他週次指標
# ============================================================

# レッドブック（前年比）(REDBOOK)
# 発表期間: 毎週火曜日と水曜日
# 発表時刻: 21:55 (夏) / 22:55 (冬) JST (8:55 AM ET)
REDBOOK_TUESDAY_CHECKER = ReleaseScheduleChecker(
    weekly_day_of_week=1,  # 火曜日
    release_hour_summer=21,
    release_minute=55,
    release_hour_winter=22,
    release_months=None,
)

REDBOOK_WEDNESDAY_CHECKER = ReleaseScheduleChecker(
    weekly_day_of_week=2,  # 水曜日
    release_hour_summer=21,
    release_minute=55,
    release_hour_winter=22,
    release_months=None,
)

# レッドブック共通チェッカー（火曜日をメインとする）
REDBOOK_CHECKER = REDBOOK_TUESDAY_CHECKER


# Consumer Credit (毎週金曜日)
# 発表: 毎週金曜日 16:15 ET (翌土曜日 5:15/6:15 JST)
# 週次パターンで正確に判定
CONSUMER_CREDIT_CHECKER = ReleaseScheduleChecker(
    weekly_day_of_week=5,  # 土曜日（ETでは金曜日だがJSTでは翌日）
    release_hour_summer=5,
    release_minute=15,
    release_hour_winter=6,
    release_months=None,
)

# ============================================================
# その他月次指標
# ============================================================

# NFIB中小企業楽観指数・NFIB中小企業設備投資計画・
# NFIB中小企業人件費 / 雇用計画・NFIB労働報酬
# 発表期間: 毎月8-14日
# 発表時刻: 19:00 (夏) / 20:00 (冬) JST (6:00 AM ET)
NFIB_CHECKER = ReleaseScheduleChecker(
    release_days=(8, 14),
    release_hour_summer=19,
    release_minute=0,
    release_hour_winter=20,
    release_months=None,
)

# 延滞率（四半期、2/5/8/11月）
# 発表期間: 毎月15-28日
# 発表時刻: 23:00 (夏) / 0:00 (冬) JST (10:00 AM ET)
DELINQUENCY_RATE_CHECKER = ReleaseScheduleChecker(
    release_days=(15, 28),
    release_hour_summer=23,
    release_minute=0,
    release_hour_winter=0,
    release_months=[2, 5, 8, 11],
)

# 自動車販売 (TOTAL_VEHICLE_SALES)
# 発表期間: 毎月1-7日
# 発表時刻: 23:00 (夏) / 0:00 (冬) JST
VEHICLE_SALES_CHECKER = ReleaseScheduleChecker(
    release_days=(1, 7),
    release_hour_summer=23,
    release_minute=0,
    release_hour_winter=0,
    release_months=None,
)

# Atlanta Fed賃金トラッカー / Indeed賃金トラッカー
# 特殊パターン: 新データ取得まで毎日チェック、取得後は月内スキップ
# → WageTrackerScheduleChecker を使用（下記クラス参照）


class WageTrackerScheduleChecker:
    """
    賃金トラッカー（Atlanta Fed / Indeed）専用スケジュールチェッカー

    発表スケジュール:
    - Atlanta Fed: 毎月第2金曜日までに更新（CPSデータ公開後）
    - Indeed: 毎月15日以降に更新

    動作ロジック:
    1. 開始日（8日 or 15日）以降、毎日指定時刻にチェック
    2. 新しいデータを取得できたら、その月はスキップ
    3. 終了日（第2金曜日 or 20日）を過ぎてもチェック継続（データ遅延対応）
    4. 3分方式で更新チェック
    """

    UPDATE_WINDOW_MINUTES = 3

    # 日次リトライ時刻（JST）
    DAILY_CHECK_HOUR = 9
    DAILY_CHECK_MINUTE = 0

    def __init__(
        self,
        start_day: int = 8,
        use_second_friday_end: bool = False,  # True: 第2金曜日まで, False: end_day使用
        end_day: int = 20,
        release_hour_summer: int = 21,
        release_minute: int = 30,
        release_hour_winter: int = 22,
    ):
        """
        Args:
            start_day: チェック開始日（1-31）
            use_second_friday_end: 終了日を第2金曜日にするか
            end_day: チェック終了日（use_second_friday_end=Falseの場合）
            release_hour_summer: 夏時間の発表時刻（時、JST）
            release_minute: 発表時刻（分）
            release_hour_winter: 冬時間の発表時刻（時、JST）
        """
        self.start_day = start_day
        self.use_second_friday_end = use_second_friday_end
        self.end_day = end_day
        self.release_hour_summer = release_hour_summer
        self.release_minute = release_minute
        self.release_hour_winter = release_hour_winter

    def should_refresh(
        self,
        last_updated_str: str,
        latest_data_date: Optional[str] = None
    ) -> bool:
        """
        キャッシュを更新すべきかどうかを判定（3分方式対応）

        Args:
            last_updated_str: 最終更新日時のISO文字列
            latest_data_date: 最新データの日付（YYYY-MM-DD）

        Returns:
            True: 更新が必要
            False: キャッシュ有効
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 今月のデータがあれば更新不要（月内スキップ）
            if latest_data_date:
                try:
                    data_date = datetime.strptime(latest_data_date, "%Y-%m-%d").date()
                    # 今月のデータがあればスキップ
                    if data_date.year == now.year and data_date.month == now.month:
                        return False
                except ValueError:
                    pass

            # チェック開始日より前ならスキップ
            if now.day < self.start_day:
                return False

            # 今日のチェック時刻を取得
            check_time = self._get_today_check_time(now)

            # チェック時刻より前ならスキップ
            if now < check_time:
                return False

            # 3分方式での判定
            update_window_end = check_time + timedelta(minutes=self.UPDATE_WINDOW_MINUTES)
            in_update_window = now <= update_window_end

            if in_update_window:
                # 3分以内: 最終更新がチェック時刻より前なら更新
                if last_updated < check_time:
                    return True
            else:
                # 3分経過後: チェック時刻以降に更新していなければ更新
                if last_updated < check_time:
                    return True

            return False

        except Exception as e:
            print(f"Error checking Wage Tracker refresh status: {e}")
            return False

    def _get_today_check_time(self, now: datetime) -> datetime:
        """今日のチェック時刻を取得"""
        return now.replace(
            hour=self.DAILY_CHECK_HOUR,
            minute=self.DAILY_CHECK_MINUTE,
            second=0,
            microsecond=0
        )

    def _get_second_friday(self, year: int, month: int) -> date:
        """指定月の第2金曜日を取得"""
        first_day = date(year, month, 1)
        first_weekday = first_day.weekday()

        # 最初の金曜日を見つける
        days_until_friday = (4 - first_weekday) % 7
        first_friday = first_day + timedelta(days=days_until_friday)

        # 第2金曜日
        second_friday = first_friday + timedelta(days=7)
        return second_friday

    def get_status(self) -> dict:
        """現在のステータスを取得（デバッグ用）"""
        now = datetime.now(JST)
        check_time = self._get_today_check_time(now)

        end_info = None
        if self.use_second_friday_end:
            second_friday = self._get_second_friday(now.year, now.month)
            end_info = f"第2金曜日: {second_friday}"
        else:
            end_info = f"終了日: {self.end_day}日"

        return {
            "now": now.isoformat(),
            "pattern": "wage_tracker_daily_until_update",
            "is_dst": is_dst(now),
            "start_day": self.start_day,
            "end_info": end_info,
            "today_check_time": check_time.isoformat(),
            "in_check_period": now.day >= self.start_day,
            "daily_check_time_jst": f"{self.DAILY_CHECK_HOUR}:{self.DAILY_CHECK_MINUTE:02d}",
        }


# Atlanta Fed賃金トラッカー用チェッカー
# 第2金曜日までチェック、その後もデータがなければ継続
ATLANTA_FED_WAGE_CHECKER = WageTrackerScheduleChecker(
    start_day=8,
    use_second_friday_end=True,
    release_hour_summer=21,
    release_minute=30,
    release_hour_winter=22,
)

# Indeed賃金トラッカー用チェッカー
# 15日以降チェック、20日までが目安
INDEED_WAGE_CHECKER = WageTrackerScheduleChecker(
    start_day=15,
    use_second_friday_end=False,
    end_day=20,
    release_hour_summer=21,
    release_minute=30,
    release_hour_winter=22,
)


# NER Pulse (週次、火曜日、月次NER発表週を除く)
# 特殊パターン: 毎週火曜日だが、月次NER発表週（第1水曜日の週）は除外
# → NERPulseScheduleChecker を使用（下記クラス参照）


class NERPulseScheduleChecker:
    """
    NER Pulse（週次雇用変動）専用スケジュールチェッカー

    発表スケジュール:
    - 毎週火曜日 8:15 AM ET（21:15/22:15 JST）
    - ただし、月次NER発表週は除外（月次NERは毎月第1水曜日に発表）

    動作ロジック:
    1. 毎週火曜日をチェック
    2. その週に第1水曜日（月次NER発表日）がある場合はスキップ
    3. 3分方式で更新チェック
    """

    UPDATE_WINDOW_MINUTES = 3

    def __init__(
        self,
        release_hour_summer: int = 21,
        release_minute: int = 15,
        release_hour_winter: int = 22,
    ):
        """
        Args:
            release_hour_summer: 夏時間の発表時刻（時、JST）
            release_minute: 発表時刻（分）
            release_hour_winter: 冬時間の発表時刻（時、JST）
        """
        self.release_hour_summer = release_hour_summer
        self.release_minute = release_minute
        self.release_hour_winter = release_hour_winter

    def should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定（3分方式対応）

        Args:
            last_updated_str: 最終更新日時のISO文字列

        Returns:
            True: 更新が必要
            False: キャッシュ有効
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 直近の発表日時を取得
            last_release = self._get_last_release(now)
            if last_release is None:
                return False

            # 現在時刻が発表時刻より前なら更新不要
            if now < last_release:
                return False

            # 発表時刻から3分以内かどうか
            update_window_end = last_release + timedelta(minutes=self.UPDATE_WINDOW_MINUTES)
            in_update_window = now <= update_window_end

            if in_update_window:
                # 3分以内: 最終更新が発表時刻より前なら更新
                if last_updated < last_release:
                    return True
            else:
                # 3分経過後: 発表時刻以降に更新していなければ更新
                if last_updated < last_release:
                    return True

            return False

        except Exception as e:
            print(f"Error checking NER Pulse refresh status: {e}")
            return False

    def _get_last_release(self, now: datetime) -> Optional[datetime]:
        """
        直近のNER Pulse発表日時を取得（月次NER週を除外）

        Args:
            now: 現在日時

        Returns:
            直近の発表日時（JST）。該当なしならNone
        """
        today = now.date()

        # 過去4週間の火曜日をチェック
        for weeks_ago in range(4):
            # 今週の火曜日を基準に過去を探索
            current_weekday = today.weekday()  # 0=月, 1=火, ...
            days_since_tuesday = (current_weekday - 1) % 7  # 火曜日=1
            this_tuesday = today - timedelta(days=days_since_tuesday)
            target_tuesday = this_tuesday - timedelta(weeks=weeks_ago)

            # 月次NER発表週かどうかをチェック
            if self._is_monthly_ner_week(target_tuesday):
                continue  # この週はスキップ

            # 発表時刻を構築
            release_time = self._build_release_datetime(target_tuesday)

            # 今日が対象火曜日で、まだ発表時刻前なら前週を探す
            if weeks_ago == 0 and now < release_time:
                continue

            return release_time

        return None

    def _get_next_release(self, now: datetime) -> Optional[datetime]:
        """
        次のNER Pulse発表日時を取得

        Args:
            now: 現在日時

        Returns:
            次の発表日時（JST）
        """
        today = now.date()

        # 今後4週間の火曜日をチェック
        for weeks_ahead in range(4):
            current_weekday = today.weekday()
            days_until_tuesday = (1 - current_weekday) % 7  # 火曜日=1
            if days_until_tuesday == 0 and weeks_ahead == 0:
                # 今日が火曜日の場合
                this_tuesday = today
            else:
                this_tuesday = today + timedelta(days=days_until_tuesday)
            target_tuesday = this_tuesday + timedelta(weeks=weeks_ahead)

            # 月次NER発表週かどうかをチェック
            if self._is_monthly_ner_week(target_tuesday):
                continue  # この週はスキップ

            # 発表時刻を構築
            release_time = self._build_release_datetime(target_tuesday)

            # 発表時刻を過ぎていたら次を探す
            if release_time <= now:
                continue

            return release_time

        return None

    def _is_monthly_ner_week(self, tuesday_date: date) -> bool:
        """
        指定された火曜日が月次NER発表週（第1水曜日の週）かどうかを判定

        月次NERは毎月第1水曜日に発表される。
        その週の火曜日（前日）はNER Pulseがない。

        Args:
            tuesday_date: 火曜日の日付

        Returns:
            True: 月次NER発表週（NER Pulseなし）
            False: 通常週（NER Pulseあり）
        """
        # この火曜日の翌日（水曜日）を取得
        wednesday_date = tuesday_date + timedelta(days=1)

        # その水曜日が第1水曜日かどうかを判定
        first_wednesday = self._get_nth_weekday_of_month(
            wednesday_date.year,
            wednesday_date.month,
            nth=1,
            weekday=2  # 水曜日=2
        )

        return wednesday_date == first_wednesday

    def _get_nth_weekday_of_month(
        self,
        year: int,
        month: int,
        nth: int,
        weekday: int
    ) -> Optional[date]:
        """
        指定月の第N週のX曜日を取得

        Args:
            year: 年
            month: 月
            nth: 第何週（1-5）
            weekday: 曜日（0=月, 2=水, 6=日）

        Returns:
            該当日付。月内に存在しない場合はNone
        """
        first_day = date(year, month, 1)
        first_weekday = first_day.weekday()

        days_until_first = (weekday - first_weekday) % 7
        first_target = first_day + timedelta(days=days_until_first)
        target = first_target + timedelta(weeks=nth - 1)

        if target.month != month:
            return None

        return target

    def _build_release_datetime(self, target_date: date) -> datetime:
        """日付と発表時刻からdatetimeを構築"""
        temp_dt = datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            12, 0, 0,
            tzinfo=JST
        )

        if is_dst(temp_dt):
            release_hour = self.release_hour_summer
        else:
            release_hour = self.release_hour_winter

        return datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            release_hour,
            self.release_minute,
            0,
            tzinfo=JST
        )

    def get_status(self) -> dict:
        """現在のステータスを取得（デバッグ用）"""
        now = datetime.now(JST)
        last_release = self._get_last_release(now)
        next_release = self._get_next_release(now)

        # 今月の発表日一覧を取得
        this_month_releases = self._get_this_month_releases(now)

        return {
            "now": now.isoformat(),
            "pattern": "ner_pulse_weekly_excluding_monthly",
            "is_dst": is_dst(now),
            "last_release": last_release.isoformat() if last_release else None,
            "next_release": next_release.isoformat() if next_release else None,
            "this_month_releases": [r.isoformat() for r in this_month_releases],
            "release_time_jst": f"{self.release_hour_summer}:{self.release_minute:02d} (summer) / {self.release_hour_winter}:{self.release_minute:02d} (winter)",
        }

    def _get_this_month_releases(self, now: datetime) -> List[datetime]:
        """今月のNER Pulse発表日一覧を取得"""
        result = []
        year = now.year
        month = now.month

        # 今月の全ての火曜日を取得
        first_day = date(year, month, 1)
        first_tuesday = first_day + timedelta(days=(1 - first_day.weekday()) % 7)

        current_tuesday = first_tuesday
        while current_tuesday.month == month:
            if not self._is_monthly_ner_week(current_tuesday):
                release_time = self._build_release_datetime(current_tuesday)
                result.append(release_time)
            current_tuesday += timedelta(weeks=1)

        return result


# NER Pulse用チェッカーインスタンス
NER_PULSE_CHECKER = NERPulseScheduleChecker(
    release_hour_summer=21,
    release_minute=15,
    release_hour_winter=22,
)

# CARTS（週次小売）
# 発表: 第1木曜日（予備版）、第2金曜日（確定版）8:30 ET
# 月内第N週パターンで正確に判定
CARTS_CHECKER = ReleaseScheduleChecker(
    nth_week_patterns=[
        {"nth": 1, "day_of_week": 3},  # 第1木曜日
        {"nth": 2, "day_of_week": 4},  # 第2金曜日
    ],
    release_hour_summer=21,
    release_minute=30,
    release_hour_winter=22,
    release_months=None,
)

# Visa Spending Momentum Index
# 特殊パターン: スケジュールファイルベース + 月1回更新成功後スキップ
# → VisaSpendingScheduleChecker を使用（下記クラス参照）


class VisaSpendingScheduleChecker:
    """
    Visa Spending Momentum Index 専用スケジュールチェッカー

    動作ロジック:
    1. スケジュールファイルから次回発表日を読み込み
    2. 発表日時を過ぎたら3分方式で更新チェック
    3. 新しいデータを取得できたら、その月はスキップ
    4. 取得できなければ翌日以降も毎日リトライ
    5. スケジュールファイルがなければ毎月15日を仮定
    """

    UPDATE_WINDOW_MINUTES = 3

    # デフォルト発表時刻（JST）
    DEFAULT_HOUR_SUMMER = 21
    DEFAULT_MINUTE = 30
    DEFAULT_HOUR_WINTER = 22

    # 日次リトライ時刻（JST）
    DAILY_RETRY_HOUR = 9
    DAILY_RETRY_MINUTE = 0

    def __init__(
        self,
        schedule_file: Optional[str] = None,
        release_hour_summer: int = 21,
        release_minute: int = 30,
        release_hour_winter: int = 22,
    ):
        """
        Args:
            schedule_file: スケジュールファイルのパス（JSON形式）
            release_hour_summer: 夏時間の発表時刻（時、JST）
            release_minute: 発表時刻（分）
            release_hour_winter: 冬時間の発表時刻（時、JST）
        """
        self.schedule_file = schedule_file
        self.release_hour_summer = release_hour_summer
        self.release_minute = release_minute
        self.release_hour_winter = release_hour_winter

    def should_refresh(
        self,
        last_updated_str: str,
        latest_data_date: Optional[str] = None
    ) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        Args:
            last_updated_str: 最終更新日時のISO文字列
            latest_data_date: 最新データの日付（YYYY-MM-DD）

        Returns:
            True: 更新が必要
            False: キャッシュ有効
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 今月の発表日時を取得
            release_dt = self._get_this_month_release(now)

            # 最新データが今月のものか確認
            if latest_data_date:
                try:
                    data_date = datetime.strptime(latest_data_date, "%Y-%m-%d").date()
                    # 今月のデータがあれば更新不要（月内スキップ）
                    if data_date.year == now.year and data_date.month == now.month:
                        return False
                    # 先月のデータがあれば、発表日以降で更新
                    if data_date.year == now.year and data_date.month == now.month - 1:
                        # 発表日前ならスキップ
                        if release_dt and now < release_dt:
                            return False
                    if data_date.year == now.year - 1 and data_date.month == 12 and now.month == 1:
                        if release_dt and now < release_dt:
                            return False
                except ValueError:
                    pass

            # 発表日時が不明ならデフォルト動作（毎日9:00にチェック）
            if release_dt is None:
                return self._should_retry_daily(now, last_updated)

            # 発表時刻より前ならスキップ
            if now < release_dt:
                return False

            # 3分方式での判定
            update_window_end = release_dt + timedelta(minutes=self.UPDATE_WINDOW_MINUTES)
            in_update_window = now <= update_window_end

            if in_update_window:
                # 3分以内: 最終更新が発表時刻より前なら更新
                if last_updated < release_dt:
                    return True
            else:
                # 3分経過後: 発表時刻以降に更新していなければ更新
                # ただし、新データがなければ日次リトライ
                if last_updated < release_dt:
                    return True
                # 発表日以降で、今月のデータがなければ日次リトライ
                return self._should_retry_daily(now, last_updated)

            return False

        except Exception as e:
            print(f"Error checking Visa Spending refresh status: {e}")
            return False

    def _get_this_month_release(self, now: datetime) -> Optional[datetime]:
        """
        今月の発表日時を取得

        Args:
            now: 現在日時

        Returns:
            発表日時（JST）。不明ならNone
        """
        # スケジュールファイルから読み込み
        schedule = self._load_schedule()

        if schedule:
            # 今月の発表日を探す
            target_month = f"{now.year:04d}-{now.month:02d}"
            for entry in schedule.get("releases", []):
                date_str = entry.get("date", "")
                if date_str.startswith(target_month):
                    try:
                        release_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                        return self._build_release_datetime(release_date)
                    except ValueError:
                        continue

        # スケジュールがなければNone（日次リトライモード）
        return None

    def _should_retry_daily(self, now: datetime, last_updated: datetime) -> bool:
        """
        日次リトライが必要かどうかを判定

        毎日9:00 JSTにリトライ（最終更新が9:00より前なら）
        """
        today_retry_time = now.replace(
            hour=self.DAILY_RETRY_HOUR,
            minute=self.DAILY_RETRY_MINUTE,
            second=0,
            microsecond=0
        )

        # 今日のリトライ時刻を過ぎていて、最終更新がそれより前なら更新
        if now >= today_retry_time and last_updated < today_retry_time:
            return True

        return False

    def _build_release_datetime(self, target_date: date) -> datetime:
        """日付と発表時刻からdatetimeを構築"""
        temp_dt = datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            12, 0, 0,
            tzinfo=JST
        )

        if is_dst(temp_dt):
            release_hour = self.release_hour_summer
        else:
            release_hour = self.release_hour_winter

        return datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            release_hour,
            self.release_minute,
            0,
            tzinfo=JST
        )

    def _load_schedule(self) -> Optional[Dict]:
        """スケジュールファイルを読み込み"""
        if not self.schedule_file:
            return None

        try:
            import json
            from pathlib import Path

            path = Path(self.schedule_file)
            if not path.exists():
                return None

            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load Visa schedule file: {e}")
            return None

    def get_status(self) -> dict:
        """現在のステータスを取得（デバッグ用）"""
        now = datetime.now(JST)
        release_dt = self._get_this_month_release(now)

        return {
            "now": now.isoformat(),
            "pattern": "visa_spending_schedule",
            "is_dst": is_dst(now),
            "this_month_release": release_dt.isoformat() if release_dt else None,
            "schedule_file": self.schedule_file,
            "daily_retry_hour": self.DAILY_RETRY_HOUR,
        }


# Visa Spending用チェッカーインスタンス
# スケジュールファイルは backend/cache/usa/consumer/visa_spending_schedule.json に配置
from pathlib import Path as _Path
_VISA_SCHEDULE_FILE = _Path(__file__).parent.parent.parent / "cache" / "usa" / "consumer" / "visa_spending_schedule.json"

VISA_SPENDING_CHECKER = VisaSpendingScheduleChecker(
    schedule_file=str(_VISA_SCHEDULE_FILE),
    release_hour_summer=21,
    release_minute=30,
    release_hour_winter=22,
)


# ============================================================
# Inflation Nowcasting スケジュールチェッカー（毎営業日）
# ============================================================

class InflationNowcastingScheduleChecker:
    """
    Cleveland Fed Inflation Nowcasting 用スケジュールチェッカー

    毎営業日（月-金）10:00 ETに更新される。
    発表時刻から3分間は毎分更新チェックを行う（3分方式）。
    """

    # 発表後の更新チェック期間（分）
    UPDATE_WINDOW_MINUTES = 3

    def __init__(
        self,
        release_hour_summer: int = 23,  # 10:00 ET = 23:00 JST（夏時間）
        release_minute: int = 0,
        release_hour_winter: int = 0,    # 10:00 ET = 00:00 JST（翌日、冬時間）
    ):
        """
        Args:
            release_hour_summer: 夏時間の発表時刻（時、JST）
            release_minute: 発表時刻（分）
            release_hour_winter: 冬時間の発表時刻（時、JST）
        """
        self.release_hour_summer = release_hour_summer
        self.release_minute = release_minute
        self.release_hour_winter = release_hour_winter

    def should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        判定ロジック（毎営業日 3分方式）:
        1. 土日はスキップ
        2. 今日の発表時刻を計算
        3. 発表時刻から3分以内なら、最終更新が発表時刻より前なら更新
        4. 発表時刻を3分以上過ぎていて、まだ更新していなければ更新

        Args:
            last_updated_str: 最終更新日時のISO文字列

        Returns:
            True: 更新が必要
            False: キャッシュ有効
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 営業日チェック（土日はスキップ）
            # 冬時間では発表が翌日0:00 JSTになるため、金曜深夜は土曜日になっている可能性
            if not self._is_business_day(now):
                return False

            # 今日の発表時刻を計算
            release_time = self._get_today_release_time(now)
            if release_time is None:
                return False

            # 発表時刻より前ならスキップ
            if now < release_time:
                return False

            # 3分方式での判定
            update_window_end = release_time + timedelta(minutes=self.UPDATE_WINDOW_MINUTES)
            in_update_window = now <= update_window_end

            if in_update_window:
                # 3分以内: 最終更新が発表時刻より前なら更新
                if last_updated < release_time:
                    return True
            else:
                # 3分経過後: 発表時刻以降に更新していなければ更新
                if last_updated < release_time:
                    return True

            return False

        except Exception as e:
            print(f"Error checking Inflation Nowcasting refresh status: {e}")
            return False

    def _is_business_day(self, dt: datetime) -> bool:
        """
        営業日かどうかを判定（土日を除外）

        冬時間の場合、金曜10:00 ETは土曜00:00 JSTになるため、
        土曜0-1時台は金曜の発表扱いとする。
        """
        weekday = dt.weekday()

        # 土曜日だが、深夜0-1時台の場合は金曜の発表時刻の可能性
        if weekday == 5 and dt.hour < 2:
            # 冬時間かどうかチェック
            if not is_dst(dt):
                return True  # 金曜の発表扱い

        # 日曜日または土曜日（深夜除く）
        if weekday >= 5:
            return False

        return True

    def _get_today_release_time(self, now: datetime) -> Optional[datetime]:
        """
        今日の発表時刻を取得

        Args:
            now: 現在日時

        Returns:
            発表時刻（JST）
        """
        # サマータイム判定
        is_summer = is_dst(now)

        if is_summer:
            release_hour = self.release_hour_summer
            target_date = now.date()
        else:
            release_hour = self.release_hour_winter
            # 冬時間では0:00 JSTになるため、実際の発表日は前日のET
            # 土曜0:00 JSTは金曜10:00 ETの発表
            if now.hour < 2:
                target_date = now.date()  # 前日からの継続
            else:
                target_date = now.date()

        return datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            release_hour,
            self.release_minute,
            0,
            tzinfo=JST
        )

    def get_status(self) -> dict:
        """現在のステータスを取得（デバッグ・スケジューラー用）"""
        now = datetime.now(JST)
        is_business = self._is_business_day(now)
        release_time = self._get_today_release_time(now) if is_business else None

        # 次回発表日時を計算（今日が営業日でない場合は次の営業日）
        next_release = None
        if release_time:
            if now < release_time:
                next_release = release_time
            else:
                # 次の営業日の発表時刻
                next_release = self._get_next_business_day_release(now)
        else:
            next_release = self._get_next_business_day_release(now)

        return {
            "now": now.isoformat(),
            "pattern": "business_day_daily",
            "is_dst": is_dst(now),
            "is_business_day": is_business,
            "release_time": release_time.isoformat() if release_time else None,
            "next_release": next_release.isoformat() if next_release else None,
        }

    def _get_next_business_day_release(self, now: datetime) -> Optional[datetime]:
        """次の営業日の発表時刻を取得"""
        check_date = now + timedelta(days=1)

        for _ in range(7):  # 最大7日先までチェック
            weekday = check_date.weekday()
            if weekday < 5:  # 月-金
                is_summer = is_dst(check_date)
                if is_summer:
                    release_hour = self.release_hour_summer
                else:
                    release_hour = self.release_hour_winter

                return datetime(
                    check_date.year,
                    check_date.month,
                    check_date.day,
                    release_hour,
                    self.release_minute,
                    0,
                    tzinfo=JST
                )
            check_date += timedelta(days=1)

        return None


# Inflation Nowcasting用チェッカーインスタンス
# 10:00 ET = 23:00 JST（夏時間）/ 00:00 JST（冬時間、翌日）
INFLATION_NOWCASTING_CHECKER = InflationNowcastingScheduleChecker(
    release_hour_summer=23,
    release_minute=0,
    release_hour_winter=0,
)

# GDPNow用チェッカー（毎営業日、不定期更新のため毎日チェック）
# 更新は経済指標発表の2-3時間後だが、不定期のため毎日6:00 JSTにチェック
GDPNOW_CHECKER = InflationNowcastingScheduleChecker(
    release_hour_summer=6,
    release_minute=0,
    release_hour_winter=6,
)

# NY Fed Term Premium用チェッカー（毎営業日）
# 日次データ、不定期更新のため毎日6:00 JSTにチェック
TERM_PREMIUM_CHECKER = InflationNowcastingScheduleChecker(
    release_hour_summer=6,
    release_minute=0,
    release_hour_winter=6,
)

# FCI-G用チェッカー（月次、不定期のため毎日チェック）
# 毎日6:00 JSTにチェック
FCI_CHECKER = InflationNowcastingScheduleChecker(
    release_hour_summer=6,
    release_minute=0,
    release_hour_winter=6,
)

# Affinity Spend用チェッカー（月1-2回、不定期のため毎日チェック）
# 毎日6:00 JSTにチェック
AFFINITY_SPEND_CHECKER = InflationNowcastingScheduleChecker(
    release_hour_summer=6,
    release_minute=0,
    release_hour_winter=6,
)

# NFCI用チェッカー（毎週水曜日 8:30 ET）
# 8:30 ET = 21:30 JST（夏時間）/ 22:30 JST（冬時間）
NFCI_CHECKER = ReleaseScheduleChecker(
    weekly_day_of_week=2,  # 水曜日 (0=月, 2=水)
    release_hour_summer=21,
    release_minute=30,
    release_hour_winter=22,
)
