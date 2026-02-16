"""
オーストラリア インフレ期待 サービス
DBからMelbourne Instituteのインフレ期待データを取得

指標:
- Consumer Inflation Expectations（消費者インフレ期待、%）

データソース:
- DB: economic_calendar_events（FMP蓄積データ + CSVインポート）
- Melbourne Institute Survey of Consumer Inflationary and Wage Expectations

発表スケジュール: 毎月

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.australia.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)

# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "australia" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "au_inflation_expectations_cache.json"

# FMPイベントパターン
FMP_EVENT_PATTERN = "Inflation Expectations"


class AuInflationExpectationsService:
    """オーストラリア インフレ期待サービス"""

    DATA_CACHE_KEY = "australia:au_inflation_expectations:data"
    ECONALPHA_ID = "au_inflation_expectations"
    FMP_COUNTRY = "AU"

    def __init__(self):
        pass

    def get_au_inflation_expectations_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """インフレ期待データを取得"""
        next_release = get_next_release_by_pattern(
            FMP_EVENT_PATTERN, country=self.FMP_COUNTRY
        )

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # DBから取得
        db_result = self._load_from_db()
        if db_result:
            latest = db_result[-1] if db_result else None

            cache_payload = {
                "data": db_result,
                "latest": latest,
                "metadata": {
                    "source": "Melbourne Institute",
                    "indicator": "Consumer Inflation Expectations",
                    "frequency": "monthly",
                    "unit": "%",
                },
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": db_result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "database",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {
                "source": "Melbourne Institute",
                "error": "No data available",
            },
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
        }

    def _load_from_db(self) -> List[Dict[str, Any]]:
        """DBから履歴データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                query = text("""
                    SELECT datetime_utc, actual
                    FROM economic_calendar_events
                    WHERE country = 'AU'
                      AND (event ILIKE '%Inflation Expectations%'
                           OR event ILIKE '%Consumer Inflation Expectation%')
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query).fetchall()

                result = []
                seen_months = set()

                for row in rows:
                    dt_utc, actual = row
                    if dt_utc:
                        # 月次データなので月単位でデデュプ
                        month_key = dt_utc.strftime("%Y-%m")
                        if month_key in seen_months:
                            continue
                        seen_months.add(month_key)

                        date_str = f"{dt_utc.year}-{dt_utc.month:02d}-01"
                        result.append({
                            "date": date_str,
                            "value": float(actual) if actual else None,
                        })

                print(f"Loaded {len(result)} AU Inflation Expectations records from DB")
                return result

        except Exception as e:
            print(f"Error loading AU Inflation Expectations from DB: {e}")
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_pattern(
            FMP_EVENT_PATTERN, last_updated_str, country=self.FMP_COUNTRY
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        return {
            "indicator": "AU Inflation Expectations",
            "source": "Melbourne Institute (DB)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(
                FMP_EVENT_PATTERN, country=self.FMP_COUNTRY
            ),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
au_inflation_expectations_service = AuInflationExpectationsService()
