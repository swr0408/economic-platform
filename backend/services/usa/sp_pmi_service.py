"""
S&P Global PMIサービス
DBからS&P Global PMI（製造業/サービス業/総合）データを取得

指標:
- S&P Global Manufacturing PMI: 製造業PMI
- S&P Global Services PMI: サービス業PMI
- S&P Global Composite PMI: 総合PMI

データソース:
- DB: economic_calendar_events（FMP蓄積データ）
- CSV: 過去データインポート

発表スケジュール:
- 速報値: 毎月第3週（23日前後）9:45 ET
- 確報値: 毎月第1週（1日前後）9:45 ET

キャッシュ方式: FMP発表日時ベース判定方式

注意事項:
- 月に2度発表（速報値・確報値）
- country='US'でフィルタリング（他国のPMIを除外）
"""
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "sp_pmi_cache.json"


class SPPMIService:
    """S&P Global PMIサービス"""

    DATA_CACHE_KEY = "economy:sp_pmi:data"

    # 3つのPMI指標に対応するECONALPHA_ID
    ECONALPHA_IDS = {
        "manufacturing": "sp_manufacturing_pmi",
        "services": "sp_services_pmi",
        "composite": "sp_composite_pmi",
    }

    # DBクエリ用のイベントパターン（国コードでフィルタリング）
    EVENT_PATTERNS = {
        "manufacturing": "S&P Global Manufacturing PMI",
        "services": "S&P Global Services PMI",
        "composite": "S&P Global Composite PMI",
    }

    def __init__(self):
        pass

    def get_sp_pmi_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        S&P Global PMIデータを取得（製造業、サービス業、総合）

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "manufacturing": {
                    "data": [{"date": "YYYY-MM-DD", "value": float, ...}, ...],
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
            # いずれかの指標のnext_releaseを取得（製造業を優先）
            next_release = get_next_release_from_fmp(self.ECONALPHA_IDS["manufacturing"])

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
                "last_updated": datetime.now(JST).isoformat()
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

            event_pattern = self.EVENT_PATTERNS.get(pmi_type)
            if not event_pattern:
                return []

            with SessionLocal() as session:
                # country='US'でフィルタリングして他国のPMIを除外
                query = text("""
                    SELECT datetime_utc, event, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'US'
                      AND event ILIKE :pattern
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query, {"pattern": f"%{event_pattern}%"}).fetchall()

                result = []
                seen_dates = set()

                # 月名から月番号へのマッピング
                month_map = {
                    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                }

                for row in rows:
                    dt_utc, event, actual, estimate, previous = row
                    if dt_utc:
                        # イベント名から対象月を抽出（例: "S&P Global Manufacturing PMI (Dec)"）
                        match = re.search(r'\((\w{3})\)', event)
                        if match:
                            month_abbr = match.group(1).lower()
                            if month_abbr in month_map:
                                target_month = month_map[month_abbr]
                                # 対象月の年を決定
                                target_year = dt_utc.year
                                if target_month > dt_utc.month:
                                    target_year -= 1
                                date_str = f"{target_year}-{target_month:02d}-01"
                            else:
                                # 月名が不明な場合は発表月の前月を使用
                                prev_month = dt_utc.month - 1 if dt_utc.month > 1 else 12
                                prev_year = dt_utc.year if dt_utc.month > 1 else dt_utc.year - 1
                                date_str = f"{prev_year}-{prev_month:02d}-01"
                        else:
                            # 括弧内に月がない場合は発表月の前月を使用
                            prev_month = dt_utc.month - 1 if dt_utc.month > 1 else 12
                            prev_year = dt_utc.year if dt_utc.month > 1 else dt_utc.year - 1
                            date_str = f"{prev_year}-{prev_month:02d}-01"

                        # 速報値と確報値があるため、同一月の確報値で上書き
                        # seen_datesで重複を許可（後のデータ=確報値で上書き）
                        # 既存データを更新する形に
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

                print(f"Loaded {len(result)} S&P {pmi_type.capitalize()} PMI records from DB")
                return result

        except Exception as e:
            print(f"Error loading S&P {pmi_type} PMI from DB: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP 3分方式）"""
        # 製造業PMIのスケジュールで判定（3つとも同時発表のため）
        return should_refresh_by_fmp_schedule(
            self.ECONALPHA_IDS["manufacturing"],
            last_updated_str
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None

            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

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
            "indicator": "S&P Global PMI (Manufacturing/Services/Composite)",
            "source": "Database (FMP)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": {
                "manufacturing": mfg_count,
                "services": svc_count,
                "composite": cmp_count,
            },
            "next_release": get_next_release_from_fmp(self.ECONALPHA_IDS["manufacturing"]),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
sp_pmi_service = SPPMIService()
