"""
UK消費ダッシュボードローダー
小売売上高などの消費関連指標を一括取得

キャッシュ更新判定: FMP発表日時ベース方式
- ONS Retail Sales: FMP発表日時ベース更新（"Retail Sales"パターン）
- BRC Retail Sales: FMP発表日時ベース更新（"BRC Retail Sales Monitor"パターン）
- GfK Consumer Confidence: FMP発表日時ベース更新（"Consumer Confidence"パターン）
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class UKConsumerLoader(BaseDashboardLoader):
    """
    UK消費ダッシュボード用データローダー

    取得データ:
    - ons_retail_sales: ONS小売売上高（前月比・前年比）
    - brc_retail_sales: BRC小売売上高（前年比）
    - gfk_consumer_confidence: GfK消費者信頼感指数

    キャッシュ方式: FMP発表日時ベース判定
    - ONS Retail Sales: FMP発表日時ベース更新
    - BRC Retail Sales: FMP発表日時ベース更新
    - GfK Consumer Confidence: FMP発表日時ベース更新
    """

    COUNTRY_CODE = "uk"
    CATEGORY_CODE = "consumer"

    def __init__(self):
        super().__init__()
        self._stale_indicators: set = set()

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
            return set()

        try:
            last_updated_dt = datetime.fromisoformat(last_updated)
            if last_updated_dt.tzinfo is None:
                last_updated_dt = last_updated_dt.replace(tzinfo=JST)

            now = datetime.now(JST)

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
        全消費データを並列で取得

        Returns:
            {
                "ons_retail_sales": {...},
                "brc_retail_sales": {...},
                "gfk_consumer_confidence": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.uk.ons_retail_sales_service import ons_retail_sales_service
        from services.uk.brc_retail_sales_service import brc_retail_sales_service
        from services.uk.gfk_consumer_confidence_service import gfk_consumer_confidence_service

        result = {
            "ons_retail_sales": None,
            "brc_retail_sales": None,
            "gfk_consumer_confidence": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self._get_ons_retail_sales, ons_retail_sales_service): "ons_retail_sales",
                executor.submit(self._get_brc_retail_sales, brc_retail_sales_service): "brc_retail_sales",
                executor.submit(self._get_gfk_consumer_confidence, gfk_consumer_confidence_service): "gfk_consumer_confidence",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_ons_retail_sales(self, service) -> dict:
        """ONS小売売上高データを取得"""
        try:
            force_refresh = self._should_force_refresh("ons_retail_sales")
            response = service.get_ons_retail_sales_data(force_refresh=force_refresh)
            return {
                "mom": response.get("mom", []),
                "yoy": response.get("yoy", []),
                "core_mom": response.get("core_mom", []),
                "core_yoy": response.get("core_yoy", []),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ONS Retail Sales: {e}")
            return {"mom": [], "yoy": [], "core_mom": [], "core_yoy": []}

    def _get_brc_retail_sales(self, service) -> dict:
        """BRC小売売上高データを取得"""
        try:
            force_refresh = self._should_force_refresh("brc_retail_sales")
            response = service.get_brc_retail_sales_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting BRC Retail Sales: {e}")
            return {"data": [], "latest": None, "next_release": None}

    def _get_gfk_consumer_confidence(self, service) -> dict:
        """GfK消費者信頼感指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("gfk_consumer_confidence")
            response = service.get_gfk_consumer_confidence_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting GfK Consumer Confidence: {e}")
            return {"data": [], "latest": None, "next_release": None}
