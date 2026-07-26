"""
オーストラリア 経常収支対GDP比サービス
ABS経常収支 / ABS名目GDP で比率を算出

指標:
- 経常収支対GDP比（Current Account to GDP Ratio）

データソース:
- ABS 5302.0 Table 4: Current Account (Series A3535187L), Seasonally Adjusted, $ Millions
- ABS 5206.0 Table 1: Nominal GDP (Series A2302467A), Current Prices, $ Millions

計算:
- Ratio (%) = (Current Account $ M / Nominal GDP $ M) × 100

発表スケジュール:
- 四半期（GDP発表時に更新）

キャッシュ方式: FMP GDP発表日ベース判定
"""
import io
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd
import requests

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "australia" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "au_current_account_gdp_ratio_cache.json"

# ABS TSSearchServlet
ABS_TS_SEARCH_URL = "https://www.abs.gov.au/servlet/TSSearchServlet"

# Series IDs
CA_SERIES_ID = "A3535187L"   # Current Account, SA, $ Millions (5302.0 Table 4)
GDP_SERIES_ID = "A2302467A"  # GDP at current prices, SA, $ Millions (5206.0 Table 1)

# FMPイベントパターン（GDP発表時に更新）
FMP_EVENT_PATTERN = "GDP Growth Rate QoQ"
FMP_COUNTRY = "AU"


class AUCurrentAccountGdpRatioService:
    """オーストラリア経常収支対GDP比サービス"""

    DATA_CACHE_KEY = "australia:au_current_account_gdp_ratio:data"

    def __init__(self):
        pass

    def get_au_current_account_gdp_ratio_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """経常収支対GDP比データを取得"""
        next_release = self._get_next_release()

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
            latest = result[-1] if result else None
            from services.usa.fmp_next_release_utils import guarded_last_updated
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
            )

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Australian Bureau of Statistics",
                    "indicator": "Current Account to GDP Ratio",
                    "description": "オーストラリア経常収支対GDP比",
                    "unit": "%",
                    "frequency": "quarterly",
                    "ca_source": "ABS 5302.0 Table 4 (A3535187L, $ Millions)",
                    "gdp_source": "ABS 5206.0 Table 1 (A2302467A, Current Prices, $ Millions)",
                },
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "api",
                "last_updated": last_updated,
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
        """ABS経常収支 + ABS名目GDPから対GDP比を計算"""
        try:
            # 1. 経常収支データを取得（$ Millions）
            print("[AU CA/GDP] Fetching current account from ABS")
            ca_data = self._fetch_series_data(CA_SERIES_ID)
            print(f"[AU CA/GDP] Current account: {len(ca_data)} quarters")

            # 2. 名目GDPデータを取得（$ Millions）
            print("[AU CA/GDP] Fetching nominal GDP from ABS")
            gdp_data = self._fetch_series_data(GDP_SERIES_ID)
            print(f"[AU CA/GDP] Nominal GDP: {len(gdp_data)} quarters")

            # 3. 比率を計算
            result = []
            for date_str in sorted(ca_data.keys()):
                if date_str in gdp_data:
                    ca_value = ca_data[date_str]    # $ Millions
                    gdp_value = gdp_data[date_str]  # $ Millions
                    if gdp_value > 0:
                        ratio = (ca_value / gdp_value) * 100
                        result.append({
                            "date": date_str,
                            "value": round(ratio, 2),
                            "current_account": round(ca_value / 1000, 3),  # B AUD
                            "gdp": round(gdp_value / 1000, 3),            # B AUD
                        })

            print(f"[AU CA/GDP] Calculated {len(result)} quarterly records")
            if result:
                print(f"[AU CA/GDP] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[AU CA/GDP] Latest: {latest['date']} Ratio={latest['value']}% CA={latest['current_account']}B GDP={latest['gdp']}B")

            return result

        except Exception as e:
            print(f"[AU CA/GDP] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_series_data(self, series_id: str) -> Dict[str, float]:
        """ABS TSSearchServlet → Excel から系列データを取得

        Returns:
            Dict[date_str, value_m]: 日付→値($ Millions)のマッピング
        """
        # 1. TSSearchServletでExcel URLを取得
        resp = requests.get(
            ABS_TS_SEARCH_URL,
            params={"sid": series_id},
            timeout=30,
        )
        resp.raise_for_status()

        root = ET.fromstring(resp.text)
        table_url = None
        for series in root.findall(".//Series"):
            url_elem = series.find("TableURL")
            if url_elem is not None and url_elem.text:
                table_url = url_elem.text.strip()
                break

        if not table_url:
            raise ValueError(f"TableURL not found for series {series_id}")

        # 2. Excel ダウンロード＆パース
        resp2 = requests.get(table_url, timeout=60)
        resp2.raise_for_status()

        df = pd.read_excel(io.BytesIO(resp2.content), sheet_name="Data1", header=None)

        # Row 9 = Series ID行, 系列の列を特定
        target_col = None
        for col in range(1, df.shape[1]):
            cell = df.iloc[9, col]
            if pd.notna(cell) and str(cell).strip() == series_id:
                target_col = col
                break

        if target_col is None:
            raise ValueError(f"Series {series_id} not found in Excel row 9")

        # Row 10以降 = データ行
        data: Dict[str, float] = {}
        for row in range(10, df.shape[0]):
            date_val = df.iloc[row, 0]
            value_val = df.iloc[row, target_col]

            if pd.isna(date_val) or pd.isna(value_val):
                continue

            try:
                if isinstance(date_val, datetime):
                    date_str = date_val.strftime("%Y-%m-%d")
                else:
                    date_str = pd.Timestamp(str(date_val)).strftime("%Y-%m-%d")

                data[date_str] = float(value_val)
            except (ValueError, TypeError):
                continue

        return data

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得"""
        try:
            from services.australia.fmp_next_release_utils import get_next_release_by_pattern
            return get_next_release_by_pattern(FMP_EVENT_PATTERN, country=FMP_COUNTRY)
        except Exception as e:
            print(f"[AU CA/GDP] Error getting next release: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            from services.australia.fmp_next_release_utils import should_refresh_by_pattern
            return should_refresh_by_pattern(FMP_EVENT_PATTERN, last_updated_str, country=FMP_COUNTRY)
        except Exception:
            try:
                last_updated = datetime.fromisoformat(last_updated_str)
                if last_updated.tzinfo is None:
                    last_updated = last_updated.replace(tzinfo=JST)
                now = datetime.now(JST)
                age = now - last_updated
                return age.total_seconds() > 86400 * 7
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
            print(f"[AU CA/GDP] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[AU CA/GDP] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "AU Current Account to GDP Ratio",
            "source": "ABS",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
au_current_account_gdp_ratio_service = AUCurrentAccountGdpRatioService()
