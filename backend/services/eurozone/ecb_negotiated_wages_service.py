"""
ECB交渉妥結賃金サービス
ECBから交渉妥結賃金データを取得

指標:
- Negotiated Wage Rates (交渉妥結賃金) 前年比
- Euro Area 20 (2023年以降の固定構成)

データソース:
- ECB Data API (STS.Q.I9.N.INWR.000000.3.ANR)
- Series Parameters:
  - freq: Q (Quarterly)
  - geo: I9 (Euro area 20 countries from 2023)
  - adjustment: N (Neither seasonally nor working day adjusted)
  - indicator: INWR (Indicator of negotiated wage rates)
  - category: 000000 (Total - all sectors)
  - source: 3 (European Central Bank)
  - transformation: ANR (Annual rate of change)

発表スケジュール:
- 四半期ごと（不定期）
- 発表時刻: 18:00-18:10 CET

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.eurozone.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_negotiated_wages_cache.json"


class ECBNegotiatedWagesService:
    """ECB交渉妥結賃金サービス"""

    # ECB Data API base URL
    ECB_API_BASE = "https://data-api.ecb.europa.eu/service/data"

    # Data flow for short-term statistics
    DATAFLOW = "STS"

    # Series key
    # Q = Quarterly
    # I9 = Euro Area 20 (fixed composition as of 1 January 2023)
    # N = Neither seasonally nor working day adjusted
    # INWR = Indicator of negotiated wage rates
    # 000000 = Total (all sectors)
    # 3 = European Central Bank (data source)
    # ANR = Annual rate of change (year-on-year percentage change)
    SERIES_KEY = "Q.I9.N.INWR.000000.3.ANR"

    DATA_CACHE_KEY = "eurozone:ecb_negotiated_wages:data"
    ECONALPHA_ID = "ecb_negotiated_wages"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """交渉妥結賃金データを取得"""
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

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    return {
                        "data": file_cache.get("data", []),
                        "latest": file_cache.get("latest"),
                        "metadata": file_cache.get("metadata", {}),
                        "next_release": file_cache.get("next_release"),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str,
                    }

        # ECB APIから取得
        # ECB STS.INWR 系列は 2025-Q3 で凍結したため、長期履歴は ECB から、直近四半期は
        # FMP (economic_calendar_events の "Negotiated Wage Growth", EU) から取得して結合する。
        ecb_data = self._fetch_ecb_data() or []
        db_data = self._fetch_from_db() or []
        merged = {d["date"]: d["value"] for d in ecb_data}
        merged.update({d["date"]: d["value"] for d in db_data})  # DB(新しい分)で上書き
        wages_data = sorted(
            ({"date": k, "value": v} for k, v in merged.items()),
            key=lambda x: x["date"],
        )

        if wages_data:
            latest = wages_data[-1] if wages_data else None
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            cache_payload = {
                "data": wages_data,
                "latest": latest,
                "metadata": {
                    "source": "European Central Bank (ECB)",
                    "dataflow": f"{self.DATAFLOW}.{self.SERIES_KEY}",
                    "area": "Euro area - 20 countries (from 2023)",
                    "unit": "Annual percentage change",
                    "frequency": "Quarterly",
                    "adjustment": "Neither seasonally nor working day adjusted",
                    "description": "Indicator of Negotiated Wage Rates",
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": wages_data,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "ecb_api",
                "last_updated": datetime.now(JST).isoformat(),
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

    def _fetch_from_db(self) -> Optional[List[Dict]]:
        """economic_calendar_events (FMP) の "Negotiated Wage Growth" (EU) から取得。

        ECB STS.Q.I9.N.INWR 系列は 2025-Q3 で凍結したため、直近四半期はこちらで補完する。
        Returns: [{"date": "YYYY-Qn", "value": float}, ...] (date 昇順)
        """
        import re
        try:
            from core.database import SessionLocal
            from sqlalchemy import text
            with SessionLocal() as session:
                rows = session.execute(text("""
                    SELECT event, event_period, datetime_utc, actual
                    FROM economic_calendar_events
                    WHERE country = 'EU'
                      AND event ILIKE '%Negotiated Wage Growth%'
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)).fetchall()

            result: Dict[str, float] = {}
            for event, period, dt, actual in rows:
                m = re.search(r'Q([1-4])', str(period or "")) or re.search(r'\(Q([1-4])\)', str(event or ""))
                if not m or actual is None or dt is None:
                    continue
                q = int(m.group(1))
                year = dt.year
                # Q4 は翌年 2 月頃に発表されるため対象四半期の年を 1 つ戻す
                if q == 4 and dt.month <= 3:
                    year -= 1
                result[f"{year}-Q{q}"] = float(actual)  # 同四半期は後勝ち (確報値)

            out = [{"date": d, "value": v} for d, v in result.items()]
            out.sort(key=lambda x: x["date"])
            print(f"[ECBNegotiatedWages] Loaded {len(out)} data points from DB (FMP)")
            return out or None
        except Exception as e:
            print(f"[ECBNegotiatedWages] DB load error: {e}")
            return None

    def _fetch_ecb_data(self, start_period: str = "2015-Q1") -> Optional[List[Dict]]:
        """
        ECB APIからデータを取得

        Args:
            start_period: 開始期間 (YYYY-QN)

        Returns:
            データポイントのリスト
        """
        url = f"{self.ECB_API_BASE}/{self.DATAFLOW}/{self.SERIES_KEY}"

        params = {
            "startPeriod": start_period,
            "format": "jsondata"
        }

        try:
            print(f"[ECBNegotiatedWages] Fetching from ECB API: {url}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Extract time series data
            if "dataSets" not in data or len(data["dataSets"]) == 0:
                print("[ECBNegotiatedWages] No data sets found")
                return None

            dataset = data["dataSets"][0]
            if "series" not in dataset:
                print("[ECBNegotiatedWages] No series found in dataset")
                return None

            # Get the first (and should be only) series
            series_data = list(dataset["series"].values())[0]
            observations = series_data.get("observations", {})

            # Get dimension values (time periods)
            dimensions = data.get("structure", {}).get("dimensions", {}).get("observation", [])
            time_dimension = None
            for dim in dimensions:
                if dim.get("id") == "TIME_PERIOD":
                    time_dimension = dim
                    break

            if not time_dimension:
                print("[ECBNegotiatedWages] No time dimension found")
                return None

            time_values = time_dimension.get("values", [])

            # Build result list
            result = []
            for obs_key, obs_value in observations.items():
                time_index = int(obs_key)
                if time_index < len(time_values):
                    date_str = time_values[time_index].get("id")
                    value = obs_value[0] if isinstance(obs_value, list) and len(obs_value) > 0 else obs_value

                    if value is not None:
                        result.append({
                            "date": date_str,
                            "value": float(value)
                        })

            # Sort by date
            result.sort(key=lambda x: x["date"])

            print(f"[ECBNegotiatedWages] Successfully fetched {len(result)} data points from ECB")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[ECBNegotiatedWages] API request error: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[ECBNegotiatedWages] Data parsing error: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ECBNegotiatedWages] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ECBNegotiatedWages] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "ECB Negotiated Wages",
            "source": "ECB Data API",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ecb_negotiated_wages_service = ECBNegotiatedWagesService()
