"""
UK住宅ダッシュボードローダー
住宅価格指数などの住宅関連指標を一括取得

キャッシュ更新判定: FMP発表日時ベース方式
- UK House Price: FMP発表日時ベース更新（"House Price Index"パターン）
- RICS House Price: FMP発表日時ベース更新（"RICS House Price Balance"パターン）
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class UKHousingLoader(BaseDashboardLoader):
    """
    UK住宅ダッシュボード用データローダー

    取得データ:
    - uk_house_price: UK住宅価格指数（Land Registry）
    - rics_house_price: RICS住宅価格（FMP/DB）

    キャッシュ方式: FMP発表日時ベース判定
    - UK House Price: FMP発表日時ベース更新
    - RICS House Price: FMP発表日時ベース更新
    """

    COUNTRY_CODE = "uk"
    CATEGORY_CODE = "housing"

    def __init__(self):
        super().__init__()
        self._stale_indicators: set = set()

    def get_expected_keys(self) -> List[str]:
        """期待されるデータキーのリスト"""
        return [
            "uk_house_price",
            "rics_house_price",
        ]

    def get_release_datetimes(self) -> List[Optional[datetime]]:
        """
        各指標の発表日時リストを返す
        """
        return []

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

            # 発表日時ベースの判定のみ
            # 各サービスが自身のキャッシュ判定を行う

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
        全住宅データを並列で取得

        Returns:
            {
                "uk_house_price": {...},
                "rics_house_price": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.uk.uk_house_price_service import uk_house_price_service
        from services.uk.rics_house_price_service import rics_house_price_service

        result = {
            "uk_house_price": None,
            "rics_house_price": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self._get_uk_house_price, uk_house_price_service): "uk_house_price",
                executor.submit(self._get_rics_house_price, rics_house_price_service): "rics_house_price",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_uk_house_price(self, service) -> dict:
        """UK住宅価格指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("uk_house_price")
            response = service.get_house_price_data(force_refresh=force_refresh)
            return {
                "series": response.get("series", {}),
                "series_mom": response.get("series_mom", {}),
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting UK House Price: {e}")
            return {"series": {}, "series_mom": {}, "latest": None, "next_release": None}

    def _get_rics_house_price(self, service) -> dict:
        """RICS住宅価格データを取得"""
        try:
            force_refresh = self._should_force_refresh("rics_house_price")
            response = service.get_rics_house_price_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting RICS House Price: {e}")
            return {"data": [], "latest": None, "next_release": None}
