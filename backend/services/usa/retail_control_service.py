"""
リテールコントロール（コントロールグループ）サービス
DBからコントロールグループの前月比データを取得

指標:
- Retail Control (Control Group): 小売売上高コントロールグループ（前月比%）

データソース:
- DB: economic_calendar_events（FMP蓄積データ）
- CSV: 過去データインポート（import_csv_to_db.py）

発表スケジュール:
- 毎月中旬 8:30 ET（小売売上高と同時発表）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "retail_control_cache.json"


class RetailControlService:
    """リテールコントロール（コントロールグループ）サービス"""

    CACHE_KEY = "retail_control:data"
    ECONALPHA_ID = "retail_control"

    def __init__(self):
        pass

    def get_retail_control_data(
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

        # DBから取得
        db_result = self._load_from_db()
        if db_result:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            latest = db_result[-1] if db_result else None
            cache_payload = {
                "data": db_result,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": db_result,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "database",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache()
        if file_cache:
            data = file_cache.get("data", [])
            return {
                "data": data,
                "latest": data[-1] if data else None,
                "next_release": file_cache.get("next_release"),
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
            import re

            with SessionLocal() as session:
                # FMPのイベント名 + CSVインポートのイベント名の両方を検索
                query = text("""
                    SELECT datetime_utc, event, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'US'
                      AND (
                        event ILIKE '%Retail Sales Ex Gas/Autos%'
                        OR event ILIKE '%Retail Control%'
                        OR event ILIKE '%Retail Sales Control Group%'
                      )
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query).fetchall()

                result = []
                seen_dates = set()

                # 月名から月番号へのマッピング
                month_map = {
                    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                }

                for row in rows:
                    dt_utc, event, actual, estimate, previous = row
                    if dt_utc:
                        # イベント名から対象月を抽出（例: "Retail Sales Ex Gas/Autos MoM (Dec)"）
                        match = re.search(r'\((\w{3})\)', event) if event else None
                        if match:
                            month_abbr = match.group(1).lower()
                            if month_abbr in month_map:
                                target_month = month_map[month_abbr]
                                target_year = dt_utc.year
                                if target_month > dt_utc.month:
                                    target_year -= 1
                                date_str = f"{target_year}-{target_month:02d}-01"
                            else:
                                date_str = dt_utc.strftime("%Y-%m-01")
                        else:
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
        """キャッシュを更新すべきかどうかを判定（FMP 3分方式）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cache_exists = redis_client.exists(self.CACHE_KEY)
        cached_data = redis_client.get(self.CACHE_KEY) if cache_exists else None

        return {
            "indicator": "Retail Control",
            "source": "Database (FMP + CSV)",
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
