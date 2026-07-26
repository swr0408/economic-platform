"""
中古住宅販売戸数サービス

FREDから中古住宅販売戸数 (EXHOSLUSM495S) を取得
※FREDデータは2024年11月以降のみ提供
※それ以前のデータはFMP DBから補完

指標:
- 中古住宅販売戸数（季節調整済み年率換算、百万戸）

データソース:
- FRED: EXHOSLUSM495S (Existing Home Sales) - 2024年11月以降
- FMP DB: economic_calendar_events - 過去データ
- 原データ: NAR (National Association of Realtors)

発表スケジュール:
- 月次 翌月下旬 10:00 ET

キャッシュ方式: FMP発表日時ベース判定方式
"""
import os
import json
from datetime import datetime, timedelta
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


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "housing"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class ExistingHomeSalesService:
    """中古住宅販売戸数サービス（FRED + FMP DBハイブリッド）"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    SERIES_ID = "EXHOSLUSM495S"
    DATA_CACHE_KEY = "housing:existing_home_sales:data"
    DATA_CACHE_FILE = CACHE_DIR / "existing_home_sales_cache.json"

    # FMPマッピング用ID
    ECONALPHA_ID = "existing_home_sales"

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_existing_home_sales_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        中古住宅販売戸数データを取得

        Args:
            force_refresh: 強制更新フラグ

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float, "mom": float, "yoy": float}, ...],
                "latest": {"date": str, "value": float, "mom": float, "yoy": float},
                "next_release": {"date": str, "datetime_jst": str, "label": str} | None,
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
                        "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
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
                        "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # データ取得（FRED + FMP DBハイブリッド）
        combined_data = self._fetch_combined_data()

        if combined_data:
            latest = combined_data[-1] if combined_data else None
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
            )

            cache_payload = {
                "data": combined_data,
                "latest": latest,
                "last_updated": last_updated
            }

            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": combined_data,
                "latest": latest,
                "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
                "cached": False,
                "source": "api (FRED + FMP DB)",
                "last_updated": last_updated
            }

        # フォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_combined_data(self) -> List[Dict[str, Any]]:
        """FREDとFMP DBからデータを取得して結合"""
        # FMP DBから過去データを取得
        db_data = self._load_from_db()

        # FREDから最新データを取得
        fred_data = self._fetch_from_fred()

        # データを結合（DBデータ優先、FREDで補完）
        combined = {}

        # まずDBデータを追加
        for item in db_data:
            date_key = item["date"][:7]  # YYYY-MM形式
            combined[date_key] = item

        # FREDデータで上書き/追加
        for item in fred_data:
            date_key = item["date"][:7]
            combined[date_key] = item

        # 日付順にソート
        result = sorted(combined.values(), key=lambda x: x["date"])

        # MoM/YoYを再計算（結合後のデータで）
        result = self._calculate_changes(result)

        return result

    def _fetch_from_fred(self) -> List[Dict[str, Any]]:
        """FREDからデータを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print(f"Fetching {self.SERIES_ID} from FRED...")

            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": self.SERIES_ID,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": "2024-01-01",
                "sort_order": "asc"
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            result = []
            for obs in data.get("observations", []):
                if obs.get("value") and obs["value"] != ".":
                    try:
                        # 百万戸単位に変換
                        value = round(float(obs["value"]) / 1000000, 2)
                        result.append({
                            "date": obs["date"],
                            "value": value,
                            "mom": None,
                            "yoy": None
                        })
                    except (ValueError, TypeError):
                        continue

            print(f"Fetched {len(result)} records from FRED ({self.SERIES_ID})")
            return result

        except Exception as e:
            print(f"Error fetching from FRED: {e}")
            return []

    def _load_from_db(self) -> List[Dict[str, Any]]:
        """DBから過去データを取得（CSV_IMPORT + FMP両方）"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text
            import re

            # 月名から月番号へのマッピング
            month_map = {
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }

            with SessionLocal() as session:
                # 販売戸数データを取得
                # - CSV_IMPORT: "Existing Home Sales" (過去データ、datetime_utc = 対象月)
                # - FMP: "Existing Home Sales (XXX)" (最近のデータ、datetime_utc = 発表日時)
                query = text("""
                    SELECT datetime_utc, event, actual, provider
                    FROM economic_calendar_events
                    WHERE country = 'US'
                      AND (
                          event = 'Existing Home Sales'
                          OR (event LIKE 'Existing Home Sales (%'
                              AND event NOT LIKE '%MoM%'
                              AND event NOT LIKE '%YoY%')
                      )
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query).fetchall()

                result = []
                seen_dates = set()

                for row in rows:
                    dt_utc, event, actual, provider = row
                    if not dt_utc:
                        continue

                    # FMPデータはイベント名から対象月を抽出
                    if provider == 'FMP' and '(' in event:
                        # "Existing Home Sales (Nov)" -> Nov -> 11月
                        match = re.search(r'\((\w+)\)', event)
                        if match:
                            month_abbr = match.group(1).lower()
                            if month_abbr in month_map:
                                target_month = month_map[month_abbr]
                                # 発表日時から対象年を推定
                                # 例: 12月に発表されたNov -> 同年の11月
                                # 例: 1月に発表されたDec -> 前年の12月
                                year = dt_utc.year
                                if dt_utc.month == 1 and target_month == 12:
                                    year -= 1
                                date_str = f"{year}-{target_month:02d}-01"
                            else:
                                continue
                        else:
                            continue
                    else:
                        # CSV_IMPORTデータはdatetime_utcが対象月（JSTの月初がUTCでは前月末になる場合があるので+1日で調整）
                        adjusted_dt = dt_utc + timedelta(days=1)
                        date_str = adjusted_dt.strftime("%Y-%m-01")

                    date_key = date_str[:7]  # YYYY-MM
                    if date_key in seen_dates:
                        continue
                    seen_dates.add(date_key)

                    value = float(actual) if actual is not None else None
                    result.append({
                        "date": date_str,
                        "value": value,
                        "mom": None,
                        "yoy": None
                    })

                # 日付順にソート
                result.sort(key=lambda x: x["date"])
                print(f"Loaded {len(result)} existing_home_sales records from DB")
                return result

        except Exception as e:
            print(f"Error loading from DB: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _calculate_changes(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """前月比・前年比を計算"""
        result = []
        for i, item in enumerate(data):
            entry = {
                "date": item["date"],
                "value": item["value"],
                "mom": None,
                "yoy": None
            }

            if item["value"] is not None:
                # 前月比
                if i >= 1 and data[i - 1]["value"] is not None:
                    prev_value = data[i - 1]["value"]
                    if prev_value != 0:
                        entry["mom"] = round(((item["value"] - prev_value) / prev_value) * 100, 2)

                # 前年比
                if i >= 12 and data[i - 12]["value"] is not None:
                    year_ago_value = data[i - 12]["value"]
                    if year_ago_value != 0:
                        entry["yoy"] = round(((item["value"] - year_ago_value) / year_ago_value) * 100, 2)

            result.append(entry)

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュ更新判定（FMP 3分方式）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not self.DATA_CACHE_FILE.exists():
                return None
            with open(self.DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {self.DATA_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Existing Home Sales",
            "source": "FRED + FMP DB (hybrid)",
            "series_id": self.SERIES_ID,
            "cache_method": "FMP発表日時ベース判定",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": self.DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
existing_home_sales_service = ExistingHomeSalesService()
