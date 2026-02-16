"""
カナダ住宅着工件数サービス

指標:
- 住宅着工件数（原数値）
- 前年比（YoY）
- 前月比（MoM）

データソース:
- Statistics Canada Table 34-10-0158-01
- Canada Mortgage and Housing Corporation (CMHC)

発表スケジュール:
- 月次（対象月の約2週間後）
- 発表時刻: 08:15 ET
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

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "canada" / "housing"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ca_housing_starts_cache.json"

# Statistics Canada CSV URL
# Table 34-10-0158-01: Canada Mortgage and Housing Corporation, housing starts, under construction and completions
STATCAN_HOUSING_STARTS_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/34100158-eng.zip"

# FMPイベントパターン
FMP_HOUSING_STARTS_PATTERN = "Housing Starts"
CA_HOUSING_STARTS_ECONALPHA_ID = "canada_housing_starts"


class CaHousingStartsService:
    """カナダ住宅着工件数サービス"""

    DATA_CACHE_KEY = "canada:ca_housing_starts:data"
    CACHE_TTL = 86400  # 24時間

    def __init__(self):
        pass

    def get_ca_housing_starts_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダ住宅着工件数データを取得"""
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
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # データソースから取得
        result = self._load_from_source()
        if result:
            # 最新値を取得
            latest = result[-1] if result else None
            next_release = get_next_release_by_pattern(FMP_HOUSING_STARTS_PATTERN, country="CA")

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Statistics Canada",
                    "table": "34-10-0158-01",
                    "indicator": "Housing Starts",
                    "description": "カナダ住宅着工件数",
                    "unit": "千件",
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
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_source(self) -> List[Dict[str, Any]]:
        """Statistics Canadaから住宅着工件数データを取得"""
        try:
            print(f"[CaHousingStarts] Fetching data from: {STATCAN_HOUSING_STARTS_URL}")

            resp = requests.get(STATCAN_HOUSING_STARTS_URL, timeout=30)
            resp.raise_for_status()

            z = zipfile.ZipFile(io.BytesIO(resp.content))
            csv_name = [n for n in z.namelist() if n.endswith('.csv') and not n.startswith('_')][0]

            with z.open(csv_name) as f:
                df = pd.read_csv(f, low_memory=False)

            print(f"[CaHousingStarts] Columns: {df.columns.tolist()}")

            # フィルタリング条件
            # GEO: Canada
            # このテーブル(34-10-0158-01)は住宅着工件数のみを含む（Type of unit等の列なし）

            # カナダ全体のデータをフィルタ
            canada_df = df[df['GEO'] == 'Canada'].copy()

            print(f"[CaHousingStarts] Found {len(canada_df)} records for Canada total housing starts")

            # 原数値を取得
            values = self._extract_values(canada_df)

            print(f"[CaHousingStarts] Extracted {len(values)} monthly values")

            # MoMとYoYを計算
            result = self._calculate_growth_rates(values)

            print(f"[CaHousingStarts] Loaded {len(result)} monthly records")
            if result:
                print(f"[CaHousingStarts] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CaHousingStarts] Latest: {latest['date']} value={latest.get('value')} mom={latest.get('mom')}% yoy={latest.get('yoy')}%")

            return result

        except Exception as e:
            print(f"[CaHousingStarts] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _extract_values(self, df: pd.DataFrame) -> Dict[str, float]:
        """原数値を抽出"""
        values = {}
        for _, row in df.iterrows():
            date_str = row['REF_DATE']  # 形式: "2024-01"
            value = row['VALUE']

            if pd.isna(value):
                continue

            try:
                # 月形式を日付に変換 (例: "2024-01" -> "2024-01-01")
                formatted_date = self._month_to_date(date_str)
                if formatted_date:
                    # 値は年率換算（SAAR）の千単位
                    values[formatted_date] = float(value)
            except (ValueError, TypeError):
                continue

        return values

    def _month_to_date(self, month_str: str) -> Optional[str]:
        """月形式を日付に変換（例: "2024-01" -> "2024-01-01"）"""
        try:
            month_str = month_str.strip()
            if len(month_str) == 7 and '-' in month_str:
                return f"{month_str}-01"
            return None
        except Exception:
            return None

    def _calculate_growth_rates(self, values: Dict[str, float]) -> List[Dict[str, Any]]:
        """MoM（前月比）とYoY（前年比）を計算"""
        sorted_dates = sorted(values.keys())
        result = []

        for i, date_str in enumerate(sorted_dates):
            if date_str not in values:
                continue

            value = values[date_str]

            item = {
                "date": date_str,
                "value": round(value, 1),  # 千単位
            }

            # MoM（前月比）を計算
            if i > 0:
                prev_date = sorted_dates[i - 1]
                if prev_date in values:
                    prev_value = values[prev_date]
                    if prev_value > 0:
                        mom = ((value - prev_value) / prev_value) * 100
                        item["mom"] = round(mom, 2)

            # YoY（前年比）を計算
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            prev_year_date = f"{dt.year - 1}-{dt.month:02d}-01"

            if prev_year_date in values:
                prev_value = values[prev_year_date]
                if prev_value > 0:
                    yoy = ((value - prev_value) / prev_value) * 100
                    item["yoy"] = round(yoy, 2)

            result.append(item)

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            return should_refresh_by_pattern(FMP_HOUSING_STARTS_PATTERN, last_updated_str, country="CA")
        except Exception:
            # FMP判定失敗時は24時間経過でリフレッシュ
            try:
                last_updated = datetime.fromisoformat(last_updated_str)
                if last_updated.tzinfo is None:
                    last_updated = last_updated.replace(tzinfo=JST)
                now = datetime.now(JST)
                age = now - last_updated
                return age.total_seconds() > 86400
            except Exception:
                return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CaHousingStarts] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaHousingStarts] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Canada Housing Starts",
            "source": "Statistics Canada",
            "table": "34-10-0158-01",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(FMP_HOUSING_STARTS_PATTERN, country="CA"),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ca_housing_starts_service = CaHousingStartsService()
