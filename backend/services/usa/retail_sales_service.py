"""
小売売上高（Advance Monthly Retail Trade Report）サービス
FRED APIから小売売上高データを取得

シリーズID:
- RSAFS: Advance Retail Sales: Retail and Food Services（総合）
- RSFSXMV: Advance Retail Sales: Retail (Excluding Motor Vehicle and Parts)（自動車除く）

コントロールグループは別サービス（retail_control_service）で取得

発表スケジュール:
- Census.gov Advance Monthly Retail Trade Report
- 毎月中旬 8:30 AM ET

キャッシュ方式: FMP発表日時ベース判定方式

リファクタリング: fred_utils.BaseMultiSeriesService を使用
"""
from typing import Dict, List, Any
from pathlib import Path

from services.usa.fred_utils import BaseMultiSeriesService


# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "consumer"


class RetailSalesService(BaseMultiSeriesService):
    """小売売上高（Advance Monthly Retail Trade Report）サービス"""

    # 必須設定
    SERIES_CONFIG = {
        "value": "RSAFS",        # 小売売上高（全体、SA、百万ドル）
        "ex_auto": "RSFSXMV"     # 小売売上高（自動車除く）
    }
    REDIS_KEY = "fred:series:retail_sales"
    ECONALPHA_ID = "retail_sales_mom"
    CACHE_FILE = CACHE_DIR / "retail_sales_cache.json"
    INDICATOR_NAME = "Retail Sales"

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
            item["ex_auto_mom"] = None
            item["ex_auto_yoy"] = None

            # 前月比
            if i >= 1:
                prev = merged_data[i - 1]
                # 総合
                if item.get("value") and prev.get("value") and prev["value"] != 0:
                    item["mom"] = round((item["value"] - prev["value"]) / prev["value"] * 100, 2)
                # 自動車除く
                if item.get("ex_auto") and prev.get("ex_auto") and prev["ex_auto"] != 0:
                    item["ex_auto_mom"] = round(
                        (item["ex_auto"] - prev["ex_auto"]) / prev["ex_auto"] * 100, 2
                    )

            # 前年比
            if i >= 12:
                year_ago = merged_data[i - 12]
                # 総合
                if item.get("value") and year_ago.get("value") and year_ago["value"] != 0:
                    item["yoy"] = round((item["value"] - year_ago["value"]) / year_ago["value"] * 100, 2)
                # 自動車除く
                if item.get("ex_auto") and year_ago.get("ex_auto") and year_ago["ex_auto"] != 0:
                    item["ex_auto_yoy"] = round(
                        (item["ex_auto"] - year_ago["ex_auto"]) / year_ago["ex_auto"] * 100, 2
                    )

        return merged_data

    def get_retail_sales_data(self, start_date=None, force_refresh=False):
        """
        小売売上高データを取得（既存APIとの互換性維持）

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            統一されたAPIレスポンス形式
        """
        return self.get_data(start_date=start_date, force_refresh=force_refresh)


# シングルトンインスタンス
retail_sales_service = RetailSalesService()
