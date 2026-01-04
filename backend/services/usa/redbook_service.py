"""
Redbook小売売上高指数サービス
Investing.comからRedbook Index（前年比）データを取得

指標:
- Redbook Index: 米国小売売上高の週次ベンチマーク（前年比、%）

データソース:
- https://sbcharts.investing.com/events_charts/us/911.json
- イベントID: 911 (Redbook Index)

発表スケジュール:
- 毎週火曜日 8:55 ET（米国東部時間）
- サマータイム中は日本時間21:55、冬時間は日本時間22:55

キャッシュ方式: 発表日時ベース判定方式
"""
import json
from datetime import datetime, date, timedelta
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

# Investing.com JSONエンドポイント
INVESTING_REDBOOK_URL = "https://sbcharts.investing.com/events_charts/us/911.json"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "redbook_cache.json"


class RedbookService:
    """Redbook小売売上高指数サービス"""

    DATA_CACHE_KEY = "investing:redbook:data"
    ECONALPHA_ID = "redbook"  # FMPマッピング用ID

    def __init__(self):
        pass

    def get_redbook_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Redbookデータを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float}, ...],
                "latest": {...},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
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
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)

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
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
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
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
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
                      AND event ILIKE '%Redbook YoY%'
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query).fetchall()

                result = []
                seen_dates = set()

                for row in rows:
                    dt_utc, actual, estimate, previous = row
                    if dt_utc:
                        date_str = dt_utc.strftime("%Y-%m-%d")
                        if date_str in seen_dates:
                            continue
                        seen_dates.add(date_str)

                        result.append({
                            "date": date_str,
                            "value": float(actual) if actual else None,
                        })

                print(f"Loaded {len(result)} Redbook records from DB")
                return result

        except Exception as e:
            print(f"Error loading from DB: {e}")
            return []

    def _get_next_release_from_fmp(self) -> Optional[Dict[str, Any]]:
        """FMP APIから次回発表日を取得"""
        try:
            from services.calendar.fmp_service import fmp_service

            today = date.today()
            # FMP APIからイベントを取得
            events = fmp_service.fetch_calendar(
                today,
                today + timedelta(days=14),
                country="US"
            )

            # 対象イベントを収集（USのみ）
            candidates = []
            for event in events:
                # USイベントのみ
                if event.get("country") != "US":
                    continue
                event_name = event.get("event", "")
                # Redbook YoYにマッチするイベントのみ
                if "redbook yoy" not in event_name.lower():
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
        """Investing.comからRedbookデータを取得（JSON API）"""
        try:
            print("Fetching Redbook from Investing.com JSON API...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": "https://jp.investing.com/"
            }

            response = requests.get(INVESTING_REDBOOK_URL, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            # dataからデータを抽出 [[timestamp, value, "No"], ...]
            data_list = data.get("data", [])
            if not data_list:
                print("No data found in response")
                return []

            result = []
            for item in data_list:
                if len(item) < 2:
                    continue

                timestamp = item[0]
                value = item[1]

                if timestamp is None or value is None:
                    continue

                try:
                    # タイムスタンプをミリ秒から日付に変換
                    dt = datetime.fromtimestamp(timestamp / 1000, tz=JST)
                    date_str = dt.strftime("%Y-%m-%d")

                    result.append({
                        "date": date_str,
                        "value": round(float(value), 2)
                    })
                except (ValueError, TypeError):
                    continue

            # 日付順にソート（古い順）
            result.sort(key=lambda x: x["date"])

            print(f"Fetched {len(result)} Redbook records from Investing.com")
            return result

        except Exception as e:
            print(f"Error fetching Redbook data: {e}")
            import traceback
            traceback.print_exc()
            return []

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
            "indicator": "Redbook Index",
            "source": "Investing.com",
            "url": INVESTING_REDBOOK_URL,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
redbook_service = RedbookService()
