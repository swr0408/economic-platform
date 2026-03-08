"""
グローバル経済政策不確実性指数（EPU）サービス

指標:
- Global EPU Index (月次) - FRED GEPUCURRENT
- US EPU Index (月次) - policyuncertainty.com Excel
- US EPU Index (日次) - policyuncertainty.com CSV

データソース:
- FRED (Federal Reserve Economic Data) - Global EPU
- policyuncertainty.com - US Monthly/Daily EPU

キャッシュ方式: 24時間固定TTL方式
"""
import os
import json
import csv
import io
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "global" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

GLOBAL_CACHE_FILE = CACHE_DIR / "global_epu_cache.json"
US_MONTHLY_CACHE_FILE = CACHE_DIR / "us_monthly_epu_cache.json"
US_DAILY_CACHE_FILE = CACHE_DIR / "us_daily_epu_cache.json"


class GlobalEpuService:
    """グローバル経済政策不確実性指数（EPU）サービス"""

    GLOBAL_CACHE_KEY = "global:epu:global:data"
    US_MONTHLY_CACHE_KEY = "global:epu:us_monthly:data"
    US_DAILY_CACHE_KEY = "global:epu:us_daily:data"

    FRED_BASE_URL = "https://api.stlouisfed.org/fred"
    GLOBAL_SERIES_ID = "GEPUCURRENT"
    DEFAULT_START_DATE = "1997-01-01"

    US_MONTHLY_XLSX_URL = "https://www.policyuncertainty.com/media/US_Policy_Uncertainty_Data.xlsx"
    US_DAILY_CSV_URL = "https://www.policyuncertainty.com/media/All_Daily_Policy_Data.csv"

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_data(self, series: str = "global", force_refresh: bool = False) -> Dict[str, Any]:
        """EPUデータを取得"""
        if series == "us_monthly":
            return self._get_us_monthly_data(force_refresh)
        if series == "us_daily":
            return self._get_us_daily_data(force_refresh)
        return self._get_global_data(force_refresh)

    # ========== Global EPU (Monthly, FRED) ==========

    def _get_global_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """グローバルEPU月次データを取得（FRED）"""
        if not force_refresh:
            cached_data = redis_client.get(self.GLOBAL_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": None,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        api_result = self._fetch_global_from_fred()
        if api_result:
            latest = api_result[-1] if api_result else None
            metadata = {
                "source": "FRED (Federal Reserve Economic Data)",
                "series_id": self.GLOBAL_SERIES_ID,
                "indicator": "Global Economic Policy Uncertainty Index",
                "unit": "Index",
                "frequency": "Monthly",
                "description": "GDP-weighted average of national EPU indices for 20 countries",
            }

            cache_payload = {
                "data": api_result,
                "latest": latest,
                "metadata": metadata,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.GLOBAL_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload, GLOBAL_CACHE_FILE)

            return {
                "data": api_result,
                "latest": latest,
                "metadata": metadata,
                "next_release": None,
                "cached": False,
                "source": "fred_api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache(GLOBAL_CACHE_FILE)
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": None,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {"data": [], "latest": None, "metadata": {}, "next_release": None, "cached": False, "source": "none", "last_updated": None}

    def _fetch_global_from_fred(self) -> Optional[List[Dict]]:
        """FRED APIからグローバルEPUデータを取得"""
        try:
            if not self.api_key:
                print("[GlobalEPU] FRED_API_KEY not set")
                return None

            print(f"[GlobalEPU] Fetching {self.GLOBAL_SERIES_ID} from FRED...")
            url = f"{self.FRED_BASE_URL}/series/observations"
            params = {
                "series_id": self.GLOBAL_SERIES_ID,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": self.DEFAULT_START_DATE,
                "sort_order": "asc",
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            observations = data.get("observations", [])
            result = []
            for obs in observations:
                if obs.get("value") and obs["value"] != ".":
                    try:
                        date_str = obs["date"][:7] + "-01"
                        value = round(float(obs["value"]), 2)
                        result.append({"date": date_str, "value": value})
                    except (ValueError, TypeError):
                        continue

            print(f"[GlobalEPU] Fetched {len(result)} records from FRED")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[GlobalEPU] FRED request error: {e}")
            return None
        except (KeyError, ValueError, TypeError) as e:
            print(f"[GlobalEPU] FRED parse error: {e}")
            return None

    # ========== US Monthly EPU (Excel) ==========

    def _get_us_monthly_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """米国EPU月次データを取得（Excel）"""
        if not force_refresh:
            cached_data = redis_client.get(self.US_MONTHLY_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": None,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        xlsx_result = self._fetch_us_monthly_xlsx()
        if xlsx_result:
            latest = xlsx_result[-1] if xlsx_result else None
            metadata = {
                "source": "Economic Policy Uncertainty (policyuncertainty.com)",
                "indicator": "US Economic Policy Uncertainty Index (Monthly)",
                "unit": "Index",
                "frequency": "Monthly",
                "description": "News-based index of US economic policy uncertainty (monthly)",
            }

            cache_payload = {
                "data": xlsx_result,
                "latest": latest,
                "metadata": metadata,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.US_MONTHLY_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload, US_MONTHLY_CACHE_FILE)

            return {
                "data": xlsx_result,
                "latest": latest,
                "metadata": metadata,
                "next_release": None,
                "cached": False,
                "source": "xlsx",
                "last_updated": datetime.now(JST).isoformat(),
            }

        file_cache = self._load_file_cache(US_MONTHLY_CACHE_FILE)
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": None,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {"data": [], "latest": None, "metadata": {}, "next_release": None, "cached": False, "source": "none", "last_updated": None}

    def _fetch_us_monthly_xlsx(self) -> Optional[List[Dict]]:
        """policyuncertainty.comからUS月次EPU Excelを取得"""
        try:
            print("[GlobalEPU] Fetching US Monthly EPU Excel...")
            response = requests.get(self.US_MONTHLY_XLSX_URL, timeout=30)
            response.raise_for_status()

            df = pd.read_excel(io.BytesIO(response.content), sheet_name="Main News Index")

            result = []
            for _, row in df.iterrows():
                try:
                    year = int(row["Year"])
                    month = int(row["Month"])
                    value = float(row["News_Based_Policy_Uncert_Index"])
                    if pd.isna(value):
                        continue
                    date_str = f"{year:04d}-{month:02d}-01"
                    result.append({"date": date_str, "value": round(value, 2)})
                except (ValueError, TypeError, KeyError):
                    continue

            # Excel is sorted newest first, reverse to oldest first
            result.sort(key=lambda x: x["date"])
            print(f"[GlobalEPU] Fetched {len(result)} monthly records from Excel")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[GlobalEPU] Excel request error: {e}")
            return None
        except Exception as e:
            print(f"[GlobalEPU] Excel parse error: {e}")
            return None

    # ========== US Daily EPU (CSV) ==========

    def _get_us_daily_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """米国EPU日次データを取得（CSV）"""
        if not force_refresh:
            cached_data = redis_client.get(self.US_DAILY_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": None,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        csv_result = self._fetch_us_daily_csv()
        if csv_result:
            latest = csv_result[-1] if csv_result else None
            metadata = {
                "source": "Economic Policy Uncertainty (policyuncertainty.com)",
                "indicator": "US Daily Economic Policy Uncertainty Index",
                "unit": "Index",
                "frequency": "Daily",
                "description": "News-based index of US economic policy uncertainty (daily)",
            }

            cache_payload = {
                "data": csv_result,
                "latest": latest,
                "metadata": metadata,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.US_DAILY_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload, US_DAILY_CACHE_FILE)

            return {
                "data": csv_result,
                "latest": latest,
                "metadata": metadata,
                "next_release": None,
                "cached": False,
                "source": "csv",
                "last_updated": datetime.now(JST).isoformat(),
            }

        file_cache = self._load_file_cache(US_DAILY_CACHE_FILE)
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": None,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {"data": [], "latest": None, "metadata": {}, "next_release": None, "cached": False, "source": "none", "last_updated": None}

    def _fetch_us_daily_csv(self) -> Optional[List[Dict]]:
        """policyuncertainty.comからUSデイリーEPU CSVを取得"""
        try:
            print("[GlobalEPU] Fetching US Daily EPU CSV...")
            response = requests.get(self.US_DAILY_CSV_URL, timeout=30)
            response.raise_for_status()

            reader = csv.DictReader(io.StringIO(response.text))
            result = []

            for row in reader:
                try:
                    day = int(row.get("day", "").strip())
                    month = int(row.get("month", "").strip())
                    year = int(row.get("year", "").strip())
                    value_str = row.get("daily_policy_index", "").strip()

                    if not value_str:
                        continue

                    value = round(float(value_str), 2)
                    date_str = f"{year:04d}-{month:02d}-{day:02d}"
                    result.append({"date": date_str, "value": value})
                except (ValueError, TypeError):
                    continue

            print(f"[GlobalEPU] Fetched {len(result)} daily records from CSV")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[GlobalEPU] CSV request error: {e}")
            return None
        except Exception as e:
            print(f"[GlobalEPU] CSV parse error: {e}")
            return None

    # ========== Common ==========

    def _should_refresh(self, last_updated_str: str) -> bool:
        """24時間経過またはJST 6:00を過ぎた新しい日なら更新"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            if (now - last_updated) > timedelta(hours=24):
                return True

            if last_updated.date() < now.date() and now.hour >= 6:
                return True

            return False
        except Exception:
            return True

    def _load_file_cache(self, cache_file: Path) -> Optional[Dict[str, Any]]:
        try:
            if not cache_file.exists():
                return None
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[GlobalEPU] Failed to load file cache {cache_file}: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any], cache_file: Path) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[GlobalEPU] Failed to save file cache {cache_file}: {e}")

    def invalidate_cache(self) -> bool:
        r1 = redis_client.delete(self.GLOBAL_CACHE_KEY)
        r2 = redis_client.delete(self.US_MONTHLY_CACHE_KEY)
        r3 = redis_client.delete(self.US_DAILY_CACHE_KEY)
        return r1 or r2 or r3

    def get_cache_status(self) -> Dict[str, Any]:
        global_exists = redis_client.exists(self.GLOBAL_CACHE_KEY)
        global_cached = redis_client.get(self.GLOBAL_CACHE_KEY) if global_exists else None
        us_monthly_exists = redis_client.exists(self.US_MONTHLY_CACHE_KEY)
        us_monthly_cached = redis_client.get(self.US_MONTHLY_CACHE_KEY) if us_monthly_exists else None
        us_exists = redis_client.exists(self.US_DAILY_CACHE_KEY)
        us_cached = redis_client.get(self.US_DAILY_CACHE_KEY) if us_exists else None

        return {
            "global": {
                "indicator": "Global EPU Index (Monthly)",
                "source": "FRED GEPUCURRENT",
                "cache_key": self.GLOBAL_CACHE_KEY,
                "exists": global_exists,
                "last_updated": global_cached.get("last_updated") if global_cached else None,
                "data_count": len(global_cached.get("data", [])) if global_cached else 0,
            },
            "us_monthly": {
                "indicator": "US Monthly EPU Index",
                "source": "policyuncertainty.com Excel",
                "cache_key": self.US_MONTHLY_CACHE_KEY,
                "exists": us_monthly_exists,
                "last_updated": us_monthly_cached.get("last_updated") if us_monthly_cached else None,
                "data_count": len(us_monthly_cached.get("data", [])) if us_monthly_cached else 0,
            },
            "us_daily": {
                "indicator": "US Daily EPU Index",
                "source": "policyuncertainty.com CSV",
                "cache_key": self.US_DAILY_CACHE_KEY,
                "exists": us_exists,
                "last_updated": us_cached.get("last_updated") if us_cached else None,
                "data_count": len(us_cached.get("data", [])) if us_cached else 0,
            },
        }


# シングルトンインスタンス
global_epu_service = GlobalEpuService()
