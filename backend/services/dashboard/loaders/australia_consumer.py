"""
オーストラリア消費ダッシュボードローダー
家計支出など消費関連指標を一括取得

キャッシュ更新判定: FMP発表日時ベース判定
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
SYDNEY = ZoneInfo("Australia/Sydney")


class AustraliaConsumerLoader(BaseDashboardLoader):
    """
    オーストラリア消費ダッシュボード用データローダー

    取得データ:
    - au_household_spending: ABS家計支出（季節調整済み、MoM/YoY）
    - au_westpac_consumer_confidence: Westpac消費者信頼感指数
    - au_nab_business_confidence: NAB企業信頼感指数
    - au_consumer_spending: 個人消費（Chain Volume Measures）
    - au_household_saving_ratio: 家計貯蓄率
    - au_disposable_personal_income: 可処分所得

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "australia"
    CATEGORY_CODE = "consumer"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "au_household_spending",
        "au_westpac_consumer_confidence",
        "au_nab_business_confidence",
        "au_consumer_spending",
        "au_household_saving_ratio",
        "au_disposable_personal_income",
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
            print(f"[AustraliaConsumer] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全消費データを取得

        Returns:
            {
                "au_household_spending": {...},
                "au_westpac_consumer_confidence": {...},
                "au_nab_business_confidence": {...},
                "au_consumer_spending": {...},
                "au_household_saving_ratio": {...},
                "au_disposable_personal_income": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.australia.au_household_spending_service import au_household_spending_service
        from services.australia.au_westpac_consumer_confidence_service import au_westpac_consumer_confidence_service
        from services.australia.au_nab_business_confidence_service import au_nab_business_confidence_service
        from services.australia.au_consumer_spending_service import au_consumer_spending_service
        from services.australia.au_household_saving_ratio_service import au_household_saving_ratio_service
        from services.australia.au_disposable_personal_income_service import au_disposable_personal_income_service

        result = {
            "au_household_spending": None,
            "au_westpac_consumer_confidence": None,
            "au_nab_business_confidence": None,
            "au_consumer_spending": None,
            "au_household_saving_ratio": None,
            "au_disposable_personal_income": None,
        }

        # データを取得
        result["au_household_spending"] = self._get_household_spending(au_household_spending_service)
        result["au_westpac_consumer_confidence"] = self._get_westpac_consumer_confidence(au_westpac_consumer_confidence_service)
        result["au_nab_business_confidence"] = self._get_nab_business_confidence(au_nab_business_confidence_service)
        result["au_consumer_spending"] = self._get_consumer_spending(au_consumer_spending_service)
        result["au_household_saving_ratio"] = self._get_household_saving_ratio(au_household_saving_ratio_service)
        result["au_disposable_personal_income"] = self._get_disposable_personal_income(au_disposable_personal_income_service)

        return result

    def _get_household_spending(self, service) -> dict:
        """ABS家計支出データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_household_spending")
            response = service.get_au_household_spending_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaConsumer] Error getting Household Spending: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_westpac_consumer_confidence(self, service) -> dict:
        """Westpac消費者信頼感指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_westpac_consumer_confidence")
            response = service.get_au_westpac_consumer_confidence_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaConsumer] Error getting Westpac Consumer Confidence: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_nab_business_confidence(self, service) -> dict:
        """NAB企業信頼感指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_nab_business_confidence")
            response = service.get_au_nab_business_confidence_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaConsumer] Error getting NAB Business Confidence: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_consumer_spending(self, service) -> dict:
        """個人消費データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_consumer_spending")
            response = service.get_au_consumer_spending_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaConsumer] Error getting Consumer Spending: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_household_saving_ratio(self, service) -> dict:
        """家計貯蓄率データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_household_saving_ratio")
            response = service.get_au_household_saving_ratio_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaConsumer] Error getting Household Saving Ratio: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_disposable_personal_income(self, service) -> dict:
        """可処分所得データを取得"""
        try:
            force_refresh = self._should_force_refresh("au_disposable_personal_income")
            response = service.get_au_disposable_personal_income_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[AustraliaConsumer] Error getting Disposable Personal Income: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}
