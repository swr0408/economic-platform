"""
日本金融政策ダッシュボードローダー
日銀政策金利、バランスシート、次回発表日などを一括取得

キャッシュ更新判定: 発表日時ベース方式
- 政策金利: 日銀金融政策決定会合発表後（11:30-13:00 JST）
- バランスシート: 月次更新（FRED経由）
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class JapanPolicyLoader(BaseDashboardLoader):
    """
    日本金融政策ダッシュボード用データローダー

    取得データ:
    - boj_policy_rate: 日銀政策金利
    - japan_balance_sheet: 日銀バランスシート（総資産）
    - boj_current_account_balance: 日銀当座預金残高

    キャッシュ方式: 発表日時ベース判定
    - 日銀金融政策決定会合: 11:30-13:00 JST（発表時刻が変動するため5分おきにチェック）
    - バランスシート: 月次更新（FRED経由、月初チェック）
    """

    COUNTRY_CODE = "japan"
    CATEGORY_CODE = "policy"

    def __init__(self):
        super().__init__()
        # 発表日時を過ぎた指標のセット（load_all実行時に判定）
        self._stale_indicators: set = set()

    # 日銀発表時刻（JST）- 11:30から13:00の間
    BOJ_RELEASE_HOUR_START_JST = 11
    BOJ_RELEASE_MINUTE_START_JST = 30
    BOJ_RELEASE_HOUR_END_JST = 13
    BOJ_RELEASE_MINUTE_END_JST = 0

    def get_release_datetimes(self) -> List[Optional[datetime]]:
        """
        各指標の発表日時リストを返す

        Returns:
            - 日銀金融政策決定会合発表日時
        """
        release_times = []

        # 日銀発表日時（政策金利の更新タイミング）
        boj_release = self._get_boj_release_datetime()
        if boj_release:
            release_times.append(boj_release)

        return release_times

    def _get_boj_release_datetime(self) -> Optional[datetime]:
        """
        次回日銀金融政策決定会合発表日時を取得

        Returns:
            日銀発表日時（JST）、取得できない場合はNone
        """
        try:
            from services.japan.fmp_next_release_utils import get_next_release_from_fmp

            next_release = get_next_release_from_fmp("boj_policy_rate")
            if not next_release:
                return None

            datetime_jst_str = next_release.get("datetime_jst")
            if not datetime_jst_str:
                return None

            return datetime.fromisoformat(datetime_jst_str)

        except Exception as e:
            print(f"Error getting BOJ release datetime: {e}")
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

            # 日銀発表（政策金利）
            # next_releaseは発表直後に次回日付へ切り替わるため、last_releaseも確認する
            boj_release = self._get_boj_release_datetime()
            boj_last = self._get_last_release_datetime_from_fmp(
                "boj_policy_rate", indicator_name="BOJ", country="japan"
            )
            if self._is_stale_by_release(last_updated_dt, now, boj_release, boj_last):
                stale.add("boj_policy_rate")
                print(f"[stale] BOJ release detected")

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
                "boj_policy_rate": {...},
                "japan_balance_sheet": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.japan.boj_policy_rate_service import boj_policy_rate_service
        from services.japan.japan_balance_sheet_service import japan_balance_sheet_service
        from services.japan.boj_current_account_balance_service import boj_current_account_balance_service

        result = {
            "boj_policy_rate": None,
            "japan_balance_sheet": None,
            "boj_current_account_balance": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self._get_boj_policy_rate, boj_policy_rate_service): "boj_policy_rate",
                executor.submit(self._get_japan_balance_sheet, japan_balance_sheet_service): "japan_balance_sheet",
                executor.submit(self._get_boj_current_account_balance, boj_current_account_balance_service): "boj_current_account_balance",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_boj_policy_rate(self, service) -> dict:
        """日銀政策金利データを取得"""
        try:
            force_refresh = self._should_force_refresh("boj_policy_rate")
            response = service.get_boj_policy_rate_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting BOJ policy rate: {e}")
            return {"data": [], "latest": None, "next_release": None}

    def _get_japan_balance_sheet(self, service) -> dict:
        """日銀バランスシートデータを取得"""
        try:
            force_refresh = self._should_force_refresh("japan_balance_sheet")
            response = service.get_balance_sheet_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting Japan Balance Sheet: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_boj_current_account_balance(self, service) -> dict:
        """日銀当座預金残高データを取得"""
        try:
            force_refresh = self._should_force_refresh("boj_current_account_balance")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting BOJ Current Account Balance: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}
