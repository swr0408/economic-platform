"""
平均時給 / 自発的離職率サービス
FRED APIからCES0500000003 & JTSQURデータを取得

指標:
- CES0500000003: 平均時給（Average Hourly Earnings of All Employees, Total Private）
- JTSQUR: 自発的離職率（Quits Rate: Total Nonfarm）

データソース:
- FRED: https://fred.stlouisfed.org/series/CES0500000003
- FRED: https://fred.stlouisfed.org/series/JTSQUR

発表スケジュール:
- 平均時給: BLS Employment Situation（雇用統計）毎月1〜15日
- 発表時刻: 21:30 (夏) / 22:30 (冬) JST
- 自発的離職率: JOLTS（毎月29日〜翌13日）

キャッシュ方式: FMP発表期間ベース判定方式

リファクタリング: fred_utils.BaseMultiSeriesService を使用
"""
import os
from typing import Dict, List, Any, Optional
from pathlib import Path

import requests

from services.usa.fred_utils import (
    BaseMultiSeriesService,
    FRED_BASE_URL,
    fetch_fred_series,
)


# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "employment"


class AverageHourlyEarningsService(BaseMultiSeriesService):
    """平均時給 / 自発的離職率サービス"""

    # 必須設定（マージ用の論理名）
    SERIES_CONFIG = {
        "level": "CES0500000003",   # 平均時給（水準値）
        "quits_rate": "JTSQUR"      # 自発的離職率
    }
    REDIS_KEY = "fred:average_hourly_earnings:data"
    ECONALPHA_ID = "average_hourly_earnings"
    CACHE_FILE = CACHE_DIR / "average_hourly_earnings_cache.json"
    INDICATOR_NAME = "Average Hourly Earnings / Quits Rate"

    # オプション設定
    PRIMARY_SERIES = "level"
    VALUE_ROUND_DIGITS = 2

    def _fetch_and_process(self, start_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        平均時給データを取得（前年比はFREDのunits=pc1を使用）
        """
        print(f"Fetching {self.INDICATOR_NAME} from FRED...")

        if not self.api_key:
            print("FRED_API_KEY not set")
            return []

        start = start_date or self.DEFAULT_START_DATE

        # 1. 平均時給（水準値）
        level_data = fetch_fred_series(
            "CES0500000003", start, self.api_key, self.VALUE_ROUND_DIGITS
        )
        print(f"  level (CES0500000003): {len(level_data)} records")

        # 2. 平均時給（前年比）- FREDのunits=pc1を使用
        yoy_data = self._fetch_series_with_units("CES0500000003", start, "pc1")
        print(f"  yoy (pc1): {len(yoy_data)} records")

        # 3. 自発的離職率
        quits_data = fetch_fred_series(
            "JTSQUR", start, self.api_key, self.VALUE_ROUND_DIGITS
        )
        print(f"  quits_rate (JTSQUR): {len(quits_data)} records")

        if not level_data:
            return []

        # データをマージ
        result = self._merge_three_series(level_data, yoy_data, quits_data)

        print(f"Fetched {len(result)} {self.INDICATOR_NAME} records")
        return result

    def _fetch_series_with_units(
        self,
        series_id: str,
        start_date: str,
        units: str
    ) -> List[Dict[str, Any]]:
        """FRED APIからシリーズデータを取得（単位変換付き）"""
        try:
            url = f"{FRED_BASE_URL}/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date,
                "sort_order": "asc",
                "units": units
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            observations = data.get("observations", [])

            result = []
            for obs in observations:
                try:
                    value_str = obs.get("value", "")
                    if value_str == "." or not value_str:
                        continue
                    value = float(value_str)
                    result.append({
                        "date": obs["date"],
                        "value": round(value, self.VALUE_ROUND_DIGITS)
                    })
                except (ValueError, KeyError):
                    continue

            return result

        except Exception as e:
            print(f"Error fetching FRED series {series_id} with units {units}: {e}")
            return []

    def _merge_three_series(
        self,
        level_data: List[Dict[str, Any]],
        yoy_data: List[Dict[str, Any]],
        quits_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """3シリーズをマージして前月比を計算"""
        # 各データをマップに変換
        level_map = {item["date"]: item["value"] for item in level_data}
        yoy_map = {item["date"]: item["value"] for item in yoy_data}
        quits_map = {item["date"]: item["value"] for item in quits_data}

        # 水準データから前月比を計算
        mom_map: Dict[str, float] = {}
        sorted_dates = sorted(level_map.keys())
        for i in range(1, len(sorted_dates)):
            prev_date = sorted_dates[i - 1]
            curr_date = sorted_dates[i]
            prev_value = level_map[prev_date]
            curr_value = level_map[curr_date]
            if prev_value and prev_value != 0:
                mom = ((curr_value - prev_value) / prev_value) * 100
                mom_map[curr_date] = round(mom, 2)

        # 全データをマージ（前年比をベースに）
        result = []
        for date in sorted(yoy_map.keys()):
            entry = {
                "date": date,
                "yoy": yoy_map.get(date),
                "mom": mom_map.get(date),
                "quits_rate": quits_map.get(date)
            }
            result.append(entry)

        return result

    def get_average_hourly_earnings_data(self, start_date=None, force_refresh=False):
        """
        平均時給 / 自発的離職率データを取得（既存APIとの互換性維持）

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            統一されたAPIレスポンス形式
        """
        return self.get_data(start_date=start_date, force_refresh=force_refresh)


# シングルトンインスタンス
average_hourly_earnings_service = AverageHourlyEarningsService()
