"""
生産者物価指数（PPI）サービス
FREDからPPI / コアPPIデータを取得

指標:
- PPIFIS: PPI（最終需要）- 季節調整済み
- PPIFES: コアPPI（最終需要、食品・エネルギー除く）- 季節調整済み

データソース:
- FRED: PPIFIS, PPIFES

発表スケジュール:
- 毎月9-17日頃 8:30 ET（米国東部時間）

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
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
PPI_CACHE_FILE = CACHE_DIR / "ppi_cache.json"
CORE_PPI_CACHE_FILE = CACHE_DIR / "core_ppi_cache.json"

# FRED シリーズID
FRED_PPI_SERIES = "PPIFIS"           # PPI（最終需要、季節調整済み）
FRED_CORE_PPI_SERIES = "PPIFES"      # コアPPI（最終需要、食品・エネルギー除く）


class PPIService:
    """生産者物価指数（PPI）サービス - FRED版"""

    PPI_CACHE_KEY = "inflation:ppi:data"
    CORE_PPI_CACHE_KEY = "inflation:core_ppi:data"
    # FMPイベントマッピング用ID
    # indicator_event_mappingテーブルのeconalpha_id: 'ppi'
    # FMPイベントパターン: Producer Price Index MoM, Producer Price Index YoY
    PPI_ECONALPHA_ID = "ppi"

    FRED_BASE_URL = "https://api.stlouisfed.org/fred"

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_ppi_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        PPIデータを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float, "yoy": float|null, "mom": float|null}, ...],
                "latest": {...},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.PPI_CACHE_KEY)
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
        fred_result = self._fetch_ppi_from_fred()
        if fred_result:
            next_release = get_next_release_from_fmp(self.PPI_ECONALPHA_ID)

            latest = fred_result[-1] if fred_result else None
            cache_payload = {
                "data": fred_result,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.PPI_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload, PPI_CACHE_FILE)

            return {
                "data": fred_result,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "FRED",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache(PPI_CACHE_FILE)
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

    def get_core_ppi_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        コアPPI（食品・エネルギー除く）データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float, "yoy": float|null, "mom": float|null}, ...],
                "latest": {...},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CORE_PPI_CACHE_KEY)
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
        fred_result = self._fetch_core_ppi_from_fred()
        if fred_result:
            next_release = get_next_release_from_fmp(self.PPI_ECONALPHA_ID)

            latest = fred_result[-1] if fred_result else None
            cache_payload = {
                "data": fred_result,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.CORE_PPI_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload, CORE_PPI_CACHE_FILE)

            return {
                "data": fred_result,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "FRED",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache(CORE_PPI_CACHE_FILE)
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

    def _fetch_ppi_from_fred(self) -> List[Dict[str, Any]]:
        """FREDからPPI（PPIFIS）データを取得し、YoY/MoMを計算"""
        return self._fetch_and_calculate_changes(FRED_PPI_SERIES)

    def _fetch_core_ppi_from_fred(self) -> List[Dict[str, Any]]:
        """FREDからコアPPI（PPIFES）データを取得し、YoY/MoMを計算"""
        return self._fetch_and_calculate_changes(FRED_CORE_PPI_SERIES)

    def _fetch_and_calculate_changes(self, series_id: str) -> List[Dict[str, Any]]:
        """FREDからデータを取得し、前年比・前月比を計算"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

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
            raw_data = []
            for obs in data.get("observations", []):
                if obs.get("value") and obs["value"] != ".":
                    try:
                        raw_data.append({
                            "date": obs["date"],
                            "index": float(obs["value"])
                        })
                    except (ValueError, TypeError):
                        continue

            if not raw_data:
                return []

            # 日付でソート
            raw_data.sort(key=lambda x: x["date"])

            # 日付→インデックスのマップを作成（正確な月の比較用）
            date_index_map = {item["date"]: item["index"] for item in raw_data}

            # YoY（前年比）とMoM（前月比）を計算
            result = []
            for item in raw_data:
                current_date = item["date"]
                current_index = item["index"]

                # 日付をパース（YYYY-MM-DD形式）
                try:
                    dt = datetime.strptime(current_date, "%Y-%m-%d")
                except ValueError:
                    continue

                yoy = None
                mom = None

                # 前月比（MoM）- 正確に1ヶ月前の日付を計算
                prev_month_year = dt.year if dt.month > 1 else dt.year - 1
                prev_month_month = dt.month - 1 if dt.month > 1 else 12
                prev_month_date = f"{prev_month_year:04d}-{prev_month_month:02d}-01"

                if prev_month_date in date_index_map:
                    prev_index = date_index_map[prev_month_date]
                    if prev_index > 0:
                        mom = round(((current_index - prev_index) / prev_index) * 100, 2)

                # 前年比（YoY）- 正確に12ヶ月前の日付を計算
                prev_year_date = f"{dt.year - 1:04d}-{dt.month:02d}-01"

                if prev_year_date in date_index_map:
                    prev_index = date_index_map[prev_year_date]
                    if prev_index > 0:
                        yoy = round(((current_index - prev_index) / prev_index) * 100, 2)

                # YoYがある場合のみ結果に追加（2001年以降）
                if yoy is not None:
                    result.append({
                        "date": current_date,
                        "value": yoy,  # メイン値はYoY
                        "yoy": yoy,
                        "mom": mom,
                        "index": round(current_index, 2),
                    })

            print(f"Fetched {len(result)} records from FRED ({series_id})")
            return result

        except Exception as e:
            print(f"Error fetching from FRED ({series_id}): {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_fmp_schedule(self.PPI_ECONALPHA_ID, last_updated_str)

    def _load_file_cache(self, cache_file: Path) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not cache_file.exists():
                return None

            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any], cache_file: Path) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {cache_file}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        ppi_deleted = redis_client.delete(self.PPI_CACHE_KEY)
        core_ppi_deleted = redis_client.delete(self.CORE_PPI_CACHE_KEY)
        return ppi_deleted or core_ppi_deleted

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        ppi_exists = redis_client.exists(self.PPI_CACHE_KEY)
        core_ppi_exists = redis_client.exists(self.CORE_PPI_CACHE_KEY)
        ppi_data = redis_client.get(self.PPI_CACHE_KEY) if ppi_exists else None
        core_ppi_data = redis_client.get(self.CORE_PPI_CACHE_KEY) if core_ppi_exists else None

        return {
            "ppi": {
                "indicator": "PPI (Producer Price Index)",
                "source": "FRED (PPIFIS)",
                "cache_key": self.PPI_CACHE_KEY,
                "exists": ppi_exists,
                "last_updated": ppi_data.get("last_updated") if ppi_data else None,
                "data_count": len(ppi_data.get("data", [])) if ppi_data else 0,
                "latest": ppi_data.get("latest") if ppi_data else None,
                "next_release": get_next_release_from_fmp(self.PPI_ECONALPHA_ID),
                "file_cache_exists": PPI_CACHE_FILE.exists()
            },
            "core_ppi": {
                "indicator": "Core PPI",
                "source": "FRED (PPIFES)",
                "cache_key": self.CORE_PPI_CACHE_KEY,
                "exists": core_ppi_exists,
                "last_updated": core_ppi_data.get("last_updated") if core_ppi_data else None,
                "data_count": len(core_ppi_data.get("data", [])) if core_ppi_data else 0,
                "latest": core_ppi_data.get("latest") if core_ppi_data else None,
                "next_release": get_next_release_from_fmp(self.PPI_ECONALPHA_ID),
                "file_cache_exists": CORE_PPI_CACHE_FILE.exists()
            }
        }


# シングルトンインスタンス
ppi_service = PPIService()
