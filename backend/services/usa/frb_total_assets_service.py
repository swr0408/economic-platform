"""
FRB総資産（FED Balance Sheet）サービス
FREDからWALCLシリーズを取得

指標:
- FRB総資産（Federal Reserve Total Assets）

データソース:
- FRED: WALCL（Millions of Dollars）

発表スケジュール:
- 週次: 毎週水曜日 3:30 pm ET (As of Wednesday)

キャッシュ方式: 独自週次スケジュール判定方式（FMP非対応）
"""
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from services.usa.fred_utils import (
    BaseSingleSeriesService,
    load_file_cache,
)
from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "monetary_policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class FRBTotalAssetsService(BaseSingleSeriesService):
    """FRB総資産サービス（FRED WALCL）"""

    SERIES_ID = "WALCL"
    REDIS_KEY = "fred:frb_total_assets:data"
    ECONALPHA_ID = ""  # FMPマッピングなし
    CACHE_FILE = CACHE_DIR / "frb_total_assets_cache.json"
    INDICATOR_NAME = "FRB Total Assets"

    # 週次データ - 変化率計算をスキップ（水準値のみ）
    SKIP_CHANGES = True
    VALUE_ROUND_DIGITS = 2
    DEFAULT_START_DATE = "2000-01-01"

    # 発表スケジュール設定
    RELEASE_DAY_OF_WEEK = 2  # 水曜日 (0=月曜, 2=水曜)
    RELEASE_HOUR_ET = 15     # 3:30 PM ET
    RELEASE_MINUTE_ET = 30

    def __init__(self):
        super().__init__()
        # CacheManagerのshould_refreshをオーバーライドするため独自実装
        self._cache_manager.econalpha_id = None  # FMPスケジュール判定を無効化

    def get_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ):
        """
        データを取得（キャッシュ優先）
        独自の週次発表スケジュール判定を使用
        """
        # 1. キャッシュチェック（独自判定）
        if not force_refresh:
            cached_data = redis_client.get(self.REDIS_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": self._calculate_next_release(),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # 2. APIから取得
        api_data = self._fetch_and_process(start_date)

        if api_data:
            latest = api_data[-1] if api_data else None
            cache_payload = {
                "data": api_data,
                "latest": latest,
                "latest_data_date": latest["date"] if latest else None,
                "last_updated": datetime.now(JST).isoformat()
            }
            self._cache_manager.save(cache_payload)

            return {
                "data": api_data,
                "latest": latest,
                "next_release": self._calculate_next_release(),
                "cached": False,
                "source": "api",
                "last_updated": cache_payload["last_updated"]
            }

        # 3. フォールバック
        file_cache = load_file_cache(self.CACHE_FILE)
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": self._calculate_next_release(),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": self._calculate_next_release(),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定（週次水曜日発表スケジュール）

        水曜日15:30 ETの発表後にキャッシュを更新
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # max-age フォールバック（発表レース凍結の自己回復）:
            # 水曜15:30 ET発表ちょうどの再取得で H.4.1 未反映のまま last_updated=now を刻むと
            # 下の発表日時判定が「消化済み」と誤認し次回水曜まで凍結する。週次のため48hで
            # 必ず再取得させ、当該週内に自己回復させる。
            if (now - last_updated).total_seconds() > 48 * 3600:
                return True

            # 最新の発表日時を計算
            latest_release = self._get_latest_release_datetime()
            if latest_release is None:
                return False

            # 最終更新が最新発表日時より前なら更新が必要
            return last_updated < latest_release <= now

        except Exception as e:
            print(f"Error in _should_refresh: {e}")
            return False

    def _get_latest_release_datetime(self) -> Optional[datetime]:
        """
        最新の発表日時を取得（現在以前の最も近い水曜日）
        """
        now_et = datetime.now(ET)
        days_since_wednesday = (now_et.weekday() - self.RELEASE_DAY_OF_WEEK) % 7

        # 今日が水曜日で発表時刻前なら、先週の水曜日を使用
        if days_since_wednesday == 0:
            release_today = now_et.replace(
                hour=self.RELEASE_HOUR_ET,
                minute=self.RELEASE_MINUTE_ET,
                second=0,
                microsecond=0
            )
            if now_et < release_today:
                days_since_wednesday = 7

        latest_wednesday = now_et - timedelta(days=days_since_wednesday)
        release_datetime_et = latest_wednesday.replace(
            hour=self.RELEASE_HOUR_ET,
            minute=self.RELEASE_MINUTE_ET,
            second=0,
            microsecond=0
        )

        return release_datetime_et.astimezone(JST)

    def _calculate_next_release(self) -> Optional[str]:
        """
        次回発表日時を計算（次の水曜日15:30 ET）
        """
        try:
            now_et = datetime.now(ET)
            days_until_wednesday = (self.RELEASE_DAY_OF_WEEK - now_et.weekday()) % 7

            # 今日が水曜日で発表時刻を過ぎていたら、来週の水曜日
            if days_until_wednesday == 0:
                release_today = now_et.replace(
                    hour=self.RELEASE_HOUR_ET,
                    minute=self.RELEASE_MINUTE_ET,
                    second=0,
                    microsecond=0
                )
                if now_et >= release_today:
                    days_until_wednesday = 7

            next_wednesday = now_et + timedelta(days=days_until_wednesday)
            next_release_et = next_wednesday.replace(
                hour=self.RELEASE_HOUR_ET,
                minute=self.RELEASE_MINUTE_ET,
                second=0,
                microsecond=0
            )

            next_release_jst = next_release_et.astimezone(JST)
            return next_release_jst.isoformat()

        except Exception as e:
            print(f"Error calculating next release: {e}")
            return None

    def get_cache_status(self):
        """キャッシュの状態を取得"""
        exists = redis_client.exists(self.REDIS_KEY)
        cached_data = redis_client.get(self.REDIS_KEY) if exists else None

        return {
            "indicator": self.INDICATOR_NAME,
            "series_id": self.SERIES_ID,
            "source": "FRED (weekly)",
            "cache_key": self.REDIS_KEY,
            "exists": exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._calculate_next_release(),
            "file_cache_exists": self.CACHE_FILE.exists()
        }


# シングルトンインスタンス
frb_total_assets_service = FRBTotalAssetsService()
