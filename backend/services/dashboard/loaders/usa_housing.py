"""
米国住宅ダッシュボードローダー
住宅関連指標を一括取得

データソース:
- 30年固定住宅ローン金利: FRED (MORTGAGE30US)
- Redfin 全米住宅価格中央値（前年比）: Redfin Data Center
- S&P/ケースシラー住宅価格指数（前年比）: FRED (SPCS20RSA)
- 新築住宅販売戸数: FRED (HSN1F)
- 中古住宅販売保留: NAR (Pending Home Sales)
- 中古住宅販売戸数: NAR (Existing Home Sales)
- NAHB住宅市場指数: NAHB (Housing Market Index)
- 住宅着工件数・建設許可件数: FRED (HOUST, PERMIT)
- 賃貸空室率: FRED (RRVRUSQ156N)

キャッシュ更新判定: 各指標のスケジュールベース
"""
from typing import Dict, Any, Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")


class USAHousingLoader(BaseDashboardLoader):
    """
    米国住宅ダッシュボード用データローダー

    取得データ:
    - mortgage_rates: 30年固定住宅ローン金利 - FRED MORTGAGE30US（毎週木曜日 12:00 ET）
    - redfin_median_price: Redfin 全米住宅価格中央値（前年比）（月次 第3金曜日）
    - case_shiller: S&P/ケースシラー住宅価格指数（前年比）（月次）
    - new_home_sales: 新築住宅販売戸数 - FRED HSN1F（月次 下旬）

    キャッシュ方式: 各指標のスケジュールベース判定
    """

    COUNTRY_CODE = "usa"
    CATEGORY_CODE = "housing"

    def __init__(self):
        super().__init__()
        # 発表日時を過ぎた指標のセット（load_all実行時に判定）
        self._stale_indicators: set = set()

    # 発表時刻設定（ET）
    MORTGAGE_RELEASE_HOUR_ET = 12
    MORTGAGE_RELEASE_MINUTE_ET = 0
    MORTGAGE_RELEASE_DAY = 3  # 木曜日

    def get_release_datetimes(self):
        """
        各指標の発表日時リストを返す
        """
        return []

    def _should_force_refresh(self, indicator: str) -> bool:
        """指標が強制更新対象かどうかを判定"""
        if "all" in self._stale_indicators:
            return True
        return indicator in self._stale_indicators

    def load_all(self) -> Dict[str, Any]:
        """
        全住宅データを並列で取得

        Returns:
            {
                "mortgage_rates": {...},
                "redfin_median_price": {...},
                "case_shiller": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.usa.freddie_mac_mortgage_rates_service import freddie_mac_mortgage_rates_service
        from services.usa.redfin_median_price_service import redfin_median_price_service
        from services.usa.case_shiller_service import case_shiller_service
        from services.usa.new_home_sales_service import new_home_sales_service
        from services.usa.pending_home_sales_service import pending_home_sales_service
        from services.usa.existing_home_sales_service import existing_home_sales_service
        from services.usa.nahb_hmi_service import nahb_hmi_service
        from services.usa.housing_starts_permits_service import housing_starts_permits_service
        from services.usa.rental_vacancy_rate_service import rental_vacancy_rate_service

        result = {
            "mortgage_rates": None,
            "redfin_median_price": None,
            "case_shiller": None,
            "new_home_sales": None,
            "pending_home_sales": None,
            "existing_home_sales": None,
            "nahb_hmi": None,
            "housing_starts_permits": None,
            "rental_vacancy_rate": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(self._get_mortgage_rates, freddie_mac_mortgage_rates_service): "mortgage_rates",
                executor.submit(self._get_redfin_median_price, redfin_median_price_service): "redfin_median_price",
                executor.submit(self._get_case_shiller, case_shiller_service): "case_shiller",
                executor.submit(self._get_new_home_sales, new_home_sales_service): "new_home_sales",
                executor.submit(self._get_pending_home_sales, pending_home_sales_service): "pending_home_sales",
                executor.submit(self._get_existing_home_sales, existing_home_sales_service): "existing_home_sales",
                executor.submit(self._get_nahb_hmi, nahb_hmi_service): "nahb_hmi",
                executor.submit(self._get_housing_starts_permits, housing_starts_permits_service): "housing_starts_permits",
                executor.submit(self._get_rental_vacancy_rate, rental_vacancy_rate_service): "rental_vacancy_rate",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_mortgage_rates(self, service) -> Optional[dict]:
        """30年固定住宅ローン金利データを取得"""
        try:
            force_refresh = self._should_force_refresh("mortgage_rates")
            response = service.get_mortgage_rates_data(force_refresh=force_refresh)
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
            print(f"Error getting Mortgage Rates data: {e}")
            return None

    def _get_redfin_median_price(self, service) -> Optional[dict]:
        """Redfin 全米住宅価格中央値（前年比）データを取得"""
        try:
            force_refresh = self._should_force_refresh("redfin_median_price")
            response = service.get_redfin_median_price_data(force_refresh=force_refresh)
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
            print(f"Error getting Redfin Median Price data: {e}")
            return None

    def _get_case_shiller(self, service) -> Optional[dict]:
        """S&P/ケースシラー住宅価格指数（前年比）データを取得"""
        try:
            force_refresh = self._should_force_refresh("case_shiller")
            response = service.get_case_shiller_data(force_refresh=force_refresh)
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
            print(f"Error getting Case-Shiller data: {e}")
            return None

    def _get_new_home_sales(self, service) -> Optional[dict]:
        """新築住宅販売戸数データを取得"""
        try:
            force_refresh = self._should_force_refresh("new_home_sales")
            response = service.get_new_home_sales_data(force_refresh=force_refresh)
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
            print(f"Error getting New Home Sales data: {e}")
            return None

    def _get_pending_home_sales(self, service) -> Optional[dict]:
        """中古住宅販売保留（前月比・前年比）データを取得"""
        try:
            force_refresh = self._should_force_refresh("pending_home_sales")
            response = service.get_pending_home_sales_data(force_refresh=force_refresh)
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
            print(f"Error getting Pending Home Sales data: {e}")
            return None

    def _get_existing_home_sales(self, service) -> Optional[dict]:
        """中古住宅販売戸数データを取得"""
        try:
            force_refresh = self._should_force_refresh("existing_home_sales")
            response = service.get_existing_home_sales_data(force_refresh=force_refresh)
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
            print(f"Error getting Existing Home Sales data: {e}")
            return None

    def _get_nahb_hmi(self, service) -> Optional[dict]:
        """NAHB住宅市場指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("nahb_hmi")
            response = service.get_nahb_hmi_data(force_refresh=force_refresh)
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
            print(f"Error getting NAHB HMI data: {e}")
            return None

    def _get_housing_starts_permits(self, service) -> Optional[dict]:
        """住宅着工件数・建設許可件数データを取得"""
        try:
            force_refresh = self._should_force_refresh("housing_starts_permits")
            response = service.get_housing_starts_permits_data(force_refresh=force_refresh)
            housing_starts = response.get("housing_starts", {})
            building_permits = response.get("building_permits", {})
            if not housing_starts.get("data") and not building_permits.get("data"):
                return None
            return {
                "housing_starts": housing_starts,
                "building_permits": building_permits,
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting Housing Starts/Permits data: {e}")
            return None

    def _get_rental_vacancy_rate(self, service) -> Optional[dict]:
        """賃貸空室率データを取得"""
        try:
            force_refresh = self._should_force_refresh("rental_vacancy_rate")
            response = service.get_rental_vacancy_rate_data(force_refresh=force_refresh)
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
            print(f"Error getting Rental Vacancy Rate data: {e}")
            return None
