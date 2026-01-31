"""
UK GfK消費者信頼感指数サービス
DBからConsumer Confidenceデータを取得

指標:
- GfK Consumer Confidence（原数値）

データソース:
- DB: economic_calendar_events（FMP蓄積データ）
- CSV: 過去データインポート

発表スケジュール:
- 毎月13日〜翌月8日
- 8:01-9:11 ロンドン時間

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "gfk_consumer_confidence_cache.json"


class GfKConsumerConfidenceService:
    """UK GfK消費者信頼感指数サービス"""

    DATA_CACHE_KEY = "uk:gfk_consumer_confidence:data"
    ECONALPHA_ID = "uk_gfk_consumer_confidence"

    # FMPカレンダー検索パターン
    FMP_EVENT_PATTERNS = ["Consumer Confidence"]

    def __init__(self):
        pass

    def get_gfk_consumer_confidence_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """GfK消費者信頼感指数データを取得"""
        # 次回発表日を取得
        next_release = self._get_next_release()

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
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

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得 - FMPカレンダーから検索"""
        try:
            from services.uk.fmp_next_release_utils import get_next_release_by_pattern

            # 複数のパターンで検索し、最も近いものを返す
            candidates = []
            for pattern in self.FMP_EVENT_PATTERNS:
                result = get_next_release_by_pattern(pattern, country="GB")
                if result:
                    candidates.append(result)

            if candidates:
                # 日付が最も近いものを選択
                candidates.sort(key=lambda x: x.get("date", ""))
                return candidates[0]

            return None
        except Exception as e:
            print(f"[GfK Consumer Confidence] Error getting next release: {e}")
            return None

    # 月名から月番号へのマッピング
    MONTH_MAP = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4,
        "may": 5, "jun": 6, "jul": 7, "aug": 8,
        "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }

    def _parse_target_month(self, event_name: str, datetime_utc: datetime) -> str:
        """
        イベント名から対象月を抽出してYYYY-MM-01形式で返す

        例: "Consumer Confidence (Jan)" + 2026-01-23 → "2026-01-01"
            "Consumer Confidence" + 2026-01-01 → "2025-12-01"（発表月の前月）
        """
        from dateutil.relativedelta import relativedelta

        # "Consumer Confidence (Mon)" パターンを検索
        match = re.search(r'\((\w{3})\)', event_name)
        if match:
            month_abbr = match.group(1).lower()
            if month_abbr in self.MONTH_MAP:
                target_month = self.MONTH_MAP[month_abbr]
                year = datetime_utc.year
                # 1月に前年12月のデータが発表される場合
                if datetime_utc.month == 1 and target_month == 12:
                    year -= 1
                return f"{year}-{target_month:02d}-01"

        # パターンがない場合（Consumer Confidenceなど）は発表月の前月を対象とする
        data_month = datetime_utc - relativedelta(months=1)
        return data_month.strftime("%Y-%m-01")

    def _load_from_db(self) -> List[Dict[str, Any]]:
        """DBから履歴データを取得

        注意: FMPイベント名に月名がある場合はその月を使用
              月名がない場合は発表月-1ヶ月をデータ対象月とする
        """
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                # datetime_utc DESCで取得して、より新しい発表データを優先する
                query = text("""
                    SELECT datetime_utc, event, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'UK'
                      AND event ILIKE '%Consumer Confidence%'
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc DESC
                """)
                rows = session.execute(query).fetchall()

                result = []
                seen_dates = set()

                for row in rows:
                    dt_utc, event_name, actual, estimate, previous = row
                    if dt_utc:
                        # イベント名から対象月を抽出
                        date_str = self._parse_target_month(event_name, dt_utc)

                        if date_str in seen_dates:
                            # 同じ対象月のデータが既にある場合はスキップ
                            # （新しい発表データを優先するためDESC順で取得）
                            continue
                        seen_dates.add(date_str)

                        result.append({
                            "date": date_str,
                            "value": float(actual) if actual else None,
                            "forecast": float(estimate) if estimate else None,
                            "previous": float(previous) if previous else None,
                        })

                # 日付でソート（ASC）
                result.sort(key=lambda x: x["date"])

                print(f"[GfK Consumer Confidence] Loaded {len(result)} records from DB")
                return result

        except Exception as e:
            print(f"[GfK Consumer Confidence] Error loading from DB: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        ロジック:
        - 7日以上経過していれば更新
        - FMPの発表日付近は頻繁にチェック
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            hours_since_update = (now - last_updated).total_seconds() / 3600

            # 7日以上経過していれば更新
            if hours_since_update >= 24 * 7:
                return True

            # FMPパターンベースの更新判定
            try:
                from services.uk.fmp_next_release_utils import should_refresh_by_pattern
                for pattern in self.FMP_EVENT_PATTERNS:
                    if should_refresh_by_pattern(pattern, last_updated_str, country="GB"):
                        print(f"[GfK Consumer Confidence] FMP pattern '{pattern}' indicates refresh needed")
                        return True
            except Exception as e:
                print(f"[GfK Consumer Confidence] Error checking FMP refresh: {e}")

            return False

        except Exception as e:
            print(f"[GfK Consumer Confidence] Error in should_refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[GfK Consumer Confidence] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[GfK Consumer Confidence] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "GfK Consumer Confidence",
            "source": "Database (FMP)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
gfk_consumer_confidence_service = GfKConsumerConfidenceService()
