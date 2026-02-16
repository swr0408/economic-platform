"""
スイス消費者ダッシュボードローダー
KOF経済バロメーター、SECO消費者景況感などを一括取得

キャッシュ更新判定: FMP発表日時ベース判定
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class SwitzerlandConsumerLoader(BaseDashboardLoader):
    """
    スイス消費者ダッシュボード用データローダー

    取得データ:
    - kof_economic_barometer: KOF経済バロメーター（先行指標）
    - ch_consumer_sentiment: SECO消費者景況感

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "switzerland"
    CATEGORY_CODE = "consumer"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "kof_economic_barometer",
        "ch_consumer_sentiment",
        "ch_retail_trade",
    ]

    def __init__(self):
        super().__init__()
        self._stale_indicators: set = set()

    def get_expected_keys(self) -> List[str]:
        """期待されるデータキーのリストを返す"""
        return self.EXPECTED_KEYS

    def get_release_datetimes(self) -> List[Optional[datetime]]:
        """各指標の発表日時リストを返す"""
        return []

    def _detect_stale_indicators(self, last_updated: Optional[str]) -> set:
        """発表日時を過ぎた指標を検出"""
        stale = set()

        if last_updated is None:
            return stale

        return stale

    def _should_force_refresh(self, indicator: str) -> bool:
        """指標が強制更新対象かどうかを判定"""
        if "all" in self._stale_indicators:
            return True
        return indicator in self._stale_indicators

    def _prepare_for_refresh(self, last_updated: Optional[str]) -> None:
        """データ再取得の前処理"""
        self._stale_indicators = self._detect_stale_indicators(last_updated)
        if self._stale_indicators:
            print(f"[SwitzerlandConsumer] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全消費者データを並列で取得

        Returns:
            {
                "kof_economic_barometer": {...},
                "ch_consumer_sentiment": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.switzerland.kof_economic_barometer_service import kof_economic_barometer_service
        from services.switzerland.ch_consumer_sentiment_service import ch_consumer_sentiment_service
        from services.switzerland.ch_retail_trade_service import ch_retail_trade_service

        result = {
            "kof_economic_barometer": None,
            "ch_consumer_sentiment": None,
            "ch_retail_trade": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self._get_kof_barometer, kof_economic_barometer_service): "kof_economic_barometer",
                executor.submit(self._get_consumer_sentiment, ch_consumer_sentiment_service): "ch_consumer_sentiment",
                executor.submit(self._get_retail_trade, ch_retail_trade_service): "ch_retail_trade",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"[SwitzerlandConsumer] Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_kof_barometer(self, service) -> dict:
        """KOF経済バロメーターデータを取得"""
        try:
            force_refresh = self._should_force_refresh("kof_economic_barometer")
            response = service.get_kof_barometer_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[SwitzerlandConsumer] Error getting KOF Barometer: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_consumer_sentiment(self, service) -> dict:
        """SECO消費者景況感データを取得"""
        try:
            force_refresh = self._should_force_refresh("ch_consumer_sentiment")
            response = service.get_consumer_sentiment_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[SwitzerlandConsumer] Error getting SECO Consumer Sentiment: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_retail_trade(self, service) -> dict:
        """小売売上高データを取得"""
        try:
            force_refresh = self._should_force_refresh("ch_retail_trade")
            response = service.get_ch_retail_trade_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[SwitzerlandConsumer] Error getting Retail Trade: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}
