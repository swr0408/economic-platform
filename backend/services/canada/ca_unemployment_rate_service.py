"""
カナダ失業率サービス

指標:
- Unemployment rate（失業率）

データソース:
- Statistics Canada Table 14-10-0287-03
- Labour force characteristics, monthly, seasonally adjusted

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
DATA_CACHE_FILE = CACHE_DIR / "ca_unemployment_rate_cache.json"

# Statistics Canada CSV URL
# Table 14-10-0287-03: Labour force characteristics (rates)
STATCAN_UNEMPLOYMENT_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/14100287-eng.zip"

# FMPイベントパターン
FMP_UNEMPLOYMENT_PATTERN = "Unemployment Rate"
CA_UNEMPLOYMENT_ECONALPHA_ID = "ca_unemployment_rate"


class CaUnemploymentRateService:
    """カナダ失業率サービス"""

    DATA_CACHE_KEY = "canada:ca_unemployment_rate:data"
    CACHE_TTL = 86400  # 24時間

    def __init__(self):
        pass

    def get_ca_unemployment_rate_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダ失業率データを取得"""
        # 次回発表日を取得
        next_release = get_next_release_by_pattern(FMP_UNEMPLOYMENT_PATTERN, country="CA")

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
                    "table": "14-10-0287-01",
                    "indicator": "Unemployment rate",
                    "description": "カナダ失業率（%）",
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
        """Statistics Canadaから失業率データを取得"""
        try:
            # 失業率データを取得
            unemployment_data = self._fetch_unemployment_data()

            if not unemployment_data:
                return []

            # 結果をリスト形式に変換
            result = []
            for date_str in sorted(unemployment_data.keys()):
                item = {
                    "date": date_str,
                    "value": unemployment_data[date_str],
                }
                result.append(item)

            print(f"[CaUnemploymentRate] Loaded {len(result)} monthly records")
            if result:
                print(f"[CaUnemploymentRate] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CaUnemploymentRate] Latest: {latest['date']} - {latest['value']}%")

            return result

        except Exception as e:
            print(f"[CaUnemploymentRate] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_unemployment_data(self) -> Dict[str, float]:
        """
        失業率データを取得
        Table 14-10-0287-01
        """
        try:
            print(f"[CaUnemploymentRate] Fetching data from: {STATCAN_UNEMPLOYMENT_URL}")

            resp = requests.get(STATCAN_UNEMPLOYMENT_URL, timeout=120)
            resp.raise_for_status()

            z = zipfile.ZipFile(io.BytesIO(resp.content))
            csv_name = [n for n in z.namelist() if n.endswith('.csv') and not n.startswith('_')][0]

            with z.open(csv_name) as f:
                df = pd.read_csv(f, low_memory=False)

            print(f"[CaUnemploymentRate] Loaded CSV with {len(df)} rows")

            # カナダ全体、15歳以上、両性、季節調整済み、推定値のデータを抽出
            gender_col = 'Gender' if 'Gender' in df.columns else 'Sex'
            gender_value = 'Total - Gender' if gender_col == 'Gender' else 'Both sexes'

            # フィルター条件を構築
            filter_mask = (
                (df['GEO'] == 'Canada') &
                (df[gender_col] == gender_value) &
                (df['Age group'] == '15 years and over')
            )

            # Statistics列がある場合はEstimateのみ
            if 'Statistics' in df.columns:
                filter_mask = filter_mask & (df['Statistics'] == 'Estimate')

            # Data type列がある場合はSeasonally adjustedのみ
            if 'Data type' in df.columns:
                filter_mask = filter_mask & (df['Data type'] == 'Seasonally adjusted')

            canada_data = df[filter_mask].copy()

            print(f"[CaUnemploymentRate] Filtered to {len(canada_data)} rows for Canada, {gender_value}, 15+, SA, Estimate")

            # 雇用統計の種類を確認
            if 'Labour force characteristics' in df.columns:
                char_col = 'Labour force characteristics'
            else:
                # 列名が異なる場合のフォールバック
                char_col = [c for c in df.columns if 'characteristics' in c.lower() or 'statistic' in c.lower()]
                if char_col:
                    char_col = char_col[0]
                else:
                    print(f"[CaUnemploymentRate] Could not find characteristics column")
                    return {}

            print(f"[CaUnemploymentRate] Using characteristics column: {char_col}")
            print(f"[CaUnemploymentRate] Available characteristics: {canada_data[char_col].unique()[:20]}")

            result: Dict[str, float] = {}

            # Unemployment rate（失業率）
            unemployment_df = canada_data[canada_data[char_col] == 'Unemployment rate'].copy()
            for _, row in unemployment_df.iterrows():
                date_str = row['REF_DATE']
                value = row['VALUE']

                if pd.isna(value):
                    continue

                try:
                    formatted_date = f"{date_str}-01"
                    result[formatted_date] = round(float(value), 1)
                except (ValueError, TypeError):
                    continue

            print(f"[CaUnemploymentRate] Loaded {len(result)} Unemployment rate records")

            return result

        except Exception as e:
            print(f"[CaUnemploymentRate] Error fetching data: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日ベース）"""
        return should_refresh_by_pattern(
            FMP_UNEMPLOYMENT_PATTERN,
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
            print(f"[CaUnemploymentRate] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaUnemploymentRate] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Unemployment rate",
            "source": "Statistics Canada",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(FMP_UNEMPLOYMENT_PATTERN, country="CA"),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ca_unemployment_rate_service = CaUnemploymentRateService()
