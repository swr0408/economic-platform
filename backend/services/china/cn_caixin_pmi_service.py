"""
中国 Caixin PMI（財新PMI）サービス
DBからCaixin PMI（製造業/サービス業）データを取得

指標:
- Caixin Manufacturing PMI: 財新製造業PMI
- Caixin Services PMI: 財新サービス業PMI

データソース:
- DB: economic_calendar_events（CSV初期インポート + FMP蓄積データ）

発表スケジュール:
- 製造業PMI: 毎月1日前後
- サービス業PMI: 毎月3日前後
  ※ 製造業とサービス業は発表日が異なる

キャッシュ方式: FMP発表日時ベース判定方式（製造業を基準）
"""
import json
import re
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    resolve_last_updated_after_fetch,
    should_refresh_by_fmp_schedule,
)

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "china" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "cn_caixin_pmi_cache.json"


class CnCaixinPmiService:
    """Caixin PMIサービス"""

    DATA_CACHE_KEY = "china:cn_caixin_pmi:data"

    ECONALPHA_IDS = {
        "manufacturing": "cn_caixin_manufacturing_pmi",
        "services": "cn_caixin_service_pmi",
    }

    # FMP は Caixin China PMI を 2026 に "S&P Global Manufacturing/Services PMI"
    # (country=CN) へ改称した (Caixin China PMI は S&P Global が編纂)。"Caixin ..."
    # 名は 2026-02 で停止。両名を OR でマッチさせ、旧 Caixin 履歴 + 新 S&P Global を
    # シームレスに結合する (同月の重複は _load_from_db が後勝ちで dedup)。
    EVENT_PATTERNS = {
        "manufacturing": ["Caixin Manufacturing PMI", "S&P Global Manufacturing PMI"],
        "services": ["Caixin Services PMI", "S&P Global Services PMI"],
    }

    def __init__(self):
        pass

    def get_data(
        self,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Caixin PMIデータを取得（製造業、サービス業）

        Returns:
            {
                "manufacturing": {
                    "data": [{"date": "YYYY-MM-DD", "value": float, ...}, ...],
                    "latest": {...},
                },
                "services": {...},
                "next_release_manufacturing": {...} | null,
                "next_release_services": {...} | null,
                "metadata": {...},
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "manufacturing": cached_data.get("manufacturing"),
                        "services": cached_data.get("services"),
                        "next_release_manufacturing": cached_data.get("next_release_manufacturing"),
                        "next_release_services": cached_data.get("next_release_services"),
                        "metadata": cached_data.get("metadata", {}),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        manufacturing_data = self._load_from_db("manufacturing")
        services_data = self._load_from_db("services")

        if manufacturing_data or services_data:
            next_release_mfg = get_next_release_from_fmp(
                self.ECONALPHA_IDS["manufacturing"], country="CN"
            )
            next_release_svc = get_next_release_from_fmp(
                self.ECONALPHA_IDS["services"], country="CN"
            )

            # 発表レース対策ラグガード:
            # 発表時刻ちょうどの再構築でFMPカレンダーの actual が未反映のまま旧月を
            # キャッシュし last_updated=now を刻むと発表消化済み扱いで凍結する
            # （2026-07-03 サービス業PMI: 発表10:45 JSTの23秒後に再構築→5月のまま凍結）。
            # 系列毎にデータ前進を確認し、未前進なら last_updated を発表直前に据え置く。
            # 製造業/サービス業は発表日が異なるため、より過去（=再取得を促す側）を採用。
            last_updated = self._resolve_last_updated(manufacturing_data, services_data)

            cache_payload = {
                "manufacturing": {
                    "data": manufacturing_data,
                    "latest": manufacturing_data[-1] if manufacturing_data else None,
                } if manufacturing_data else None,
                "services": {
                    "data": services_data,
                    "latest": services_data[-1] if services_data else None,
                } if services_data else None,
                "next_release_manufacturing": next_release_mfg,
                "next_release_services": next_release_svc,
                "metadata": {
                    "indicator": "Caixin PMI (Manufacturing / Services)",
                    "source": "S&P Global / Caixin",
                    "manufacturing_records": len(manufacturing_data) if manufacturing_data else 0,
                    "services_records": len(services_data) if services_data else 0,
                    "last_fetched": datetime.now(JST).isoformat(),
                },
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                **cache_payload,
                "cached": False,
                "source": "database",
            }

        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "manufacturing": file_cache.get("manufacturing"),
                "services": file_cache.get("services"),
                "next_release_manufacturing": file_cache.get("next_release_manufacturing"),
                "next_release_services": file_cache.get("next_release_services"),
                "metadata": file_cache.get("metadata", {}),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "manufacturing": None,
            "services": None,
            "next_release_manufacturing": None,
            "next_release_services": None,
            "metadata": {},
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_db(self, pmi_type: str) -> List[Dict[str, Any]]:
        """DBから履歴データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            event_patterns = self.EVENT_PATTERNS.get(pmi_type)
            if not event_patterns:
                return []

            if isinstance(event_patterns, str):
                event_patterns = [event_patterns]

            with SessionLocal() as session:
                pattern_conditions = " OR ".join(
                    [f"event ILIKE :pattern{i}" for i in range(len(event_patterns))]
                )
                query = text(f"""
                    SELECT datetime_utc, event, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'CN'
                      AND ({pattern_conditions})
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)

                params = {}
                for i, pattern in enumerate(event_patterns):
                    params[f"pattern{i}"] = f"%{pattern}%"

                rows = session.execute(query, params).fetchall()

                result = []
                month_map = {
                    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
                }

                for row in rows:
                    dt_utc, event, actual, estimate, previous = row
                    if dt_utc:
                        # イベント名から対象月を抽出（例: "Caixin Manufacturing PMI (Dec)"）
                        match = re.search(r'\((\w{3})\)', event)
                        if match:
                            month_abbr = match.group(1).lower()
                            if month_abbr in month_map:
                                target_month = month_map[month_abbr]
                                target_year = dt_utc.year
                                if target_month > dt_utc.month:
                                    target_year -= 1
                                date_str = f"{target_year}-{target_month:02d}-01"
                            else:
                                prev_month = dt_utc.month - 1 if dt_utc.month > 1 else 12
                                prev_year = dt_utc.year if dt_utc.month > 1 else dt_utc.year - 1
                                date_str = f"{prev_year}-{prev_month:02d}-01"
                        else:
                            # CSV_IMPORTデータ: datetime_utcがデータ月のUTC月初12:00
                            date_str = f"{dt_utc.year}-{dt_utc.month:02d}-01"

                        # 同月の重複（速報値/確報値）は後のデータで上書き
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
                            result[existing_idx] = data_point
                        else:
                            result.append(data_point)

                logger.info(f"Loaded {len(result)} Caixin {pmi_type.capitalize()} PMI records from DB")
                return result

        except Exception as e:
            logger.error(f"Error loading Caixin {pmi_type} PMI from DB: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _resolve_last_updated(
        self,
        manufacturing_data: List[Dict[str, Any]],
        services_data: List[Dict[str, Any]],
    ) -> str:
        """系列毎のラグガードを適用した last_updated を返す。

        前回キャッシュ（Redis→ファイルの順）と比較し、直近発表があったのに
        データが前進していない系列があれば、その発表直前に据え置いて再取得を促す。
        製造業/サービス業で発表日が異なるため、両系列の解決値のうち古い方を採用する。
        """
        prev_cache = redis_client.get(self.DATA_CACHE_KEY) or self._load_file_cache() or {}
        prev_last_updated = prev_cache.get("last_updated")

        def _latest_date(data: Optional[List[Dict[str, Any]]]) -> Optional[str]:
            return data[-1]["date"] if data else None

        def _prev_latest_date(pmi_type: str) -> Optional[str]:
            series = prev_cache.get(pmi_type)
            return _latest_date(series.get("data")) if series else None

        resolved = [
            resolve_last_updated_after_fetch(
                self.ECONALPHA_IDS[pmi_type],
                new_latest_date=_latest_date(new_data),
                prev_latest_date=_prev_latest_date(pmi_type),
                prev_last_updated=prev_last_updated,
            )
            for pmi_type, new_data in (
                ("manufacturing", manufacturing_data),
                ("services", services_data),
            )
        ]
        return min(resolved, key=datetime.fromisoformat)

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP 3分方式）"""
        # 製造業（毎月1日前後）とサービス業（毎月3日前後）は発表日が異なるため、
        # 両系列のOR判定が必須。製造業のみの判定だとサービス業発表日（例: 2026-07-03）に
        # 再取得トリガーが無く、max_age まで旧月のまま凍結する。
        # max_age_hours=24: FMPは発表直後に誤った actual（例: 2026-06 は S&P Global
        # Manufacturing PMI に NBS 非製造業PMI値 50.2 が混入、正=51.7）を配信し数時間後に
        # 訂正することがある。発表レースで last_updated が発表時刻直後に刻まれると通常の
        # 発表日判定では訂正を取り込めず凍結するため、24h の max-age で翌日までに
        # 自己回復させFMP訂正値を反映する。
        return any(
            should_refresh_by_fmp_schedule(
                econalpha_id,
                last_updated_str,
                max_age_hours=24,
            )
            for econalpha_id in self.ECONALPHA_IDS.values()
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> Dict[str, Any]:
        redis_client.delete(self.DATA_CACHE_KEY)
        return {"success": True, "message": "Caixin PMI cache invalidated"}

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        mfg_count = 0
        svc_count = 0
        if cached_data:
            mfg = cached_data.get("manufacturing")
            svc = cached_data.get("services")
            mfg_count = len(mfg.get("data", [])) if mfg else 0
            svc_count = len(svc.get("data", [])) if svc else 0

        return {
            "indicator": "Caixin PMI (Manufacturing / Services)",
            "source": "Database (FMP)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": {
                "manufacturing": mfg_count,
                "services": svc_count,
            },
            "next_release_manufacturing": get_next_release_from_fmp(
                self.ECONALPHA_IDS["manufacturing"], country="CN"
            ),
            "next_release_services": get_next_release_from_fmp(
                self.ECONALPHA_IDS["services"], country="CN"
            ),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
cn_caixin_pmi_service = CnCaixinPmiService()
