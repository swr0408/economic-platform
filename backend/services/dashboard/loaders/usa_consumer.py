"""
米国消費ダッシュボードローダー
小売売上高 + コントロールグループを一括取得

キャッシュ更新判定: 発表日時ベース方式
- 発表日: Census.govから自動取得（next_release）
- 発表時刻: 8:30 ET
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")


class USAConsumerLoader(BaseDashboardLoader):
    """
    米国消費ダッシュボード用データローダー

    取得データ:
    - retail_sales: 小売売上高 - FRED RSAFS, RSFSXMV（毎月中旬 8:30 ET）
    - retail_control: コントロールグループ - Investing.com（毎月中旬 8:30 ET）

    キャッシュ方式: 発表日時ベース判定
    - 小売売上高発表: 毎月中旬 8:30 ET
    """

    COUNTRY_CODE = "usa"
    CATEGORY_CODE = "consumer"

    # 発表時刻設定（ET）
    RETAIL_SALES_RELEASE_HOUR_ET = 8
    RETAIL_SALES_RELEASE_MINUTE_ET = 30

    def get_release_datetimes(self) -> List[Optional[datetime]]:
        """
        各指標の発表日時リストを返す

        Returns:
            - 小売売上高発表日時（8:30 ET）
        """
        release_times = []

        # 小売売上高発表日時
        retail_release = self._get_retail_sales_release_datetime()
        if retail_release:
            release_times.append(retail_release)

        return release_times

    def _get_retail_sales_release_datetime(self) -> Optional[datetime]:
        """
        小売売上高の発表日時を取得

        Returns:
            発表日時（JST）、取得できない場合はNone
        """
        try:
            from services.usa.retail_sales_service import retail_sales_service

            # サービスからnext_releaseを取得（キャッシュから軽量に取得）
            data = retail_sales_service.get_retail_sales_data()
            next_release = data.get("next_release")

            if not next_release:
                return None

            date_str = next_release.get("date")
            if not date_str:
                return None

            # YYYY-MM-DD形式をパース
            try:
                base_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                return None

            # 発表時刻（8:30 ET）をJSTに変換
            release_et = datetime(
                base_date.year, base_date.month, base_date.day,
                self.RETAIL_SALES_RELEASE_HOUR_ET,
                self.RETAIL_SALES_RELEASE_MINUTE_ET,
                tzinfo=ET
            )
            release_jst = release_et.astimezone(JST)

            return release_jst

        except Exception as e:
            print(f"Error getting Retail Sales release datetime: {e}")
            return None

    def load_all(self) -> Dict[str, Any]:
        """
        全消費データを並列で取得

        Returns:
            {
                "retail_sales": {...},
                "retail_control": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.usa.retail_sales_service import retail_sales_service
        from services.usa.retail_control_service import retail_control_service

        result = {
            "retail_sales": None,
            "retail_control": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self._get_retail_sales, retail_sales_service): "retail_sales",
                executor.submit(self._get_retail_control, retail_control_service): "retail_control",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_retail_sales(self, service) -> Optional[dict]:
        """小売売上高データを取得"""
        try:
            response = service.get_retail_sales_data()
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
            print(f"Error getting Retail Sales data: {e}")
            return None

    def _get_retail_control(self, service) -> Optional[dict]:
        """コントロールグループデータを取得"""
        try:
            response = service.get_control_group_data()
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting Retail Control data: {e}")
            return None

    def invalidate_cache(self) -> bool:
        """
        キャッシュを無効化（ダッシュボード + 個別サービス）
        """
        from services.usa.retail_sales_service import retail_sales_service
        from services.usa.retail_control_service import retail_control_service

        # 小売売上高サービスのRedisキャッシュを無効化
        try:
            retail_sales_service.invalidate_cache()
            print("Retail Sales Redis cache invalidated")
        except Exception as e:
            print(f"Error invalidating Retail Sales cache: {e}")

        # コントロールグループサービスのRedisキャッシュを無効化
        try:
            retail_control_service.invalidate_cache()
            print("Retail Control Redis cache invalidated")
        except Exception as e:
            print(f"Error invalidating Retail Control cache: {e}")

        # 親クラスのinvalidate_cacheを呼び出し
        return super().invalidate_cache()
