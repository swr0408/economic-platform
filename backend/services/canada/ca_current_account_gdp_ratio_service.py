"""
カナダ経常収支対GDP比サービス

指標:
- 経常収支対GDP比（Current Account to GDP Ratio）

データソース:
- Statistics Canada Table 36-10-0018-01 (経常収支)
- Statistics Canada Table 36-10-0104-01 (GDP)

発表スケジュール:
- 四半期ごと

注意:
- 経常収支（季節調整済み）/ 名目GDP x 100 で計算
- 単位: %
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
DATA_CACHE_FILE = CACHE_DIR / "ca_current_account_gdp_ratio_cache.json"

# Statistics Canada CSV URLs
# Table 36-10-0018-01: Balance of international payments, current account
STATCAN_CURRENT_ACCOUNT_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/36100018-eng.zip"
# Table 36-10-0104-01: GDP支出ベース（名目GDP用）
STATCAN_GDP_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/36100104-eng.zip"

# FMPイベントパターン（GDPの発表タイミングで更新）
FMP_GDP_PATTERN = "Gross Domestic Product"


class CaCurrentAccountGdpRatioService:
    """カナダ経常収支対GDP比サービス"""

    DATA_CACHE_KEY = "canada:ca_current_account_gdp_ratio:data"
    CACHE_TTL = 86400  # 24時間

    def __init__(self):
        pass

    def get_ca_current_account_gdp_ratio_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダ経常収支対GDP比データを取得"""
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
            # GDPの発表タイミングで更新
            next_release = get_next_release_by_pattern(FMP_GDP_PATTERN, country="CA")

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Statistics Canada",
                    "tables": ["36-10-0018-01", "36-10-0104-01"],
                    "indicator": "Current Account to GDP Ratio",
                    "description": "カナダ経常収支対GDP比",
                    "unit": "%",
                    "frequency": "quarterly",
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
        """Statistics Canadaから経常収支対GDP比データを取得"""
        try:
            # 1. 経常収支データを取得
            print(f"[CaCAGdpRatio] Fetching current account data from: {STATCAN_CURRENT_ACCOUNT_URL}")
            ca_data = self._fetch_current_account()
            print(f"[CaCAGdpRatio] Current account data: {len(ca_data)} quarters")

            # 2. GDPデータを取得（名目GDP）
            print(f"[CaCAGdpRatio] Fetching GDP data from: {STATCAN_GDP_URL}")
            gdp_data = self._fetch_gdp()
            print(f"[CaCAGdpRatio] GDP data: {len(gdp_data)} quarters")

            # 3. 経常収支 / GDP * 100 を計算
            result = []
            for date_str in sorted(ca_data.keys()):
                if date_str in gdp_data:
                    ca_value = ca_data[date_str]
                    gdp_value = gdp_data[date_str]
                    if gdp_value > 0:
                        ratio = (ca_value / gdp_value) * 100
                        result.append({
                            "date": date_str,
                            "value": round(ratio, 2),
                            "current_account": round(ca_value, 2),
                            "gdp": round(gdp_value, 2),
                        })

            print(f"[CaCAGdpRatio] Loaded {len(result)} quarterly records")
            if result:
                print(f"[CaCAGdpRatio] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CaCAGdpRatio] Latest: {latest['date']} Ratio={latest.get('value')}%")

            return result

        except Exception as e:
            print(f"[CaCAGdpRatio] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_current_account(self) -> Dict[str, float]:
        """経常収支データを取得"""
        df = fetch_statcan_csv(STATCAN_CURRENT_ACCOUNT_URL)

        # 経常収支（Total current account）のバランス（季節調整済み）を取得
        filtered_df = df[
            (df['Receipts, payments and balances'] == 'Balances, seasonally adjusted') &
            (df['Current account'] == 'Total current account')
        ].copy()

        ca_data = {}
        for _, row in filtered_df.iterrows():
            date_str = str(row['REF_DATE'])
            value = row['VALUE']
            if pd.isna(value):
                continue
            formatted_date = self._quarter_to_date(date_str)
            if formatted_date:
                ca_data[formatted_date] = float(value)

        return ca_data

    def _fetch_gdp(self) -> Dict[str, float]:
        """名目GDPデータを取得"""
        df = fetch_statcan_csv(STATCAN_GDP_URL)

        # 名目GDP（Current prices）を取得
        # Estimates: 'Gross domestic product at market prices'
        # Prices: 'Current prices'
        filtered_df = df[
            (df['Estimates'].str.contains('Gross domestic product at market prices', na=False)) &
            (df['Prices'] == 'Current prices')
        ].copy()

        print(f"[CaCAGdpRatio] GDP filtered rows: {len(filtered_df)}")

        gdp_data = {}
        for _, row in filtered_df.iterrows():
            date_str = str(row['REF_DATE'])
            value = row['VALUE']
            if pd.isna(value):
                continue
            formatted_date = self._quarter_to_date(date_str)
            if formatted_date:
                gdp_data[formatted_date] = float(value)

        return gdp_data

    def _quarter_to_date(self, date_str: str) -> Optional[str]:
        """四半期形式を日付に変換（例: "2024-01" -> "2024-01-01"）"""
        try:
            date_str = date_str.strip()
            if len(date_str) == 7 and '-' in date_str:
                return f"{date_str}-01"
            return None
        except Exception:
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（GDPの発表タイミングで更新）"""
        try:
            return should_refresh_by_pattern(FMP_GDP_PATTERN, last_updated_str, country="CA")
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
            print(f"[CaCAGdpRatio] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaCAGdpRatio] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Canada Current Account to GDP Ratio",
            "source": "Statistics Canada",
            "tables": ["36-10-0018-01", "36-10-0104-01"],
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(FMP_GDP_PATTERN, country="CA"),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ca_current_account_gdp_ratio_service = CaCurrentAccountGdpRatioService()
