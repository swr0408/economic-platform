"""
中古住宅販売保留サービス
DBからPending Home Salesデータを取得

指標:
- 契約中住宅販売指数（前月比・前年比）

データソース:
- DB: economic_calendar_events（FMP蓄積データ + CSVインポート）

発表スケジュール:
- 月次（毎月下旬 10:00 ET頃）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
    guarded_last_updated,
)


JST = ZoneInfo("Asia/Tokyo")

# FMPの発表イベントは「リリース日」で記録され、参照月は event 名のサフィックス
# (例: "Pending Home Sales MoM (May)") に入る。リリース日は参照月の約1ヶ月後なので、
# datetime_utc の月をそのまま使うと全データが1ヶ月後方にずれる。ラベルから参照月を復元する。
_MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_LABEL_MONTH_RE = re.compile(
    r"\((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\)", re.IGNORECASE
)

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "housing"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "pending_home_sales_cache.json"


class PendingHomeSalesService:
    """中古住宅販売保留サービス"""

    DATA_CACHE_KEY = "housing:pending_home_sales:data"
    # MoMをメインとして使用（YoYも同時に取得）
    ECONALPHA_ID_MOM = "pending_home_sales_mom"
    ECONALPHA_ID_YOY = "pending_home_sales_yoy"

    def __init__(self):
        pass

    def get_pending_home_sales_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        中古住宅販売保留データを取得

        Args:
            force_refresh: 強制更新フラグ

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "mom": float, "yoy": float}, ...],
                "latest": {"date": str, "mom": float, "yoy": float},
                "next_release": {...} | None,
                "cached": bool,
                "source": str,
                "last_updated": str
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
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # DBから取得
        db_result = self._load_from_db()
        if db_result:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID_MOM)
            latest = db_result[-1] if db_result else None
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
            )

            cache_payload = {
                "data": db_result,
                "latest": latest,
                "next_release": next_release,
                "last_updated": last_updated
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": db_result,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "database",
                "last_updated": last_updated
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    @staticmethod
    def _reference_date(dt_utc: datetime, event: str) -> str:
        """イベントの参照月（YYYY-MM-01）を決定する。

        - ラベル付き("... (May)")はリリース日に記録されているため、ラベルの月を
          参照月とし、年はリリース年からロールオーバーを考慮して復元する。
        - ラベル無し(過去の蓄積分)は従来どおり datetime_utc の月を参照月とする。
        """
        m = _LABEL_MONTH_RE.search(event or "")
        if m:
            ref_month = _MONTH_ABBR[m.group(1).lower()]
            ref_year = dt_utc.year
            # リリースは参照月の約1ヶ月後。参照月がリリース月より大きければ前年(12月→1月)。
            if ref_month > dt_utc.month:
                ref_year -= 1
            return f"{ref_year:04d}-{ref_month:02d}-01"
        return dt_utc.strftime("%Y-%m-01")

    def _aggregate_by_reference_month(self, rows) -> Dict[str, Optional[float]]:
        """イベント行を参照月ごとに集約する。

        同一参照月に複数行ある場合の優先順位:
          ラベル付き(=参照月が明示, 信頼度高) > ラベル無し。
        同優先度では新しいリリース(datetime_utc が後)を採用(改定値優先)。
        """
        # date_str -> (priority, datetime_utc, value)
        best: Dict[str, Tuple[int, datetime, Optional[float]]] = {}
        for row in rows:
            dt_utc, event, actual = row
            if not dt_utc:
                continue
            date_str = self._reference_date(dt_utc, event)
            priority = 2 if _LABEL_MONTH_RE.search(event or "") else 1
            value = float(actual) if actual is not None else None
            existing = best.get(date_str)
            if existing is None or (priority, dt_utc) > (existing[0], existing[1]):
                best[date_str] = (priority, dt_utc, value)
        return {d: v[2] for d, v in best.items()}

    def _load_from_db(self) -> List[Dict[str, Any]]:
        """DBから履歴データを取得（MoMとYoYを結合）"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                # MoMデータを取得
                mom_query = text("""
                    SELECT datetime_utc, event, actual
                    FROM economic_calendar_events
                    WHERE country = 'US'
                      AND event ILIKE '%Pending Home Sales MoM%'
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                mom_rows = session.execute(mom_query).fetchall()

                # YoYデータを取得
                yoy_query = text("""
                    SELECT datetime_utc, event, actual
                    FROM economic_calendar_events
                    WHERE country = 'US'
                      AND event ILIKE '%Pending Home Sales YoY%'
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                yoy_rows = session.execute(yoy_query).fetchall()

                # 参照月別にデータを集約（ラベルから参照月を復元・優先度付き）
                mom_dict = self._aggregate_by_reference_month(mom_rows)
                yoy_dict = self._aggregate_by_reference_month(yoy_rows)

                # 全ての日付を統合
                all_dates = sorted(set(mom_dict.keys()) | set(yoy_dict.keys()))

                result = []
                for date_str in all_dates:
                    mom_value = mom_dict.get(date_str)
                    yoy_value = yoy_dict.get(date_str)

                    # MoMまたはYoYのどちらかが存在すれば追加
                    if mom_value is not None or yoy_value is not None:
                        result.append({
                            "date": date_str,
                            "mom": mom_value,
                            "yoy": yoy_value,
                        })

                print(f"Loaded {len(result)} pending_home_sales records from DB")
                return result

        except Exception as e:
            print(f"Error loading from DB: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP 3分方式）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID_MOM, last_updated_str)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Pending Home Sales",
            "source": "Database (FMP + CSV)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID_MOM),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
pending_home_sales_service = PendingHomeSalesService()
