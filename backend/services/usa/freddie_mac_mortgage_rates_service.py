"""
フレディ・マック30年固定住宅ローン金利サービス

FREDから30年固定住宅ローン金利データを取得

指標:
- 30年固定住宅ローン金利 (Freddie Mac Primary Mortgage Market Survey)

データソース:
- FRED: MORTGAGE30US

発表スケジュール:
- 週次（毎週木曜日 12:00 ET）
- PMMS results are released weekly on Thursdays at 12 p.m. ET

キャッシュ方式: 週次スケジュールベース
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from services.usa.base_fred_service import BaseFREDService
from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "housing"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class FreddieMacMortgageRatesService(BaseFREDService):
    """フレディ・マック30年固定住宅ローン金利サービス"""

    SERIES_ID = "MORTGAGE30US"
    DATA_CACHE_KEY = "housing:freddie_mac_mortgage_rates:data"
    DATA_CACHE_FILE = CACHE_DIR / "freddie_mac_mortgage_rates_cache.json"

    # ECONALPHA_IDなし（FMPにこの指標はない）
    ECONALPHA_ID = ""

    # デフォルトの開始日
    DEFAULT_START_DATE = "2000-01-01"

    # 発表スケジュール（木曜日 12:00 ET）
    RELEASE_DAY_OF_WEEK = 3  # 0=月曜, 3=木曜
    RELEASE_HOUR_ET = 12
    RELEASE_MINUTE_ET = 0

    # フォールバックTTL（時間）
    FALLBACK_CACHE_TTL_HOURS = 24

    def __init__(self):
        super().__init__()

    def get_mortgage_rates_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        30年固定住宅ローン金利データを取得

        Args:
            force_refresh: 強制更新フラグ

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float}, ...],
                "latest": {"date": str, "value": float},
                "next_release": {"date": str, "datetime_jst": str, "label": str} | None,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        result = self.get_data(force_refresh=force_refresh)

        # next_releaseを計算して追加
        next_release = self._get_next_release()
        result["next_release"] = next_release

        return result

    def _calculate_changes(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        週次データなので前月比・前年比は計算せず、値のみ返す
        """
        result = []
        for item in raw_data:
            result.append({
                "date": item["date"],
                "value": item["value"],
            })
        return result

    def _should_refresh(self, last_updated_str: str, cached_data: Dict[str, Any]) -> bool:
        """
        キャッシュを更新すべきかどうかを判定（週次スケジュールベース）

        判定ロジック:
        1. 直近の発表日時を計算（木曜日12:00 ET）
        2. 現在時刻が発表日時を過ぎているか確認
        3. 最終更新が発表日時より前なら更新
        4. フォールバック: 24時間以上経過していれば更新
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 直近の発表日時を取得
            last_release = self._get_last_release()
            if last_release:
                release_datetime = datetime.fromisoformat(last_release["datetime_jst"])

                # 発表時刻より前なら更新不要
                if now < release_datetime:
                    # フォールバックTTLチェック
                    elapsed_hours = (now - last_updated).total_seconds() / 3600
                    return elapsed_hours >= self.FALLBACK_CACHE_TTL_HOURS

                # 発表日時を過ぎていて、最終更新が発表日時より前なら更新
                if last_updated < release_datetime:
                    return True

                return False

            # フォールバック: 24時間TTL
            elapsed_hours = (now - last_updated).total_seconds() / 3600
            return elapsed_hours >= self.FALLBACK_CACHE_TTL_HOURS

        except Exception as e:
            print(f"Error checking refresh: {e}")
            return True

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日を計算（木曜日12:00 ET）
        """
        try:
            now = datetime.now(ET)

            # 今週の木曜日を計算
            days_until_thursday = (self.RELEASE_DAY_OF_WEEK - now.weekday()) % 7
            if days_until_thursday == 0:
                # 今日が木曜日の場合
                today_release = now.replace(
                    hour=self.RELEASE_HOUR_ET,
                    minute=self.RELEASE_MINUTE_ET,
                    second=0,
                    microsecond=0
                )
                if now >= today_release:
                    # 既に発表済み → 来週の木曜日
                    days_until_thursday = 7

            next_thursday = now + timedelta(days=days_until_thursday)
            release_time_et = next_thursday.replace(
                hour=self.RELEASE_HOUR_ET,
                minute=self.RELEASE_MINUTE_ET,
                second=0,
                microsecond=0
            )
            release_time_jst = release_time_et.astimezone(JST)

            return {
                "date": release_time_et.strftime("%Y-%m-%d"),
                "datetime_jst": release_time_jst.isoformat(),
                "time_jst": release_time_jst.strftime("%H:%M"),
                "label": f"Freddie Mac Mortgage Rates ({release_time_et.strftime('%b %d')})",
            }

        except Exception as e:
            print(f"Error calculating next release: {e}")
            return None

    def _get_last_release(self) -> Optional[Dict[str, Any]]:
        """
        直近の発表日を計算（過去の木曜日12:00 ET）
        """
        try:
            now = datetime.now(ET)

            # 直近の木曜日を計算
            days_since_thursday = (now.weekday() - self.RELEASE_DAY_OF_WEEK) % 7
            if days_since_thursday == 0:
                # 今日が木曜日
                today_release = now.replace(
                    hour=self.RELEASE_HOUR_ET,
                    minute=self.RELEASE_MINUTE_ET,
                    second=0,
                    microsecond=0
                )
                if now < today_release:
                    # まだ発表されていない → 先週の木曜日
                    days_since_thursday = 7

            last_thursday = now - timedelta(days=days_since_thursday)
            release_time_et = last_thursday.replace(
                hour=self.RELEASE_HOUR_ET,
                minute=self.RELEASE_MINUTE_ET,
                second=0,
                microsecond=0
            )
            release_time_jst = release_time_et.astimezone(JST)

            return {
                "date": release_time_et.strftime("%Y-%m-%d"),
                "datetime_jst": release_time_jst.isoformat(),
                "time_jst": release_time_jst.strftime("%H:%M"),
                "label": f"Freddie Mac Mortgage Rates ({release_time_et.strftime('%b %d')})",
            }

        except Exception as e:
            print(f"Error calculating last release: {e}")
            return None

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Freddie Mac 30-Year Fixed Rate Mortgage",
            "source": "FRED",
            "series_id": self.SERIES_ID,
            "cache_method": "週次スケジュールベース（木曜日12:00 ET）",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "last_release": self._get_last_release(),
            "file_cache_exists": self.DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
freddie_mac_mortgage_rates_service = FreddieMacMortgageRatesService()
