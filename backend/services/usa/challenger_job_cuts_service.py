"""
Challenger人員削減数サービス
DBからChallenger Job Cutsデータを取得

指標:
- Challenger Job Cuts: 米国企業の人員削減発表数

データソース:
- DB: economic_calendar_events（FMP蓄積データ）
- CSV: 過去データインポート

発表スケジュール:
- 毎月第1木曜日頃 7:30 ET

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
    guarded_last_updated,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "challenger_job_cuts_cache.json"


class ChallengerJobCutsService:
    """Challenger人員削減数サービス"""

    DATA_CACHE_KEY = "challenger:job_cuts:data"
    ECONALPHA_ID = "challenger_job_cuts"

    def __init__(self):
        pass

    def get_challenger_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Challenger人員削減数データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float, "mom": float | null, "yoy": float | null}, ...],
                "latest": {...},
                "next_release": null,
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

        # DBから取得
        db_result = self._load_from_db()
        if db_result:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            # 変化率を計算
            processed_data = self._calculate_changes(db_result)
            latest = processed_data[-1] if processed_data else None
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
            )

            cache_payload = {
                "data": processed_data,
                "latest": latest,
                "next_release": next_release,
                "last_updated": last_updated
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": processed_data,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "database",
                "last_updated": last_updated
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
                query = text("""
                    SELECT datetime_utc, event, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'US'
                      AND event ILIKE '%Challenger Job Cuts%'
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
                        # イベント名から対象月を抽出（例: "Challenger Job Cuts (Dec)"）
                        match = re.search(r'\((\w{3})\)', event)
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
                            "value": float(actual) if actual else None,
                        })

                print(f"Loaded {len(result)} Challenger Job Cuts records from DB")
                return result

        except Exception as e:
            print(f"Error loading from DB: {e}")
            return []

    def _calculate_changes(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """前月比と前年比を計算"""
        if not data:
            return []

        # 月別インデックスを作成
        month_map = {}
        for item in data:
            # date: "YYYY-MM-01" から年月を抽出
            date_str = item["date"]
            year = int(date_str[:4])
            month = int(date_str[5:7])
            key = (year, month)
            month_map[key] = item["value"]

        result = []
        for item in data:
            date_str = item["date"]
            year = int(date_str[:4])
            month = int(date_str[5:7])
            current_value = item["value"]

            # 前月比（MoM）
            if month == 1:
                prev_month_key = (year - 1, 12)
            else:
                prev_month_key = (year, month - 1)

            prev_month_value = month_map.get(prev_month_key)
            mom = None
            if prev_month_value and prev_month_value != 0 and current_value is not None:
                mom = round((current_value - prev_month_value) / prev_month_value * 100, 1)

            # 前年比（YoY）
            prev_year_key = (year - 1, month)
            prev_year_value = month_map.get(prev_year_key)
            yoy = None
            if prev_year_value and prev_year_value != 0 and current_value is not None:
                yoy = round((current_value - prev_year_value) / prev_year_value * 100, 1)

            result.append({
                "date": date_str,
                "value": current_value,
                "mom": mom,
                "yoy": yoy
            })

        return result

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得（FMPから）"""
        return get_next_release_from_fmp(self.ECONALPHA_ID)

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
            print(f"Challenger Job Cuts cache saved to {DATA_CACHE_FILE}")
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
            "indicator": "Challenger Job Cuts",
            "source": "Database (FMP)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
challenger_job_cuts_service = ChallengerJobCutsService()
