"""
日本経済指標発表スケジュール判定ユーティリティ

日本の経済指標の発表期間と発表時刻に基づいて、キャッシュ更新が必要かどうかを判定する。

使用方法:
    from services.japan.release_schedule_utils import JapanReleaseScheduleChecker

    # パターン1: 日付範囲ベース（毎月X日〜Y日）
    checker = JapanReleaseScheduleChecker(
        release_days=(10, 18),          # 発表期間: 10〜18日
        release_hour_jst=8,             # 発表時刻（時、JST）
        release_minute_jst=50,          # 発表時刻（分）
    )

    # パターン2: 四半期（1/4/7/10月の特定期間）
    checker = JapanReleaseScheduleChecker(
        release_days=(3, 8),
        release_hour_jst=15,
        release_minute_jst=0,
        release_months=[1, 4, 7, 10],   # 四半期月のみ
    )

    # パターン3: 週次（毎週X曜日）
    checker = JapanReleaseScheduleChecker(
        weekly_day_of_week=2,           # 水曜日 (0=月, 2=水, 6=日)
        release_hour_jst=15,
        release_minute_jst=15,
    )

    if checker.should_refresh(last_updated_str):
        # データ更新処理
"""
from datetime import datetime, timedelta, date
from typing import Optional, Tuple, List, Dict
from zoneinfo import ZoneInfo


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class JapanReleaseScheduleChecker:
    """
    日本経済指標発表スケジュール判定クラス

    発表期間と発表時刻に基づいて、キャッシュ更新が必要かどうかを判定する。
    発表時刻から3分間は毎分更新チェックを行い、取りこぼしを防ぐ。

    3つのパターンに対応:
    1. 日付範囲ベース: release_days=(10, 18) で10〜18日の間をチェック
    2. 四半期: release_months=[1,4,7,10] で特定月のみチェック
    3. 週次: weekly_day_of_week=2 で毎週水曜日をチェック
    """

    # 発表時刻後の更新チェック期間（分）
    UPDATE_WINDOW_MINUTES = 3

    def __init__(
        self,
        release_days: Optional[Tuple[int, int]] = None,
        release_hour_jst: int = 0,
        release_minute_jst: int = 0,
        release_months: Optional[List[int]] = None,
        weekly_day_of_week: Optional[int] = None,
    ):
        """
        Args:
            release_days: 発表期間（開始日, 終了日）。例: (10, 18) = 10〜18日
            release_hour_jst: 発表時刻（時、JST）
            release_minute_jst: 発表時刻（分）
            release_months: 発表月のリスト。Noneなら毎月
            weekly_day_of_week: 週次発表の曜日（0=月, 1=火, ..., 6=日）
        """
        self.release_days = release_days
        self.release_hour_jst = release_hour_jst
        self.release_minute_jst = release_minute_jst
        self.release_months = release_months
        self.weekly_day_of_week = weekly_day_of_week

    def should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        判定ロジック（パターン別）:
        1. weekly_day_of_week が設定されている場合 → 週次判定
        2. release_days が設定されている場合 → 日付範囲判定

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

            # パターン2: 日付範囲判定
            if self.release_days is not None:
                return self._should_refresh_date_range(now, last_updated)

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return False

    def _should_refresh_date_range(self, now: datetime, last_updated: datetime) -> bool:
        """
        日付範囲ベースの更新判定

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

    def _build_release_datetime(self, target_date: date) -> datetime:
        """
        日付と発表時刻からdatetimeを構築

        Args:
            target_date: 対象日付

        Returns:
            発表日時（JST）
        """
        return datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            self.release_hour_jst,
            self.release_minute_jst,
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
        if self.release_days is None:
            return False
        start_day, end_day = self.release_days
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
            # 今日の発表時刻を構築
            release_time = now.replace(
                hour=self.release_hour_jst,
                minute=self.release_minute_jst,
                second=0,
                microsecond=0
            )
            return release_time

        except Exception as e:
            print(f"Error getting release time: {e}")
            return None

    def get_status(self) -> dict:
        """現在のステータスを取得（デバッグ・スケジューラー用）"""
        now = datetime.now(JST)

        status = {
            "now": now.isoformat(),
            "in_release_month": self._in_release_month(now),
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
        else:
            status["pattern"] = "date_range"
            status["release_days"] = self.release_days
            status["in_release_period"] = self._in_release_period(now)
            release_time = self._get_release_time(now) if self._in_release_period(now) else None
            status["release_time"] = release_time.isoformat() if release_time else None

        return status


# ============================================================
# 日本指標用のプリセット定義
# ============================================================

# 企業物価指数（CGPI）関連 - 飲食料品・農林水産物、輸入・輸出物価
# 発表期間: 毎月10-18日
# 発表時刻: 8:50 JST
JAPAN_CGPI_CHECKER = JapanReleaseScheduleChecker(
    release_days=(10, 18),
    release_hour_jst=8,
    release_minute_jst=50,
    release_months=None,  # 毎月
)

# 日銀GDPギャップ
# 発表期間: 四半期（1/4/7/10月）3-8日
# 発表時刻: 15:00 JST（推定）
JAPAN_BOJ_GDP_GAP_CHECKER = JapanReleaseScheduleChecker(
    release_days=(3, 8),
    release_hour_jst=15,
    release_minute_jst=0,
    release_months=[1, 4, 7, 10],
)

# 内閣府GDPギャップ（月例経済報告）
# 発表期間: 毎月20-28日頃
# 発表時刻: 15:00 JST（推定）
JAPAN_CAO_GDP_GAP_CHECKER = JapanReleaseScheduleChecker(
    release_days=(20, 28),
    release_hour_jst=15,
    release_minute_jst=0,
    release_months=None,
)

# POS-UVPI（消費者購買単価指数）
# 発表: 毎週水曜日 15:15 JST
JAPAN_POS_UVPI_CHECKER = JapanReleaseScheduleChecker(
    weekly_day_of_week=2,  # 水曜日 (0=月, 2=水)
    release_hour_jst=15,
    release_minute_jst=15,
    release_months=None,
)
