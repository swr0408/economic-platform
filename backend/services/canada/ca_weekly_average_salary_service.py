"""
カナダ週間平均給与サービス

指標:
- Average weekly earnings including overtime for all employees（週間平均給与）
- 前年比（YoY）、前月比（MoM）

データソース:
- Statistics Canada Table 14-10-0022-01
- Payroll employment, earnings and hours, by industry group, unadjusted for seasonality

発表スケジュール:
- 毎月発表
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
DATA_CACHE_FILE = CACHE_DIR / "ca_weekly_average_salary_cache.json"

# Statistics Canada CSV URL
# Table 14-10-0222-01: Average weekly earnings by industry, monthly, seasonally adjusted
STATCAN_EARNINGS_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/14100222-eng.zip"

# FMPイベントパターン
FMP_EARNINGS_PATTERN = "Average Weekly Earnings"
CA_EARNINGS_ECONALPHA_ID = "ca_weekly_average_salary"


class CaWeeklyAverageSalaryService:
    """カナダ週間平均給与サービス"""

    DATA_CACHE_KEY = "canada:ca_weekly_average_salary:data"
    CACHE_TTL = 86400  # 24時間

    def __init__(self):
        pass

    def get_ca_weekly_average_salary_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダ週間平均給与データを取得"""
        # 次回発表日を取得
        next_release = get_next_release_by_pattern(FMP_EARNINGS_PATTERN, country="CA")

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
                    "table": "14-10-0222-01",
                    "indicator": "Average weekly earnings including overtime",
                    "description": "カナダ週間平均給与（前年比・前月比）",
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
        """Statistics Canadaから週間平均給与データを取得"""
        try:
            # 給与データを取得
            earnings_data = self._fetch_earnings_data()

            if not earnings_data:
                return []

            # 前年比・前月比を計算
            result = []
            sorted_dates = sorted(earnings_data.keys())

            for i, date_str in enumerate(sorted_dates):
                current_value = earnings_data[date_str]

                item = {
                    "date": date_str,
                    "value": current_value,
                    "yoy": None,
                    "mom": None,
                }

                # 前年比を計算
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                prev_year_date = f"{dt.year - 1:04d}-{dt.month:02d}-01"
                if prev_year_date in earnings_data:
                    prev_value = earnings_data[prev_year_date]
                    if prev_value > 0:
                        yoy = ((current_value - prev_value) / prev_value) * 100
                        item["yoy"] = round(yoy, 2)

                # 前月比を計算
                if i > 0:
                    prev_date = sorted_dates[i - 1]
                    prev_value = earnings_data[prev_date]
                    if prev_value > 0:
                        mom = ((current_value - prev_value) / prev_value) * 100
                        item["mom"] = round(mom, 2)

                result.append(item)

            print(f"[CaWeeklyEarnings] Loaded {len(result)} monthly records")
            if result:
                print(f"[CaWeeklyEarnings] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CaWeeklyEarnings] Latest: {latest['date']} - ${latest['value']}, YoY: {latest['yoy']}%, MoM: {latest['mom']}%")

            return result

        except Exception as e:
            print(f"[CaWeeklyEarnings] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_earnings_data(self) -> Dict[str, float]:
        """
        週間平均給与データを取得
        Table 14-10-0222-01

        フィルター条件:
        - GEO: Canada
        - Estimate: Average weekly earnings including overtime for all employees
        """
        try:
            print(f"[CaWeeklyEarnings] Fetching data from: {STATCAN_EARNINGS_URL}")

            resp = requests.get(STATCAN_EARNINGS_URL, timeout=120)
            resp.raise_for_status()

            z = zipfile.ZipFile(io.BytesIO(resp.content))
            csv_name = [n for n in z.namelist() if n.endswith('.csv') and not n.startswith('_')][0]

            with z.open(csv_name) as f:
                df = pd.read_csv(f, low_memory=False)

            print(f"[CaWeeklyEarnings] Loaded CSV with {len(df)} rows")
            print(f"[CaWeeklyEarnings] Columns: {list(df.columns)}")

            # Estimateカラムを確認
            estimate_col = None
            for col_name in ['Estimate', 'Estimates', 'ESTIMATE']:
                if col_name in df.columns:
                    estimate_col = col_name
                    break

            if estimate_col is None:
                # カラム名を探す
                estimate_candidates = [c for c in df.columns if 'estimate' in c.lower()]
                if estimate_candidates:
                    estimate_col = estimate_candidates[0]
                    print(f"[CaWeeklyEarnings] Using Estimate column: {estimate_col}")
                else:
                    print(f"[CaWeeklyEarnings] No Estimate column found. Available columns: {list(df.columns)}")
                    return {}

            # ユニーク値を確認
            print(f"[CaWeeklyEarnings] Unique {estimate_col} values: {df[estimate_col].unique()[:15]}")

            # フィルタリング
            # Average weekly earnings including overtime for all employees のデータを使用
            filter_mask = (
                (df['GEO'] == 'Canada') &
                (df[estimate_col].str.contains('Average weekly earnings including overtime', case=False, na=False)) &
                (df[estimate_col].str.contains('all employees', case=False, na=False))
            )

            canada_data = df[filter_mask].copy()

            print(f"[CaWeeklyEarnings] Filtered to {len(canada_data)} rows")

            if len(canada_data) == 0:
                # フィルター条件を緩める - Average weekly earnings だけで検索
                print("[CaWeeklyEarnings] Trying alternative filter...")
                filter_mask = (
                    (df['GEO'] == 'Canada') &
                    (df[estimate_col].str.contains('Average weekly earnings', case=False, na=False))
                )
                canada_data = df[filter_mask].copy()
                print(f"[CaWeeklyEarnings] Alternative filter: {len(canada_data)} rows")

                if len(canada_data) > 0:
                    # all employees を優先
                    all_emp_data = canada_data[canada_data[estimate_col].str.contains('all employees', case=False, na=False)]
                    if len(all_emp_data) > 0:
                        canada_data = all_emp_data
                        print(f"[CaWeeklyEarnings] All employees filter: {len(canada_data)} rows")

            if len(canada_data) == 0:
                print("[CaWeeklyEarnings] No data found with specified filters")
                # 全てのEstimate値を出力してデバッグ
                print(f"[CaWeeklyEarnings] All Estimate values: {df[estimate_col].unique()}")
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

            print(f"[CaWeeklyEarnings] Loaded {len(result)} earnings records")

            return result

        except Exception as e:
            print(f"[CaWeeklyEarnings] Error fetching data: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日ベース）"""
        return should_refresh_by_pattern(
            FMP_EARNINGS_PATTERN,
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
            print(f"[CaWeeklyEarnings] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaWeeklyEarnings] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Average weekly earnings",
            "source": "Statistics Canada",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(FMP_EARNINGS_PATTERN, country="CA"),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ca_weekly_average_salary_service = CaWeeklyAverageSalaryService()
