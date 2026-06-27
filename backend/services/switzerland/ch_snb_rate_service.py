"""
スイス政策金利（SNB Interest Rate Decision）サービス
DBからSNB政策金利データを取得

指標:
- SNB政策金利（Swiss National Bank Policy Rate）

データソース:
- DB: economic_calendar_events（FMP蓄積データ）
- CSV: 過去データインポート

発表スケジュール:
- 不定期（年4回程度、四半期ごと）
- 発表時刻: 08:30 チューリッヒ時間

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.switzerland.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
    resolve_last_updated_after_fetch,
)


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "switzerland" / "monetary_policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ch_snb_rate_cache.json"


class ChSnbRateService:
    """スイス政策金利サービス"""

    DATA_CACHE_KEY = "switzerland:ch_snb_rate:data"
    ECONALPHA_ID = "ch_snb_rate"
    FMP_EVENT_PATTERN = "SNB Interest Rate Decision"

    def __init__(self):
        pass

    def get_ch_snb_rate_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """SNB政策金利データを取得"""
        # 次回発表日を取得
        next_release = get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country="CH")

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

            # 発表時刻レース対策（ラグガード）: 最新会合日が前回から進んでいない
            # （FMP actual未populate等）場合は last_updated を発表直前に据え置き、
            # 反映後の次ポーリングでの再取得を促す。
            _prev_cache = redis_client.get(self.DATA_CACHE_KEY)
            _prev_latest = _prev_cache.get("latest") if isinstance(_prev_cache, dict) else None
            _resolved_last_updated = resolve_last_updated_after_fetch(
                self.FMP_EVENT_PATTERN,
                latest.get("date") if isinstance(latest, dict) else None,
                _prev_latest.get("date") if isinstance(_prev_latest, dict) else None,
                _prev_cache.get("last_updated") if isinstance(_prev_cache, dict) else None,
                country="CH",
            )

            cache_payload = {
                "data": db_result,
                "latest": latest,
                "metadata": {
                    "source": "Swiss National Bank",
                    "indicator": "SNB Policy Rate",
                    "description": "スイス国立銀行政策金利",
                },
                "last_updated": _resolved_last_updated,
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
                "last_updated": _resolved_last_updated,
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
            "metadata": {},
            "next_release": next_release,
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
                    SELECT datetime_utc, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'CH'
                      AND event ILIKE '%SNB Interest Rate Decision%'
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query).fetchall()

                result = []
                seen_dates = set()

                for row in rows:
                    dt_utc, actual, estimate, previous = row
                    if dt_utc:
                        # 発表日をそのまま使用（政策金利は日次データ）
                        date_str = dt_utc.strftime("%Y-%m-%d")
                        if date_str in seen_dates:
                            continue
                        seen_dates.add(date_str)

                        result.append({
                            "date": date_str,
                            "value": float(actual) if actual is not None else None,
                            "forecast": float(estimate) if estimate is not None else None,
                            "previous": float(previous) if previous is not None else None,
                        })

                print(f"[ChSnbRate] Loaded {len(result)} records from DB")
                return result

        except Exception as e:
            print(f"[ChSnbRate] Error loading from DB: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日ベース）"""
        return should_refresh_by_pattern(
            self.FMP_EVENT_PATTERN,
            last_updated_str,
            country="CH"
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ChSnbRate] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ChSnbRate] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "SNB Policy Rate",
            "source": "Swiss National Bank",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country="CH"),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ch_snb_rate_service = ChSnbRateService()
