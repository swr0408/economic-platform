"""
FMPベース経済指標サービス

Investing.comスクレイピングからFMP + DB蓄積方式に移行。

対応指標:
- ISM製造業景況指数 (ISM Manufacturing PMI)
- ISM非製造業景況指数 (ISM Non-Manufacturing PMI / ISM Services PMI)
- CB消費者信頼感指数 (CB Consumer Confidence)
- チャレンジャー人員削減数 (Challenger Job Cuts)
- レッドブック前年比 (Redbook YoY)
- コントロールグループ (Retail Sales Ex Gas/Autos MoM)

データフロー:
1. DB (economic_calendar_events) から過去データを取得
2. FMP APIから直近データを取得（キャッシュ更新）
3. Redisにキャッシュ（スケジュール判定で更新）

次回発表日:
- FMP APIから将来の日付を取得して次回発表日を特定
"""
import os
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

from core.database import SessionLocal
from core.redis_client import redis_client
from services.calendar.fmp_service import fmp_service
from sqlalchemy import text

# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")
ET = ZoneInfo("America/New_York")


# 指標定義
INDICATOR_CONFIGS = {
    "ism_manufacturing": {
        "fmp_patterns": ["ISM Manufacturing PMI"],
        "cache_key": "fmp:ism_manufacturing",
        "frequency": "monthly",
        "country": "US",
    },
    "ism_non_manufacturing": {
        "fmp_patterns": ["ISM Non-Manufacturing PMI", "ISM Services PMI"],
        "cache_key": "fmp:ism_non_manufacturing",
        "frequency": "monthly",
        "country": "US",
    },
    "cb_consumer_confidence": {
        "fmp_patterns": ["CB Consumer Confidence"],
        "cache_key": "fmp:cb_consumer_confidence",
        "frequency": "monthly",
        "country": "US",
    },
    "challenger_job_cuts": {
        "fmp_patterns": ["Challenger Job Cuts"],
        "cache_key": "fmp:challenger_job_cuts",
        "frequency": "monthly",
        "country": "US",
    },
    "redbook_yoy": {
        "fmp_patterns": ["Redbook YoY"],
        "cache_key": "fmp:redbook_yoy",
        "frequency": "weekly",
        "country": "US",
    },
    "retail_control": {
        "fmp_patterns": ["Retail Sales Ex Gas/Autos MoM"],
        "cache_key": "fmp:retail_control",
        "frequency": "monthly",
        "country": "US",
    },
}


class FMPIndicatorService:
    """FMPベース経済指標サービス"""

    def __init__(self, indicator_id: str):
        if indicator_id not in INDICATOR_CONFIGS:
            raise ValueError(f"Unknown indicator: {indicator_id}")

        self.indicator_id = indicator_id
        self.config = INDICATOR_CONFIGS[indicator_id]
        self.fmp_patterns = self.config["fmp_patterns"]
        self.cache_key = self.config["cache_key"]
        self.frequency = self.config["frequency"]
        self.country = self.config["country"]

    def get_data(self, force_refresh: bool = False) -> dict[str, Any]:
        """
        指標データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float, ...}, ...],
                "latest": {...},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | None,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # 1. Redisキャッシュをチェック
        if not force_refresh:
            cached = redis_client.get(self.cache_key)
            if cached:
                last_updated = cached.get("last_updated")
                if last_updated and not self._should_refresh(last_updated):
                    return {
                        "data": cached.get("data", []),
                        "latest": cached.get("latest"),
                        "next_release": cached.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated,
                    }

        # 2. DBから履歴データを取得
        db_data = self._load_from_db()

        # 3. FMPから最新データを取得・更新
        fmp_data, next_release = self._fetch_from_fmp()

        # 4. データをマージ（FMPで更新されたデータを優先）
        merged_data = self._merge_data(db_data, fmp_data)

        # 5. 日付順にソート
        merged_data.sort(key=lambda x: x["date"])

        latest = merged_data[-1] if merged_data else None

        # 6. Redisにキャッシュ
        cache_payload = {
            "data": merged_data,
            "latest": latest,
            "next_release": next_release,
            "last_updated": datetime.now(JST).isoformat(),
        }
        redis_client.set(self.cache_key, cache_payload, expire=0)

        return {
            "data": merged_data,
            "latest": latest,
            "next_release": next_release,
            "cached": False,
            "source": "fmp+db",
            "last_updated": datetime.now(JST).isoformat(),
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュ更新が必要かどうか判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 頻度に応じた更新判定
            if self.frequency == "weekly":
                # 週次: 1日以上経過で更新
                return (now - last_updated).days >= 1
            else:
                # 月次: 当日の6時以降で前日以前なら更新
                today_6am = datetime.combine(now.date(), datetime.min.time(), tzinfo=JST).replace(hour=6)
                if now >= today_6am and last_updated < today_6am:
                    return True
                return False

        except Exception:
            return True

    def _load_from_db(self) -> list[dict]:
        """DBから履歴データを取得"""
        result = []

        try:
            with SessionLocal() as session:
                # パターンマッチでイベントを検索
                pattern_conditions = " OR ".join(
                    [f"LOWER(event) LIKE LOWER('%{p}%')" for p in self.fmp_patterns]
                )

                query = text(f"""
                    SELECT
                        datetime_utc,
                        event_period,
                        actual,
                        estimate,
                        previous
                    FROM economic_calendar_events
                    WHERE country = :country
                      AND ({pattern_conditions})
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc DESC
                    LIMIT 500
                """)

                rows = session.execute(query, {"country": self.country}).fetchall()

                for row in rows:
                    dt_utc, period, actual, estimate, previous = row

                    # 日付を文字列に変換
                    if dt_utc:
                        if self.frequency == "weekly":
                            date_str = dt_utc.strftime("%Y-%m-%d")
                        else:
                            # 月次は月初日に正規化
                            date_str = dt_utc.strftime("%Y-%m-01")
                    else:
                        continue

                    result.append({
                        "date": date_str,
                        "value": float(actual) if actual else None,
                        "forecast": float(estimate) if estimate else None,
                        "previous": float(previous) if previous else None,
                        "period": period,
                    })

        except Exception as e:
            print(f"Error loading from DB: {e}")
            import traceback
            traceback.print_exc()

        return result

    def _fetch_from_fmp(self) -> tuple[list[dict], dict | None]:
        """FMPから最新データを取得"""
        result = []
        next_release = None

        try:
            today = date.today()
            from_date = today - timedelta(days=90)
            to_date = today + timedelta(days=60)  # 将来の発表日も取得

            events = fmp_service.fetch_calendar(from_date, to_date)

            for event in events:
                if event.get("country") != self.country:
                    continue

                event_name = event.get("event", "")
                matched = False
                for pattern in self.fmp_patterns:
                    if pattern.lower() in event_name.lower():
                        matched = True
                        break

                if not matched:
                    continue

                # 日時パース
                dt_utc, has_time = fmp_service.parse_datetime(event.get("date", ""))
                if not dt_utc:
                    continue

                actual = event.get("actual")
                estimate = event.get("estimate")
                previous = event.get("previous")

                # 実績があるデータ
                if actual is not None:
                    if self.frequency == "weekly":
                        date_str = dt_utc.strftime("%Y-%m-%d")
                    else:
                        date_str = dt_utc.strftime("%Y-%m-01")

                    result.append({
                        "date": date_str,
                        "value": float(actual),
                        "forecast": float(estimate) if estimate else None,
                        "previous": float(previous) if previous else None,
                        "period": fmp_service.extract_period_info(event_name),
                    })

                    # DBにも保存
                    self._save_to_db(event)

                # 将来のイベント（次回発表日）
                elif dt_utc.date() > today and next_release is None:
                    next_release = {
                        "date": dt_utc.strftime("%Y-%m-%d"),
                        "datetime_utc": dt_utc.isoformat(),
                        "label": event_name,
                        "estimate": estimate,
                    }

        except Exception as e:
            print(f"Error fetching from FMP: {e}")
            import traceback
            traceback.print_exc()

        return result, next_release

    def _save_to_db(self, event: dict) -> None:
        """FMPイベントをDBに保存"""
        try:
            processed = fmp_service.process_event(event)

            with SessionLocal() as session:
                import json
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
            print(f"Error saving to DB: {e}")

    def _merge_data(
        self,
        db_data: list[dict],
        fmp_data: list[dict]
    ) -> list[dict]:
        """DBデータとFMPデータをマージ（FMPを優先）"""
        merged = {}

        # DBデータを追加
        for item in db_data:
            key = item["date"]
            merged[key] = item

        # FMPデータで上書き
        for item in fmp_data:
            key = item["date"]
            merged[key] = item

        return list(merged.values())

    def get_next_release_date(self) -> dict | None:
        """次回発表日を取得"""
        cached = redis_client.get(self.cache_key)
        if cached:
            return cached.get("next_release")
        return None

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.cache_key)

    def get_cache_status(self) -> dict[str, Any]:
        """キャッシュ状態を取得"""
        cached = redis_client.get(self.cache_key)
        exists = cached is not None

        return {
            "indicator_id": self.indicator_id,
            "cache_key": self.cache_key,
            "exists": exists,
            "last_updated": cached.get("last_updated") if cached else None,
            "data_count": len(cached.get("data", [])) if cached else 0,
            "latest": cached.get("latest") if cached else None,
            "next_release": cached.get("next_release") if cached else None,
        }


# 各指標のサービスインスタンス
class ISMManufacturingFMPService(FMPIndicatorService):
    """ISM製造業景況指数（FMPベース）"""
    def __init__(self):
        super().__init__("ism_manufacturing")


class ISMNonManufacturingFMPService(FMPIndicatorService):
    """ISM非製造業景況指数（FMPベース）"""
    def __init__(self):
        super().__init__("ism_non_manufacturing")


class CBConsumerConfidenceFMPService(FMPIndicatorService):
    """CB消費者信頼感指数（FMPベース）"""
    def __init__(self):
        super().__init__("cb_consumer_confidence")


class ChallengerJobCutsFMPService(FMPIndicatorService):
    """チャレンジャー人員削減数（FMPベース）"""
    def __init__(self):
        super().__init__("challenger_job_cuts")


class RedbookYoYFMPService(FMPIndicatorService):
    """レッドブック前年比（FMPベース）"""
    def __init__(self):
        super().__init__("redbook_yoy")


class RetailControlFMPService(FMPIndicatorService):
    """コントロールグループ（FMPベース）"""
    def __init__(self):
        super().__init__("retail_control")


# シングルトンインスタンス
ism_manufacturing_fmp_service = ISMManufacturingFMPService()
ism_non_manufacturing_fmp_service = ISMNonManufacturingFMPService()
cb_consumer_confidence_fmp_service = CBConsumerConfidenceFMPService()
challenger_job_cuts_fmp_service = ChallengerJobCutsFMPService()
redbook_yoy_fmp_service = RedbookYoYFMPService()
retail_control_fmp_service = RetailControlFMPService()
