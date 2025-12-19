"""
米国金融政策ダッシュボードローダー
政策金利、タームプレミアム、FedWatch、FOMC関連データを一括取得

キャッシュ更新判定: last_updated方式（スケジュール時刻: 6:00 JST）
- 政策金利: FOMC発表後に更新（policy_rate_scheduler）
- タームプレミアム: 毎日6:00 JST更新
- FedWatch: 30分ごと更新（Celery Beat）
- SEP日程: 静的データ（キャッシュ常時使用）
"""
from typing import Dict, Any, Optional
from datetime import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


class USAPolicyLoader(BaseDashboardLoader):
    """
    米国金融政策ダッシュボード用データローダー

    取得データ:
    - policy_rate: 政策金利（FRED DFEDTARU）
    - term_premium: タームプレミアム（NY Fed ACM）
    - kw_term_premium: KWタームプレミアム（FRED THREEFYTP10）
    - sep_dates: SEP発表日リスト
    - fedwatch_screenshot_url: FedWatchスクリーンショットURL

    キャッシュ方式: last_updated判定（スケジュール時刻: 6:00 JST）
    """

    COUNTRY_CODE = "usa"
    CATEGORY_CODE = "policy"

    def get_schedule_time(self) -> Optional[time]:
        """
        スケジュール時刻を返す
        タームプレミアムの更新時刻に合わせて6:00 JST
        """
        return time(6, 0)  # 6:00 JST

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
