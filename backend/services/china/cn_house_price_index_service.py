"""
中国 住宅価格指数（House Price Index YoY）サービス

指標:
- House Price Index YoY: 70都市新築商品住宅価格指数（前年比）

データソース:
- DB: economic_calendar_events（CSVインポート + FMP蓄積データ）
- CSV: 過去データインポート（中国住宅価格指数.csv）
- FMP: 最新値の自動取得

発表スケジュール:
- 毎月中旬（NBS）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import re
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    get_fmp_event_patterns,
    get_last_release_from_fmp,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")

# キャッシュ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "china" / "housing"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "cn_house_price_index_cache.json"

# FMPスケジュールベース更新チェック期間（分）
UPDATE_WINDOW_MINUTES = 3


class CnHousePriceIndexService:
    """中国住宅価格指数サービス"""

    DATA_CACHE_KEY = "china:cn_house_price_index:data"
    ECONALPHA_ID = "cn_house_price_index"

    def __init__(self):
        pass

    def get_data(
        self,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        住宅価格指数データを取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float, ...}, ...],
                "latest": {...},
                "next_release": {...} | null,
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
                        "last_updated": last_updated_str,
                    }

        # DBから取得
        db_result = self._load_from_db()
        if db_result:
            next_release = get_next_release_from_fmp(
                self.ECONALPHA_ID, country="CN"
            )

            latest = db_result[-1] if db_result else None
            cache_payload = {
                "data": db_result,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": db_result,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "database",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_db(self) -> List[Dict[str, Any]]:
        """DBから履歴データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                query = text("""
                    SELECT datetime_utc, event, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'CN'
                      AND event ILIKE '%House Price Index YoY%'
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query).fetchall()

                result = []
                seen_dates = set()

                month_map = {
                    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
                    "may": 5, "jun": 6, "jul": 7, "aug": 8,
                    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
                }

                for row in rows:
                    dt_utc, event, actual, estimate, previous = row
                    if not dt_utc:
                        continue

                    # イベント名から対象月を抽出: "House Price Index YoY (Dec)"
                    match = re.search(r"\((\w{3})\)", event)
                    if match:
                        month_abbr = match.group(1).lower()
                        if month_abbr in month_map:
                            target_month = month_map[month_abbr]
                            target_year = dt_utc.year
                            if target_month > dt_utc.month:
                                target_year -= 1
                            date_str = f"{target_year}-{target_month:02d}-01"
                        else:
                            prev_month = dt_utc.month - 1 if dt_utc.month > 1 else 12
                            prev_year = dt_utc.year if dt_utc.month > 1 else dt_utc.year - 1
                            date_str = f"{prev_year}-{prev_month:02d}-01"
                    else:
                        # CSV_IMPORTデータ: datetime_utcが対象月そのもの
                        date_str = dt_utc.strftime("%Y-%m-01")

                    if date_str in seen_dates:
                        continue
                    seen_dates.add(date_str)

                    result.append({
                        "date": date_str,
                        "value": float(actual) if actual is not None else None,
                        "forecast": float(estimate) if estimate is not None else None,
                        "previous": float(previous) if previous is not None else None,
                    })

                print(f"[CnHousePriceIndex] Loaded {len(result)} records from DB")
                return result

        except Exception as e:
            print(f"[CnHousePriceIndex] Error loading from DB: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMPベース）"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # DBから直近の発表イベントを取得
            patterns = get_fmp_event_patterns(self.ECONALPHA_ID)
            if not patterns:
                elapsed = (now - last_updated).total_seconds()
                return elapsed > 24 * 60 * 60

            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                pattern_conditions = " OR ".join(
                    [f"event ILIKE '%{p}%'" for p in patterns]
                )
                query = text(f"""
                    SELECT datetime_utc
                    FROM economic_calendar_events
                    WHERE country = 'CN'
                      AND ({pattern_conditions})
                      AND actual IS NOT NULL
                      AND datetime_utc <= NOW()
                    ORDER BY datetime_utc DESC
                    LIMIT 1
                """)
                row = session.execute(query).fetchone()

                if not row:
                    return False

                dt_utc = row[0]
                if dt_utc.tzinfo is None:
                    dt_utc = dt_utc.replace(tzinfo=UTC)

                release_datetime = dt_utc.astimezone(JST)

                if now < release_datetime:
                    return False

                update_window_end = release_datetime + timedelta(
                    minutes=UPDATE_WINDOW_MINUTES
                )

                if now <= update_window_end:
                    if last_updated < release_datetime:
                        return True
                else:
                    if last_updated < release_datetime:
                        return True

                return False

        except Exception as e:
            print(f"[CnHousePriceIndex] Error checking refresh: {e}")
            return False

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CnHousePriceIndex] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CnHousePriceIndex] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "House Price Index YoY",
            "source": "Database (FMP)",
            "data_cache": {
                "exists": data_exists,
                "last_updated": cached_data.get("last_updated") if cached_data else None,
                "record_count": len(cached_data.get("data", [])) if cached_data else 0,
            },
            "file_cache": {
                "exists": DATA_CACHE_FILE.exists(),
            },
        }


# シングルトン
cn_house_price_index_service = CnHousePriceIndexService()
