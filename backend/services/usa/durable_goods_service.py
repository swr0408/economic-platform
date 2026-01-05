"""
耐久財受注（Durable Goods Orders）サービス
FRED APIからDGORDER, ADXTNOデータを取得

シリーズID:
- DGORDER: Manufacturers' New Orders: Durable Goods (Millions of Dollars)
- ADXTNO: Manufacturers' New Orders: Durable Goods Excluding Transportation (Millions of Dollars)

発表スケジュール:
- Census.gov M3サーベイ Advance Report
- 毎月下旬 8:30 AM ET

キャッシュ方式: FMP発表日時ベース判定方式

リファクタリング: fred_utils.BaseMultiSeriesService を使用
"""
from typing import Dict, List, Any
from pathlib import Path

from services.usa.fred_utils import BaseMultiSeriesService


# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "economy"


class DurableGoodsService(BaseMultiSeriesService):
    """耐久財受注（Durable Goods Orders）サービス"""

    # 必須設定
    SERIES_CONFIG = {
        "value": "DGORDER",        # 耐久財新規受注
        "ex_transport": "ADXTNO"   # 耐久財新規受注（輸送除外）
    }
    REDIS_KEY = "fred:series:durable_goods"
    ECONALPHA_ID = "durable_goods_mom"
    CACHE_FILE = CACHE_DIR / "durable_goods_cache.json"
    INDICATOR_NAME = "Durable Goods Orders"

    # オプション設定
    PRIMARY_SERIES = "value"
    VALUE_ROUND_DIGITS = 2

    def _process_merged_data(
        self,
        merged_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """変化率を計算（前月比・前年比）"""
        for i, item in enumerate(merged_data):
            item["mom"] = None
            item["yoy"] = None
            item["ex_transport_mom"] = None
            item["ex_transport_yoy"] = None

            # 前月比
            if i >= 1:
                prev = merged_data[i - 1]
                # 総合
                if item.get("value") and prev.get("value") and prev["value"] != 0:
                    item["mom"] = round((item["value"] - prev["value"]) / prev["value"] * 100, 2)
                # 輸送除外
                if item.get("ex_transport") and prev.get("ex_transport") and prev["ex_transport"] != 0:
                    item["ex_transport_mom"] = round(
                        (item["ex_transport"] - prev["ex_transport"]) / prev["ex_transport"] * 100, 2
                    )

            # 前年比
            if i >= 12:
                year_ago = merged_data[i - 12]
                # 総合
                if item.get("value") and year_ago.get("value") and year_ago["value"] != 0:
                    item["yoy"] = round((item["value"] - year_ago["value"]) / year_ago["value"] * 100, 2)
                # 輸送除外
                if item.get("ex_transport") and year_ago.get("ex_transport") and year_ago["ex_transport"] != 0:
                    item["ex_transport_yoy"] = round(
                        (item["ex_transport"] - year_ago["ex_transport"]) / year_ago["ex_transport"] * 100, 2
                    )

        return merged_data

    def get_durable_goods_data(self, start_date=None, force_refresh=False):
        """
        耐久財受注データを取得（既存APIとの互換性維持）

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            統一されたAPIレスポンス形式
        """
        return self.get_data(start_date=start_date, force_refresh=force_refresh)


# シングルトンインスタンス
durable_goods_service = DurableGoodsService()
