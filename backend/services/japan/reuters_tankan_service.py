"""
ロイター短観サービス (Reuters Tankan)

指標:
- 製造業ロイター短観: CSV (履歴) + DB (FMP蓄積) + FMP (最新値)
- 非製造業ロイター短観: CSV (手動更新) のみ

データソース:
- 製造業: FMP API / DB (economic_calendar_events) / 手動CSV履歴
- 非製造業: 手動CSV（FMPにイベントなし）

CSVパス:
- backend/data/manual_update/monthly/japan/ロイター短観製造業.csv
- backend/data/manual_update/monthly/japan/ロイター短観非製造業.csv

発表スケジュール:
- 月次

キャッシュ方式:
- 製造業: FMP発表日時ベース判定 + CSVファイルmtime
- 非製造業: CSVファイルmtimeのみ
"""
import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.database import SessionLocal
from core.redis_client import redis_client
from services.calendar.fmp_service import fmp_service
from services.japan.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)
from sqlalchemy import text


JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")

CSV_DIR = Path(__file__).parent.parent.parent / "data" / "manual_update" / "monthly" / "japan"
MANUFACTURING_CSV = CSV_DIR / "ロイター短観製造業.csv"
NON_MANUFACTURING_CSV = CSV_DIR / "ロイター短観非製造業.csv"

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "reuters_tankan_cache.json"

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


class ReutersTankanService:
    """ロイター短観サービス"""

    DATA_CACHE_KEY = "japan:economy:reuters_tankan:data"

    ECONALPHA_ID = "reuters_tankan"
    FMP_PATTERN = "Reuters Tankan Index"
    COUNTRY = "JP"

    def __init__(self):
        pass

    def get_reuters_tankan_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        ロイター短観データを取得

        Returns:
            {
                "manufacturing": {"data": [...], "latest": {...}},
                "non_manufacturing": {"data": [...], "latest": {...}},
                "next_release": {...},
                "cached": bool,
                "source": str,
                "last_updated": str,
            }
        """
        next_release = self._get_next_release()

        if not force_refresh:
            cached = redis_client.get(self.DATA_CACHE_KEY)
            if cached:
                last_updated_str = cached.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str, cached):
                    return {
                        "manufacturing": cached.get("manufacturing"),
                        "non_manufacturing": cached.get("non_manufacturing"),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        manufacturing_data = self._load_manufacturing()
        non_manufacturing_data = self._load_non_manufacturing()

        if manufacturing_data or non_manufacturing_data:
            from services.usa.fmp_next_release_utils import guarded_last_updated_nested
            now_str = datetime.now(JST).isoformat()
            _dates = [s[-1].get("date") for s in (manufacturing_data, non_manufacturing_data) if s]
            _new_date = max([d for d in _dates if d], default=None)
            last_updated = guarded_last_updated_nested(
                self.DATA_CACHE_KEY, ("manufacturing", "non_manufacturing"), _new_date, now_str
            )
            cache_payload = {
                "manufacturing": {
                    "data": manufacturing_data,
                    "latest": manufacturing_data[-1] if manufacturing_data else None,
                } if manufacturing_data else None,
                "non_manufacturing": {
                    "data": non_manufacturing_data,
                    "latest": non_manufacturing_data[-1] if non_manufacturing_data else None,
                } if non_manufacturing_data else None,
                "next_release": next_release,
                "csv_mtime": {
                    "manufacturing": self._get_file_mtime(MANUFACTURING_CSV),
                    "non_manufacturing": self._get_file_mtime(NON_MANUFACTURING_CSV),
                },
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "manufacturing": cache_payload["manufacturing"],
                "non_manufacturing": cache_payload["non_manufacturing"],
                "next_release": next_release,
                "cached": False,
                "source": "csv+fmp+db",
                "last_updated": cache_payload["last_updated"],
            }

        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "manufacturing": file_cache.get("manufacturing"),
                "non_manufacturing": file_cache.get("non_manufacturing"),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "manufacturing": None,
            "non_manufacturing": None,
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_manufacturing(self) -> List[Dict[str, Any]]:
        """製造業ロイター短観をCSV + DB + FMPからマージ"""
        result: List[Dict[str, Any]] = []

        csv_data = self._load_from_csv(MANUFACTURING_CSV)
        result.extend(csv_data)

        db_data = self._load_from_db(self.FMP_PATTERN)
        result.extend(db_data)

        fmp_data = self._fetch_from_fmp(self.FMP_PATTERN)
        result.extend(fmp_data)

        merged: Dict[str, Dict[str, Any]] = {}
        for item in result:
            merged[item["date"]] = item

        return sorted(merged.values(), key=lambda x: x["date"])

    def _load_non_manufacturing(self) -> List[Dict[str, Any]]:
        """非製造業ロイター短観をCSVのみから取得"""
        return self._load_from_csv(NON_MANUFACTURING_CSV)

    def _load_from_csv(self, csv_path: Path) -> List[Dict[str, Any]]:
        """
        CSVファイルからデータを読み込み

        CSV形式: 公表日,時間,結果,予想,前回
        例: 2026/5,,8,,
        """
        result: List[Dict[str, Any]] = []

        if not csv_path.exists():
            print(f"[ReutersTankan] CSV file not found: {csv_path}")
            return result

        try:
            import csv as csv_module
            for encoding in ("utf-8-sig", "utf-8", "cp932", "shift-jis"):
                attempt: List[Dict[str, Any]] = []
                try:
                    with open(csv_path, "r", encoding=encoding) as f:
                        reader = csv_module.DictReader(f)
                        for row in reader:
                            date_str = (row.get("公表日") or "").strip()
                            value_str = (row.get("結果") or "").strip()
                            forecast_str = (row.get("予想") or "").strip()
                            previous_str = (row.get("前回") or "").strip()

                            if not date_str or not value_str:
                                continue

                            parts = date_str.split("/")
                            if len(parts) != 2:
                                continue
                            try:
                                year = int(parts[0])
                                month = int(parts[1])
                                date_formatted = f"{year:04d}-{month:02d}-01"
                            except ValueError:
                                continue

                            try:
                                value = float(value_str)
                            except ValueError:
                                continue

                            forecast = self._safe_float(forecast_str)
                            previous = self._safe_float(previous_str)

                            attempt.append({
                                "date": date_formatted,
                                "value": value,
                                "forecast": forecast,
                                "previous": previous,
                            })
                    result = attempt
                    break
                except UnicodeDecodeError:
                    continue

            print(f"[ReutersTankan] Loaded {len(result)} records from CSV: {csv_path.name}")

        except Exception as e:
            print(f"[ReutersTankan] Error loading from CSV {csv_path}: {e}")
            import traceback
            traceback.print_exc()

        return result

    def _load_from_db(self, pattern: str) -> List[Dict[str, Any]]:
        """DBから履歴データを取得（製造業のみ）"""
        result: List[Dict[str, Any]] = []

        try:
            with SessionLocal() as session:
                # ASC で取得し、同月複数行(改定値)があれば後勝ち (= 最新発表が勝つ)
                query = text("""
                    SELECT datetime_utc, event, event_period, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = :country
                      AND LOWER(event) LIKE LOWER(:pattern)
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                    LIMIT 500
                """)
                rows = session.execute(query, {
                    "country": self.COUNTRY,
                    "pattern": f"%{pattern}%",
                }).fetchall()

                by_date: Dict[str, Dict[str, Any]] = {}
                for row in rows:
                    dt_utc, event, period, actual, estimate, previous = row
                    if not dt_utc:
                        continue
                    date_str = self._extract_target_month(event, dt_utc)
                    by_date[date_str] = {
                        "date": date_str,
                        "value": float(actual) if actual is not None else None,
                        "forecast": float(estimate) if estimate is not None else None,
                        "previous": float(previous) if previous is not None else None,
                    }
                result = list(by_date.values())

        except Exception as e:
            print(f"[ReutersTankan] Error loading from DB: {e}")

        return result

    def _fetch_from_fmp(self, pattern: str) -> List[Dict[str, Any]]:
        """FMPから最新データを取得し、DBに保存"""
        result: List[Dict[str, Any]] = []

        try:
            today = date.today()
            events = fmp_service.fetch_calendar(
                today - timedelta(days=90),
                today + timedelta(days=60),
                country=self.COUNTRY,
            )

            for event in events:
                if event.get("country") != self.COUNTRY:
                    continue

                event_name = event.get("event", "")
                if pattern.lower() not in event_name.lower():
                    continue

                actual = event.get("actual")
                if actual is None:
                    continue

                dt_utc, _ = fmp_service.parse_datetime(event.get("date", ""))
                if not dt_utc:
                    continue

                date_str = self._extract_target_month(event_name, dt_utc)
                result.append({
                    "date": date_str,
                    "value": float(actual),
                    "forecast": float(event.get("estimate")) if event.get("estimate") is not None else None,
                    "previous": float(event.get("previous")) if event.get("previous") is not None else None,
                })

                self._save_to_db(event)

        except Exception as e:
            print(f"[ReutersTankan] Error fetching from FMP: {e}")

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
            print(f"[ReutersTankan] Error saving to DB: {e}")

    def _extract_target_month(self, event_name: Optional[str], dt_utc: datetime) -> str:
        """イベント名から対象月を抽出（例: "Reuters Tankan Index (May)" → 2026-05-01）"""
        if event_name:
            match = re.search(r"\((\w{3})\)", event_name)
            if match:
                month_abbr = match.group(1).lower()
                if month_abbr in MONTH_MAP:
                    target_month = MONTH_MAP[month_abbr]
                    target_year = dt_utc.year
                    if target_month > dt_utc.month:
                        target_year -= 1
                    return f"{target_year:04d}-{target_month:02d}-01"
        return dt_utc.strftime("%Y-%m-01")

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """FMPから次回発表日を取得（製造業向け）"""
        try:
            return get_next_release_from_fmp(self.ECONALPHA_ID)
        except Exception as e:
            print(f"[ReutersTankan] Error getting next release: {e}")
            return None

    def _should_refresh(self, last_updated_str: str, cached: Dict[str, Any]) -> bool:
        """
        キャッシュを更新すべきか判定

        判定基準:
        1. CSVファイルのmtime変化 (manual_update検知)
        2. FMP発表スケジュール (製造業)
        """
        try:
            cached_mtimes = cached.get("csv_mtime") or {}
            for csv_path, key in (
                (MANUFACTURING_CSV, "manufacturing"),
                (NON_MANUFACTURING_CSV, "non_manufacturing"),
            ):
                current_mtime = self._get_file_mtime(csv_path)
                cached_mtime = cached_mtimes.get(key)
                if current_mtime is None:
                    continue
                if cached_mtime is None or abs(current_mtime - cached_mtime) > 0.01:
                    print(f"[ReutersTankan] CSV mtime changed ({key}), refreshing")
                    return True

            if should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str):
                return True

            return False

        except Exception as e:
            print(f"[ReutersTankan] Error checking refresh: {e}")
            return True

    def _get_file_mtime(self, csv_path: Path) -> Optional[float]:
        """CSVファイルの更新日時を取得"""
        try:
            if csv_path.exists():
                return os.path.getmtime(csv_path)
        except Exception:
            pass
        return None

    def _safe_float(self, value: str) -> Optional[float]:
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ReutersTankan] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ReutersTankan] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        mfg_count = 0
        non_mfg_count = 0
        if cached_data:
            mfg = cached_data.get("manufacturing")
            non_mfg = cached_data.get("non_manufacturing")
            mfg_count = len(mfg.get("data", [])) if mfg else 0
            non_mfg_count = len(non_mfg.get("data", [])) if non_mfg else 0

        return {
            "indicator": "ロイター短観 (Reuters Tankan)",
            "source": "Reuters / FMP / 手動CSV",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": {
                "manufacturing": mfg_count,
                "non_manufacturing": non_mfg_count,
            },
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
reuters_tankan_service = ReutersTankanService()
