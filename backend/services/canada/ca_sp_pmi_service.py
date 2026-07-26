"""
カナダ S&P Global PMI サービス

指標:
- S&P Global Manufacturing PMI: 製造業PMI
- S&P Global Services PMI: サービス業PMI
- S&P Global Composite PMI: 総合PMI

データソース:
- CSV履歴データ (backend/data/csv_import/カナダ*.csv)
- DB蓄積 (economic_calendar_events)
- FMP API (最新値)

発表スケジュール:
- 速報値: 毎月第3週（23日前後）
- 確報値: 毎月第1週（1日前後）

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
from services.canada.fmp_next_release_utils import (
    get_next_release_by_pattern,
    resolve_last_updated_after_fetch,
    should_refresh_by_pattern,
)
from sqlalchemy import text


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")
TORONTO = ZoneInfo("America/Toronto")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "canada" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ca_sp_pmi_cache.json"

# CSVデータ
CSV_DIR = Path(__file__).parent.parent.parent / "data" / "csv_import"
CSV_FILES = {
    "manufacturing": CSV_DIR / "カナダ製造業PMI.csv",
    "services": CSV_DIR / "カナダサービスPMI.csv",
    "composite": CSV_DIR / "カナダ総合PMI.csv",
}

# FMPパターン（country='CA'でフィルタリング）
# FMPでは汎用名で登録されることもあるためフォールバック追加
EVENT_PATTERNS = {
    "manufacturing": ["S&P Global Manufacturing PMI"],
    "services": ["S&P Global Services PMI", "Services PMI"],
    "composite": ["S&P Global Composite PMI"],
}

COUNTRY = "CA"

MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}


class CaSpPmiService:
    """カナダ S&P Global PMI サービス（CSV + DB + FMP方式、3系列）"""

    DATA_CACHE_KEY = "canada:ca_sp_pmi:data"

    def __init__(self):
        pass

    def get_ca_sp_pmi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """S&P Global PMIデータを取得（製造業、サービス業、総合）"""
        next_release = self._get_next_release()

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "manufacturing": cached_data.get("manufacturing"),
                        "services": cached_data.get("services"),
                        "composite": cached_data.get("composite"),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # 3系列それぞれ取得（CSV + DB + FMP マージ）
        manufacturing_data = self._load_series("manufacturing")
        services_data = self._load_series("services")
        composite_data = self._load_series("composite")

        # 欠損検知ガード: 総合PMIが製造業/サービス業より遅れている場合に警告
        # （FMPが総合のactualをNULL配信する事象が過去にあり、製造/サービスは
        #  更新されるため監視が「最新」と誤認しやすい→ログで顕在化させる）
        self._warn_if_composite_lags(manufacturing_data, services_data, composite_data)

        # 発表時刻レース対策: 発表直後の取得でFMP actual未同期の旧月を
        # last_updated=now で保存すると should_refresh が消化済み判定し凍結する。
        # 3系列のうち「最も遅れている系列」の最新月を指紋とし、前回から前進して
        # いなければ last_updated を発表直前に据え置いて再取得を促す。
        prev_cache = redis_client.get(self.DATA_CACHE_KEY) or self._load_file_cache() or {}
        resolved_last_updated = resolve_last_updated_after_fetch(
            [p for pats in EVENT_PATTERNS.values() for p in pats],
            self._min_latest_date([manufacturing_data, services_data, composite_data]),
            self._min_latest_date_from_cache(prev_cache),
            prev_cache.get("last_updated"),
            country=COUNTRY,
        )

        cache_payload = {
            "manufacturing": {
                "data": manufacturing_data,
                "latest": manufacturing_data[-1] if manufacturing_data else None,
            } if manufacturing_data else None,
            "services": {
                "data": services_data,
                "latest": services_data[-1] if services_data else None,
            } if services_data else None,
            "composite": {
                "data": composite_data,
                "latest": composite_data[-1] if composite_data else None,
            } if composite_data else None,
            "last_updated": resolved_last_updated,
        }
        redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
        self._save_file_cache(cache_payload)

        return {
            "manufacturing": cache_payload.get("manufacturing"),
            "services": cache_payload.get("services"),
            "composite": cache_payload.get("composite"),
            "next_release": next_release,
            "cached": False,
            "source": "csv+db+fmp",
            "last_updated": resolved_last_updated,
        }

    @staticmethod
    def _min_latest_date(series_list: List[List[Dict[str, Any]]]) -> Optional[str]:
        """3系列のうち最も遅れている系列の最新月 (YYYY-MM-DD)。全系列前進で初めて前進する。"""
        dates = [s[-1].get("date") for s in series_list if s]
        dates = [d for d in dates if d]
        return min(dates) if dates else None

    @staticmethod
    def _min_latest_date_from_cache(cache: Dict[str, Any]) -> Optional[str]:
        """キャッシュpayload形式から _min_latest_date 相当を求める。"""
        dates = []
        for key in ("manufacturing", "services", "composite"):
            v = cache.get(key)
            latest = v.get("latest") if isinstance(v, dict) else None
            if isinstance(latest, dict) and latest.get("date"):
                dates.append(latest["date"])
        return min(dates) if dates else None

    def _warn_if_composite_lags(
        self,
        manufacturing_data: List[Dict[str, Any]],
        services_data: List[Dict[str, Any]],
        composite_data: List[Dict[str, Any]],
    ) -> None:
        """総合PMIの最新月が製造業/サービス業より古い場合に警告ログを出す。

        FMPが総合PMIのactualをNULLで配信する欠損事象では、製造業/サービス業だけ
        前進し総合が凍結する（CSVシードで補完するが、再発を検知できるようにする）。
        """
        try:
            def _latest(data: List[Dict[str, Any]]) -> Optional[str]:
                return data[-1]["date"] if data else None

            comp_latest = _latest(composite_data)
            peer_latest = max(
                [d for d in (_latest(manufacturing_data), _latest(services_data)) if d],
                default=None,
            )
            if comp_latest and peer_latest and comp_latest < peer_latest:
                print(
                    f"[CaSpPmi] WARNING: Composite PMI lags peers "
                    f"(composite={comp_latest}, manufacturing/services={peer_latest}). "
                    f"FMP may be missing the composite actual; "
                    f"seed data/csv_import/カナダ総合PMI.csv to recover."
                )
        except Exception as e:
            print(f"[CaSpPmi] Error in composite-lag guard: {e}")

    def _load_series(self, pmi_type: str) -> List[Dict[str, Any]]:
        """1つのPMI系列のデータを取得しマージ（CSV + DB + FMP）"""
        result = []

        try:
            # 1. CSVから履歴データ
            csv_data = self._load_from_csv(pmi_type)
            result.extend(csv_data)

            # 2. DBから履歴データ
            db_data = self._load_from_db(pmi_type)
            result.extend(db_data)

            # 3. FMPから最新データ
            fmp_data = self._fetch_from_fmp(pmi_type)
            result.extend(fmp_data)

            # 日付でマージ（後から追加されたものを優先）
            merged = {}
            for item in result:
                merged[item["date"]] = item

            result = sorted(merged.values(), key=lambda x: x["date"])
            print(f"[CaSpPmi] {pmi_type}: Loaded {len(result)} records (merged)")

        except Exception as e:
            print(f"[CaSpPmi] Error loading {pmi_type}: {e}")
            import traceback
            traceback.print_exc()

        return result

    def _load_from_csv(self, pmi_type: str) -> List[Dict[str, Any]]:
        """CSVファイルから履歴データを読み込む"""
        result = []
        csv_file = CSV_FILES.get(pmi_type)

        try:
            if not csv_file or not csv_file.exists():
                print(f"[CaSpPmi] CSV file not found for {pmi_type}: {csv_file}")
                return result

            import csv
            with open(csv_file, "r", encoding="utf-8") as f:
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

            print(f"[CaSpPmi] {pmi_type}: Loaded {len(result)} records from CSV")

        except Exception as e:
            print(f"[CaSpPmi] Error loading {pmi_type} from CSV: {e}")

        return result

    def _load_from_db(self, pmi_type: str) -> List[Dict[str, Any]]:
        """DBから履歴データを取得"""
        result = []
        event_patterns = EVENT_PATTERNS.get(pmi_type)
        if not event_patterns:
            return result

        # リストでない場合はリストに変換
        if isinstance(event_patterns, str):
            event_patterns = [event_patterns]

        try:
            with SessionLocal() as session:
                # 複数パターンをOR条件で結合
                pattern_conditions = " OR ".join(
                    [f"LOWER(event) LIKE LOWER(:pattern{i})" for i in range(len(event_patterns))]
                )
                query = text(f"""
                    SELECT
                        datetime_utc,
                        event,
                        actual,
                        estimate,
                        previous
                    FROM economic_calendar_events
                    WHERE country = :country
                      AND ({pattern_conditions})
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)

                params = {"country": COUNTRY}
                for i, pattern in enumerate(event_patterns):
                    params[f"pattern{i}"] = f"%{pattern}%"

                rows = session.execute(query, params).fetchall()

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

            print(f"[CaSpPmi] {pmi_type}: Loaded {len(result)} records from DB")

        except Exception as e:
            print(f"[CaSpPmi] Error loading {pmi_type} from DB: {e}")

        return result

    def _fetch_from_fmp(self, pmi_type: str) -> List[Dict[str, Any]]:
        """FMPから最新データを取得"""
        result = []
        event_patterns = EVENT_PATTERNS.get(pmi_type)
        if not event_patterns:
            return result

        # リストでない場合はリストに変換
        if isinstance(event_patterns, str):
            event_patterns = [event_patterns]

        try:
            today = date.today()
            from_date = today - timedelta(days=90)
            to_date = today + timedelta(days=60)

            events = fmp_service.fetch_calendar(from_date, to_date, country=COUNTRY)

            for event in events:
                if event.get("country") != COUNTRY:
                    continue

                event_name = event.get("event", "")
                # 複数パターンのいずれかにマッチするか確認
                matched = any(p.lower() in event_name.lower() for p in event_patterns)
                if not matched:
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

            print(f"[CaSpPmi] {pmi_type}: Fetched {len(result)} records from FMP")

        except Exception as e:
            print(f"[CaSpPmi] Error fetching {pmi_type} from FMP: {e}")

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
            print(f"[CaSpPmi] Error saving to DB: {e}")

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得（製造業PMIのスケジュールで代表）"""
        try:
            pattern = EVENT_PATTERNS["manufacturing"]
            if isinstance(pattern, list):
                pattern = pattern[0]
            return get_next_release_by_pattern(pattern, country=COUNTRY)
        except Exception as e:
            print(f"[CaSpPmi] Error getting next release: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            pattern = EVENT_PATTERNS["manufacturing"]
            if isinstance(pattern, list):
                pattern = pattern[0]
            return should_refresh_by_pattern(pattern, last_updated_str, country=COUNTRY)
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
            print(f"[CaSpPmi] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaSpPmi] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        next_release = self._get_next_release()

        mfg_count = 0
        svc_count = 0
        cmp_count = 0
        if cached_data:
            mfg = cached_data.get("manufacturing")
            svc = cached_data.get("services")
            cmp = cached_data.get("composite")
            mfg_count = len(mfg.get("data", [])) if mfg else 0
            svc_count = len(svc.get("data", [])) if svc else 0
            cmp_count = len(cmp.get("data", [])) if cmp else 0

        return {
            "indicator": "Canada S&P Global PMI (Manufacturing/Services/Composite)",
            "source": "S&P Global / CSV / FMP",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": {
                "manufacturing": mfg_count,
                "services": svc_count,
                "composite": cmp_count,
            },
            "next_release": next_release,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ca_sp_pmi_service = CaSpPmiService()
