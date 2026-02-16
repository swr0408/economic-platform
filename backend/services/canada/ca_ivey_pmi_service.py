"""
カナダ Ivey PMI サービス

指標:
- Ivey Purchasing Managers Index (季節調整済) — 景況感指数

データソース:
- CSV履歴データ (backend/data/csv_import/IveyPMI.csv)
- DB蓄積 (economic_calendar_events)
- FMP API (最新値)

発表スケジュール:
- 毎月上旬
- FMPパターン: "Ivey PMI s.a"

値の解釈:
- 50超 = 景気拡大、50未満 = 景気縮小
"""
import json
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.database import SessionLocal
from core.redis_client import redis_client
from services.calendar.fmp_service import fmp_service
from services.canada.fmp_next_release_utils import get_next_release_by_pattern, should_refresh_by_pattern
from sqlalchemy import text


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")
TORONTO = ZoneInfo("America/Toronto")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "canada" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ca_ivey_pmi_cache.json"

# CSVデータ
CSV_DIR = Path(__file__).parent.parent.parent / "data" / "csv_import"
IVEY_PMI_CSV = CSV_DIR / "IveyPMI.csv"

# FMPパターン
FMP_PATTERN = "Ivey PMI s.a"
COUNTRY = "CA"

MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}


class CaIveyPmiService:
    """カナダ Ivey PMI サービス（CSV + DB + FMP方式）"""

    DATA_CACHE_KEY = "canada:ca_ivey_pmi:data"

    def __init__(self):
        pass

    def get_ca_ivey_pmi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Ivey PMIデータを取得"""
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

        # データを取得（CSV + DB + FMP マージ）
        data = self._load_all_data()

        latest = data[-1] if data else None

        cache_payload = {
            "data": data,
            "latest": latest,
            "metadata": {
                "source": "Ivey Business School",
                "indicator": "Ivey Purchasing Managers Index",
                "description": "Ivey PMI（季節調整済）",
                "unit": "index",
                "frequency": "monthly",
                "threshold": 50,
            },
            "last_updated": datetime.now(JST).isoformat(),
        }
        redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
        self._save_file_cache(cache_payload)

        return {
            "data": data,
            "latest": latest,
            "metadata": cache_payload["metadata"],
            "next_release": next_release,
            "cached": False,
            "source": "csv+db+fmp",
            "last_updated": datetime.now(JST).isoformat(),
        }

    def _load_all_data(self) -> List[Dict[str, Any]]:
        """CSV + DB + FMP からデータを取得しマージ"""
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
            print(f"[CaIveyPmi] Loaded {len(result)} records (merged)")

        except Exception as e:
            print(f"[CaIveyPmi] Error loading data: {e}")
            import traceback
            traceback.print_exc()

        return result

    def _load_from_csv(self) -> List[Dict[str, Any]]:
        """CSVファイルから履歴データを読み込む"""
        result = []

        try:
            if not IVEY_PMI_CSV.exists():
                print(f"[CaIveyPmi] CSV file not found: {IVEY_PMI_CSV}")
                return result

            import csv
            with open(IVEY_PMI_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    date_str = row.get("公表日", "").strip()
                    value_str = row.get("結果", "").strip()

                    if not date_str or not value_str:
                        continue

                    # 日付を変換 (2011/6 -> 2011-06-01)
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

            print(f"[CaIveyPmi] Loaded {len(result)} records from CSV")

        except Exception as e:
            print(f"[CaIveyPmi] Error loading from CSV: {e}")
            import traceback
            traceback.print_exc()

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
                        event_period,
                        actual,
                        estimate,
                        previous
                    FROM economic_calendar_events
                    WHERE country = :country
                      AND LOWER(event) LIKE LOWER(:pattern)
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc DESC
                    LIMIT 500
                """)

                rows = session.execute(query, {
                    "country": COUNTRY,
                    "pattern": f"%{FMP_PATTERN}%"
                }).fetchall()

                for row in rows:
                    dt_utc, event, period, actual, estimate, previous = row

                    if not dt_utc:
                        continue

                    # イベント名から対象月を抽出 (例: "Ivey PMI s.a (Dec)")
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

            print(f"[CaIveyPmi] Loaded {len(result)} records from DB")

        except Exception as e:
            print(f"[CaIveyPmi] Error loading from DB: {e}")

        return result

    def _fetch_from_fmp(self) -> List[Dict[str, Any]]:
        """FMPから最新データを取得"""
        result = []

        try:
            today = date.today()
            from_date = today - timedelta(days=90)
            to_date = today + timedelta(days=60)

            events = fmp_service.fetch_calendar(from_date, to_date, country=COUNTRY)

            for event in events:
                if event.get("country") != COUNTRY:
                    continue

                event_name = event.get("event", "")
                if FMP_PATTERN.lower() not in event_name.lower():
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

            print(f"[CaIveyPmi] Fetched {len(result)} records from FMP")

        except Exception as e:
            print(f"[CaIveyPmi] Error fetching from FMP: {e}")

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
            print(f"[CaIveyPmi] Error saving to DB: {e}")

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得"""
        try:
            return get_next_release_by_pattern(FMP_PATTERN, country=COUNTRY)
        except Exception as e:
            print(f"[CaIveyPmi] Error getting next release: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            return should_refresh_by_pattern(FMP_PATTERN, last_updated_str, country=COUNTRY)
        except Exception:
            # FMPパターンチェック失敗時は時間ベースのフォールバック
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
            print(f"[CaIveyPmi] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaIveyPmi] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        next_release = self._get_next_release()

        return {
            "indicator": "Canada Ivey PMI",
            "source": "Ivey Business School / FMP",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": next_release,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ca_ivey_pmi_service = CaIveyPmiService()
