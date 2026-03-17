"""
OECD CLI（景気先行指数）サービス

OECD Composite Leading Indicators (CLI)
11ヶ国/地域の月次CLIデータをOECD SDMX REST APIから取得

取得対象:
- G20, G7, Major Five Asia (A5M)
- USA, JPN, CHN, DEU, GBR, KOR, AUS, CAN

データソース: OECD SDMX REST API
キャッシュ方式: 24時間固定TTL
"""
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "global" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "oecd_cli_cache.json"

# OECD SDMX API URL
OECD_CLI_URL = (
    "https://sdmx.oecd.org/public/rest/data/"
    "OECD.SDD.STES,DSD_STES@DF_CLI,/"
    "CAN+AUS+G20+GBR+CHN+G7+A5M+USA+KOR+JPN+DEU"
    ".M.LI...AA...H"
    "?dimensionAtObservation=AllDimensions"
)

# OECD国コード → 内部キーマップ
COUNTRY_MAP: Dict[str, str] = {
    "G20": "g20",
    "G7": "g7",
    "A5M": "a5m",
    "USA": "usa",
    "JPN": "jpn",
    "CHN": "chn",
    "DEU": "deu",
    "GBR": "gbr",
    "KOR": "kor",
    "AUS": "aus",
    "CAN": "can",
}

ALL_COUNTRIES = ["g20", "g7", "a5m", "usa", "jpn", "chn", "deu", "gbr", "kor", "aus", "can"]


class OecdCliService:
    """OECD CLI（景気先行指数）サービス"""

    CACHE_KEY = "global:oecd_cli:data"

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """OECD CLIデータを取得"""
        if not force_refresh:
            cached = redis_client.get(self.CACHE_KEY)
            if cached:
                last_updated_str = cached.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached.get("data", []),
                        "latest": cached.get("latest"),
                        "metadata": cached.get("metadata", {}),
                        "next_release": None,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        api_result = self._fetch_from_oecd()
        if api_result:
            latest = api_result[-1] if api_result else None
            metadata = {
                "source": "OECD (Organisation for Economic Co-operation and Development)",
                "indicator": "Composite Leading Indicators (CLI)",
                "unit": "Amplitude adjusted (long-term average = 100)",
                "frequency": "Monthly",
                "countries": list(COUNTRY_MAP.values()),
            }

            cache_payload = {
                "data": api_result,
                "latest": latest,
                "metadata": metadata,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": api_result,
                "latest": latest,
                "metadata": metadata,
                "next_release": None,
                "cached": False,
                "source": "oecd_api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
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

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
        }

    def _fetch_from_oecd(self) -> Optional[List[Dict[str, Any]]]:
        """OECD SDMX APIからCLIデータを取得"""
        try:
            print("[OECD CLI] Fetching from OECD SDMX API...")
            headers = {
                "Accept": "application/vnd.sdmx.data+json;version=1.0",
                "User-Agent": "Mozilla/5.0 (economic-platform)",
            }
            resp = requests.get(OECD_CLI_URL, headers=headers, timeout=60)
            resp.raise_for_status()
            raw = resp.json()

            return self._parse_sdmx_observations(raw)

        except requests.exceptions.RequestException as e:
            print(f"[OECD CLI] Request error: {e}")
            return None
        except Exception as e:
            print(f"[OECD CLI] Parse error: {e}")
            return None

    def _parse_sdmx_observations(self, raw_data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """SDMX JSONレスポンスをパースして日付×国マトリクスに変換"""
        try:
            datasets = raw_data.get("data", {}).get("dataSets", [])
            if not datasets:
                print("[OECD CLI] No dataSets in response")
                return None

            observations = datasets[0].get("observations", {})
            if not observations:
                print("[OECD CLI] No observations in response")
                return None

            # SDMX JSON v1: data.structure (singular, dict)
            # SDMX JSON v2: data.structures (plural, list)
            structure = raw_data.get("data", {}).get("structure")
            if not structure:
                structures_list = raw_data.get("data", {}).get("structures", [])
                structure = structures_list[0] if structures_list else None
            if not structure:
                print("[OECD CLI] No structure in response")
                return None

            dimensions = structure.get("dimensions", {}).get("observation", [])

            # ディメンション位置を特定
            dim_ids = [d.get("id", "") for d in dimensions]
            dim_lookups: Dict[str, Dict[str, str]] = {}
            for dim in dimensions:
                dim_id = dim.get("id", "")
                values = dim.get("values", [])
                dim_lookups[dim_id] = {
                    str(i): v.get("id", "") for i, v in enumerate(values)
                }

            # REF_AREAとTIME_PERIODの位置を見つける
            ref_area_pos = None
            time_pos = None
            for i, dim_id in enumerate(dim_ids):
                if dim_id == "REF_AREA":
                    ref_area_pos = i
                elif dim_id == "TIME_PERIOD":
                    time_pos = i

            if ref_area_pos is None or time_pos is None:
                print(f"[OECD CLI] Could not find REF_AREA or TIME_PERIOD in dimensions: {dim_ids}")
                return None

            # 観測値をパース: date → {country_key: value}
            date_country_map: Dict[str, Dict[str, float]] = {}

            for obs_key, obs_value in observations.items():
                if obs_value is None or obs_value[0] is None:
                    continue

                value = obs_value[0]
                indices = obs_key.split(":")

                # 国コードと日付を取得
                country_oecd = dim_lookups.get("REF_AREA", {}).get(indices[ref_area_pos], "")
                time_period = dim_lookups.get("TIME_PERIOD", {}).get(indices[time_pos], "")

                country_key = COUNTRY_MAP.get(country_oecd)
                if not country_key or not time_period:
                    continue

                # "2024-01" → "2024-01-01"
                date_str = time_period + "-01" if len(time_period) == 7 else time_period

                if date_str not in date_country_map:
                    date_country_map[date_str] = {}
                date_country_map[date_str][country_key] = round(float(value), 4)

            # ソート済みリストに変換
            result = []
            for date_str in sorted(date_country_map.keys()):
                record: Dict[str, Any] = {"date": date_str}
                for country in ALL_COUNTRIES:
                    record[country] = date_country_map[date_str].get(country)
                result.append(record)

            print(f"[OECD CLI] Parsed {len(result)} monthly records for {len(COUNTRY_MAP)} countries")
            return result

        except Exception as e:
            print(f"[OECD CLI] Error parsing SDMX data: {e}")
            return None

    # ========== キャッシュ ==========

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

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not CACHE_FILE.exists():
                return None
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[OECD CLI] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[OECD CLI] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        exists = redis_client.exists(self.CACHE_KEY)
        cached = redis_client.get(self.CACHE_KEY) if exists else None
        return {
            "indicator": "OECD Composite Leading Indicators (CLI)",
            "source": "OECD SDMX API",
            "cache_key": self.CACHE_KEY,
            "exists": exists,
            "last_updated": cached.get("last_updated") if cached else None,
            "data_count": len(cached.get("data", [])) if cached else 0,
            "countries": ALL_COUNTRIES,
        }


# シングルトンインスタンス
oecd_cli_service = OecdCliService()
