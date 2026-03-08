"""
NZ 乳製品価格（GDT）サービス

指標:
- GlobalDairyTrade Price Index: GDT価格指数（変化率）

データソース:
- CSV履歴データ (backend/data/csv_import/世界乳製品取引価格指数.csv)
- DB蓄積 (economic_calendar_events)
- FMP API (最新値・前回値修正を含む)

FMPマッピング:
- GlobalDairyTrade Price Index (econalpha_id: nz_global_dairy_trade)

発表スケジュール: 隔週（不定期）
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
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "newzealand" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "nz_global_dairy_trade_cache.json"

# CSVデータ
CSV_DIR = Path(__file__).parent.parent.parent / "data" / "csv_import"
CSV_FILE = CSV_DIR / "世界乳製品取引価格指数.csv"

# FMPパターン
FMP_EVENT_PATTERN = "GlobalDairyTrade Price Index"
FMP_COUNTRY = "NZ"


class NzGlobalDairyTradeService:
    """NZ 乳製品価格（GDT）サービス（CSV + DB + FMP方式）"""

    DATA_CACHE_KEY = "newzealand:nz_global_dairy_trade:data"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """GDT価格指数データを取得"""
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

        if latest:
            print(f"[NzGDT] Latest: {latest['date']} value={latest['value']:.2f}%")

        metadata = {
            "source": "GlobalDairyTrade",
            "indicator": "GlobalDairyTrade Price Index",
            "description": "GDT乳製品価格指数（変化率）",
            "unit": "%",
            "frequency": "irregular",
        }

        cache_payload = {
            "data": data,
            "latest": latest,
            "metadata": metadata,
            "last_updated": datetime.now(JST).isoformat(),
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
            "last_updated": datetime.now(JST).isoformat(),
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

            # 3. FMPから最新データ（前回値修正も含む）
            fmp_data = self._fetch_from_fmp()
            result.extend(fmp_data)

            # 日付でマージ（後から追加されたものを優先 = FMP > DB > CSV）
            merged = {}
            for item in result:
                merged[item["date"]] = item

            result = sorted(merged.values(), key=lambda x: x["date"])
            print(f"[NzGDT] Loaded {len(result)} records (merged)")

        except Exception as e:
            print(f"[NzGDT] Error loading data: {e}")
            import traceback
            traceback.print_exc()

        return result

    def _load_from_csv(self) -> List[Dict[str, Any]]:
        """CSVファイルから履歴データを読み込む

        CSV形式: 公表日,時刻,結果,予想,前回
        日付形式: 2022年02月02日
        値形式: 4.10%（パーセンテージ変化率）
        """
        result = []

        try:
            if not CSV_FILE.exists():
                print(f"[NzGDT] CSV file not found: {CSV_FILE}")
                return result

            with open(CSV_FILE, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    date_str = row.get("公表日", "").strip()
                    value_str = row.get("結果", "").strip()

                    if not date_str or not value_str:
                        continue

                    # 日付パース: "2022年02月02日" → "2022-02-02"
                    date_match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', date_str)
                    if not date_match:
                        continue

                    year = int(date_match.group(1))
                    month = int(date_match.group(2))
                    day = int(date_match.group(3))
                    date_formatted = f"{year}-{month:02d}-{day:02d}"

                    # 値のパース: "4.10%" → 4.1
                    try:
                        value = float(value_str.replace('%', '').strip())
                    except ValueError:
                        continue

                    result.append({
                        "date": date_formatted,
                        "value": round(value, 2),
                    })

            print(f"[NzGDT] Loaded {len(result)} records from CSV")

        except Exception as e:
            print(f"[NzGDT] Error loading from CSV: {e}")

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

                    # 発表日をそのまま使用（アークランド時間に変換）
                    if dt_utc.tzinfo is None:
                        dt_utc = dt_utc.replace(tzinfo=UTC)
                    dt_nz = dt_utc.astimezone(AUCKLAND)
                    date_formatted = dt_nz.strftime("%Y-%m-%d")

                    result.append({
                        "date": date_formatted,
                        "value": round(float(actual), 2) if actual else None,
                    })

            print(f"[NzGDT] Loaded {len(result)} records from DB")

        except Exception as e:
            print(f"[NzGDT] Error loading from DB: {e}")

        return result

    def _fetch_from_fmp(self) -> List[Dict[str, Any]]:
        """FMPから最新データを取得（前回値の修正も含む）"""
        result = []

        try:
            today = date.today()
            # 隔週データなので広めに取得
            from_date = today - timedelta(days=60)
            to_date = today + timedelta(days=45)

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

                # 発表日をNZ時間に変換
                if dt_utc.tzinfo is None:
                    dt_utc = dt_utc.replace(tzinfo=UTC)
                dt_nz = dt_utc.astimezone(AUCKLAND)
                date_formatted = dt_nz.strftime("%Y-%m-%d")

                result.append({
                    "date": date_formatted,
                    "value": round(float(actual), 2),
                })

                # DBにも保存（蓄積方式）
                self._save_to_db(event)

            print(f"[NzGDT] Fetched {len(result)} records from FMP")

        except Exception as e:
            print(f"[NzGDT] Error fetching from FMP: {e}")

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
            print(f"[NzGDT] Error saving to DB: {e}")

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得"""
        try:
            return get_next_release_by_pattern(FMP_EVENT_PATTERN, country=FMP_COUNTRY)
        except Exception as e:
            print(f"[NzGDT] Error getting next release: {e}")
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
                # 隔週データなので7日でリフレッシュ
                return (now - last_updated).total_seconds() > 604800
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
            print(f"[NzGDT] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[NzGDT] Failed to save file cache: {e}")

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
            "indicator": "NZ GlobalDairyTrade Price Index",
            "source": "GlobalDairyTrade / CSV / FMP",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": data_count,
            "next_release": next_release,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
nz_global_dairy_trade_service = NzGlobalDairyTradeService()
