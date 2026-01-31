"""
ユーロ圏求人欠員率サービス
Eurostatから求人欠員率データを取得

指標:
- Job Vacancy Rate (求人欠員率) - ユーロ圏
- 四半期データ

データソース:
- Eurostat API (jvs_q_nace2 dataset)
- Series Parameters:
  - freq: Q (Quarterly)
  - s_adj: NSA (Not seasonally adjusted)
  - nace_r2: B-S (Industry, construction and services)
  - sizeclas: TOTAL (All sizes)
  - indic_em: JVR (Job vacancy rate)
  - geo: EA20 (Euro area - 20 countries)

発表スケジュール:
- Eurostatリリースカレンダーから取得
- https://ec.europa.eu/eurostat/o/calendars/eventsIcal

キャッシュ方式: Eurostatリリースカレンダーベース更新
"""
import json
import re
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "eurostat_job_vacancy_cache.json"


class EurostatJobVacancyService:
    """ユーロ圏求人欠員率サービス（Eurostat API）"""

    # Eurostat API base URL
    EUROSTAT_API_BASE = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data"

    # Dataset code
    DATASET = "jvs_q_nace2"

    # Series parameters for EA20 Job Vacancy Rate
    # Series key: Q.NSA.B-S.TOTAL.JVR.EA20
    SERIES_PARAMS = {
        "freq": "Q",           # Quarterly
        "s_adj": "NSA",        # Not seasonally adjusted
        "nace_r2": "B-S",      # Industry, construction and services
        "sizeclas": "TOTAL",   # All sizes
        "indic_em": "JVR",     # Job vacancy rate
        "geo": "EA20"          # Euro area - 20 countries
    }

    DATA_CACHE_KEY = "eurozone:eurostat_job_vacancy:data"
    CALENDAR_CACHE_KEY = "eurozone:eurostat_job_vacancy:calendar"

    # Eurostat リリースカレンダーURL
    EUROSTAT_CALENDAR_URL = "https://ec.europa.eu/eurostat/o/calendars/eventsIcal"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """求人欠員率データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str, cached_data):
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
                if last_updated_str and not self._should_refresh(last_updated_str, file_cache):
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

        # Eurostat APIから取得
        job_vacancy_data = self._fetch_eurostat_data() or []

        if job_vacancy_data:
            latest = job_vacancy_data[-1] if job_vacancy_data else None

            # データ更新時にカレンダーキャッシュをクリアして再取得
            self._invalidate_calendar_cache()
            next_release = self._calculate_next_release()

            cache_payload = {
                "data": job_vacancy_data,
                "latest": latest,
                "metadata": {
                    "source": "Eurostat - Job Vacancy Statistics",
                    "dataset": self.DATASET,
                    "area": "Euro area - 20 countries",
                    "unit": "Percentage",
                    "frequency": "Quarterly",
                    "adjustment": "Not seasonally adjusted",
                    "sector": "Industry, construction and services (B-S)",
                    "description": "Job vacancy rate",
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": job_vacancy_data,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "eurostat_api",
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

    def _fetch_eurostat_data(self, start_period: str = "2015-Q1") -> Optional[List[Dict]]:
        """
        Eurostat APIからデータを取得

        Args:
            start_period: 開始期間 (YYYY-QN)

        Returns:
            データポイントのリスト
        """
        # Build series key: Q.NSA.B-S.TOTAL.JVR.EA20
        series_key = ".".join([
            self.SERIES_PARAMS["freq"],
            self.SERIES_PARAMS["s_adj"],
            self.SERIES_PARAMS["nace_r2"],
            self.SERIES_PARAMS["sizeclas"],
            self.SERIES_PARAMS["indic_em"],
            self.SERIES_PARAMS["geo"]
        ])

        url = f"{self.EUROSTAT_API_BASE}/{self.DATASET}/{series_key}/"

        params = {
            "format": "JSON",
            "startPeriod": start_period
        }

        try:
            print(f"[EurostatJobVacancy] Fetching from Eurostat API: {url}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Extract dimensions and values
            dimensions = data.get("dimension", {})
            time_dim = dimensions.get("time", {})
            time_category = time_dim.get("category", {})
            time_index = time_category.get("index", {})

            values = data.get("value", {})

            if not time_index or not values:
                print("[EurostatJobVacancy] No data found in Eurostat response")
                return None

            # Create index to time mapping
            idx_to_time = {v: k for k, v in time_index.items()}

            # Build result list
            result = []
            for val_idx_str in sorted(values.keys(), key=lambda x: int(x)):
                val_idx = int(val_idx_str)
                time_period = idx_to_time.get(val_idx)
                value = values.get(val_idx_str)

                if time_period and value is not None:
                    result.append({
                        "date": time_period,
                        "value": float(value)
                    })

            print(f"[EurostatJobVacancy] Successfully fetched {len(result)} data points from Eurostat")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[EurostatJobVacancy] API request error: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[EurostatJobVacancy] Data parsing error: {e}")
            return None

    def _should_refresh(self, last_updated_str: str, cached_data: Dict[str, Any]) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        Eurostatリリースカレンダーの発表日を過ぎていれば更新
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 次回発表日を取得
            next_release = self._get_next_release_from_calendar()
            if not next_release:
                # カレンダーが取得できない場合は24時間ごとに更新
                if (now - last_updated).total_seconds() > 86400:
                    return True
                return False

            # 発表日を過ぎているか確認
            release_date_str = next_release.get("date")
            if release_date_str:
                release_date = datetime.strptime(release_date_str, "%Y-%m-%d").replace(tzinfo=JST)
                # 発表日の11:00 CET = 19:00 JST 以降で、最終更新が発表日前なら更新
                release_datetime = release_date.replace(hour=19, minute=0, second=0)
                if now >= release_datetime and last_updated < release_datetime:
                    return True

            return False

        except Exception as e:
            print(f"[EurostatJobVacancy] Error checking refresh status: {e}")
            return False

    def _get_next_release_from_calendar(self) -> Optional[Dict[str, Any]]:
        """
        Eurostatリリースカレンダーから次回発表日を取得
        """
        # キャッシュをチェック（1日間有効）
        cached = redis_client.get(self.CALENDAR_CACHE_KEY)
        if cached:
            cache_time = cached.get("cached_at")
            if cache_time:
                try:
                    cache_dt = datetime.fromisoformat(cache_time)
                    if (datetime.now(JST) - cache_dt).total_seconds() < 86400:
                        return cached.get("next_release")
                except Exception:
                    pass

        # カレンダーを取得
        next_release = self._fetch_calendar_data()

        # キャッシュに保存
        if next_release:
            redis_client.set(self.CALENDAR_CACHE_KEY, {
                "next_release": next_release,
                "cached_at": datetime.now(JST).isoformat()
            }, expire=86400)

        return next_release

    def _fetch_calendar_data(self) -> Optional[Dict[str, Any]]:
        """
        EurostatカレンダーからJob Vacancyの次回発表日を取得
        """
        try:
            print("[EurostatJobVacancy] Fetching Eurostat release calendar...")
            response = requests.get(self.EUROSTAT_CALENDAR_URL, timeout=30)
            response.raise_for_status()

            ical_text = response.text
            now = datetime.now(JST)

            # Job Vacancyイベントを探す（Euro indicators releaseのみ）
            # パターン: DTSTART;VALUE=DATE:YYYYMMDD followed by SUMMARY:Job vacancy
            events = []
            lines = ical_text.split('\n')
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith('DTSTART;VALUE=DATE:'):
                    date_str = line.replace('DTSTART;VALUE=DATE:', '')
                    # 次の数行でSUMMARYとX-CATEGORYを探す
                    summary = None
                    category = None
                    for j in range(i + 1, min(i + 10, len(lines))):
                        check_line = lines[j].strip()
                        if check_line.startswith('SUMMARY:'):
                            summary = check_line.replace('SUMMARY:', '')
                        if check_line.startswith('X-CATEGORY:'):
                            category = check_line.replace('X-CATEGORY:', '')
                        if check_line.startswith('END:VEVENT'):
                            break

                    # Job vacancy（flash estimatesではない）でEuro indicators releaseを含むもの
                    if summary and summary == 'Job vacancy' and category and 'Euro indicators release' in category:
                        try:
                            event_date = datetime.strptime(date_str, '%Y%m%d').replace(tzinfo=JST)
                            if event_date.date() >= now.date():
                                events.append({
                                    "date": event_date.strftime('%Y-%m-%d'),
                                    "summary": summary,
                                    "datetime_jst": event_date.replace(hour=19, minute=0).strftime('%Y-%m-%d %H:%M'),
                                    "time_jst": "19:00",
                                })
                        except ValueError:
                            pass
                i += 1

            # 最も近い発表日を返す
            if events:
                events.sort(key=lambda x: x["date"])
                next_event = events[0]
                return {
                    "date": next_event["date"],
                    "datetime_jst": next_event["datetime_jst"],
                    "time_jst": next_event["time_jst"],
                    "label": f"Job Vacancy Rate ({next_event['date']})",
                }

            print("[EurostatJobVacancy] No upcoming Job Vacancy releases found in calendar")
            return None

        except requests.exceptions.RequestException as e:
            print(f"[EurostatJobVacancy] Calendar fetch error: {e}")
            return None
        except Exception as e:
            print(f"[EurostatJobVacancy] Calendar parsing error: {e}")
            return None

    def _calculate_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表予定を取得（Eurostatカレンダーから）
        """
        return self._get_next_release_from_calendar()

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[EurostatJobVacancy] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[EurostatJobVacancy] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        self._invalidate_calendar_cache()
        return redis_client.delete(self.DATA_CACHE_KEY)

    def _invalidate_calendar_cache(self) -> bool:
        """カレンダーキャッシュを無効化"""
        return redis_client.delete(self.CALENDAR_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Eurostat Job Vacancy Rate",
            "source": "Eurostat API (jvs_q_nace2)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._calculate_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
eurostat_job_vacancy_service = EurostatJobVacancyService()
