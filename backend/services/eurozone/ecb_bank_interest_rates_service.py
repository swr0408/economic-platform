"""
ECB Bank Interest Rates サービス
ECB Data APIから銀行金利データを取得

指標:
- Loans to corporations (new business): 企業向け新規融資金利
- Loans to households for house purchase (new business): 住宅ローン新規金利

データソース:
- ECB Legacy API (MIR): MIR.M.U2.B.A2A.A.R.A.2240.EUR.N (企業向け)
- ECB Legacy API (MIR): MIR.M.U2.B.A2C.A.R.A.2250.EUR.N (住宅ローン)

発表スケジュール:
- 月次発表（ECBカレンダーより取得）
- https://www.ecb.europa.eu/press/calendars/statscal/mfm/html/stprmf.en.html

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path
from bs4 import BeautifulSoup
import re

from core.redis_client import redis_client


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
CET = ZoneInfo("Europe/Berlin")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "monetary_policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_bank_interest_rates_cache.json"
SCHEDULE_CACHE_FILE = CACHE_DIR / "ecb_mir_schedule_cache.json"


class ECBBankInterestRatesService:
    """ECB Bank Interest Rates サービス"""

    # ECB Legacy API（SDMX形式）
    ECB_LEGACY_API_BASE = "https://data-api.ecb.europa.eu/service/data"

    # シリーズキー（Legacy API用）
    # MIR = MFI Interest Rate Statistics
    # M = Monthly
    # U2 = Euro Area
    # B = Outstanding amounts / New business
    # A2A = Loans to non-financial corporations
    # A2C = Loans to households for house purchase
    # A = All maturities
    # R = Rate
    # A = Annualized agreed rate (AAR)
    # 2240 = Total new business
    # 2250 = Housing loans total
    # EUR = Euro
    # N = Neither seasonally nor working day adjusted
    SERIES_KEY_CORPORATIONS = "M.U2.B.A2A.A.R.A.2240.EUR.N"  # 企業向け新規融資金利
    SERIES_KEY_HOUSING = "M.U2.B.A2C.A.R.A.2250.EUR.N"       # 住宅ローン新規金利

    # ECBカレンダーURL（MIR発表スケジュール）
    ECB_CALENDAR_URL = "https://www.ecb.europa.eu/press/calendars/statscal/mfm/html/stprmf.en.html"

    DATA_CACHE_KEY = "monetary_policy:ecb_bank_interest_rates:data"
    SCHEDULE_CACHE_KEY = "monetary_policy:ecb_bank_interest_rates:schedule"

    def __init__(self):
        pass

    def _fetch_series_data(self, series_key: str, start_date: str = "2015-01-01") -> Optional[List[Dict]]:
        """ECB Legacy API（SDMX）からシリーズデータを取得"""
        url = f"{self.ECB_LEGACY_API_BASE}/MIR/{series_key}"
        params = {
            "startPeriod": start_date,
            "format": "jsondata"
        }

        try:
            print(f"[ECB Bank Interest Rates] Fetching: {url}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if "dataSets" not in data or len(data["dataSets"]) == 0:
                print(f"[ECB Bank Interest Rates] No data sets found for {series_key}")
                return None

            dataset = data["dataSets"][0]
            if "series" not in dataset:
                print(f"[ECB Bank Interest Rates] No series found for {series_key}")
                return None

            series_data = list(dataset["series"].values())[0]
            observations = series_data.get("observations", {})

            # 時間次元を取得
            dimensions = data.get("structure", {}).get("dimensions", {}).get("observation", [])
            time_dimension = None
            for dim in dimensions:
                if dim.get("id") == "TIME_PERIOD":
                    time_dimension = dim
                    break

            if not time_dimension:
                print(f"[ECB Bank Interest Rates] No time dimension found for {series_key}")
                return None

            time_values = time_dimension.get("values", [])

            result = []
            for obs_key, obs_value in observations.items():
                time_index = int(obs_key)
                if time_index < len(time_values):
                    period = time_values[time_index].get("id")
                    value = obs_value[0] if isinstance(obs_value, list) and len(obs_value) > 0 else obs_value

                    if value is not None and period:
                        # 日付を月初形式に変換（2024-01 → 2024-01-01）
                        date_str = f"{period}-01" if len(period) == 7 else period
                        result.append({
                            "date": date_str,
                            "value": float(value)
                        })

            result.sort(key=lambda x: x["date"])
            print(f"[ECB Bank Interest Rates] Fetched {len(result)} data points for {series_key}")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[ECB Bank Interest Rates] Request error for {series_key}: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[ECB Bank Interest Rates] Parse error for {series_key}: {e}")
            return None

    def _fetch_release_schedule(self) -> Optional[Dict[str, Any]]:
        """ECBカレンダーからMIR発表スケジュールを取得"""
        try:
            print(f"[ECB Bank Interest Rates] Fetching release schedule from: {self.ECB_CALENDAR_URL}")
            response = requests.get(self.ECB_CALENDAR_URL, timeout=30)
            response.raise_for_status()

            # ページ全体のテキストから日付パターンを抽出
            # 形式: "DD/MM/YYYY HH:MM CET" (例: "04/02/2026 10:00 CET")
            text = response.text
            releases = []

            # DD/MM/YYYY HH:MM CET パターンを検索
            date_pattern = re.findall(r'(\d{2})/(\d{2})/(\d{4})\s+(\d{2}):(\d{2})\s+CET', text)

            for match in date_pattern:
                day, month, year, hour, minute = match
                try:
                    release_datetime = datetime(
                        int(year), int(month), int(day),
                        int(hour), int(minute),
                        tzinfo=CET
                    )
                    release_datetime_jst = release_datetime.astimezone(JST)

                    releases.append({
                        "date": release_datetime.strftime("%Y-%m-%d"),
                        "datetime_cet": release_datetime.isoformat(),
                        "datetime_jst": release_datetime_jst.isoformat(),
                        "time_cet": f"{hour}:{minute}",
                        "time_jst": release_datetime_jst.strftime("%H:%M")
                    })
                except ValueError as e:
                    print(f"[ECB Bank Interest Rates] Date parse error: {e}")
                    continue

            if releases:
                # 重複を除去して日付でソート
                seen = set()
                unique_releases = []
                for r in releases:
                    if r["date"] not in seen:
                        seen.add(r["date"])
                        unique_releases.append(r)
                unique_releases.sort(key=lambda x: x["date"])

                # 次回発表日を特定
                now = datetime.now(CET)
                next_release = None
                for release in unique_releases:
                    release_datetime = datetime.fromisoformat(release["datetime_cet"])
                    if release_datetime >= now:
                        next_release = release
                        break

                print(f"[ECB Bank Interest Rates] Found {len(unique_releases)} releases, next: {next_release}")
                return {
                    "releases": unique_releases,
                    "next_release": next_release,
                    "fetched_at": datetime.now(JST).isoformat()
                }

            print("[ECB Bank Interest Rates] No releases found in calendar")
            return None

        except requests.exceptions.RequestException as e:
            print(f"[ECB Bank Interest Rates] Schedule fetch error: {e}")
            return None
        except Exception as e:
            print(f"[ECB Bank Interest Rates] Schedule parse error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得（キャッシュ付き）"""
        now = datetime.now(JST)

        # Redisキャッシュチェック
        cached_schedule = redis_client.get(self.SCHEDULE_CACHE_KEY)
        if cached_schedule:
            fetched_at_str = cached_schedule.get("fetched_at")
            if fetched_at_str:
                fetched_at = datetime.fromisoformat(fetched_at_str)
                if fetched_at.tzinfo is None:
                    fetched_at = fetched_at.replace(tzinfo=JST)

                # 半年に一度の更新判定（1月10日または7月10日を過ぎたら更新）
                should_update = False
                current_month = now.month
                current_day = now.day

                if current_month == 1 and current_day >= 10:
                    # 1月10日以降: 前年の取得なら更新
                    if fetched_at.year < now.year:
                        should_update = True
                elif current_month == 7 and current_day >= 10:
                    # 7月10日以降: 6月以前の取得なら更新
                    if fetched_at.month < 7 or fetched_at.year < now.year:
                        should_update = True
                elif current_month > 7:
                    # 8月以降: 6月以前の取得なら更新
                    if fetched_at.month < 7 or fetched_at.year < now.year:
                        should_update = True

                if not should_update:
                    # キャッシュから次回発表日を探す
                    releases = cached_schedule.get("releases", [])
                    today = now.strftime("%Y-%m-%d")
                    for release in releases:
                        if release.get("date", "") >= today:
                            return release
                    # 次回発表日が見つからない場合は更新
                    should_update = True

                if not should_update:
                    return cached_schedule.get("next_release")

        # ECBカレンダーから取得
        schedule_data = self._fetch_release_schedule()
        if schedule_data:
            redis_client.set(self.SCHEDULE_CACHE_KEY, schedule_data, expire=0)  # 無期限（半年ロジックで管理）
            self._save_schedule_cache(schedule_data)
            return schedule_data.get("next_release")

        # ファイルキャッシュフォールバック
        file_cache = self._load_schedule_cache()
        if file_cache:
            releases = file_cache.get("releases", [])
            today = now.strftime("%Y-%m-%d")
            for release in releases:
                if release.get("date", "") >= today:
                    return release

        return None

    def get_bank_interest_rates_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ECB Bank Interest Ratesデータを取得（企業向け・住宅ローン）"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    next_release = self._get_next_release()
                    return {
                        "corporations": cached_data.get("corporations", {}),
                        "housing": cached_data.get("housing", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ECB APIからデータ取得
        corporations_data = self._fetch_series_data(self.SERIES_KEY_CORPORATIONS) or []
        housing_data = self._fetch_series_data(self.SERIES_KEY_HOUSING) or []

        has_data = len(corporations_data) > 0 or len(housing_data) > 0

        if has_data:
            next_release = self._get_next_release()

            corporations_latest = corporations_data[-1] if corporations_data else None
            housing_latest = housing_data[-1] if housing_data else None

            cache_payload = {
                "corporations": {
                    "data": corporations_data,
                    "latest": corporations_latest,
                },
                "housing": {
                    "data": housing_data,
                    "latest": housing_latest,
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "corporations": {
                    "data": corporations_data,
                    "latest": corporations_latest,
                },
                "housing": {
                    "data": housing_data,
                    "latest": housing_latest,
                },
                "next_release": next_release,
                "cached": False,
                "source": "ecb_api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            next_release = self._get_next_release()
            return {
                "corporations": file_cache.get("corporations", {}),
                "housing": file_cache.get("housing", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "corporations": {"data": [], "latest": None},
            "housing": {"data": [], "latest": None},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)

            # 次回発表日を確認
            next_release = self._get_next_release()
            if next_release:
                next_date = datetime.strptime(next_release["date"], "%Y-%m-%d")
                next_datetime = next_date.replace(hour=18, minute=0, tzinfo=JST)  # 18:00 JST

                # 発表日時を過ぎていて、最終更新が発表前なら更新
                if now >= next_datetime and last_updated < next_datetime:
                    return True

            # 24時間以上経過していたら更新
            if (now - last_updated).total_seconds() > 86400:
                return True

            return False
        except Exception as e:
            print(f"[ECB Bank Interest Rates] Error checking refresh: {e}")
            return True

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

    def _load_schedule_cache(self) -> Optional[Dict[str, Any]]:
        """スケジュールファイルキャッシュを読み込み"""
        try:
            if not SCHEDULE_CACHE_FILE.exists():
                return None
            with open(SCHEDULE_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load schedule cache: {e}")
            return None

    def _save_schedule_cache(self, data: Dict[str, Any]) -> None:
        """スケジュールファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(SCHEDULE_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Schedule cache saved to {SCHEDULE_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save schedule cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        redis_client.delete(self.SCHEDULE_CACHE_KEY)
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        corporations_data = cached_data.get("corporations", {}) if cached_data else {}
        housing_data = cached_data.get("housing", {}) if cached_data else {}

        return {
            "indicator": "ECB Bank Interest Rates",
            "source": "ECB Data API (MIR)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "corporations_count": len(corporations_data.get("data", [])),
            "housing_count": len(housing_data.get("data", [])),
            "corporations_latest": corporations_data.get("latest"),
            "housing_latest": housing_data.get("latest"),
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
ecb_bank_interest_rates_service = ECBBankInterestRatesService()
