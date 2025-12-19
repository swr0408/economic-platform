"""
BEA GDP項目別成長率サービス
BEA NIPA テーブル（T10101）からGDP項目別成長率を取得

項目:
- GDP（実質GDP成長率）
- PCE（個人消費）
- GPDI（民間投資）
- Exports（輸出）
- Imports（輸入）
- Government（政府支出）

キャッシュ方式: last_updated判定（TTLなし）
更新タイミング: BEA発表スケジュールに基づいて自動更新
"""
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo

import requests

from core.redis_client import redis_client

# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# BEA API設定
BEA_API_BASE = "https://apps.bea.gov/api/data/"


class BEAGDPComponentsService:
    """BEA GDP項目別成長率サービス"""

    CACHE_KEY = "bea:gdp_components_growth"

    def __init__(self):
        self.api_key = os.environ.get("BEA_API_KEY", "")

    def _quarter_to_date_str(self, q: str) -> str:
        """'2024Q1' -> '2024-01-01' のように四半期表記を月初の日付に変換"""
        try:
            year = int(q[:4])
            qi = int(q[-1])
            month = {1: 1, 2: 4, 3: 7, 4: 10}[qi]
            return f"{year:04d}-{month:02d}-01"
        except Exception:
            return q

    def _date_to_quarter(self, date_str: str) -> str:
        """'2024-01-01' -> '2024Q1' のように日付を四半期表記に変換"""
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            year = date.year
            quarter = (date.month - 1) // 3 + 1
            return f"{year}Q{quarter}"
        except Exception:
            return date_str

    def fetch_gdp_components_growth(
        self,
        start_year: int = 2010,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        GDP項目別成長率を取得

        Args:
            start_year: 開始年
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [
                    {
                        "date": "YYYY-MM-DD",
                        "quarter": "2024Q1",
                        "pce": float,
                        "gpdi": float,
                        "exports": float,
                        "imports": float,
                        "government": float,
                        "gdp": float
                    },
                    ...
                ],
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # キャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CACHE_KEY)
            if cached_data:
                return {
                    "data": cached_data.get("data", []),
                    "cached": True,
                    "source": "redis",
                    "last_updated": cached_data.get("last_updated")
                }

        # 外部APIから取得
        api_data = self._fetch_from_bea(start_year)

        if api_data:
            cache_payload = {
                "data": api_data,
                "last_updated": datetime.now(JST).isoformat()
            }
            # TTLなし（last_updated判定方式）
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)

            return {
                "data": api_data,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        return {
            "data": [],
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_bea(self, start_year: int) -> Optional[List[Dict[str, Any]]]:
        """BEA NIPA APIからGDP項目別成長率を取得"""
        try:
            if not self.api_key:
                print("BEA_API_KEY not set")
                return None

            current_year = datetime.now().year
            year_range = ",".join(str(year) for year in range(start_year, current_year + 2))

            print(f"Fetching GDP components growth from BEA (T10101)...")

            # まずT10101（Percent change）を試行
            data_rows = self._fetch_table("T10101", "Q", year_range)

            # 取れない場合はT10105（連鎖数量指数）からフォールバック
            computed_from_levels = False
            if not data_rows:
                print("T10101 failed, trying T10105 fallback...")
                data_rows = self._fetch_table("T10105", "Q", year_range)
                computed_from_levels = True if data_rows else False

            if not data_rows:
                print("No data available from BEA")
                return None

            # データをマッピング・整形
            return self._process_data(data_rows, start_year, computed_from_levels)

        except Exception as e:
            print(f"Error fetching GDP components growth from BEA: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_table(self, table: str, frequency: str, year_range: str) -> Optional[List[Dict]]:
        """BEA NIPA テーブルを取得"""
        try:
            params = {
                "UserID": self.api_key,
                "method": "GetData",
                "datasetname": "NIPA",
                "TableName": table,
                "Frequency": frequency,
                "Year": year_range,
                "ResultFormat": "JSON"
            }

            response = requests.get(BEA_API_BASE, params=params, timeout=60)
            response.raise_for_status()
            raw = response.json()

            api = raw.get("BEAAPI") if isinstance(raw, dict) else None
            if api and "Error" in api:
                err = api.get("Error", {})
                msg = err.get("ErrorDetail") or err.get("ErrorCode") or "BEA error"
                print(f"BEA API error: {msg}")
                return None

            data_rows = (api or {}).get("Results", {}).get("Data") if api else None
            return data_rows

        except Exception as e:
            print(f"Error fetching BEA table {table}: {e}")
            return None

    def _map_line(self, desc: str) -> Optional[str]:
        """LineDescriptionをキーにマッピング"""
        d = (desc or "").strip().lower()
        if not d:
            return None
        if "gross domestic product" in d:
            return "gdp"
        if "personal consumption expenditures" in d:
            return "pce"
        if "gross private domestic investment" in d:
            return "gpdi"
        if d.startswith("exports") or "exports of goods and services" in d:
            return "exports"
        if d.startswith("imports") or "imports of goods and services" in d:
            return "imports"
        if "government consumption expenditures and gross investment" in d:
            return "government"
        return None

    def _process_data(
        self,
        data_rows: List[Dict],
        start_year: int,
        computed_from_levels: bool
    ) -> List[Dict[str, Any]]:
        """BEAデータを整形"""
        # TimePeriodごとに値を集計
        temp: Dict[str, Dict[str, float]] = {}

        for row in data_rows:
            line = row.get("LineDescription") or row.get("SeriesDescription") or ""
            key = self._map_line(line)
            if not key:
                continue

            tp = row.get("TimePeriod")
            # 開始年でフィルタ
            try:
                year_int = int(str(tp)[:4])
                if year_int < start_year:
                    continue
            except Exception:
                pass

            val = row.get("DataValue")
            if val in (None, "", ".", "NaN", "(NA)"):
                continue

            try:
                num = float(str(val).replace(",", ""))
            except Exception:
                continue

            if tp not in temp:
                temp[tp] = {}
            temp[tp][key] = num

        # シリーズ配列を構築
        points: List[Dict[str, Any]] = []
        sorted_keys = sorted(temp.keys())

        for idx, tp in enumerate(sorted_keys):
            row_data = temp[tp]
            date = self._quarter_to_date_str(tp)
            quarter = self._date_to_quarter(date)

            if computed_from_levels and idx > 0:
                # T10105から前期比％を計算
                prev = temp[sorted_keys[idx - 1]]

                def pct(cur_key: str) -> Optional[float]:
                    if cur_key not in row_data or cur_key not in prev:
                        return None
                    prev_v = prev[cur_key]
                    if prev_v == 0:
                        return None
                    return round(((row_data[cur_key] / prev_v) - 1.0) * 100.0, 2)

                point = {
                    "date": date,
                    "quarter": quarter,
                    "pce": pct("pce"),
                    "gpdi": pct("gpdi"),
                    "exports": pct("exports"),
                    "imports": pct("imports"),
                    "government": pct("government"),
                    "gdp": pct("gdp")
                }
                points.append(point)
            else:
                # 既に％のテーブル
                point = {
                    "date": date,
                    "quarter": quarter,
                    "pce": round(row_data.get("pce"), 2) if row_data.get("pce") is not None else None,
                    "gpdi": round(row_data.get("gpdi"), 2) if row_data.get("gpdi") is not None else None,
                    "exports": round(row_data.get("exports"), 2) if row_data.get("exports") is not None else None,
                    "imports": round(row_data.get("imports"), 2) if row_data.get("imports") is not None else None,
                    "government": round(row_data.get("government"), 2) if row_data.get("government") is not None else None,
                    "gdp": round(row_data.get("gdp"), 2) if row_data.get("gdp") is not None else None
                }
                points.append(point)

        print(f"Processed {len(points)} quarters of GDP components growth data")
        return points

    def get_gdp_components_growth(self, force_refresh: bool = False) -> Dict[str, Any]:
        """GDP項目別成長率データを取得（エイリアス）"""
        return self.fetch_gdp_components_growth(force_refresh=force_refresh)

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cache_exists = redis_client.exists(self.CACHE_KEY)
        ttl = redis_client.ttl(self.CACHE_KEY) if cache_exists else -1

        cached_data = redis_client.get(self.CACHE_KEY) if cache_exists else None

        return {
            "cache_key": self.CACHE_KEY,
            "exists": cache_exists,
            "ttl_seconds": ttl,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "record_count": len(cached_data.get("data", [])) if cached_data else 0
        }

    def get_latest_values(self) -> Optional[Dict[str, Any]]:
        """最新のGDP項目別成長率を取得"""
        result = self.get_gdp_components_growth()
        data = result.get("data", [])
        return data[-1] if data else None


# シングルトンインスタンス
bea_gdp_components_service = BEAGDPComponentsService()
