"""
ドイツGfK消費者信頼感指数サービス
DBからGfK Consumer Confidenceデータを取得

指標:
- ドイツGfK消費者信頼感指数（翌月予測）

データソース:
- DB: economic_calendar_events（CSV + FMP蓄積データ）
- CSV: 過去データインポート

発表スケジュール:
- 毎月下旬（不定期）
- 翌月のドイツ消費者信頼感を予測

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.eurozone.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")
CET = ZoneInfo("Europe/Berlin")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "germany_consumer_confidence_gfk_cache.json"


class GermanyConsumerConfidenceGfKService:
    """ドイツGfK消費者信頼感指数サービス"""

    DATA_CACHE_KEY = "eurozone:germany_consumer_confidence_gfk:data"
    ECONALPHA_ID = "germany_consumer_confidence_gfk"
    FMP_COUNTRY = "DE"
    FMP_EVENT_PATTERN = "Consumer Confidence"

    def __init__(self):
        pass

    def get_germany_consumer_confidence_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        ドイツGfK消費者信頼感指数データを取得

        Returns:
            {
                "data": [...],  # データ配列
                "latest": {...},  # 最新値
                "metadata": {...},
                "next_release": {...},
                "cached": bool,
                "source": str
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
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # DBから取得
        db_result = self._load_from_db()

        if db_result:
            next_release = get_next_release_by_pattern(
                self.FMP_EVENT_PATTERN,
                country=self.FMP_COUNTRY
            )

            # 最新値を取得
            latest = db_result[-1] if db_result else None

            from services.usa.fmp_next_release_utils import guarded_last_updated
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
            )
            cache_payload = {
                "data": db_result,
                "latest": latest,
                "metadata": {
                    "source": "GfK",
                    "country": "Germany (DE)",
                    "description": "ドイツGfK消費者信頼感指数（翌月予測）",
                    "unit": "pt",
                    "note": "翌月の消費者信頼感予測値。0を上回ると消費意欲が高い状態を示す。",
                },
                "next_release": next_release,
                "last_updated": last_updated,
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
                "last_updated": last_updated,
            }

        # ファイルキャッシュフォールバック
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
            "error": "No data available",
        }

    # 月名から月番号へのマッピング
    MONTH_MAP = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4,
        "may": 5, "jun": 6, "jul": 7, "aug": 8,
        "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }

    def _parse_target_month(self, event_name: str, datetime_utc: datetime) -> str:
        """
        イベント名から対象月を抽出してYYYY-MM-01形式で返す

        例: "Consumer Confidence (Feb)" + 2026-01-28 → "2026-02-01"
            "GfK Consumer Confidence" + 2026-01-01 → "2026-01-01"（発表月をそのまま使用）
        """
        # "Consumer Confidence (Mon)" パターンを検索
        match = re.search(r'\((\w{3})\)', event_name)
        if match:
            month_abbr = match.group(1).lower()
            if month_abbr in self.MONTH_MAP:
                target_month = self.MONTH_MAP[month_abbr]
                year = datetime_utc.year
                # 12月に翌年1月のデータが発表される場合
                if datetime_utc.month == 12 and target_month == 1:
                    year += 1
                return f"{year}-{target_month:02d}-01"

        # パターンがない場合（GfK Consumer Confidenceなど）は発表月の翌月を対象とする
        # GfKは翌月予測なので、発表月+1
        year = datetime_utc.year
        month = datetime_utc.month + 1
        if month > 12:
            month = 1
            year += 1
        return f"{year}-{month:02d}-01"

    @staticmethod
    def _prior_month(date_str: str) -> str:
        """'YYYY-MM-01' の1か月前を 'YYYY-MM-01' で返す"""
        year, month, _ = date_str.split("-")
        year, month = int(year), int(month)
        month -= 1
        if month < 1:
            month = 12
            year -= 1
        return f"{year}-{month:02d}-01"

    def _load_from_db(self) -> List[Dict[str, Any]]:
        """DBから履歴データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                # GfK Consumer Confidence または Consumer Confidence でドイツのイベントを取得
                # イベント名も取得して対象月を判定する
                # datetime_utc DESCで取得して、より新しい発表データを優先する
                query = text("""
                    SELECT datetime_utc, event, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'DE'
                      AND (
                          event ILIKE '%GfK Consumer Confidence%'
                          OR event ILIKE '%Consumer Confidence%'
                      )
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc DESC
                """)
                rows = session.execute(query).fetchall()

                result_map: Dict[str, Dict[str, Any]] = {}  # date_str -> データ点（自身のactual）
                revision_map: Dict[str, float] = {}         # 前月 date_str -> 改定値（翌月発表のprevious）
                seen_dates = set()
                seen_revisions = set()

                for row in rows:  # DESC順（新しい発表が先）
                    dt_utc, event_name, actual, estimate, previous = row
                    if not dt_utc:
                        continue

                    # イベント名から対象月を抽出（翌月予測のため）
                    date_str = self._parse_target_month(event_name, dt_utc)

                    # 各対象月のデータ点（新しい発表を優先）
                    if date_str not in seen_dates:
                        seen_dates.add(date_str)
                        result_map[date_str] = {
                            "date": date_str,
                            "value": float(actual) if actual is not None else None,
                            "forecast": float(estimate) if estimate is not None else None,
                            "previous": float(previous) if previous is not None else None,
                        }

                    # GfKは翌月予測の発表時に前月を改定する。previous は対象月-1（前月）の
                    # 改定値なので、前月のデータ点に書き戻す（最新発表の previous を優先）。
                    if previous is not None:
                        prior_date = self._prior_month(date_str)
                        if prior_date not in seen_revisions:
                            seen_revisions.add(prior_date)
                            revision_map[prior_date] = float(previous)

                # 改定適用: 前月以前の value を確報値（翌月発表の previous）で上書き。
                # 該当月のデータ点が存在する場合のみ（previous だけの幻の月は作らない）。
                applied = 0
                for prior_date, revised in revision_map.items():
                    point = result_map.get(prior_date)
                    if point is not None and point.get("value") != revised:
                        point["value"] = revised
                        applied += 1

                result = sorted(result_map.values(), key=lambda x: x["date"])

                print(
                    f"[GermanyConsumerConfidenceGfK] Loaded {len(result)} records from DB "
                    f"({applied} prior-month revisions applied)"
                )
                return result

        except Exception as e:
            print(f"[GermanyConsumerConfidenceGfK] Error loading from DB: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_pattern(
            self.FMP_EVENT_PATTERN,
            last_updated_str,
            country=self.FMP_COUNTRY
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            return cached
        except Exception as e:
            print(f"[GermanyConsumerConfidenceGfK] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[GermanyConsumerConfidenceGfK] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Germany GfK Consumer Confidence",
            "source": "Database (CSV + FMP)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(
                self.FMP_EVENT_PATTERN,
                country=self.FMP_COUNTRY
            ),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
germany_consumer_confidence_gfk_service = GermanyConsumerConfidenceGfKService()
