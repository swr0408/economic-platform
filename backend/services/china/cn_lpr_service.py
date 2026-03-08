"""
中国ローンプライムレート（Loan Prime Rate）サービス

指標:
- cn_lpr_1y: ローンプライムレート 1年（1Y LPR）: %
- cn_lpr_5y: ローンプライムレート 5年（5Y LPR）: %

データソース:
- DB: economic_calendar_events（CSV_IMPORTで過去データ投入、FMPで新規蓄積）
  - 1Y: event ILIKE '%Loan Prime Rate 1Y%', country='CN'
  - 5Y: event ILIKE '%Loan Prime Rate 5Y%', country='CN'

データフロー:
1. 過去データ: backend/data/csv_import/ローンプライムレート.csv / ローンプライムレート5Y.csv
   → import_csv_to_db.py で economic_calendar_events にインポート済み
2. 新規データ: FMP経済カレンダーが毎月発表後に蓄積
3. サービス: DBから全データを取得してマージして提供

発表スケジュール:
- 毎月20日（前後する場合あり）10:00-10:15 CST（北京時間）
- FMPイベント: "Loan Prime Rate 1Y" / "Loan Prime Rate 5Y"

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.china.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
CST = ZoneInfo("Asia/Shanghai")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "china" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# FMPイベントパターン
FMP_EVENT_1Y = "Loan Prime Rate 1Y"
FMP_EVENT_5Y = "Loan Prime Rate 5Y"
FMP_COUNTRY = "CN"


def _parse_rate_value(value: Any) -> Optional[float]:
    """金利値をパース（%記号対応、Decimal対応）"""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        pass
    if isinstance(value, str):
        cleaned = value.replace('%', '').strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _load_lpr_from_db(event_pattern: str) -> List[Dict[str, Any]]:
    """DBからLPRデータを取得"""
    try:
        from core.database import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as session:
            query = text("""
                SELECT datetime_utc, event, actual, estimate, previous
                FROM economic_calendar_events
                WHERE country = 'CN'
                  AND event ILIKE :pattern
                  AND actual IS NOT NULL
                ORDER BY datetime_utc ASC
            """)
            rows = session.execute(query, {"pattern": f"%{event_pattern}%"}).fetchall()

            result = []
            seen_dates = set()

            for row in rows:
                dt_utc, event, actual, estimate, previous = row
                if dt_utc:
                    date_str = dt_utc.strftime("%Y-%m-%d")

                    if date_str in seen_dates:
                        continue
                    seen_dates.add(date_str)

                    value = _parse_rate_value(actual)
                    forecast = _parse_rate_value(estimate)
                    prev_val = _parse_rate_value(previous)

                    result.append({
                        "date": date_str,
                        "value": value,
                        "forecast": forecast,
                        "previous": prev_val,
                    })

            print(f"[CnLPR] Loaded {len(result)} records for '{event_pattern}' from DB")
            return result

    except Exception as e:
        print(f"[CnLPR] Error loading from DB for '{event_pattern}': {e}")
        import traceback
        traceback.print_exc()
        return []


class CnLprService:
    """中国ローンプライムレートサービス（1Y + 5Y）"""

    DATA_CACHE_KEY_1Y = "china:cn_lpr_1y:data"
    DATA_CACHE_KEY_5Y = "china:cn_lpr_5y:data"
    ECONALPHA_ID_1Y = "cn_lpr_1y"
    ECONALPHA_ID_5Y = "cn_lpr_5y"

    def __init__(self):
        self._cache_file_1y = CACHE_DIR / "cn_lpr_1y_cache.json"
        self._cache_file_5y = CACHE_DIR / "cn_lpr_5y_cache.json"

    def get_lpr_1y_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """1Y LPRデータを取得"""
        return self._get_lpr_data(
            cache_key=self.DATA_CACHE_KEY_1Y,
            event_pattern=FMP_EVENT_1Y,
            cache_file=self._cache_file_1y,
            label="1Y LPR",
        )

    def get_lpr_5y_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """5Y LPRデータを取得"""
        return self._get_lpr_data(
            cache_key=self.DATA_CACHE_KEY_5Y,
            event_pattern=FMP_EVENT_5Y,
            cache_file=self._cache_file_5y,
            label="5Y LPR",
        )

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """1Y + 5Y 両方をまとめて取得（ダッシュボード用）"""
        lpr_1y = self.get_lpr_1y_data(force_refresh=force_refresh)
        lpr_5y = self.get_lpr_5y_data(force_refresh=force_refresh)
        return {
            "lpr_1y": lpr_1y,
            "lpr_5y": lpr_5y,
        }

    def _get_lpr_data(
        self,
        cache_key: str,
        event_pattern: str,
        cache_file: Path,
        label: str,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """LPRデータ取得の共通処理"""
        next_release = self._get_next_release(event_pattern)

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(event_pattern, last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # DBから取得
        db_result = _load_lpr_from_db(event_pattern)

        if db_result:
            latest = db_result[-1] if db_result else None
            metadata = {
                "source": "DB (CSV_IMPORT + FMP)",
                "indicator": f"China Loan Prime Rate ({label})",
                "unit": "%",
                "frequency": "monthly",
                "event_pattern": event_pattern,
            }
            cache_payload = {
                "data": db_result,
                "latest": latest,
                "metadata": metadata,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(cache_key, cache_payload, expire=0)
            self._save_file_cache(cache_file, cache_payload)

            return {
                "data": db_result,
                "latest": latest,
                "metadata": metadata,
                "next_release": next_release,
                "cached": False,
                "source": "database",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache(cache_file)
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

    def _get_next_release(self, event_pattern: str) -> Optional[Dict[str, Any]]:
        """次回発表日を取得"""
        try:
            return get_next_release_by_pattern(event_pattern, country=FMP_COUNTRY)
        except Exception as e:
            print(f"[CnLPR] Error getting next release for '{event_pattern}': {e}")
            return None

    def _should_refresh(self, event_pattern: str, last_updated_str: str) -> bool:
        """キャッシュを更新すべきか判定"""
        try:
            return should_refresh_by_pattern(event_pattern, last_updated_str, country=FMP_COUNTRY)
        except Exception:
            try:
                last_updated = datetime.fromisoformat(last_updated_str)
                if last_updated.tzinfo is None:
                    last_updated = last_updated.replace(tzinfo=JST)
                now = datetime.now(JST)
                return (now - last_updated).total_seconds() > 86400
            except Exception:
                return True

    def _load_file_cache(self, cache_file: Path) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not cache_file.exists():
                return None
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[CnLPR] Failed to load file cache {cache_file}: {e}")
            return None

    def _save_file_cache(self, cache_file: Path, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CnLPR] Failed to save file cache {cache_file}: {e}")

    def invalidate_cache(self) -> Dict[str, bool]:
        """両方のキャッシュを無効化"""
        return {
            "lpr_1y": bool(redis_client.delete(self.DATA_CACHE_KEY_1Y)),
            "lpr_5y": bool(redis_client.delete(self.DATA_CACHE_KEY_5Y)),
        }

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_1y = redis_client.get(self.DATA_CACHE_KEY_1Y)
        data_5y = redis_client.get(self.DATA_CACHE_KEY_5Y)
        return {
            "indicator": "China Loan Prime Rate (1Y + 5Y)",
            "source": "DB (CSV_IMPORT + FMP)",
            "lpr_1y": {
                "cache_key": self.DATA_CACHE_KEY_1Y,
                "exists": data_1y is not None,
                "last_updated": data_1y.get("last_updated") if data_1y else None,
                "data_count": len(data_1y.get("data", [])) if data_1y else 0,
                "next_release": self._get_next_release(FMP_EVENT_1Y),
            },
            "lpr_5y": {
                "cache_key": self.DATA_CACHE_KEY_5Y,
                "exists": data_5y is not None,
                "last_updated": data_5y.get("last_updated") if data_5y else None,
                "data_count": len(data_5y.get("data", [])) if data_5y else 0,
                "next_release": self._get_next_release(FMP_EVENT_5Y),
            },
        }


# シングルトンインスタンス
cn_lpr_service = CnLprService()
