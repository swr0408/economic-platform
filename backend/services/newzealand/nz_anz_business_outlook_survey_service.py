"""
NZ ANZ企業景況感指数（Business Confidence）サービス

指標:
- ANZ Business Confidence: 企業の景況感を示す指数

データソース:
- CSV履歴データ (backend/data/csv_import/ANZ企業景況感指数.csv)
- DB蓄積 (economic_calendar_events)
- FMP API (最新値)

FMPマッピング:
- ANZ Business Confidence (econalpha_id: nz_anz_corporate business_sentiment)

発表スケジュール: 毎月
"""
import csv
import json
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.database import SessionLocal
from core.redis_client import redis_client
from services.calendar.fmp_service import fmp_service
from services.newzealand.fmp_next_release_utils import get_next_release_by_pattern, should_refresh_by_pattern
from sqlalchemy import text


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")
AUCKLAND = ZoneInfo("Pacific/Auckland")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "newzealand" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "nz_anz_business_outlook_survey_cache.json"

# CSVデータ
CSV_DIR = Path(__file__).parent.parent.parent / "data" / "csv_import"
CSV_FILE = CSV_DIR / "ANZ企業景況感指数.csv"

# FMPパターン
FMP_EVENT_PATTERN = "ANZ Business Confidence"
FMP_COUNTRY = "NZ"

MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}


class NzAnzBusinessOutlookSurveyService:
    """NZ ANZ企業景況感指数サービス（CSV + DB + FMP方式）"""

    DATA_CACHE_KEY = "newzealand:nz_anz_business_outlook_survey:data"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ANZ企業景況感指数データを取得"""
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
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # データ取得（CSV + DB + FMP マージ）
        data = self._load_data()

        latest = data[-1] if data else None
        from services.usa.fmp_next_release_utils import guarded_last_updated
        now_str = datetime.now(JST).isoformat()
        last_updated = guarded_last_updated(
            self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
        )

        metadata = {
            "source": "ANZ",
            "indicator": "ANZ Business Outlook - Business Confidence",
            "description": "ANZ企業景況感指数",
            "unit": "index",
            "frequency": "monthly",
        }

        cache_payload = {
            "data": data,
            "latest": latest,
            "metadata": metadata,
            "last_updated": last_updated,
        }
        redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
        self._save_file_cache(cache_payload)

        return {
            "data": data,
            "latest": latest,
            "metadata": metadata,
            "next_release": next_release,
            "cached": False,
            "source": "csv+db+fmp",
            "last_updated": last_updated,
        }

    def _load_data(self) -> List[Dict[str, Any]]:
        """データを取得しマージ（CSV + DB + FMP）"""
        result = []

        try:
            # 1. CSVから履歴データ
            csv_data = self._load_from_csv()
            result.extend(csv_data)

            # 2. DBから履歴データ
            db_data = self._load_from_db()
            result.extend(db_data)

            # 3. FMPから最新データ
            fmp_data = self._fetch_from_fmp()
            result.extend(fmp_data)

            # 日付でマージ（後から追加されたものを優先）
            merged = {}
            for item in result:
                merged[item["date"]] = item

            result = sorted(merged.values(), key=lambda x: x["date"])
            print(f"[NzAnzBizSurvey] Loaded {len(result)} records (merged)")

        except Exception as e:
            print(f"[NzAnzBizSurvey] Error loading data: {e}")
            import traceback
            traceback.print_exc()

        return result

    def _load_from_csv(self) -> List[Dict[str, Any]]:
        """CSVファイルから履歴データを読み込む"""
        result = []

        try:
            if not CSV_FILE.exists():
                print(f"[NzAnzBizSurvey] CSV file not found: {CSV_FILE}")
                return result

            with open(CSV_FILE, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    date_str = row.get("公表日", "").strip()
                    value_str = row.get("結果", "").strip()

                    if not date_str or not value_str:
                        continue

                    try:
                        parts = date_str.split("/")
                        if len(parts) == 2:
                            year, month = parts
                            date_formatted = f"{year}-{int(month):02d}-01"
                        else:
                            continue
                    except ValueError:
                        continue

                    try:
                        value = float(value_str)
                    except ValueError:
                        continue

                    result.append({
                        "date": date_formatted,
                        "value": round(value, 1),
                    })

            print(f"[NzAnzBizSurvey] Loaded {len(result)} records from CSV")

        except Exception as e:
            print(f"[NzAnzBizSurvey] Error loading from CSV: {e}")

        return result

    def _load_from_db(self) -> List[Dict[str, Any]]:
        """DBから履歴データを取得"""
        result = []

        try:
            with SessionLocal() as session:
                query = text("""
                    SELECT
                        datetime_utc,
                        event,
                        actual,
                        estimate,
                        previous
                    FROM economic_calendar_events
                    WHERE country = :country
                      AND LOWER(event) LIKE LOWER(:pattern)
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)

                rows = session.execute(query, {
                    "country": FMP_COUNTRY,
                    "pattern": f"%{FMP_EVENT_PATTERN}%",
                }).fetchall()

                for row in rows:
                    dt_utc, event, actual, estimate, previous = row

                    if not dt_utc:
                        continue

                    # イベント名から対象月を抽出
                    match = re.search(r'\((\w{3})\)', event) if event else None
                    if match:
                        month_abbr = match.group(1).lower()
                        if month_abbr in MONTH_MAP:
                            target_month = MONTH_MAP[month_abbr]
                            target_year = dt_utc.year
                            if target_month > dt_utc.month:
                                target_year -= 1
                            date_str = f"{target_year}-{target_month:02d}-01"
                        else:
                            date_str = dt_utc.strftime("%Y-%m-01")
                    else:
                        date_str = dt_utc.strftime("%Y-%m-01")

                    result.append({
                        "date": date_str,
                        "value": round(float(actual), 1) if actual else None,
                    })

            print(f"[NzAnzBizSurvey] Loaded {len(result)} records from DB")

        except Exception as e:
            print(f"[NzAnzBizSurvey] Error loading from DB: {e}")

        return result

    def _fetch_from_fmp(self) -> List[Dict[str, Any]]:
        """FMPから最新データを取得"""
        result = []

        try:
            today = date.today()
            from_date = today - timedelta(days=90)
            to_date = today + timedelta(days=60)

            events = fmp_service.fetch_calendar(from_date, to_date, country=FMP_COUNTRY)

            for event in events:
                if event.get("country") != FMP_COUNTRY:
                    continue

                event_name = event.get("event", "")
                if FMP_EVENT_PATTERN.lower() not in event_name.lower():
                    continue

                dt_utc, _ = fmp_service.parse_datetime(event.get("date", ""))
                if not dt_utc:
                    continue

                actual = event.get("actual")
                if actual is None:
                    continue

                # イベント名から対象月を抽出
                match = re.search(r'\((\w{3})\)', event_name)
                if match:
                    month_abbr = match.group(1).lower()
                    if month_abbr in MONTH_MAP:
                        target_month = MONTH_MAP[month_abbr]
                        target_year = dt_utc.year
                        if target_month > dt_utc.month:
                            target_year -= 1
                        date_str = f"{target_year}-{target_month:02d}-01"
                    else:
                        date_str = dt_utc.strftime("%Y-%m-01")
                else:
                    date_str = dt_utc.strftime("%Y-%m-01")

                result.append({
                    "date": date_str,
                    "value": round(float(actual), 1),
                })

                # DBにも保存（蓄積方式）
                self._save_to_db(event)

            print(f"[NzAnzBizSurvey] Fetched {len(result)} records from FMP")

        except Exception as e:
            print(f"[NzAnzBizSurvey] Error fetching from FMP: {e}")

        return result

    def _save_to_db(self, event: dict) -> None:
        """FMPイベントをDBに保存"""
        try:
            processed = fmp_service.process_event(event)

            with SessionLocal() as session:
                query = text("""
                    INSERT INTO economic_calendar_events (
                        provider, event_key, country, currency, event, event_period,
                        datetime_raw, datetime_utc, has_time, impact,
                        previous, estimate, actual, change, change_pct, unit, raw_json
                    ) VALUES (
                        :provider, :event_key, :country, :currency, :event, :event_period,
                        :datetime_raw, :datetime_utc, :has_time, :impact,
                        :previous, :estimate, :actual, :change, :change_pct, :unit, :raw_json
                    )
                    ON CONFLICT (provider, event_key) DO UPDATE SET
                        previous = EXCLUDED.previous,
                        estimate = EXCLUDED.estimate,
                        actual = EXCLUDED.actual,
                        change = EXCLUDED.change,
                        change_pct = EXCLUDED.change_pct,
                        updated_at = NOW()
                """)

                session.execute(query, {
                    "provider": processed["provider"],
                    "event_key": processed["event_key"],
                    "country": processed["country"],
                    "currency": processed["currency"],
                    "event": processed["event"],
                    "event_period": processed["event_period"],
                    "datetime_raw": processed["datetime_raw"],
                    "datetime_utc": processed["datetime_utc"],
                    "has_time": processed["has_time"],
                    "impact": processed["impact"],
                    "previous": processed["previous"],
                    "estimate": processed["estimate"],
                    "actual": processed["actual"],
                    "change": processed["change"],
                    "change_pct": processed["change_pct"],
                    "unit": processed["unit"],
                    "raw_json": json.dumps(processed["raw_json"]),
                })
                session.commit()

        except Exception as e:
            print(f"[NzAnzBizSurvey] Error saving to DB: {e}")

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得"""
        try:
            return get_next_release_by_pattern(FMP_EVENT_PATTERN, country=FMP_COUNTRY)
        except Exception as e:
            print(f"[NzAnzBizSurvey] Error getting next release: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            return should_refresh_by_pattern(FMP_EVENT_PATTERN, last_updated_str, country=FMP_COUNTRY)
        except Exception:
            try:
                last_updated = datetime.fromisoformat(last_updated_str)
                if last_updated.tzinfo is None:
                    last_updated = last_updated.replace(tzinfo=JST)
                now = datetime.now(JST)
                return (now - last_updated).total_seconds() > 86400
            except Exception:
                return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[NzAnzBizSurvey] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[NzAnzBizSurvey] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        next_release = self._get_next_release()

        data_count = 0
        if cached_data:
            data_count = len(cached_data.get("data", []))

        return {
            "indicator": "NZ ANZ Business Outlook - Business Confidence",
            "source": "ANZ / CSV / FMP",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": data_count,
            "next_release": next_release,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
nz_anz_business_outlook_survey_service = NzAnzBusinessOutlookSurveyService()
