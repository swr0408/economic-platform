"""
ユーロ圏消費者信頼感指数サービス
Eurostat APIから Consumer Confidence Indicator データを取得

指標:
- Consumer Confidence Indicator - Euro Area 20
- 季節調整済み (SA)
- バランス値 (BAL)

データソース:
- Eurostat (European Statistical Office)
- Dataset: ei_bsco_m (Business and Consumer Surveys)

発表スケジュール:
- 毎月25日〜翌月8日 18:00-18:10 CET

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import re
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.eurozone.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
    resolve_last_updated_after_fetch,
)

# 月略称 → 月番号（FMPイベントラベル "(Jun)" 等の解析用）
_MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "eurostat_consumer_confidence_cache.json"


class EurostatConsumerConfidenceService:
    """ユーロ圏消費者信頼感指数サービス (Eurostat API)"""

    DATA_CACHE_KEY = "eurozone:consumer_confidence:data"
    ECONALPHA_ID = "eurostat_consumer_confidence"
    FMP_EVENT_PATTERN = "Consumer Confidence"

    # Eurostat API設定
    EUROSTAT_API_BASE = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data"
    DATASET = "ei_bsco_m"

    # Series key components:
    # M = Monthly
    # BS-CSMCI = Consumer confidence indicator
    # SA = Seasonally adjusted, not calendar adjusted
    # BAL = Balance
    # EA21 = Euro area - 21 countries。2026 にユーロ圏が 21 か国へ拡大し、
    #        EA20 集計は 2025-12 で値が停止 (期間は宣言されるが value=null)。
    #        EA21 は 2000-01 以降の全履歴 + 2026 の最新値を持つため EA21 を使用。
    SERIES_KEY = "M.BS-CSMCI.SA.BAL.EA21"

    def __init__(self):
        pass

    def get_consumer_confidence_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """消費者信頼感指数データを取得"""
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
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # 取得前の最新月（発表時刻レース ラグガード用）
        prev_cache = redis_client.get(self.DATA_CACHE_KEY) or {}
        prev_latest_date = (prev_cache.get("latest") or {}).get("date")
        prev_last_updated = prev_cache.get("last_updated")

        # Eurostat APIから取得
        api_result = self._fetch_from_eurostat()
        if api_result:
            # 速報値補完: Eurostat `ei_bsco_m` はDG ECFINフラッシュに数時間〜数日ラグがある。
            # FMP（economic_calendar_events）にあるフラッシュ実値で、Eurostat最新月より先の
            # 月を補完する（同一スケール=DG ECFIN消費者信頼感バランス、検証済 May -19.0 一致）。
            api_result = self._supplement_from_fmp(api_result)

            next_release = get_next_release_by_pattern(self.FMP_EVENT_PATTERN)
            latest = api_result[-1] if api_result else None

            # 発表時刻レース対策: 取得データが新月に未反映なら last_updated を発表直前に据え置き、
            # 次回ポーリングで再取得を促す（旧月を「発表消化済み」として翌月まで凍結させない）。
            new_latest_date = (latest or {}).get("date")
            resolved_last_updated = resolve_last_updated_after_fetch(
                self.FMP_EVENT_PATTERN, new_latest_date, prev_latest_date, prev_last_updated,
            )

            cache_payload = {
                "data": api_result,
                "latest": latest,
                "metadata": {
                    "source": "Eurostat",
                    "dataset": self.DATASET,
                    "indicator": "Consumer Confidence Indicator - Euro Area 21",
                    "unit": "Balance",
                    "adjustment": "Seasonally adjusted",
                    "description": "消費者信頼感指数（ユーロ圏21カ国）",
                },
                "next_release": next_release,
                "last_updated": resolved_last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": api_result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "eurostat_api",
                "last_updated": resolved_last_updated,
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _fetch_from_eurostat(self, start_date: str = "2015-01") -> Optional[List[Dict]]:
        """Eurostat APIからデータを取得"""
        url = f"{self.EUROSTAT_API_BASE}/{self.DATASET}/{self.SERIES_KEY}"

        params = {
            "startPeriod": start_date,
            "format": "JSON"
        }

        try:
            print(f"[EurostatConsumerConfidence] Fetching data from Eurostat: {self.SERIES_KEY}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Eurostat JSON形式を解析
            values = data.get("value", {})
            if not values:
                print("[EurostatConsumerConfidence] No values found in response")
                return None

            # 時間次元を取得
            time_dimension = data.get("dimension", {}).get("time", {})
            time_category = time_dimension.get("category", {})
            time_index = time_category.get("index", {})

            # index -> date のマッピングを作成
            index_to_date = {v: k for k, v in time_index.items()}

            # 結果リストを構築
            result = []
            for idx_str, value in values.items():
                idx = int(idx_str)
                date_str = index_to_date.get(idx)

                if date_str and value is not None:
                    result.append({
                        "date": date_str,
                        "value": float(value)
                    })

            # 日付でソート
            result.sort(key=lambda x: x["date"])

            print(f"[EurostatConsumerConfidence] Fetched {len(result)} data points")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[EurostatConsumerConfidence] Request error: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[EurostatConsumerConfidence] Parse error: {e}")
            return None

    def _supplement_from_fmp(self, eurostat_data: List[Dict]) -> List[Dict]:
        """FMP（economic_calendar_events）の速報(フラッシュ)実値で Eurostat 最新月より
        先の月を補完する。

        Eurostat `ei_bsco_m` はDG ECFINフラッシュに数時間〜数日ラグするため、発表済みの
        当月フラッシュが反映されない。FMPは同じDG ECFIN消費者信頼感を当月フラッシュとして
        持つ（イベント例: "Consumer Confidence (Jun)" actual=-17.7）。Eurostat最新月より
        後の月だけを追記し、Eurostatが後日確報を出したらそちらが優先される（追記しない）。
        """
        if not eurostat_data:
            return eurostat_data
        try:
            latest_eurostat = eurostat_data[-1]["date"]  # "YYYY-MM"
            existing = {d["date"] for d in eurostat_data}

            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                rows = session.execute(
                    text("""
                        SELECT datetime_utc, event, actual
                        FROM economic_calendar_events
                        WHERE country = 'EU'
                          AND event ILIKE '%Consumer Confidence%'
                          AND actual IS NOT NULL
                          AND datetime_utc >= NOW() - INTERVAL '120 days'
                        ORDER BY datetime_utc ASC
                    """)
                ).fetchall()

            # ref月 → 値（同一refは後勝ち=確報優先）
            by_month: Dict[str, float] = {}
            for dt_utc, event, actual in rows:
                ref = self._parse_ref_month(event, dt_utc)
                if ref and actual is not None:
                    by_month[ref] = float(actual)

            added = []
            for ref, val in by_month.items():
                if ref not in existing and ref > latest_eurostat:
                    eurostat_data.append({"date": ref, "value": val})
                    added.append(ref)

            if added:
                eurostat_data.sort(key=lambda x: x["date"])
                print(f"[EurostatConsumerConfidence] FMP flash supplement added: {added}")

            return eurostat_data
        except Exception as e:
            print(f"[EurostatConsumerConfidence] FMP supplement error: {e}")
            return eurostat_data

    @staticmethod
    def _parse_ref_month(label: str, release_dt: datetime) -> Optional[str]:
        """イベントラベルの "(Jun)" 等から参照月 "YYYY-MM" を復元。

        消費者信頼感のフラッシュは当月分（"(Jun)" は6月発表=6月分）だが、確報は
        翌月に前月分を出すこともある（"(Dec)" を1月に発表）。ラベル月が発表月より
        先行している場合は前年と判定する。
        """
        m = re.search(r"\(([A-Za-z]{3})\)", label or "")
        if not m:
            return None
        mon = _MONTH_ABBR.get(m.group(1).lower())
        if not mon:
            return None
        year = release_dt.year
        # 例: ラベル Dec を 1月に発表 → mon(12) > release.month(1)+1 → 前年
        if mon > release_dt.month + 1:
            year -= 1
        return f"{year:04d}-{mon:02d}"

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_pattern(self.FMP_EVENT_PATTERN, last_updated_str)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[EurostatConsumerConfidence] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[EurostatConsumerConfidence] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Eurostat Consumer Confidence",
            "source": "Eurostat API",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(self.FMP_EVENT_PATTERN),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
eurostat_consumer_confidence_service = EurostatConsumerConfidenceService()
