"""
韓国輸出（前年比）サービス
DBから韓国輸出YoYデータを取得

指標:
- Exports YoY (South Korea): 韓国輸出（前年比）

データソース:
- DB: economic_calendar_events（CSV過去データ + FMP蓄積データ）
- 原典: MOTIR (Ministry of Trade, Industry and Resources)

発表スケジュール:
- 月初に速報値、月中旬に確報値が発表
- 同一月のデータは確報値（後のレコード）で上書き

キャッシュ方式: FMP発表日時ベース判定方式

注意事項:
- country='KR'でフィルタリング
- 速報値と確報値がある場合は確報値で上書き（datetime_utc昇順で後のレコードが優先）
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
    resolve_last_updated_after_fetch,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "global" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "south_korean_exports_cache.json"


class SouthKoreanExportsService:
    """韓国輸出（前年比）サービス"""

    DATA_CACHE_KEY = "global:south_korean_exports:data"
    ECONALPHA_ID = "south_korean_exports"

    # DBクエリ用のイベントパターン
    EVENT_PATTERNS = ["Exports YoY"]

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """韓国輸出データを取得"""

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
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # 取得前の最新月（発表時刻レース ラグガード用）
        prev_cache = redis_client.get(self.DATA_CACHE_KEY) or {}
        prev_latest_date = (prev_cache.get("latest") or {}).get("date")
        prev_last_updated = prev_cache.get("last_updated")

        # DBから取得
        data = self._load_from_db()

        if data:
            latest = data[-1] if data else None
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            metadata = {
                "source": "MOTIR (Ministry of Trade, Industry and Resources)",
                "indicator": "South Korean Exports YoY",
                "description": "韓国輸出（前年比）",
                "unit": "%",
                "frequency": "monthly",
            }

            # 発表時刻レース対策: 取得データが新月に未反映（FMP actual 遅延）なら
            # last_updated を発表直前に据え置き、次回ポーリングで再取得を促す。
            # データ前進時は now を返す。
            new_latest_date = (latest or {}).get("date")
            resolved_last_updated = resolve_last_updated_after_fetch(
                self.ECONALPHA_ID, new_latest_date, prev_latest_date, prev_last_updated,
            )

            cache_payload = {
                "data": data,
                "latest": latest,
                "metadata": metadata,
                "next_release": next_release,
                "last_updated": resolved_last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                **cache_payload,
                "cached": False,
                "source": "database",
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
        }

    def _load_from_db(self) -> List[Dict[str, Any]]:
        """DBから履歴データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text
            import re

            with SessionLocal() as session:
                # country='KR'でフィルタリング
                pattern_conditions = " OR ".join(
                    [f"event ILIKE :pattern{i}" for i in range(len(self.EVENT_PATTERNS))]
                )
                query = text(f"""
                    SELECT datetime_utc, event, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'KR'
                      AND ({pattern_conditions})
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)

                params = {}
                for i, pattern in enumerate(self.EVENT_PATTERNS):
                    params[f"pattern{i}"] = f"%{pattern}%"

                rows = session.execute(query, params).fetchall()

                result = []

                # 月名から月番号へのマッピング
                month_map = {
                    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                }

                for row in rows:
                    dt_utc, event, actual, estimate, previous = row
                    if dt_utc:
                        # イベント名から対象月を抽出（例: "Exports YoY (Oct)"）
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
                                prev_month = dt_utc.month - 1 if dt_utc.month > 1 else 12
                                prev_year = dt_utc.year if dt_utc.month > 1 else dt_utc.year - 1
                                date_str = f"{prev_year}-{prev_month:02d}-01"
                        else:
                            # 括弧内に月がない場合はCSVインポートデータ
                            # datetime_utcはJST→UTC変換されているためJSTに戻して月を取得
                            dt_jst = dt_utc.astimezone(JST) if dt_utc.tzinfo else dt_utc.replace(tzinfo=ZoneInfo("UTC")).astimezone(JST)
                            date_str = f"{dt_jst.year}-{dt_jst.month:02d}-01"

                        # 速報値と確報値がある場合、確報値（後のレコード）で上書き
                        existing_idx = None
                        for i, existing in enumerate(result):
                            if existing["date"] == date_str:
                                existing_idx = i
                                break

                        data_point = {
                            "date": date_str,
                            "value": float(actual) if actual else None,
                            "forecast": float(estimate) if estimate else None,
                            "previous": float(previous) if previous else None,
                        }

                        if existing_idx is not None:
                            result[existing_idx] = data_point
                        else:
                            result.append(data_point)

                print(f"[SouthKoreanExports] Loaded {len(result)} records from DB")
                return result

        except Exception as e:
            print(f"[SouthKoreanExports] Error loading from DB: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP 3分方式）"""
        return should_refresh_by_fmp_schedule(
            self.ECONALPHA_ID,
            last_updated_str
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[SouthKoreanExports] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[SouthKoreanExports] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        data_count = 0
        latest_date = None
        if cached_data:
            data_count = len(cached_data.get("data", []))
            latest_date = cached_data.get("latest", {}).get("date") if cached_data.get("latest") else None

        return {
            "indicator": "South Korean Exports YoY",
            "source": "Database (CSV + FMP)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "latest_date": latest_date,
            "data_count": data_count,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
south_korean_exports_service = SouthKoreanExportsService()
