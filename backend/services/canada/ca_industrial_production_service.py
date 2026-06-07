"""
カナダ鉱工業生産サービス

指標:
- 鉱工業生産（前月比: MoM）
- 鉱工業生産（前年比: YoY）

データソース:
- Statistics Canada Table 36-10-0434-01
- Industrial production [T010]（季節調整済み年率、Chained 2017 dollars）

発表スケジュール:
- 月次（GDP by industry と同時発表）
- 発表時刻: 08:30 ET

注意:
- SAAR版（v65201219）を採用（ノイズが少なく、StatCanのDaily解説と整合）
- Trading Economicsとは値が異なる場合あり（TEはTrading-day adjusted版を使用している可能性）
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
from services.canada.statcan_utils import fetch_statcan_csv


JST = ZoneInfo("Asia/Tokyo")
TORONTO = ZoneInfo("America/Toronto")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "canada" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ca_industrial_production_cache.json"

# Statistics Canada CSV URL
# Table 36-10-0434-01: GDP by industry (monthly)
STATCAN_GDP_MONTHLY_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/36100434-eng.zip"

# FMPイベントパターン（GDP monthly と同時発表）
FMP_GDP_MONTHLY_PATTERN = "Gross Domestic Product MoM"
CA_INDUSTRIAL_PRODUCTION_ECONALPHA_ID = "ca_gdp_monthly"  # GDPと同じマッピングを使用


class CaIndustrialProductionService:
    """カナダ鉱工業生産サービス"""

    DATA_CACHE_KEY = "canada:ca_industrial_production:data"
    CACHE_TTL = 86400  # 24時間

    def __init__(self):
        pass

    def get_ca_industrial_production_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダ鉱工業生産データを取得"""
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
            next_release = get_next_release_by_pattern(FMP_GDP_MONTHLY_PATTERN, country="CA")

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Statistics Canada",
                    "table": "36-10-0434-01",
                    "indicator": "Industrial production [T010]",
                    "description": "カナダ鉱工業生産（季節調整済み年率）",
                    "unit": "%",
                    "frequency": "monthly",
                    "note": "SAAR版を採用。Trading Economicsとは定義・調整方法の違いにより値が異なる場合があります。",
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
        """Statistics Canadaから鉱工業生産データを取得"""
        try:
            print(f"[CaIndustrialProduction] Fetching data from: {STATCAN_GDP_MONTHLY_URL}")

            df = fetch_statcan_csv(STATCAN_GDP_MONTHLY_URL)

            print(f"[CaIndustrialProduction] Columns: {df.columns.tolist()}")

            # Industrial production [T010]、季節調整済み年率、Chained (2017) dollarsのデータをフィルタ
            ip_data = df[
                (df['North American Industry Classification System (NAICS)'] == 'Industrial production [T010]') &
                (df['Seasonal adjustment'] == 'Seasonally adjusted at annual rates') &
                (df['Prices'] == 'Chained (2017) dollars')
            ].copy()

            print(f"[CaIndustrialProduction] Found {len(ip_data)} industrial production records")

            # 日付と値を辞書に格納
            ip_values = {}
            for _, row in ip_data.iterrows():
                date_str = row['REF_DATE']  # 形式: "2024-01" (YYYY-MM)
                value = row['VALUE']

                if pd.isna(value):
                    continue

                try:
                    # 月形式を日付に変換 (例: "2024-01" -> "2024-01-01")
                    formatted_date = self._month_to_date(date_str)
                    if formatted_date:
                        ip_values[formatted_date] = float(value)
                except (ValueError, TypeError):
                    continue

            print(f"[CaIndustrialProduction] Parsed {len(ip_values)} IP values")

            # MoMとYoYを計算
            result = self._calculate_growth_rates(ip_values)

            print(f"[CaIndustrialProduction] Loaded {len(result)} monthly records")
            if result:
                print(f"[CaIndustrialProduction] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CaIndustrialProduction] Latest: {latest['date']} MoM={latest.get('mom')}% YoY={latest.get('yoy')}%")

            return result

        except Exception as e:
            print(f"[CaIndustrialProduction] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _month_to_date(self, month_str: str) -> Optional[str]:
        """月形式を日付に変換（例: "2024-01" -> "2024-01-01"）"""
        try:
            month_str = month_str.strip()
            # 形式: "2024-01" -> "2024-01-01"
            if len(month_str) == 7 and '-' in month_str:
                return f"{month_str}-01"
            return None
        except Exception:
            return None

    def _calculate_growth_rates(self, ip_values: Dict[str, float]) -> List[Dict[str, Any]]:
        """MoM（前月比）とYoY（前年比）を計算

        Args:
            ip_values: 日付 -> Industrial production絶対値（Chained 2017 dollars, millions）
        """
        # 日付でソート
        sorted_dates = sorted(ip_values.keys())
        result = []

        for i, date_str in enumerate(sorted_dates):
            current_value = ip_values[date_str]
            item = {
                "date": date_str,
                "value": round(current_value, 2),
            }

            # MoM（前月比）を計算
            if i > 0:
                prev_date = sorted_dates[i - 1]
                prev_value = ip_values[prev_date]
                if prev_value > 0:
                    mom = ((current_value - prev_value) / prev_value) * 100
                    item["mom"] = round(mom, 2)

            # YoY（前年比）を計算
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            prev_year_date = f"{dt.year - 1}-{dt.month:02d}-01"
            if prev_year_date in ip_values:
                prev_year_value = ip_values[prev_year_date]
                if prev_year_value > 0:
                    yoy = ((current_value - prev_year_value) / prev_year_value) * 100
                    item["yoy"] = round(yoy, 2)

            # MoMまたはYoYがある場合のみ追加
            if "mom" in item or "yoy" in item:
                result.append(item)

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            return should_refresh_by_pattern(FMP_GDP_MONTHLY_PATTERN, last_updated_str, country="CA")
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
            print(f"[CaIndustrialProduction] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaIndustrialProduction] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Canada Industrial Production",
            "source": "Statistics Canada",
            "table": "36-10-0434-01",
            "series": "Industrial production [T010]",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(FMP_GDP_MONTHLY_PATTERN, country="CA"),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ca_industrial_production_service = CaIndustrialProductionService()
