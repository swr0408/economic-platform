"""
オーストラリア金融政策ダッシュボードローダー
RBA政策金利などを一括取得

キャッシュ更新判定: FMP発表日時ベース判定
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
SYDNEY = ZoneInfo("Australia/Sydney")


class AustraliaPolicyLoader(BaseDashboardLoader):
    """
    オーストラリア金融政策ダッシュボード用データローダー

    取得データ:
    - au_rba_rate: RBA政策金利（キャッシュレート目標）
    - au_asx_rate_tracker: ASX RBA Rate Tracker
    - au_monetary_policy: RBA SMP経済予測

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "australia"
    CATEGORY_CODE = "policy"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "au_rba_rate",
        "au_asx_rate_tracker",
        "au_monetary_policy",
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
            print(f"[AustraliaPolicy] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全金融政策データを取得

        Returns:
            {
                "au_rba_rate": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.australia.rba_policy_rate_service import rba_policy_rate_service
        from services.australia.asx_rate_tracker_service import asx_rate_tracker_service
        from services.australia.rba_smp_forecast_service import rba_smp_forecast_service

        result = {
            "au_rba_rate": None,
            "au_asx_rate_tracker": None,
            "au_monetary_policy": None,
        }

        # データを取得
        result["au_rba_rate"] = self._get_au_rba_rate(rba_policy_rate_service)
        result["au_asx_rate_tracker"] = self._get_asx_rate_tracker(asx_rate_tracker_service)
        result["au_monetary_policy"] = self._get_monetary_policy(rba_smp_forecast_service)

        return result

    def _get_au_rba_rate(self, service) -> dict:
        """RBA政策金利データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_rba_rate")
            response = service.get_au_rba_rate_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaPolicy] Error getting RBA Rate: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_asx_rate_tracker(self, service) -> dict:
        """ASX RBA Rate Trackerデータを取得"""
        try:
            force_refresh = self._should_force_refresh("au_asx_rate_tracker")
            response = service.get_rate_tracker_data(force_refresh=force_refresh)
            return {
                "summary": response.get("summary"),
                "probability_history": response.get("probability_history", []),
                "probability_meta": response.get("probability_meta"),
                "yield_curve": response.get("yield_curve"),
            }
        except Exception as e:
            print(f"[AustraliaPolicy] Error getting ASX Rate Tracker: {e}")
            return {"summary": None, "probability_history": [], "probability_meta": None, "yield_curve": None}

    def _get_monetary_policy(self, service) -> dict:
        """RBA SMP経済予測データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_monetary_policy")
            response = service.get_smp_forecast_data(force_refresh=force_refresh)
            return {
                "indicators": response.get("indicators", {}),
                "metadata": response.get("metadata", {}),
            }
        except Exception as e:
            print(f"[AustraliaPolicy] Error getting SMP Forecast: {e}")
            return {"indicators": {}, "metadata": {}}
