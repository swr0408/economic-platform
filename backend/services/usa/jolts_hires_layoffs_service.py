"""
JOLTS採用数 / 解雇数サービス
FRED APIからデータを取得

指標:
- JTSHIL: JOLTS採用数（Hires: Total Nonfarm、千人）
- JTSLDL: JOLTS解雇数（Layoffs and Discharges: Total Nonfarm、千人）

データソース:
- FRED: https://fred.stlouisfed.org/series/JTSHIL
- FRED: https://fred.stlouisfed.org/series/JTSLDL

発表スケジュール:
- JOLTS: 毎月上旬（参照月の翌々月初旬）
- 発表期間: 毎月29日〜翌月13日（月跨ぎ）
- 発表時刻: 23:00 (夏) / 0:00 (冬) JST
- jolts_indeed_serviceと同じスケジュール（JOLTS関連指標）

キャッシュ方式: 発表期間ベース判定方式
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
    guarded_last_updated,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# FREDシリーズID
HIRES_SERIES_ID = "JTSHIL"      # JOLTS採用数（千人）
LAYOFFS_SERIES_ID = "JTSLDL"    # JOLTS解雇数（千人）

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "jolts_hires_layoffs_cache.json"

# 系列設定
SERIES_CONFIG = {
    "hires": {
        "series_id": HIRES_SERIES_ID,
        "name": "JOLTS採用数",
        "name_en": "JOLTS Hires",
        "color": "#1890ff"  # 青
    },
    "layoffs": {
        "series_id": LAYOFFS_SERIES_ID,
        "name": "JOLTS解雇数",
        "name_en": "JOLTS Layoffs and Discharges",
        "color": "#ff4d4f"  # 赤
    }
}


class JoltsHiresLayoffsService:
    """JOLTS採用数 / 解雇数サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:jolts_hires_layoffs:data"
    ECONALPHA_ID = "jolts_openings"  # FMPマッピング用ID（JOLTS求人と同じスケジュール）

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_hires_layoffs_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        JOLTS採用数 / 解雇数データを取得

        Returns:
            {
                "data": [{"date": str, "hires": float, "layoffs": float}, ...],
                "latest": {...},
                "series_config": {...},
                "next_release": {"date": str, "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "series_config": SERIES_CONFIG,
                        "next_release": None,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    return {
                        "data": file_cache.get("data", []),
                        "latest": file_cache.get("latest"),
                        "series_config": SERIES_CONFIG,
                        "next_release": None,
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # FRED APIから取得
        api_data = self._fetch_from_api(start_date)

        if api_data:
            latest = api_data[-1] if api_data else None
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
            )

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "latest_data_date": latest["date"] if latest else None,
                "last_updated": last_updated
            }

            # キャッシュに保存
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": api_data,
                "latest": latest,
                "series_config": SERIES_CONFIG,
                "next_release": None,
                "cached": False,
                "source": "api",
                "last_updated": last_updated
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "series_config": SERIES_CONFIG,
                "next_release": None,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "series_config": SERIES_CONFIG,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_api(self, start_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """FRED APIから採用数・解雇数データを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print("Fetching JOLTS Hires/Layoffs from FRED API...")

            start = start_date or "2000-01-01"

            # 採用数を取得
            hires_data = self._fetch_series(HIRES_SERIES_ID, start)
            # 解雇数を取得
            layoffs_data = self._fetch_series(LAYOFFS_SERIES_ID, start)

            if not hires_data and not layoffs_data:
                print("No data fetched from FRED")
                return []

            # 日付でマージ
            merged = self._merge_series(hires_data, layoffs_data)

            print(f"Fetched {len(merged)} JOLTS Hires/Layoffs records")
            return merged

        except Exception as e:
            print(f"Error fetching JOLTS Hires/Layoffs: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_series(self, series_id: str, start_date: str) -> Dict[str, float]:
        """FREDシリーズを取得"""
        try:
            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date,
                "sort_order": "asc"
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            result = {}
            for obs in data.get("observations", []):
                date_str = obs.get("date")
                value = obs.get("value")

                if date_str and value and value != ".":
                    try:
                        result[date_str] = float(value)
                    except (ValueError, TypeError):
                        continue

            print(f"Fetched {len(result)} records for {series_id}")
            return result

        except Exception as e:
            print(f"Error fetching {series_id}: {e}")
            return {}

    def _merge_series(
        self,
        hires_data: Dict[str, float],
        layoffs_data: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """2つのシリーズをマージ"""
        all_dates = sorted(set(hires_data.keys()) | set(layoffs_data.keys()))

        result = []
        for date_str in all_dates:
            hires = hires_data.get(date_str)
            layoffs = layoffs_data.get(date_str)

            # どちらかのデータがあれば追加
            if hires is not None or layoffs is not None:
                result.append({
                    "date": date_str,
                    "hires": hires,
                    "layoffs": layoffs
                })

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP 3分方式）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None

            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "JOLTS Hires / Layoffs",
            "series_ids": [HIRES_SERIES_ID, LAYOFFS_SERIES_ID],
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
jolts_hires_layoffs_service = JoltsHiresLayoffsService()
