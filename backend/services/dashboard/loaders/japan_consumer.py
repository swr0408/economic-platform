"""
日本消費ダッシュボードローダー
消費支出・小売販売額など消費関連指標を一括取得

キャッシュ更新判定: FMP発表日時ベース方式
- 消費支出: 毎月上旬発表（FMPカレンダーから取得）
- 小売販売額: 毎月下旬発表（FMPカレンダーから取得）
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class JapanConsumerLoader(BaseDashboardLoader):
    """
    日本消費ダッシュボード用データローダー

    取得データ:
    - consumption_expenditure: 実質消費支出（MoM/YoY）
    - retail_sales: 小売業販売額（MoM/YoY）

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "japan"
    CATEGORY_CODE = "consumer"

    def __init__(self):
        super().__init__()
        self._stale_indicators: set = set()

    def get_release_datetimes(self) -> List[Optional[datetime]]:
        """
        各指標の発表日時リストを返す
        """
        release_times = []

        # 消費支出発表日時
        consumption_release = self._get_consumption_release_datetime()
        if consumption_release:
            release_times.append(consumption_release)

        # 小売販売額発表日時
        retail_release = self._get_retail_sales_release_datetime()
        if retail_release:
            release_times.append(retail_release)

        return release_times

    def _get_consumption_release_datetime(self) -> Optional[datetime]:
        """
        次回消費支出発表日時を取得
        """
        try:
            from services.japan.fmp_next_release_utils import get_next_release_from_fmp

            next_release = get_next_release_from_fmp("jp_household_spending_yoy")
            if not next_release:
                return None

            datetime_jst_str = next_release.get("datetime_jst")
            if not datetime_jst_str:
                return None

            return datetime.fromisoformat(datetime_jst_str)

        except Exception as e:
            print(f"Error getting consumption release datetime: {e}")
            return None

    def _get_retail_sales_release_datetime(self) -> Optional[datetime]:
        """
        次回小売販売額発表日時を取得
        """
        try:
            from services.japan.fmp_next_release_utils import get_next_release_from_fmp

            next_release = get_next_release_from_fmp("jp_retail_sales_yoy")
            if not next_release:
                return None

            datetime_jst_str = next_release.get("datetime_jst")
            if not datetime_jst_str:
                return None

            return datetime.fromisoformat(datetime_jst_str)

        except Exception as e:
            print(f"Error getting retail sales release datetime: {e}")
            return None

    def _detect_stale_indicators(self, last_updated: Optional[str]) -> set:
        """
        発表日時を過ぎた指標を検出
        """
        stale = set()

        if last_updated is None:
            return {"all"}

        try:
            last_updated_dt = datetime.fromisoformat(last_updated)
            if last_updated_dt.tzinfo is None:
                last_updated_dt = last_updated_dt.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 消費支出発表
            consumption_release = self._get_consumption_release_datetime()
            if consumption_release and last_updated_dt < consumption_release <= now:
                stale.add("consumption_expenditure")
                print(f"[stale] Consumption release detected: {consumption_release.isoformat()}")

            # 小売販売額発表
            retail_release = self._get_retail_sales_release_datetime()
            if retail_release and last_updated_dt < retail_release <= now:
                stale.add("retail_sales")
                print(f"[stale] Retail sales release detected: {retail_release.isoformat()}")

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
        """
        self._stale_indicators = self._detect_stale_indicators(last_updated)
        if self._stale_indicators:
            print(f"Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全消費データを並列で取得

        Returns:
            {
                "consumption_expenditure": {...},
                "retail_sales": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.japan.consumption_expenditure_service import consumption_expenditure_service
        from services.japan.retail_sales_service import retail_sales_service

        result = {
            "consumption_expenditure": None,
            "retail_sales": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self._get_consumption_expenditure, consumption_expenditure_service): "consumption_expenditure",
                executor.submit(self._get_retail_sales, retail_sales_service): "retail_sales",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_consumption_expenditure(self, service) -> dict:
        """実質消費支出データを取得"""
        try:
            force_refresh = self._should_force_refresh("consumption_expenditure")
            response = service.get_consumption_expenditure_data(force_refresh=force_refresh)
            return {
                "mom": response.get("mom"),
                "yoy": response.get("yoy"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting consumption expenditure: {e}")
            return {"mom": None, "yoy": None, "next_release": None}

    def _get_retail_sales(self, service) -> dict:
        """小売業販売額データを取得"""
        try:
            force_refresh = self._should_force_refresh("retail_sales")
            response = service.get_retail_sales_data(force_refresh=force_refresh)
            return {
                "mom": response.get("mom"),
                "yoy": response.get("yoy"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting retail sales: {e}")
            return {"mom": None, "yoy": None, "next_release": None}
