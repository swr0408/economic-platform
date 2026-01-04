"""
リテールコントロール（コントロールグループ）サービス
Investing.comからコントロールグループの前月比データを取得

データソース:
- https://sbcharts.investing.com/events_charts/us/1506.json
- イベントID: 1506 (Retail Control m/m)

発表スケジュール:
- 毎月中旬 8:30 AM ET（小売売上高と同時発表）

日付変換:
- FREDの小売売上高データ日付と1対1でマッチング
- Investing.comの発表日順（新→旧）とFREDのデータ日付順（新→旧）を位置でマッチ
- 政府閉鎖等で発表がスキップされた場合でも正確に対応

キャッシュ方式: 発表日時ベース判定方式
- retail_sales_serviceから次回発表日を取得して判定
"""
import json
import os
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
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

# FRED API設定
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
FRED_SERIES_URL = "https://api.stlouisfed.org/fred/series/observations"
RSAFS_SERIES_ID = "RSAFS"  # 小売売上高（全体）

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "retail_control_cache.json"

# Investing.com JSONエンドポイント
INVESTING_CONTROL_URL = "https://sbcharts.investing.com/events_charts/us/1506.json"


class RetailControlService:
    """リテールコントロール（コントロールグループ）サービス"""

    CACHE_KEY = "investing:retail_control"
    ECONALPHA_ID = "retail_control"  # FMPマッピング用ID

    def __init__(self):
        """初期化"""
        pass

    def get_control_group_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        コントロールグループの前月比データを取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "mom": float, "forecast": float | null}, ...],
                "latest": {...},
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

        # 優先順位: 1. DB(FMP蓄積) → 2. Investing.com API（フォールバック）
        db_result = self._load_from_db()
        if db_result:
            # 次回発表日をFMPから取得
            next_release = self._get_next_release_from_fmp()

            latest = db_result[-1] if db_result else None
            cache_payload = {
                "data": db_result,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)

            return {
                "data": db_result,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "database",
                "last_updated": datetime.now(JST).isoformat()
            }

        # DBにデータがない場合はInvesting.comから取得（フォールバック）
        api_data = self._fetch_from_investing()

        if api_data:
            latest = api_data[-1] if api_data else None
            cache_payload = {
                "data": api_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": api_data,
                "latest": latest,
                "next_release": None,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache()
        if file_cache:
            data = file_cache.get("data", [])
            return {
                "data": data,
                "latest": data[-1] if data else None,
                "next_release": None,
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

    def _load_from_db(self) -> List[Dict[str, Any]]:
        """DBから履歴データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                query = text("""
                    SELECT datetime_utc, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'US'
                      AND (event ILIKE '%Retail Sales Ex Gas/Autos%' OR event ILIKE '%Retail Control%')
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query).fetchall()

                result = []
                seen_dates = set()

                for row in rows:
                    dt_utc, actual, estimate, previous = row
                    if dt_utc:
                        # 月初日に正規化
                        date_str = dt_utc.strftime("%Y-%m-01")
                        if date_str in seen_dates:
                            continue
                        seen_dates.add(date_str)

                        result.append({
                            "date": date_str,
                            "mom": float(actual) if actual else None,
                            "forecast": float(estimate) if estimate else None,
                        })

                print(f"Loaded {len(result)} Retail Control records from DB")
                return result

        except Exception as e:
            print(f"Error loading from DB: {e}")
            return []

    def _get_next_release_from_fmp(self) -> Optional[Dict[str, Any]]:
        """FMP APIから次回発表日を取得"""
        try:
            from services.calendar.fmp_service import fmp_service
            from datetime import timedelta

            today = date.today()
            # FMP APIからイベントを取得
            # コントロールグループは Retail Sales と同日発表
            events = fmp_service.fetch_calendar(
                today,
                today + timedelta(days=45),
                country="US"
            )

            # 対象イベントを収集（USのみ）
            candidates = []
            for event in events:
                # USイベントのみ
                if event.get("country") != "US":
                    continue
                event_name = event.get("event", "")
                # Retail Sales Ex Gas/Autos MoM にマッチするイベントのみ
                if "retail sales ex gas/autos" not in event_name.lower():
                    continue
                # 将来のイベント（actual が None）
                if event.get("actual") is None:
                    dt_utc, _ = fmp_service.parse_datetime(event.get("date", ""))
                    if dt_utc and dt_utc.date() >= today:
                        candidates.append({
                            "date": dt_utc.strftime("%Y-%m-%d"),
                            "datetime_utc": dt_utc.isoformat(),
                            "label": event_name,
                            "estimate": event.get("estimate"),
                            "_dt": dt_utc,
                        })

            # 日付順でソートして最も近いイベントを返す
            if candidates:
                candidates.sort(key=lambda x: x["_dt"])
                result = candidates[0]
                del result["_dt"]
                return result

            return None

        except Exception as e:
            print(f"Error fetching next release from FMP: {e}")
            return None

    def _fetch_from_investing(self) -> List[Dict[str, Any]]:
        """Investing.comからコントロールグループデータを取得"""
        try:
            print("Fetching Retail Control from Investing.com...")

            # FREDから小売売上高データの日付リストを取得（新しい順）
            fred_dates = self._get_fred_retail_dates()

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": "https://jp.investing.com/"
            }

            response = requests.get(INVESTING_CONTROL_URL, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            # attrからデータを抽出
            attr_list = data.get("attr", [])
            if not attr_list:
                print("No attr data found in response")
                return []

            # Investing.comデータを発表日順にソート（新しい順）
            investing_data = []
            for item in attr_list:
                timestamp = item.get("timestamp")
                actual = item.get("actual")

                if timestamp is None or actual is None:
                    continue

                investing_data.append({
                    "timestamp": timestamp,
                    "actual": actual,
                    "forecast": item.get("forecast"),
                    "revised": item.get("revised")
                })

            # 発表日の新しい順にソート
            investing_data.sort(key=lambda x: x["timestamp"], reverse=True)

            print(f"Investing.com data count: {len(investing_data)}")
            print(f"FRED dates count: {len(fred_dates)}")

            # 1対1でマッチング（新しい順同士）
            result = []
            match_count = min(len(investing_data), len(fred_dates))

            for i in range(match_count):
                inv_item = investing_data[i]
                fred_date = fred_dates[i]  # FRED日付（新しい順のi番目）

                # タイムスタンプを発表日に変換（ミリ秒 → 秒）
                release_dt = datetime.fromtimestamp(inv_item["timestamp"] / 1000, tz=JST)
                release_date_str = release_dt.strftime("%Y-%m-%d")

                entry = {
                    "date": fred_date,  # FREDの日付を使用
                    "release_date": release_date_str,
                    "mom": float(inv_item["actual"]),
                    "forecast": float(inv_item["forecast"]) if inv_item.get("forecast") is not None else None,
                    "revised": float(inv_item["revised"]) if inv_item.get("revised") is not None else None
                }
                result.append(entry)

            # 日付順にソート（古い順）
            result.sort(key=lambda x: x["date"])

            print(f"Matched {len(result)} records (Investing.com + FRED dates)")
            return result

        except Exception as e:
            print(f"Error fetching Retail Control: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _get_fred_retail_dates(self) -> List[str]:
        """
        FREDから小売売上高データの日付リストを取得（新しい順）

        Returns:
            ["2025-10-01", "2025-09-01", "2025-08-01", ...]
        """
        try:
            if not FRED_API_KEY:
                print("FRED_API_KEY not set")
                return []

            params = {
                "series_id": RSAFS_SERIES_ID,
                "api_key": FRED_API_KEY,
                "file_type": "json",
                "sort_order": "desc"  # 新しい順
            }

            response = requests.get(FRED_SERIES_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            dates = []
            for obs in data.get("observations", []):
                if obs.get("value") and obs["value"] != ".":
                    dates.append(obs["date"])

            print(f"Fetched {len(dates)} FRED retail sales dates")
            return dates

        except Exception as e:
            print(f"Error fetching FRED retail sales dates: {e}")
            return []

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not CACHE_FILE.exists():
                return None

            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        FMPスケジュールベースの3分方式で判定
        """
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cache_exists = redis_client.exists(self.CACHE_KEY)
        cached_data = redis_client.get(self.CACHE_KEY) if cache_exists else None

        return {
            "source": "Investing.com",
            "url": INVESTING_CONTROL_URL,
            "cache_key": self.CACHE_KEY,
            "exists": cache_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "file_cache_exists": CACHE_FILE.exists(),
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID)
        }


# シングルトンインスタンス
retail_control_service = RetailControlService()
