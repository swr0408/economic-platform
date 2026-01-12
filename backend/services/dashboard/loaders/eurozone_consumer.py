"""
ユーロ圏消費ダッシュボードローダー
小売売上高、消費者信頼感などの消費関連指標を一括取得

キャッシュ更新判定: FMP発表日時ベース方式
- ECB Retail Trade: FMP発表日時ベース更新（"Retail Sales"パターン）
- Eurostat Consumer Confidence: FMP発表日時ベース更新（"Consumer Confidence"パターン）
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class EurozoneConsumerLoader(BaseDashboardLoader):
    """
    ユーロ圏消費ダッシュボード用データローダー

    取得データ:
    - ecb_retail_trade: ECB小売売上高（前月比・前年比）
    - eurostat_consumer_confidence: Eurostat消費者信頼感指数

    キャッシュ方式: FMP発表日時ベース判定
    - ECB Retail Trade: FMP発表日時ベース更新
    - Eurostat Consumer Confidence: FMP発表日時ベース更新
    """

    COUNTRY_CODE = "eurozone"
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
            return {"all"}

        try:
            last_updated_dt = datetime.fromisoformat(last_updated)
            if last_updated_dt.tzinfo is None:
                last_updated_dt = last_updated_dt.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 24時間以上経過していれば更新
            if (now - last_updated_dt) > timedelta(hours=24):
                stale.add("ecb_retail_trade")
                stale.add("eurostat_consumer_confidence")

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
                "ecb_retail_trade": {...},
                "eurostat_consumer_confidence": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.eurozone.ecb_retail_trade_service import ecb_retail_trade_service
        from services.eurozone.eurostat_consumer_confidence_service import eurostat_consumer_confidence_service

        result = {
            "ecb_retail_trade": None,
            "eurostat_consumer_confidence": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self._get_ecb_retail_trade, ecb_retail_trade_service): "ecb_retail_trade",
                executor.submit(self._get_consumer_confidence, eurostat_consumer_confidence_service): "eurostat_consumer_confidence",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_ecb_retail_trade(self, service) -> dict:
        """ECB小売売上高データを取得"""
        try:
            force_refresh = self._should_force_refresh("ecb_retail_trade")
            response = service.get_ecb_retail_trade_data(force_refresh=force_refresh)
            return {
                "retail_yoy": response.get("retail_yoy", []),
                "retail_mom": response.get("retail_mom", []),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ECB Retail Trade: {e}")
            return {"retail_yoy": [], "retail_mom": [], "metadata": {}}

    def _get_consumer_confidence(self, service) -> dict:
        """Eurostat消費者信頼感指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("eurostat_consumer_confidence")
            response = service.get_consumer_confidence_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting Eurostat Consumer Confidence: {e}")
            return {"data": [], "latest": None, "metadata": {}}
