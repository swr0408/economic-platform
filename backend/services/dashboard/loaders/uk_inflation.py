"""
UK物価ダッシュボードローダー
CPI/CPIH/PPI/BRC Shop Price/BOE Inflation Attitudesなどの物価関連指標を一括取得

キャッシュ更新判定: FMP発表日時ベース方式
- ONS CPIH: FMP発表日時ベース更新（"CPI"パターン）
- ONS PPI: FMP発表日時ベース更新（"PPI"パターン）
- BRC Shop Price: FMP発表日時ベース更新（"BRC Shop Price Index YoY"パターン）
- BOE Inflation Attitudes: 四半期毎（90日キャッシュ）
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class UKInflationLoader(BaseDashboardLoader):
    """
    UK物価ダッシュボード用データローダー

    取得データ:
    - ons_cpih: ONS CPI/CPIH（前月比・前年比）
    - ons_ppi: ONS PPI（生産者物価指数：出荷価格・投入価格）
    - brc_shop_price: BRC店頭価格指数（前年比）
    - boe_inflation_attitudes: BOEインフレ期待調査（中央値）

    キャッシュ方式: FMP発表日時ベース判定
    - ONS CPIH: FMP発表日時ベース更新
    - ONS PPI: FMP発表日時ベース更新
    - BRC Shop Price: FMP発表日時ベース更新
    - BOE Inflation Attitudes: 四半期毎（90日キャッシュ）
    """

    COUNTRY_CODE = "uk"
    CATEGORY_CODE = "inflation"

    def __init__(self):
        super().__init__()
        self._stale_indicators: set = set()

    def get_expected_keys(self) -> List[str]:
        """期待されるデータキーのリスト"""
        return [
            "ons_cpih",
            "ons_ppi",
            "brc_shop_price",
            "boe_inflation_attitudes",
        ]


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
            return {"all"}

        return set()

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
        全物価データを並列で取得

        Returns:
            {
                "ons_cpih": {...},
                "ons_ppi": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.uk.ons_cpih_service import ons_cpih_service
        from services.uk.ons_ppi_service import ons_ppi_service
        from services.uk.brc_shop_price_service import brc_shop_price_service
        from services.uk.boe_inflation_attitudes_service import boe_inflation_attitudes_service

        result = {
            "ons_cpih": None,
            "ons_ppi": None,
            "brc_shop_price": None,
            "boe_inflation_attitudes": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self._get_ons_cpih, ons_cpih_service): "ons_cpih",
                executor.submit(self._get_ons_ppi, ons_ppi_service): "ons_ppi",
                executor.submit(self._get_brc_shop_price, brc_shop_price_service): "brc_shop_price",
                executor.submit(self._get_boe_inflation_attitudes, boe_inflation_attitudes_service): "boe_inflation_attitudes",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_ons_cpih(self, service) -> dict:
        """ONS CPI/CPIHデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ons_cpih")
            response = service.get_ons_cpih_data(force_refresh=force_refresh)
            return {
                "series": response.get("series", {}),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ONS CPIH: {e}")
            return {"series": {}, "latest": None, "metadata": {}, "next_release": None}

    def _get_ons_ppi(self, service) -> dict:
        """ONS PPIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ons_ppi")
            response = service.get_ons_ppi_data(force_refresh=force_refresh)
            return {
                "series": response.get("series", {}),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ONS PPI: {e}")
            return {"series": {}, "latest": None, "metadata": {}, "next_release": None}

    def _get_brc_shop_price(self, service) -> dict:
        """BRC店頭価格指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("brc_shop_price")
            response = service.get_brc_shop_price_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting BRC Shop Price: {e}")
            return {"data": [], "latest": None, "next_release": None}

    def _get_boe_inflation_attitudes(self, service) -> dict:
        """BOEインフレ期待調査データを取得"""
        try:
            force_refresh = self._should_force_refresh("boe_inflation_attitudes")
            response = service.get_inflation_attitudes_data(force_refresh=force_refresh)
            return {
                "series": response.get("series", {}),
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting BOE Inflation Attitudes: {e}")
            return {"series": {}, "latest": None, "next_release": None}
