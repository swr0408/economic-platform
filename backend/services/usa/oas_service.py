"""
OAS（Option-Adjusted Spread）サービス
FREDからOASシリーズを取得

指標:
- BAMLH0A0HYM2: ICE BofA US High Yield Index Option-Adjusted Spread
- BAMLC0A0CM: ICE BofA US Corporate Index Option-Adjusted Spread
- BAMLH0A0HYM2EY: ICE BofA US High Yield Index Effective Yield

データソース:
- FRED: BAMLH0A0HYM2, BAMLC0A0CM, BAMLH0A0HYM2EY

発表スケジュール:
- 日次: 毎日 9:00 AM CST

キャッシュ方式: 独自日次スケジュール判定方式（FMP非対応）
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from zoneinfo import ZoneInfo
from pathlib import Path
import json

from services.usa.fred_utils import (
    BaseSingleSeriesService,
    load_file_cache,
    fetch_fred_series,
)
from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
CST = ZoneInfo("America/Chicago")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "monetary_policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class OASService(BaseSingleSeriesService):
    """OAS（Option-Adjusted Spread）サービス"""

    # シリーズ定義
    SERIES_HY_SPREAD = "BAMLH0A0HYM2"  # High Yield OAS
    SERIES_IG_SPREAD = "BAMLC0A0CM"     # Investment Grade OAS
    SERIES_HY_YIELD = "BAMLH0A0HYM2EY"  # High Yield Effective Yield

    # Redis キー
    REDIS_KEY_HY_SPREAD = "fred:oas_hy_spread:data"
    REDIS_KEY_IG_SPREAD = "fred:oas_ig_spread:data"
    REDIS_KEY_HY_YIELD = "fred:oas_hy_yield:data"

    # ファイルキャッシュ
    CACHE_FILE_HY_SPREAD = CACHE_DIR / "oas_hy_spread_cache.json"
    CACHE_FILE_IG_SPREAD = CACHE_DIR / "oas_ig_spread_cache.json"
    CACHE_FILE_HY_YIELD = CACHE_DIR / "oas_hy_yield_cache.json"

    INDICATOR_NAME = "OAS"
    ECONALPHA_ID = ""  # FMPマッピングなし

    # 日次データ
    SKIP_CHANGES = True
    VALUE_ROUND_DIGITS = 2
    DEFAULT_START_DATE = "2000-01-01"

    # 発表スケジュール設定（毎日9:00 AM CST）
    RELEASE_HOUR_CST = 9
    RELEASE_MINUTE_CST = 0

    def __init__(self):
        super().__init__()
        self._cache_manager.econalpha_id = None

    def get_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ):
        """
        全3シリーズのデータを取得（キャッシュ優先）
        """
        # High Yield OAS
        hy_spread_data = self._get_series_data(
            series_id=self.SERIES_HY_SPREAD,
            redis_key=self.REDIS_KEY_HY_SPREAD,
            cache_file=self.CACHE_FILE_HY_SPREAD,
            start_date=start_date,
            force_refresh=force_refresh
        )

        # Investment Grade OAS
        ig_spread_data = self._get_series_data(
            series_id=self.SERIES_IG_SPREAD,
            redis_key=self.REDIS_KEY_IG_SPREAD,
            cache_file=self.CACHE_FILE_IG_SPREAD,
            start_date=start_date,
            force_refresh=force_refresh
        )

        # High Yield Effective Yield
        hy_yield_data = self._get_series_data(
            series_id=self.SERIES_HY_YIELD,
            redis_key=self.REDIS_KEY_HY_YIELD,
            cache_file=self.CACHE_FILE_HY_YIELD,
            start_date=start_date,
            force_refresh=force_refresh
        )

        return {
            "hy_spread": hy_spread_data.get("data", []),
            "ig_spread": ig_spread_data.get("data", []),
            "hy_yield": hy_yield_data.get("data", []),
            "latest_hy_spread": hy_spread_data.get("latest"),
            "latest_ig_spread": ig_spread_data.get("latest"),
            "latest_hy_yield": hy_yield_data.get("latest"),
            "next_release": self._calculate_next_release(),
            "cached": all([
                hy_spread_data.get("cached", False),
                ig_spread_data.get("cached", False),
                hy_yield_data.get("cached", False)
            ]),
            "source": hy_spread_data.get("source", "unknown"),
            "last_updated": hy_spread_data.get("last_updated")
        }

    def _get_series_data(
        self,
        series_id: str,
        redis_key: str,
        cache_file: Path,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """個別シリーズのデータを取得"""
        # 1. キャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(redis_key)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # 2. APIから取得
        api_data = self._fetch_series(series_id, start_date)

        if api_data:
            latest = api_data[-1] if api_data else None
            cache_payload = {
                "data": api_data,
                "latest": latest,
                "latest_data_date": latest["date"] if latest else None,
                "last_updated": datetime.now(JST).isoformat()
            }

            # Redisに保存
            redis_client.set(redis_key, cache_payload)

            # ファイルキャッシュにも保存
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(cache_payload, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"Error saving file cache for {series_id}: {e}")

            return {
                "data": api_data,
                "latest": latest,
                "cached": False,
                "source": "api",
                "last_updated": cache_payload["last_updated"]
            }

        # 3. フォールバック
        file_cache = load_file_cache(cache_file)
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "cached": False,
            "source": "none",
            "last_updated": None
        }

    def _fetch_series(self, series_id: str, start_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """FREDから指定シリーズを取得"""
        try:
            start = start_date or self.DEFAULT_START_DATE
            raw_data = fetch_fred_series(
                series_id=series_id,
                start_date=start,
                round_digits=self.VALUE_ROUND_DIGITS
            )
            return raw_data

        except Exception as e:
            print(f"Error fetching {series_id}: {e}")
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定（日次9:00 AM CST発表スケジュール）
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

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
        最新の発表日時を取得（今日または昨日の9:00 AM CST）
        """
        now_cst = datetime.now(CST)
        today_release = now_cst.replace(
            hour=self.RELEASE_HOUR_CST,
            minute=self.RELEASE_MINUTE_CST,
            second=0,
            microsecond=0
        )

        # 今日の発表時刻を過ぎていれば今日、まだなら昨日
        if now_cst >= today_release:
            latest_release = today_release
        else:
            latest_release = today_release - timedelta(days=1)

        return latest_release.astimezone(JST)

    def _calculate_next_release(self) -> Optional[str]:
        """
        次回発表日時を計算（次の9:00 AM CST）
        """
        try:
            now_cst = datetime.now(CST)
            today_release = now_cst.replace(
                hour=self.RELEASE_HOUR_CST,
                minute=self.RELEASE_MINUTE_CST,
                second=0,
                microsecond=0
            )

            # 今日の発表時刻を過ぎていれば明日、まだなら今日
            if now_cst >= today_release:
                next_release = today_release + timedelta(days=1)
            else:
                next_release = today_release

            next_release_jst = next_release.astimezone(JST)
            return next_release_jst.isoformat()

        except Exception as e:
            print(f"Error calculating next release: {e}")
            return None

    def get_cache_status(self):
        """キャッシュの状態を取得"""
        def get_series_status(redis_key, series_id, cache_file):
            exists = redis_client.exists(redis_key)
            cached = redis_client.get(redis_key) if exists else None
            return {
                "series_id": series_id,
                "cache_key": redis_key,
                "exists": exists,
                "last_updated": cached.get("last_updated") if cached else None,
                "data_count": len(cached.get("data", [])) if cached else 0,
                "latest": cached.get("latest") if cached else None,
                "file_cache_exists": cache_file.exists()
            }

        return {
            "indicator": self.INDICATOR_NAME,
            "source": "FRED (daily)",
            "series": {
                "hy_spread": get_series_status(
                    self.REDIS_KEY_HY_SPREAD,
                    self.SERIES_HY_SPREAD,
                    self.CACHE_FILE_HY_SPREAD
                ),
                "ig_spread": get_series_status(
                    self.REDIS_KEY_IG_SPREAD,
                    self.SERIES_IG_SPREAD,
                    self.CACHE_FILE_IG_SPREAD
                ),
                "hy_yield": get_series_status(
                    self.REDIS_KEY_HY_YIELD,
                    self.SERIES_HY_YIELD,
                    self.CACHE_FILE_HY_YIELD
                ),
            },
            "next_release": self._calculate_next_release(),
        }

    def invalidate_cache(self) -> bool:
        """全シリーズのキャッシュを無効化"""
        try:
            redis_client.delete(self.REDIS_KEY_HY_SPREAD)
            redis_client.delete(self.REDIS_KEY_IG_SPREAD)
            redis_client.delete(self.REDIS_KEY_HY_YIELD)
            return True
        except Exception as e:
            print(f"Error invalidating cache: {e}")
            return False


# シングルトンインスタンス
oas_service = OASService()
