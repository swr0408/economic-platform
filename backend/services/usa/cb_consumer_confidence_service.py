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

    # 発表時刻設定（ET）- 10:00 ET
    RELEASE_HOUR_ET = 10
    RELEASE_MINUTE_ET = 0

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
                    # 表示用は最終週のみ（22日以降）
                    next_release = self._get_next_release(for_display=True)
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": next_release,
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
                    data = file_cache.get("data", [])
                    # 表示用は最終週のみ（22日以降）
                    next_release = self._get_next_release(for_display=True)

                    # Redisにも保存
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)

                    return {
                        "data": data,
                        "latest": file_cache.get("latest"),
                        "next_release": next_release,
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # Investing.comからJSONで取得
        api_data = self._fetch_from_investing()
        # 表示用は最終週のみ（22日以降）
        next_release = self._get_next_release(for_display=True)

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
                "next_release": next_release,
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
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

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
        """
        キャッシュを更新すべきかどうかを判定

        判定ロジック:
        - 次回発表日時（最終火曜日 10:00 ET）を過ぎており、かつ最終更新が発表日時より前なら更新
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 次回発表日時を取得
            next_release = self._get_next_release()

            if next_release and next_release.get("date"):
                # 発表日時をパース
                release_date_str = next_release["date"]
                release_date = datetime.strptime(release_date_str, "%Y-%m-%d")

                # 発表時刻（10:00 ET）をJSTに変換
                release_et = datetime(
                    release_date.year, release_date.month, release_date.day,
                    self.RELEASE_HOUR_ET, self.RELEASE_MINUTE_ET,
                    tzinfo=ET
                )
                release_jst = release_et.astimezone(JST)

                # 発表日時を過ぎており、かつ最終更新が発表日時より前なら更新が必要
                if now >= release_jst and last_updated < release_jst:
                    return True

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return False

    def _get_next_release(self, for_display: bool = False) -> Optional[Dict[str, Any]]:
        """
        次回発表日を計算

        CB消費者信頼感は毎月最終火曜日発表

        Args:
            for_display: 表示用の場合True（最終週22日以降のみ返す）
        """
        try:
            now = datetime.now(ET)
            today = now.date()

            # 表示用の場合、最終週（22日以降）のみ計算
            # それ以外はNoneを返す（不要な情報を表示しない）
            if for_display and today.day < 22:
                return None

            # 今月の最終火曜日を計算
            last_tuesday_this_month = self._get_last_tuesday_of_month(today.year, today.month)

            # 発表時刻
            release_time = datetime(
                last_tuesday_this_month.year, last_tuesday_this_month.month, last_tuesday_this_month.day,
                self.RELEASE_HOUR_ET, self.RELEASE_MINUTE_ET,
                tzinfo=ET
            )

            # 今月の発表日時を過ぎていれば来月の最終火曜日
            if now >= release_time:
                # 来月を計算
                if today.month == 12:
                    next_year = today.year + 1
                    next_month = 1
                else:
                    next_year = today.year
                    next_month = today.month + 1

                next_release_date = self._get_last_tuesday_of_month(next_year, next_month)
            else:
                next_release_date = last_tuesday_this_month

            return {
                "date": next_release_date.strftime("%Y-%m-%d"),
                "label": f"CB Consumer Confidence - {next_release_date.strftime('%Y/%m/%d')} (火) 10:00 ET"
            }

        except Exception as e:
            print(f"Error calculating next release: {e}")
            return None

    def _get_last_tuesday_of_month(self, year: int, month: int) -> date:
        """
        指定した年月の最終火曜日を取得

        Args:
            year: 年
            month: 月

        Returns:
            最終火曜日の日付
        """
        # 月末を計算
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)

        last_day = next_month - timedelta(days=1)

        # 最終火曜日を探す（火曜日=1）
        days_since_tuesday = (last_day.weekday() - 1) % 7
        last_tuesday = last_day - timedelta(days=days_since_tuesday)

        return last_tuesday

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
            "next_release": self._get_next_release(for_display=True),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
cb_consumer_confidence_service = CBConsumerConfidenceService()
