"""
ニュージーランド消費ダッシュボードローダー
小売売上高等を一括取得

キャッシュ更新判定: FMP発表日時ベース判定
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
AUCKLAND = ZoneInfo("Pacific/Auckland")


class NewZealandConsumerLoader(BaseDashboardLoader):
    """
    ニュージーランド消費ダッシュボード用データローダー

    取得データ:
    - nz_retail_sales: 小売売上高（QoQ・YoY、全体・コア）
    - nz_anz_business_outlook_survey: ANZ企業景況感指数
    - nz_nzier_business_conditions_index: NZIER企業景況指数

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "newzealand"
    CATEGORY_CODE = "consumer"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "nz_retail_sales",
        "nz_anz_business_outlook_survey",
        "nz_nzier_business_conditions_index",
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
            print(f"[NewZealandConsumer] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全消費データを取得

        Returns:
            {
                "nz_retail_sales": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.newzealand.nz_retail_sales_service import nz_retail_sales_service
        from services.newzealand.nz_anz_business_outlook_survey_service import nz_anz_business_outlook_survey_service
        from services.newzealand.nz_nzier_business_conditions_index_service import nz_nzier_business_conditions_index_service

        result = {
            "nz_retail_sales": None,
            "nz_anz_business_outlook_survey": None,
            "nz_nzier_business_conditions_index": None,
        }

        # データを取得
        result["nz_retail_sales"] = self._get_indicator(
            nz_retail_sales_service, "nz_retail_sales", "Retail Sales"
        )
        result["nz_anz_business_outlook_survey"] = self._get_indicator(
            nz_anz_business_outlook_survey_service, "nz_anz_business_outlook_survey", "ANZ Business Outlook Survey"
        )
        result["nz_nzier_business_conditions_index"] = self._get_indicator(
            nz_nzier_business_conditions_index_service, "nz_nzier_business_conditions_index", "NZIER Business Conditions"
        )

        return result

    def _get_indicator(self, service, indicator_key: str, label: str) -> dict:
        """指標データを取得"""
        try:
            force_refresh = self._should_force_refresh(indicator_key)
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[NewZealandConsumer] Error getting {label}: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}
