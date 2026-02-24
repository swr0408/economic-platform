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
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "uk_pmi_cache.json"


class UKPMIService:
    """UK PMIサービス"""

    DATA_CACHE_KEY = "uk:pmi:data"
    ECONALPHA_ID = "uk_pmi"

    # FMPカレンダー検索パターン（製造業・サービス・総合）
    # FMPでは3指標が同時発表されるため、製造業には全パターンを含む
    FMP_EVENT_PATTERNS = {
        "manufacturing": ["S&P Global Manufacturing PMI", "S&P Global Services PMI", "S&P Global Composite PMI"],
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
            cache_payload = {
                "manufacturing": manufacturing,
                "services": services,
                "composite": composite,
                "last_updated": datetime.now(JST).isoformat(),
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
                "last_updated": datetime.now(JST).isoformat(),
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

    def _load_from_db(self, pmi_type: str) -> List[Dict[str, Any]]:
        """DBから特定のPMI系列データを取得"""
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

                # Flash（速報）とFinal（確報）の両方を取得し、同月は確報を優先
                query = text(f"""
                    WITH ranked_events AS (
                        SELECT
                            datetime_utc,
                            actual,
                            estimate,
                            previous,
                            event,
                            -- Flash < Final の優先度（同月は確報を優先）
                            CASE
                                WHEN event ILIKE '%Final%' THEN 2
                                WHEN event ILIKE '%Flash%' THEN 1
                                ELSE 1
                            END as priority,
                            ROW_NUMBER() OVER (
                                PARTITION BY DATE_TRUNC('month', datetime_utc)
                                ORDER BY
                                    CASE
                                        WHEN event ILIKE '%Final%' THEN 2
                                        WHEN event ILIKE '%Flash%' THEN 1
                                        ELSE 1
                                    END DESC,
                                    datetime_utc DESC
                            ) as rn
                        FROM economic_calendar_events
                        WHERE country = 'UK'
                          AND ({pattern_conditions})
                          AND actual IS NOT NULL
                    )
                    SELECT datetime_utc, actual, estimate, previous, event
                    FROM ranked_events
                    WHERE rn = 1
                    ORDER BY datetime_utc ASC
                """)

                params = {}
                for i, pattern in enumerate(event_patterns):
                    params[f"pattern{i}"] = f"%{pattern}%"

                rows = session.execute(query, params).fetchall()

                result = []
                seen_dates = set()

                for row in rows:
                    dt_utc, actual, estimate, previous, event = row
                    if dt_utc:
                        # 月初日に正規化
                        date_str = dt_utc.strftime("%Y-%m-01")
                        if date_str in seen_dates:
                            continue
                        seen_dates.add(date_str)

                        result.append({
                            "date": date_str,
                            "value": float(actual) if actual else None,
                            "forecast": float(estimate) if estimate else None,
                            "previous": float(previous) if previous else None,
                            "is_flash": "Flash" in event if event else False,
                        })

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
