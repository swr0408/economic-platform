"""
日銀バランスシートサービス（Japan Balance Sheet / BOJ Total Assets）
FRED APIから日銀総資産データを取得

シリーズID:
- JPNASSETS: Bank of Japan: Total Assets for Japan
              (月次、非季節調整、1億円単位)

データソース:
- Federal Reserve Bank of St. Louis (FRED)
- Source: Bank of Japan (日本銀行)

発表スケジュール:
- 営業毎旬報告: 毎月10日、20日、月末時点のデータを発表
- 発表時刻: 10:00 JST
- スケジュール取得元: https://www.boj.or.jp/about/calendar/index.htm

キャッシュ方式: 発表日時ベース判定方式
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# FREDシリーズID
SERIES_ID = "JPNASSETS"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "monetary_policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "japan_balance_sheet_cache.json"


class JapanBalanceSheetService:
    """日銀バランスシートサービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "japan:balance_sheet:data"

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")
        self._boj_calendar_service = None

    @property
    def boj_calendar_service(self):
        """遅延インポートでBOJカレンダーサービスを取得"""
        if self._boj_calendar_service is None:
            from services.japan.boj_calendar_service import boj_calendar_service
            self._boj_calendar_service = boj_calendar_service
        return self._boj_calendar_service

    def _get_next_release(self) -> dict | None:
        """次回発表日時を取得"""
        try:
            return self.boj_calendar_service.get_next_eigyo_maijun_release()
        except Exception as e:
            print(f"Error getting next release: {e}")
            return None

    def get_balance_sheet_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        日銀バランスシートデータを取得

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float, "value_trillion": float}, ...],
                "latest": {...},
                "metadata": {...},
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
                if last_updated_str and not self._should_refresh(last_updated_str, cached_data):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": self._get_next_release(),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str, file_cache):
                    # Redisにも保存
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)

                    return {
                        "data": file_cache.get("data", []),
                        "latest": file_cache.get("latest"),
                        "metadata": file_cache.get("metadata", {}),
                        "next_release": self._get_next_release(),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # 外部APIから取得
        api_data = self._fetch_from_api(start_date)

        if api_data:
            latest = api_data[-1] if api_data else None

            metadata = {
                "source": "Bank of Japan (via FRED)",
                "description": "Bank of Japan: Total Assets",
                "unit": "100 Million Yen (億円)",
                "display_unit": "Trillion Yen (兆円)",
                "frequency": "Monthly",
                "series_id": SERIES_ID
            }

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "metadata": metadata,
                "last_updated": datetime.now(JST).isoformat()
            }
            # TTLなし（月次更新判定方式）
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            # ファイルにも保存
            self._save_file_cache(cache_payload)

            return {
                "data": api_data,
                "latest": latest,
                "metadata": metadata,
                "next_release": self._get_next_release(),
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
                "metadata": file_cache.get("metadata", {}),
                "next_release": self._get_next_release(),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": self._get_next_release(),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_api(
        self,
        start_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """FRED APIから日銀バランスシートデータを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print("Fetching Japan Balance Sheet (BOJ Total Assets) from FRED...")

            # デフォルト期間（1998年から - データ開始時点）
            if not start_date:
                start_date = "1998-01-01"

            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": SERIES_ID,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date,
                "sort_order": "asc"
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            result = []
            for obs in data.get("observations", []):
                if obs.get("value") and obs["value"] != ".":
                    try:
                        value = float(obs["value"])
                        # value: 億円単位の生データ
                        # value_trillion: 兆円単位（表示用）
                        result.append({
                            "date": obs["date"],
                            "value": round(value, 0),  # 億円
                            "value_trillion": round(value / 10000, 2)  # 兆円
                        })
                    except (ValueError, TypeError):
                        continue

            print(f"Fetched {len(result)} monthly records from FRED (Japan Balance Sheet)")
            if result:
                latest = result[-1]
                print(f"Latest: {latest['date']} - {latest['value_trillion']} 兆円")

            return result

        except Exception as e:
            print(f"Error fetching Japan Balance Sheet: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str, cached_data: dict = None) -> bool:
        """
        キャッシュを更新すべきかどうかを判定（発表日時ベース）

        以下の条件で更新:
        1. 営業毎旬報告の発表日時（10:00 JST）を過ぎた場合
        2. 最新データの月より現在の月が進んでいる場合（更新漏れ対策）

        Args:
            last_updated_str: 最終更新日時（ISO形式）
            cached_data: キャッシュされたデータ（latest情報を含む）
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 条件1: 営業毎旬報告の発表日時をチェック
            try:
                schedule_result = self.boj_calendar_service.get_eigyo_maijun_schedule()
                schedule = schedule_result.get("schedule", [])

                for item in schedule:
                    release_date = item.get("date")
                    release_time = item.get("time", "10:00")

                    if not release_date:
                        continue

                    # 発表日時を構築
                    release_dt = datetime.strptime(
                        f"{release_date} {release_time}",
                        "%Y-%m-%d %H:%M"
                    ).replace(tzinfo=JST)

                    # 発表後で、かつキャッシュ更新前なら更新
                    if last_updated < release_dt <= now:
                        print(f"[Japan Balance Sheet] Release detected: {release_dt.isoformat()}")
                        return True

            except Exception as e:
                print(f"Error checking release schedule: {e}")
                # スケジュール取得失敗時はフォールバック判定

            # 条件2: 最新データの月と現在を比較（更新漏れ対策）
            if cached_data and cached_data.get("latest"):
                latest_date_str = cached_data["latest"].get("date")
                if latest_date_str:
                    latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d")
                    # FREDのデータは約2ヶ月遅れ（例: 11月発表は9月データ）
                    # 最新データの月 + 3ヶ月 < 現在の月 なら更新が必要
                    months_diff = (now.year - latest_date.year) * 12 + (now.month - latest_date.month)
                    if months_diff >= 3:
                        print(f"[Japan Balance Sheet] Stale data detected: latest={latest_date_str}, now={now.strftime('%Y-%m-%d')}")
                        return True

            return False

        except Exception as e:
            print(f"Error in _should_refresh: {e}")
            return True

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
            "series_id": SERIES_ID,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
japan_balance_sheet_service = JapanBalanceSheetService()
