"""
日本価格ダッシュボードローダー
CPI（全国・東京）などインフレ関連指標を一括取得

キャッシュ更新判定: FMP発表日時ベース方式
- 全国CPI: 毎月18日〜21日頃 08:30 JST
- 東京CPI: 毎月24日〜28日頃 08:30 JST
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class JapanPriceLoader(BaseDashboardLoader):
    """
    日本価格ダッシュボード用データローダー

    取得データ:
    - national_cpi: 全国消費者物価指数（YoY/MoM、Core、Core-Core含む）
    - tokyo_cpi: 東京都区部消費者物価指数（YoY/MoM、Core、Core-Core含む）

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "japan"
    CATEGORY_CODE = "price"

    def __init__(self):
        super().__init__()
        self._stale_indicators: set = set()

    def get_release_datetimes(self) -> List[Optional[datetime]]:
        """
        各指標の発表日時リストを返す
        """
        release_times = []

        # 全国CPI発表日時
        national_release = self._get_national_cpi_release_datetime()
        if national_release:
            release_times.append(national_release)

        # 東京CPI発表日時
        tokyo_release = self._get_tokyo_cpi_release_datetime()
        if tokyo_release:
            release_times.append(tokyo_release)

        return release_times

    def _get_national_cpi_release_datetime(self) -> Optional[datetime]:
        """
        次回全国CPI発表日時を取得
        """
        try:
            from services.japan.fmp_next_release_utils import get_next_release_from_fmp

            next_release = get_next_release_from_fmp("jp_national_cpi")
            if not next_release:
                return None

            datetime_jst_str = next_release.get("datetime_jst")
            if not datetime_jst_str:
                return None

            return datetime.fromisoformat(datetime_jst_str)

        except Exception as e:
            print(f"Error getting national CPI release datetime: {e}")
            return None

    def _get_tokyo_cpi_release_datetime(self) -> Optional[datetime]:
        """
        次回東京CPI発表日時を取得
        """
        try:
            from services.japan.fmp_next_release_utils import get_next_release_from_fmp

            next_release = get_next_release_from_fmp("jp_tokyo_cpi")
            if not next_release:
                return None

            datetime_jst_str = next_release.get("datetime_jst")
            if not datetime_jst_str:
                return None

            return datetime.fromisoformat(datetime_jst_str)

        except Exception as e:
            print(f"Error getting Tokyo CPI release datetime: {e}")
            return None

    def _detect_stale_indicators(self, last_updated: Optional[str]) -> set:
        """
        発表日時を過ぎた指標を検出
        """
        stale = set()

        if last_updated is None:
            return set()

        try:
            last_updated_dt = datetime.fromisoformat(last_updated)
            if last_updated_dt.tzinfo is None:
                last_updated_dt = last_updated_dt.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 全国CPI発表
            national_release = self._get_national_cpi_release_datetime()
            if national_release and last_updated_dt < national_release <= now:
                stale.add("national_cpi")
                print(f"[stale] National CPI release detected: {national_release.isoformat()}")

            # 東京CPI発表
            tokyo_release = self._get_tokyo_cpi_release_datetime()
            if tokyo_release and last_updated_dt < tokyo_release <= now:
                stale.add("tokyo_cpi")
                print(f"[stale] Tokyo CPI release detected: {tokyo_release.isoformat()}")

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
        全価格データを並列で取得

        Returns:
            {
                "national_cpi": {...},
                "tokyo_cpi": {...},
                "terms_of_trade": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.japan.japan_national_cpi_service import japan_national_cpi_service
        from services.japan.japan_tokyo_cpi_service import japan_tokyo_cpi_service
        from services.japan.japan_terms_of_trade_service import japan_terms_of_trade_service

        result = {
            "national_cpi": None,
            "tokyo_cpi": None,
            "terms_of_trade": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self._get_national_cpi, japan_national_cpi_service): "national_cpi",
                executor.submit(self._get_tokyo_cpi, japan_tokyo_cpi_service): "tokyo_cpi",
                executor.submit(self._get_terms_of_trade, japan_terms_of_trade_service): "terms_of_trade",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_national_cpi(self, service) -> dict:
        """全国CPIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("national_cpi")
            response = service.get_national_cpi_data(force_refresh=force_refresh)
            data = response.get("data", [])
            latest = response.get("latest") or (data[-1] if data else None)

            return {
                "data": data,
                "latest": latest,
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting national CPI: {e}")
            import traceback
            traceback.print_exc()
            return {"data": [], "latest": None, "next_release": None}

    def _get_tokyo_cpi(self, service) -> dict:
        """東京CPIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("tokyo_cpi")
            response = service.get_tokyo_cpi_data(force_refresh=force_refresh)
            data = response.get("data", [])
            latest = response.get("latest") or (data[-1] if data else None)

            return {
                "data": data,
                "latest": latest,
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting Tokyo CPI: {e}")
            import traceback
            traceback.print_exc()
            return {"data": [], "latest": None, "next_release": None}

    def _get_terms_of_trade(self, service) -> dict:
        """交易条件データを取得"""
        try:
            force_refresh = self._should_force_refresh("terms_of_trade")
            response = service.get_data(force_refresh=force_refresh)
            data = response.get("data", [])
            latest = response.get("latest") or (data[-1] if data else None)

            return {
                "data": data,
                "latest": latest,
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting Terms of Trade: {e}")
            import traceback
            traceback.print_exc()
            return {"data": [], "latest": None, "next_release": None}
