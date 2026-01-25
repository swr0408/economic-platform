"""
輸入物価指数/輸出物価指数サービス
FREDから輸入物価指数（IR）と輸出物価指数（IQ）データを取得

指標:
- IR: 輸入物価指数（Import Price Index）- 全輸入品
- IQ: 輸出物価指数（Export Price Index）- 全輸出品

データソース:
- FRED: IR, IQ

発表スケジュール:
- 毎月中旬頃 8:30 ET（米国東部時間）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
IMPORT_EXPORT_PRICE_CACHE_FILE = CACHE_DIR / "import_export_price_cache.json"

# FRED シリーズID
FRED_IMPORT_PRICE_SERIES = "IR"   # 輸入物価指数
FRED_EXPORT_PRICE_SERIES = "IQ"   # 輸出物価指数


class ImportExportPriceService:
    """輸入物価指数/輸出物価指数サービス - FRED版"""

    CACHE_KEY = "inflation:import_export_price:data"
    # FMPイベントマッピング用ID
    # indicator_event_mappingテーブルのeconalpha_id
    ECONALPHA_ID = "import_price_index"

    FRED_BASE_URL = "https://api.stlouisfed.org/fred"

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_import_export_price_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        輸入物価指数/輸出物価指数データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "import_yoy": float, "export_yoy": float}, ...],
                "latest": {...},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # FREDから取得
        fred_result = self._fetch_from_fred()
        if fred_result:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            latest = fred_result[-1] if fred_result else None
            cache_payload = {
                "data": fred_result,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": fred_result,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "FRED",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_fred(self) -> List[Dict[str, Any]]:
        """FREDから輸入物価指数と輸出物価指数データを取得し、YoYを計算してマージ"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            # 輸入物価指数を取得
            import_data = self._fetch_single_series(FRED_IMPORT_PRICE_SERIES)
            # 輸出物価指数を取得
            export_data = self._fetch_single_series(FRED_EXPORT_PRICE_SERIES)

            if not import_data and not export_data:
                return []

            # データをマージ
            result = self._merge_data(import_data, export_data)

            print(f"Fetched {len(result)} import/export price records from FRED")
            return result

        except Exception as e:
            print(f"Error fetching import/export price from FRED: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_single_series(self, series_id: str) -> Dict[str, float]:
        """単一のFREDシリーズを取得し、YoYを計算して日付→YoYのマップを返す"""
        try:
            print(f"Fetching FRED series: {series_id}...")

            url = f"{self.FRED_BASE_URL}/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": "2000-01-01",
                "sort_order": "asc"
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            # 有効なデータのみ抽出
            raw_data = {}
            for obs in data.get("observations", []):
                if obs.get("value") and obs["value"] != ".":
                    try:
                        raw_data[obs["date"]] = float(obs["value"])
                    except (ValueError, TypeError):
                        continue

            if not raw_data:
                return {}

            # YoY（前年比）を計算
            yoy_data = {}
            for date_str, current_value in raw_data.items():
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    # 12ヶ月前の日付
                    prev_year_date = f"{dt.year - 1:04d}-{dt.month:02d}-01"

                    if prev_year_date in raw_data:
                        prev_value = raw_data[prev_year_date]
                        if prev_value > 0:
                            yoy = round(((current_value - prev_value) / prev_value) * 100, 2)
                            yoy_data[date_str] = yoy
                except (ValueError, TypeError):
                    continue

            print(f"Calculated {len(yoy_data)} YoY records for {series_id}")
            return yoy_data

        except Exception as e:
            print(f"Error fetching FRED series {series_id}: {e}")
            return {}

    def _merge_data(
        self,
        import_data: Dict[str, float],
        export_data: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """輸入と輸出のYoYデータをマージ"""
        # 全日付を収集
        all_dates = set(import_data.keys()) | set(export_data.keys())

        result = []
        for date_str in sorted(all_dates):
            import_yoy = import_data.get(date_str)
            export_yoy = export_data.get(date_str)

            # 少なくとも一方のデータがある場合のみ追加
            if import_yoy is not None or export_yoy is not None:
                result.append({
                    "date": date_str,
                    "import_yoy": import_yoy,
                    "export_yoy": export_yoy,
                })

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not IMPORT_EXPORT_PRICE_CACHE_FILE.exists():
                return None

            with open(IMPORT_EXPORT_PRICE_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(IMPORT_EXPORT_PRICE_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {IMPORT_EXPORT_PRICE_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        exists = redis_client.exists(self.CACHE_KEY)
        cached_data = redis_client.get(self.CACHE_KEY) if exists else None

        return {
            "indicator": "Import/Export Price Index",
            "source": "FRED (IR, IQ)",
            "cache_key": self.CACHE_KEY,
            "exists": exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": IMPORT_EXPORT_PRICE_CACHE_FILE.exists()
        }


# シングルトンインスタンス
import_export_price_service = ImportExportPriceService()
