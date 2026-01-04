"""
CB消費者信頼感指数サービス
Investing.comからCB Consumer Confidenceデータを取得

指標:
- CB Consumer Confidence Index: 消費者信頼感指数（Conference Board発表）

データソース:
- https://sbcharts.investing.com/events_charts/us/48.json
- イベントID: 48 (CB Consumer Confidence)

発表スケジュール:
- 毎月最終火曜日 10:00 ET（米国東部時間）
- サマータイム中は日本時間23:00、冬時間は日本時間24:00（翌0:00）

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
ET = ZoneInfo("America/New_York")

# Investing.com JSONエンドポイント
INVESTING_CB_CONSUMER_CONFIDENCE_URL = "https://sbcharts.investing.com/events_charts/us/48.json"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "cb_consumer_confidence_cache.json"


class CBConsumerConfidenceService:
    """CB消費者信頼感指数サービス"""

    DATA_CACHE_KEY = "investing:cb_consumer_confidence:data"
    ECONALPHA_ID = "cb_consumer_confidence"  # FMPマッピング用ID

    def __init__(self):
        pass

    def get_cb_consumer_confidence_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        CB消費者信頼感データを取得

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
                "latest_data_date": latest["date"] if latest else None,
                "last_updated": datetime.now(JST).isoformat()
            }
            # TTLなし（発表日時ベース判定方式）
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            # ファイルにも保存
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
                      AND event ILIKE '%CB Consumer Confidence%'
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
                            "value": float(actual) if actual else None,
                        })

                print(f"Loaded {len(result)} CB Consumer Confidence records from DB")
                return result

        except Exception as e:
            print(f"Error loading from DB: {e}")
            return []

    def _get_next_release_from_fmp(self) -> Optional[Dict[str, Any]]:
        """FMP APIから次回発表日を取得、なければスケジュールから計算"""
        try:
            from services.calendar.fmp_service import fmp_service

            today = date.today()
            # FMP APIからイベントを取得
            events = fmp_service.fetch_calendar(
                today,
                today + timedelta(days=60),
                country="US"
            )

            # 対象イベントを収集（USのみ、CB Consumer Confidence）
            candidates = []
            for event in events:
                # USイベントのみ
                if event.get("country") != "US":
                    continue
                event_name = event.get("event", "")
                event_lower = event_name.lower()
                # CB Consumer Confidence または Consumer Confidence にマッチ
                if "consumer confidence" not in event_lower and "cb consumer" not in event_lower:
                    continue
                # 他の Consumer Confidence を除外（FGV, Michigan, Westpac等）
                if any(x in event_lower for x in ["fgv", "michigan", "westpac", "anz"]):
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

            # FMPにイベントがない場合、スケジュールから計算（毎月最終火曜日 10:00 ET）
            return self._calculate_next_release_date()

        except Exception as e:
            print(f"Error fetching next release from FMP: {e}")
            # エラー時もスケジュールから計算
            return self._calculate_next_release_date()

    def _calculate_next_release_date(self) -> Optional[Dict[str, Any]]:
        """CB消費者信頼感指数の次回発表日を計算（毎月最終火曜日 10:00 ET）"""
        try:
            import calendar

            today = date.today()
            # 今月と来月の最終火曜日を計算
            for month_offset in range(3):
                year = today.year
                month = today.month + month_offset
                if month > 12:
                    month -= 12
                    year += 1

                # 月の最終日を取得
                last_day = calendar.monthrange(year, month)[1]
                last_date = date(year, month, last_day)

                # 最終火曜日を計算（火曜日 = 1）
                days_since_tuesday = (last_date.weekday() - 1) % 7
                last_tuesday = last_date - timedelta(days=days_since_tuesday)

                # 今日以降であれば採用
                if last_tuesday >= today:
                    # 10:00 ET = 15:00 UTC
                    dt_utc = datetime(last_tuesday.year, last_tuesday.month, last_tuesday.day, 15, 0, 0)
                    return {
                        "date": last_tuesday.strftime("%Y-%m-%d"),
                        "datetime_utc": dt_utc.isoformat() + "+00:00",
                        "label": f"CB Consumer Confidence ({calendar.month_abbr[month]})",
                        "estimate": None,
                    }

            return None

        except Exception as e:
            print(f"Error calculating next release date: {e}")
            return None

    def _fetch_from_investing(self) -> List[Dict[str, Any]]:
        """Investing.comからCB消費者信頼感データを取得（JSON API）"""
        try:
            print("Fetching CB Consumer Confidence from Investing.com JSON API...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": "https://jp.investing.com/"
            }

            response = requests.get(INVESTING_CB_CONSUMER_CONFIDENCE_URL, headers=headers, timeout=30)
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
                        "value": round(float(value), 1)
                    })
                except (ValueError, TypeError):
                    continue

            # 日付順にソート（古い順）
            result.sort(key=lambda x: x["date"])

            print(f"Fetched {len(result)} CB Consumer Confidence records from Investing.com")
            return result

        except Exception as e:
            print(f"Error fetching CB Consumer Confidence data: {e}")
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
            "indicator": "CB Consumer Confidence Index",
            "source": "Investing.com",
            "url": INVESTING_CB_CONSUMER_CONFIDENCE_URL,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
cb_consumer_confidence_service = CBConsumerConfidenceService()
