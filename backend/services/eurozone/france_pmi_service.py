"""
フランス HCOB PMIサービス
DBからHCOB PMI（製造業/サービス業/総合）データを取得

指標:
- HCOB Manufacturing PMI: 製造業PMI
- HCOB Services PMI: サービス業PMI
- HCOB Composite PMI: 総合PMI

データソース:
- DB: economic_calendar_events（FMP蓄積データ）
- CSV: 過去データインポート

発表スケジュール:
- 速報値: 毎月第3週（23日前後）
- 確報値: 毎月第1週（1日前後）

キャッシュ方式: FMP発表日時ベース判定方式

注意事項:
- 月に2度発表（速報値・確報値）
- country='FR'でフィルタリング
"""
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.eurozone.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
CET = ZoneInfo("Europe/Paris")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "france_pmi_cache.json"


class FrancePMIService:
    """フランス HCOB PMIサービス"""

    DATA_CACHE_KEY = "eurozone:economy:france_pmi:data"
    ECONALPHA_ID = "france_pmi"

    # DBクエリ用のイベントパターン（国コードでフィルタリング）
    EVENT_PATTERNS = {
        "manufacturing": ["Manufacturing PMI", "HCOB Manufacturing PMI", "S&P Global Manufacturing PMI"],
        "services": ["Services PMI", "HCOB Services PMI", "S&P Global Services PMI"],
        "composite": ["Composite PMI", "HCOB Composite PMI", "S&P Global Composite PMI"],
    }

    def __init__(self):
        pass

    def get_france_pmi_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        フランス HCOB PMIデータを取得（製造業、サービス業、総合）

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "manufacturing": {
                    "data": [{"date": "YYYY-MM", "value": float, ...}, ...],
                    "latest": {...},
                },
                "services": {...},
                "composite": {...},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
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
                        "manufacturing": cached_data.get("manufacturing"),
                        "services": cached_data.get("services"),
                        "composite": cached_data.get("composite"),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # DBから取得
        manufacturing_data = self._load_from_db("manufacturing")
        services_data = self._load_from_db("services")
        composite_data = self._load_from_db("composite")

        if manufacturing_data or services_data or composite_data:
            # next_releaseを取得
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            from services.usa.fmp_next_release_utils import guarded_last_updated_nested, _max_date_of
            now_str = datetime.now(CET).isoformat()
            last_updated = guarded_last_updated_nested(
                self.DATA_CACHE_KEY, ("manufacturing", "services", "composite"),
                _max_date_of(manufacturing_data, services_data, composite_data), now_str
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
                "next_release": next_release,
                "last_updated": last_updated
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                **cache_payload,
                "cached": False,
                "source": "database",
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "manufacturing": file_cache.get("manufacturing"),
                "services": file_cache.get("services"),
                "composite": file_cache.get("composite"),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "manufacturing": None,
            "services": None,
            "composite": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _load_from_db(self, pmi_type: str) -> List[Dict[str, Any]]:
        """DBから履歴データを取得

        Args:
            pmi_type: "manufacturing", "services", or "composite"
        """
        try:
            from core.database import SessionLocal
            from sqlalchemy import text
            import re

            event_patterns = self.EVENT_PATTERNS.get(pmi_type)
            if not event_patterns:
                return []

            with SessionLocal() as session:
                # country='FR'でフィルタリング
                # 複数のパターンに対応
                # SQLインジェクション対策: 値は直埋めせずバインドパラメータで渡す
                pattern_conditions = " OR ".join(
                    [f"event ILIKE :pat{i}" for i in range(len(event_patterns))]
                )
                pattern_params = {f"pat{i}": f"%{p}%" for i, p in enumerate(event_patterns)}
                query = text(f"""
                    SELECT datetime_utc, event, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'FR'
                      AND ({pattern_conditions})
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query, pattern_params).fetchall()

                result = []

                # 月名から月番号へのマッピング
                month_map = {
                    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                }

                for row in rows:
                    dt_utc, event, actual, estimate, previous = row
                    if dt_utc:
                        # イベント名から対象月を抽出（例: "Manufacturing PMI (Dec)"）
                        match = re.search(r'\((\w{3})\)', event)
                        if match:
                            month_abbr = match.group(1).lower()
                            if month_abbr in month_map:
                                target_month = month_map[month_abbr]
                                # 対象月の年を決定
                                target_year = dt_utc.year
                                if target_month > dt_utc.month:
                                    target_year -= 1
                                date_str = f"{target_year}-{target_month:02d}"
                            else:
                                # 月名が不明な場合は発表月の前月を使用
                                prev_month = dt_utc.month - 1 if dt_utc.month > 1 else 12
                                prev_year = dt_utc.year if dt_utc.month > 1 else dt_utc.year - 1
                                date_str = f"{prev_year}-{prev_month:02d}"
                        else:
                            # 括弧内に月がない場合は発表月の前月を使用
                            prev_month = dt_utc.month - 1 if dt_utc.month > 1 else 12
                            prev_year = dt_utc.year if dt_utc.month > 1 else dt_utc.year - 1
                            date_str = f"{prev_year}-{prev_month:02d}"

                        # 速報値と確報値があるため、同一月の確報値で上書き
                        existing_idx = None
                        for i, existing in enumerate(result):
                            if existing["date"] == date_str:
                                existing_idx = i
                                break

                        data_point = {
                            "date": date_str,
                            "value": float(actual) if actual else None,
                            "forecast": float(estimate) if estimate else None,
                            "previous": float(previous) if previous else None,
                        }

                        if existing_idx is not None:
                            # 確報値で上書き
                            result[existing_idx] = data_point
                        else:
                            result.append(data_point)

                print(f"[FrancePMI] Loaded {len(result)} FR {pmi_type.capitalize()} PMI records from DB")
                return result

        except Exception as e:
            print(f"[FrancePMI] Error loading FR {pmi_type} PMI from DB: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日時ベース）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None

            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[FrancePMI] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[FrancePMI] Cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"[FrancePMI] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

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
            "indicator": "France HCOB PMI (Manufacturing/Services/Composite)",
            "source": "Database (FMP)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": {
                "manufacturing": mfg_count,
                "services": svc_count,
                "composite": cmp_count,
            },
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
france_pmi_service = FrancePMIService()
