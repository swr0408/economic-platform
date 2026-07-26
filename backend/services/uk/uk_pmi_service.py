"""
UK PMIサービス
DBからS&P Global PMI（製造業・サービス業・総合）データを取得

指標:
- S&P Global Manufacturing PMI（製造業PMI）
- S&P Global Services PMI（サービス業PMI）
- S&P Global Composite PMI（総合PMI）

データソース:
- DB: economic_calendar_events（FMP蓄積データ）
- CSV: 過去データインポート

発表スケジュール:
- 毎月（速報値と確報値あり）
- FMPカレンダーから次回発表日を取得

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")
UTC = ZoneInfo("UTC")

# FMPのPMIイベントは「リリース日」で記録され、参照月は event 名のサフィックス
# (例: "S&P Global Manufacturing PMI (May)") に入る。リリースは参照月の約1ヶ月後なので、
# datetime_utc の月をそのまま使うと全データが1ヶ月後方にずれる。ラベルから参照月を復元する。
# 過去の蓄積分(ラベル無し)は datetime_utc が参照月初に記録されているため、そのまま使う。
_MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_LABEL_MONTH_RE = re.compile(
    r"\((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\)", re.IGNORECASE
)

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "uk_pmi_cache.json"


class UKPMIService:
    """UK PMIサービス"""

    DATA_CACHE_KEY = "uk:pmi:data"
    ECONALPHA_ID = "uk_pmi"

    # FMPカレンダー検索パターン（製造業・サービス・総合）
    # 各系列は自分のイベント名のみにマッチさせる。
    # （以前は manufacturing が3指標すべてを OR でマッチしており、月次パーティション
    #  で Composite/Services の値を製造業として誤選択していた＝値が混入するバグ）
    FMP_EVENT_PATTERNS = {
        "manufacturing": ["S&P Global Manufacturing PMI"],
        "services": ["S&P Global Services PMI"],
        "composite": ["S&P Global Composite PMI"],
    }

    def __init__(self):
        pass

    def get_uk_pmi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """UK PMIデータを取得（3系列）"""
        # 次回発表日を取得
        next_release = self._get_next_release()

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "manufacturing": cached_data.get("manufacturing", []),
                        "services": cached_data.get("services", []),
                        "composite": cached_data.get("composite", []),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # DBから取得（3系列）
        manufacturing = self._load_from_db("manufacturing")
        services = self._load_from_db("services")
        composite = self._load_from_db("composite")

        if manufacturing or services or composite:
            from services.usa.fmp_next_release_utils import guarded_last_updated_keys, _max_date_of
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated_keys(
                self.DATA_CACHE_KEY, ("manufacturing", "services", "composite"),
                _max_date_of(manufacturing, services, composite), now_str
            )
            cache_payload = {
                "manufacturing": manufacturing,
                "services": services,
                "composite": composite,
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "manufacturing": manufacturing,
                "services": services,
                "composite": composite,
                "next_release": next_release,
                "cached": False,
                "source": "database",
                "last_updated": last_updated,
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "manufacturing": file_cache.get("manufacturing", []),
                "services": file_cache.get("services", []),
                "composite": file_cache.get("composite", []),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "manufacturing": [],
            "services": [],
            "composite": [],
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

            # 製造業PMIで検索（通常最初に発表される）
            pattern = self.FMP_EVENT_PATTERNS["manufacturing"]
            if isinstance(pattern, list):
                pattern = pattern[0]
            result = get_next_release_by_pattern(pattern, country="GB")
            return result
        except Exception as e:
            print(f"[UK PMI] Error getting next release: {e}")
            return None

    @staticmethod
    def _reference_date(dt_utc: datetime, event: str) -> str:
        """イベントの参照月（YYYY-MM-01）を決定する。

        - ラベル付き("... (May)")はリリース日に記録されているため、ラベルの月を
          参照月とし、年はリリース年からロールオーバーを考慮して復元する。
        - ラベル無し(過去の蓄積分)は datetime_utc の月を参照月とする。
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

    @staticmethod
    def _prior_month(date_str: str) -> str:
        """YYYY-MM-01 形式の前月を返す。"""
        year, month, _ = date_str.split("-")
        year, month = int(year), int(month)
        month -= 1
        if month == 0:
            month = 12
            year -= 1
        return f"{year:04d}-{month:02d}-01"

    def _aggregate_by_reference_month(self, rows) -> Dict[str, Optional[float]]:
        """イベント行(datetime_utc, event, actual, previous)を参照月ごとに集約する。

        優先順位（高い方を採用、同順位は新しいリリース=改定値を優先）:
          4: ラベル付き確報 actual（参照月の翌月以降にリリース＝確定値）
          3: ラベル無し actual（過去蓄積分。datetime_utc が参照月初）
          2: previous フィールド由来（翌月リリースの previous = 当月の確定値。FMPが
             当月の actual を populate していない欠落月を実値で補完。捏造ではない）
          1: ラベル付き速報 actual（参照月内にリリース＝flash/暫定値）

        FMPには稀に「参照月内にリリースされた非Flashラベル」の不正行（前月のflash値が
        混入）が存在するため、Flashキーワードでなく**リリース時期**で速報/確報を判定する。
        """
        # date_str -> (priority, datetime_utc, value)
        best: Dict[str, Tuple[int, datetime, float]] = {}

        def consider(date_str: str, priority: int, dt_utc: datetime, value: Optional[float]):
            if value is None:
                return
            existing = best.get(date_str)
            if existing is None or (priority, dt_utc) > (existing[0], existing[1]):
                best[date_str] = (priority, dt_utc, value)

        for row in rows:
            dt_utc, event, actual, previous = row
            if not dt_utc:
                continue
            labeled = bool(_LABEL_MONTH_RE.search(event or ""))
            ref_date = self._reference_date(dt_utc, event)
            ref_year, ref_month = int(ref_date[:4]), int(ref_date[5:7])
            # 確報=参照月が終わった後にリリース。参照月内のリリースは速報(flash/暫定)。
            released_after_ref = (dt_utc.year, dt_utc.month) > (ref_year, ref_month)
            if not labeled:
                actual_priority = 3
            elif released_after_ref:
                actual_priority = 4
            else:
                actual_priority = 1
            # 当月の actual
            consider(
                ref_date,
                actual_priority,
                dt_utc,
                float(actual) if actual is not None else None,
            )
            # previous = 前月の確定値（欠落補完用フォールバック）
            if previous is not None:
                consider(
                    self._prior_month(ref_date),
                    2,
                    dt_utc,
                    float(previous),
                )

        return {d: v[2] for d, v in best.items()}

    def _load_from_db(self, pmi_type: str) -> List[Dict[str, Any]]:
        """DBから特定のPMI系列データを取得（参照月ベースで集約）"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            event_patterns = self.FMP_EVENT_PATTERNS.get(pmi_type)
            if not event_patterns:
                return []

            # リストでない場合はリストに変換
            if isinstance(event_patterns, str):
                event_patterns = [event_patterns]

            with SessionLocal() as session:
                # 複数パターンをOR条件で結合
                pattern_conditions = " OR ".join(
                    [f"event ILIKE :pattern{i}" for i in range(len(event_patterns))]
                )

                # actual と previous の両方を取得（previous は欠落補完に使う）。
                # 参照月の決定とFlash/Final・改定の集約は Python 側で行う。
                query = text(f"""
                    SELECT datetime_utc, event, actual, previous
                    FROM economic_calendar_events
                    WHERE country = 'UK'
                      AND ({pattern_conditions})
                      AND (actual IS NOT NULL OR previous IS NOT NULL)
                    ORDER BY datetime_utc ASC
                """)

                params = {}
                for i, pattern in enumerate(event_patterns):
                    params[f"pattern{i}"] = f"%{pattern}%"

                rows = session.execute(query, params).fetchall()

                value_by_date = self._aggregate_by_reference_month(rows)

                result = [
                    {"date": date_str, "value": value}
                    for date_str, value in sorted(value_by_date.items())
                ]

                print(f"[UK PMI] Loaded {len(result)} {pmi_type} records from DB")
                return result

        except Exception as e:
            print(f"[UK PMI] Error loading {pmi_type} from DB: {e}")
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
                # 製造業PMIで判定（通常最初に発表される）
                pattern = self.FMP_EVENT_PATTERNS["manufacturing"]
                if isinstance(pattern, list):
                    pattern = pattern[0]
                if should_refresh_by_pattern(
                    pattern,
                    last_updated_str,
                    country="GB"
                ):
                    print(f"[UK PMI] FMP pattern indicates refresh needed")
                    return True
            except Exception as e:
                print(f"[UK PMI] Error checking FMP refresh: {e}")

            return False

        except Exception as e:
            print(f"[UK PMI] Error in should_refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[UK PMI] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[UK PMI] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "UK S&P Global PMI",
            "source": "Database (FMP)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "manufacturing_count": len(cached_data.get("manufacturing", [])) if cached_data else 0,
            "services_count": len(cached_data.get("services", [])) if cached_data else 0,
            "composite_count": len(cached_data.get("composite", [])) if cached_data else 0,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
uk_pmi_service = UKPMIService()
