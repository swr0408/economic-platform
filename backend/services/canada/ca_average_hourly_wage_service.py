"""
カナダ平均時給サービス

指標:
- Average hourly wages（平均時給）
- 前年比（YoY）、前月比（MoM）

データソース:
- Statistics Canada Table 14-10-0065-01
- Employee wages, by occupation and industry, monthly, unadjusted for seasonality

発表スケジュール:
- 毎月発表（雇用統計と同時）
- 発表時刻: 08:30 ET
"""
import json
import zipfile
import io
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd

from core.redis_client import redis_client
from services.canada.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")
TORONTO = ZoneInfo("America/Toronto")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "canada" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ca_average_hourly_wage_cache.json"

# Statistics Canada CSV URL
# Table 14-10-0065-01: Employee wages by occupation and industry
STATCAN_WAGE_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/14100065-eng.zip"

# FMPイベントパターン
FMP_WAGE_PATTERN = "Average Hourly Wages YoY"
CA_WAGE_ECONALPHA_ID = "ca_average_hourly_wage"


class CaAverageHourlyWageService:
    """カナダ平均時給サービス"""

    DATA_CACHE_KEY = "canada:ca_average_hourly_wage:data"
    CACHE_TTL = 86400  # 24時間

    def __init__(self):
        pass

    def get_ca_average_hourly_wage_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダ平均時給データを取得"""
        # 次回発表日を取得
        next_release = get_next_release_by_pattern(FMP_WAGE_PATTERN, country="CA")

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # データソースから取得
        result = self._load_from_source()
        if result:
            # 最新値を取得
            latest = result[-1] if result else None

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Statistics Canada",
                    "table": "14-10-0065-01",
                    "indicator": "Average hourly wages",
                    "description": "カナダ平均時給（前年比・前月比）",
                    "unit": "%",
                    "frequency": "monthly",
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=self.CACHE_TTL)
            self._save_file_cache(cache_payload)

            return {
                "data": result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_source(self) -> List[Dict[str, Any]]:
        """Statistics Canadaから平均時給データを取得"""
        try:
            # 時給データを取得
            wage_data = self._fetch_wage_data()

            if not wage_data:
                return []

            # 前年比・前月比を計算
            result = []
            sorted_dates = sorted(wage_data.keys())

            for i, date_str in enumerate(sorted_dates):
                current_value = wage_data[date_str]

                item = {
                    "date": date_str,
                    "value": current_value,
                    "yoy": None,
                    "mom": None,
                }

                # 前年比を計算
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                prev_year_date = f"{dt.year - 1:04d}-{dt.month:02d}-01"
                if prev_year_date in wage_data:
                    prev_value = wage_data[prev_year_date]
                    if prev_value > 0:
                        yoy = ((current_value - prev_value) / prev_value) * 100
                        item["yoy"] = round(yoy, 2)

                # 前月比を計算
                if i > 0:
                    prev_date = sorted_dates[i - 1]
                    prev_value = wage_data[prev_date]
                    if prev_value > 0:
                        mom = ((current_value - prev_value) / prev_value) * 100
                        item["mom"] = round(mom, 2)

                result.append(item)

            print(f"[CaWage] Loaded {len(result)} monthly records")
            if result:
                print(f"[CaWage] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CaWage] Latest: {latest['date']} - ${latest['value']}, YoY: {latest['yoy']}%, MoM: {latest['mom']}%")

            return result

        except Exception as e:
            print(f"[CaWage] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_wage_data(self) -> Dict[str, float]:
        """
        平均時給データを取得
        Table 14-10-0065-01

        フィルター条件:
        - GEO: Canada
        - Job permanency: Permanent employees
        - Union coverage: Total employees, covered and not covered by union
        - Gender: Total - Gender
        - Age group: 15 years and over
        - Wages: Average hourly wage rate
        """
        try:
            print(f"[CaWage] Fetching data from: {STATCAN_WAGE_URL}")

            resp = requests.get(STATCAN_WAGE_URL, timeout=120)
            resp.raise_for_status()

            z = zipfile.ZipFile(io.BytesIO(resp.content))
            csv_name = [n for n in z.namelist() if n.endswith('.csv') and not n.startswith('_')][0]

            with z.open(csv_name) as f:
                df = pd.read_csv(f, low_memory=False)

            print(f"[CaWage] Loaded CSV with {len(df)} rows")

            # フィルタリング
            # Permanent employees（恒久雇用）のデータを使用
            # これがInvesting.comなどで報告されるAverage Hourly Wages YoYと一致
            filter_mask = (
                (df['GEO'] == 'Canada') &
                (df['Job permanency'] == 'Permanent employees') &
                (df['Union coverage'] == 'Total employees, covered and not covered by union') &
                (df['Gender'] == 'Total - Gender') &
                (df['Age group'] == '15 years and over') &
                (df['Wages'] == 'Average hourly wage rate')
            )

            canada_data = df[filter_mask].copy()

            print(f"[CaWage] Filtered to {len(canada_data)} rows for Permanent employees")

            if len(canada_data) == 0:
                print("[CaWage] No data found with specified filters")
                return {}

            result: Dict[str, float] = {}

            for _, row in canada_data.iterrows():
                date_str = row['REF_DATE']
                value = row['VALUE']

                if pd.isna(value):
                    continue

                try:
                    formatted_date = f"{date_str}-01"
                    result[formatted_date] = round(float(value), 2)
                except (ValueError, TypeError):
                    continue

            print(f"[CaWage] Loaded {len(result)} wage records")

            return result

        except Exception as e:
            print(f"[CaWage] Error fetching data: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日ベース）"""
        return should_refresh_by_pattern(
            FMP_WAGE_PATTERN,
            last_updated_str,
            country="CA"
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CaWage] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaWage] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Average hourly wages",
            "source": "Statistics Canada",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(FMP_WAGE_PATTERN, country="CA"),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ca_average_hourly_wage_service = CaAverageHourlyWageService()
