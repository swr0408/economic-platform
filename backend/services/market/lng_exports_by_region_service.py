"""
米国LNG輸出（国別・エリア別） (U.S. LNG Exports by Region/Country) サービス

データソース:
  - EIA API v2: 月次データ
  - /v2/natural-gas/move/expc/data/
  - process=EVE (Exports by Vessel = LNG)
  - 各国 duoarea コードでフィルタリング
  - units=MMCF → BCF (÷1000)

エリア区分:
  - East Asia & Southeast Asia: 日本, 韓国, 中国, 台湾, タイ, シンガポール, フィリピン, マレーシア, バングラデシュ
  - South Asia: インド, パキスタン
  - Europe: オランダ, フランス, 英国, ドイツ, スペイン, トルコ, ベルギー, イタリア, ギリシャ, ポーランド, ポルトガル, リトアニア, クロアチア, フィンランド, マルタ
  - South & Central America: ブラジル, アルゼンチン, コロンビア, チリ, メキシコ, パナマ, ジャマイカ, ドミニカ, ニカラグア, ハイチ, バハマ, バルバドス, エルサルバドル, アンティグア・バーブーダ
  - Middle East & North Africa: エジプト, クウェート, バーレーン, UAE, ヨルダン, イスラエル, モーリタニア, セネガル

更新: 6時間TTL (Redis + ファイル)
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "lng_exports_by_region_cache.json"

REDIS_KEY = "market:lng_exports_by_region:data"

EIA_EXPORT_URL = "https://api.eia.gov/v2/natural-gas/move/expc/data/"

# duoarea codes → (country_key, country_name_ja, country_name_en)
COUNTRY_MAP = {
    # East Asia & Southeast Asia
    "NUS-NJA": ("japan", "日本", "Japan"),
    "NUS-NKS": ("south_korea", "韓国", "South Korea"),
    "NUS-NCH": ("china", "中国", "China"),
    "NUS-NTW": ("taiwan", "台湾", "Taiwan"),
    "NUS-NTH": ("thailand", "タイ", "Thailand"),
    "NUS-NSN": ("singapore", "シンガポール", "Singapore"),
    "NUS-NRP": ("philippines", "フィリピン", "Philippines"),
    "NUS-NMY": ("malaysia", "マレーシア", "Malaysia"),
    "NUS-NBG": ("bangladesh", "バングラデシュ", "Bangladesh"),
    # South Asia
    "NUS-NIN": ("india", "インド", "India"),
    "NUS-NPK": ("pakistan", "パキスタン", "Pakistan"),
    # Europe
    "NUS-NNL": ("netherlands", "オランダ", "Netherlands"),
    "NUS-NFR": ("france", "フランス", "France"),
    "NUS-NUK": ("uk", "英国", "United Kingdom"),
    "NUS-NGM": ("germany", "ドイツ", "Germany"),
    "NUS-NSP": ("spain", "スペイン", "Spain"),
    "NUS-NTU": ("turkey", "トルコ", "Türkiye"),
    "NUS-NBE": ("belgium", "ベルギー", "Belgium"),
    "NUS-NIT": ("italy", "イタリア", "Italy"),
    "NUS-NGR": ("greece", "ギリシャ", "Greece"),
    "NUS-NPL": ("poland", "ポーランド", "Poland"),
    "NUS-NPO": ("portugal", "ポルトガル", "Portugal"),
    "NUS-NLH": ("lithuania", "リトアニア", "Lithuania"),
    "NUS-NHR": ("croatia", "クロアチア", "Croatia"),
    "NUS-NFI": ("finland", "フィンランド", "Finland"),
    "NUS-NM6": ("malta", "マルタ", "Malta"),
    # South & Central America
    "NUS-NBR": ("brazil", "ブラジル", "Brazil"),
    "NUS-NAR": ("argentina", "アルゼンチン", "Argentina"),
    "NUS-NCO": ("colombia", "コロンビア", "Colombia"),
    "NUS-NCI": ("chile", "チリ", "Chile"),
    "NUS-NMX": ("mexico", "メキシコ", "Mexico"),
    "NUS-NPM": ("panama", "パナマ", "Panama"),
    "NUS-NJM": ("jamaica", "ジャマイカ", "Jamaica"),
    "NUS-NDR": ("dominican_republic", "ドミニカ", "Dominican Republic"),
    "NUS-NNU": ("nicaragua", "ニカラグア", "Nicaragua"),
    "NUS-NHA": ("haiti", "ハイチ", "Haiti"),
    "NUS-NBF": ("bahamas", "バハマ", "Bahamas"),
    "NUS-NBB": ("barbados", "バルバドス", "Barbados"),
    "NUS-NES": ("el_salvador", "エルサルバドル", "El Salvador"),
    "NUS-NAC": ("antigua", "アンティグア・バーブーダ", "Antigua and Barbuda"),
    # Middle East & North Africa
    "NUS-NEG": ("egypt", "エジプト", "Egypt"),
    "NUS-NKU": ("kuwait", "クウェート", "Kuwait"),
    "NUS-NBA": ("bahrain", "バーレーン", "Bahrain"),
    "NUS-NTC": ("uae", "UAE", "United Arab Emirates"),
    "NUS-NJO": ("jordan", "ヨルダン", "Jordan"),
    "NUS-NIS": ("israel", "イスラエル", "Israel"),
    "NUS-NMR": ("mauritania", "モーリタニア", "Mauritania"),
    "NUS-NSG": ("senegal", "セネガル", "Senegal"),
}

# Region groupings: region_key → list of country_keys
REGION_GROUPS = {
    "east_asia_se_asia": {
        "name_ja": "東アジア・東南アジア",
        "name_en": "East Asia & SE Asia",
        "countries": ["japan", "south_korea", "china", "taiwan", "thailand", "singapore", "philippines", "malaysia", "bangladesh"],
    },
    "south_asia": {
        "name_ja": "南アジア",
        "name_en": "South Asia",
        "countries": ["india", "pakistan"],
    },
    "europe": {
        "name_ja": "欧州",
        "name_en": "Europe",
        "countries": ["netherlands", "france", "uk", "germany", "spain", "turkey", "belgium", "italy", "greece", "poland", "portugal", "lithuania", "croatia", "finland", "malta"],
    },
    "south_central_america": {
        "name_ja": "中南米",
        "name_en": "S & C America",
        "countries": ["brazil", "argentina", "colombia", "chile", "mexico", "panama", "jamaica", "dominican_republic", "nicaragua", "haiti", "bahamas", "barbados", "el_salvador", "antigua"],
    },
    "middle_east_africa": {
        "name_ja": "中東・北アフリカ",
        "name_en": "ME & N Africa",
        "countries": ["egypt", "kuwait", "bahrain", "uae", "jordan", "israel", "mauritania", "senegal"],
    },
}

# Top individual countries to track (from user spec)
TOP_COUNTRIES = [
    "netherlands", "france", "uk", "germany", "spain", "turkey",
    "japan", "south_korea", "india", "china",
]


class LngExportsByRegionService:
    """米国LNG輸出（国別・エリア別）サービス"""

    def _should_refresh(self) -> bool:
        try:
            cached = redis_client.get(REDIS_KEY)
            if not cached:
                return True
            last_updated_str = cached.get("last_updated")
            if not last_updated_str:
                return True
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)
            return (now - last_updated).total_seconds() >= 6 * 3600
        except Exception:
            return True

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        if not force_refresh and not self._should_refresh():
            cached = self._load_from_redis()
            if cached and cached.get("data"):
                cached["next_release"] = self._get_next_release()
                return cached

        try:
            data = self._build_data()
            if data and data.get("data"):
                self._save_to_cache(data)
                data["next_release"] = self._get_next_release()
                return data
        except Exception as e:
            logger.error(f"[LngExports] Build error: {e}")
            import traceback
            traceback.print_exc()

        cached = self._load_from_redis()
        if cached and cached.get("data"):
            cached["next_release"] = self._get_next_release()
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            cached["next_release"] = self._get_next_release()
            return cached

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "metadata": {"source": "EIA"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """EIA Monthly Energy Review の次回発表日を取得"""
        try:
            import re
            resp = requests.get(
                "https://www.eia.gov/totalenergy/data/monthly/",
                timeout=15,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code == 200:
                match = re.search(
                    r'Next Release Date:.*?<span[^>]*class="date"[^>]*>\s*'
                    r'(\w+ \d+,\s*\d{4})',
                    resp.text,
                    re.DOTALL,
                )
                if match:
                    from datetime import datetime as dt
                    date_str = match.group(1).strip()
                    parsed = dt.strptime(date_str, "%B %d, %Y")
                    return {
                        "date": parsed.strftime("%Y-%m-%d"),
                        "label": f"Monthly Energy Review ({date_str})",
                    }
        except Exception as e:
            logger.warning(f"[LngExports] Next release scrape error: {e}")
        return None

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """EIA API v2 からLNG輸出データを国別に取得し、エリア別に集計"""
        logger.info("[LngExports] Building data from EIA API v2...")

        api_key = os.environ.get("EIA_API_KEY", "")
        if not api_key:
            logger.warning("[LngExports] EIA_API_KEY not set")
            return None

        # Fetch all LNG export data (process=EVE) for all countries at once
        # Do NOT filter by duoarea to get all countries in a single query
        all_rows = self._fetch_from_eia(api_key)
        if not all_rows:
            return None

        # Build country-level monthly data: {date: {country_key: bcf_value}}
        country_monthly: Dict[str, Dict[str, float]] = {}

        for row in all_rows:
            period = row.get("period", "")
            duoarea = row.get("duoarea", "")
            value = row.get("value")
            units = row.get("units", "")

            if not period or not duoarea or value is None:
                continue
            if units != "MMCF":
                continue
            if duoarea not in COUNTRY_MAP:
                continue

            country_key = COUNTRY_MAP[duoarea][0]

            try:
                bcf = round(float(value) / 1000, 3)
            except (ValueError, TypeError):
                continue

            date_str = f"{period}-01" if len(period) == 7 else period
            if date_str not in country_monthly:
                country_monthly[date_str] = {}
            country_monthly[date_str][country_key] = bcf

        if not country_monthly:
            logger.error("[LngExports] No data from EIA API")
            return None

        # Build result data with region aggregates + top country columns
        result_data: List[Dict[str, Any]] = []

        for date_str in sorted(country_monthly.keys()):
            countries = country_monthly[date_str]
            item: Dict[str, Any] = {"date": date_str}

            # Calculate region totals
            total = 0.0
            for region_key, region_info in REGION_GROUPS.items():
                region_total = 0.0
                for ck in region_info["countries"]:
                    if ck in countries:
                        region_total += countries[ck]
                item[region_key] = round(region_total, 3) if region_total > 0 else None
                total += region_total

            item["total"] = round(total, 3) if total > 0 else None

            # Add top country values
            for ck in TOP_COUNTRIES:
                item[ck] = round(countries[ck], 3) if ck in countries and countries[ck] > 0 else None

            result_data.append(item)

        # Filter: must have total > 0
        result_data = [d for d in result_data if d.get("total") is not None and d["total"] > 0]

        if not result_data:
            logger.error("[LngExports] No valid data after processing")
            return None

        latest = result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[LngExports] {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest total={latest.get('total')}"
        )

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "EIA",
                "frequency": "monthly",
                "unit": "BCF",
                "series": "U.S. LNG Exports by Region/Country",
                "data_count": len(result_data),
                "start_date": result_data[0]["date"],
                "end_date": result_data[-1]["date"],
                "regions": {
                    rk: {"name_ja": rv["name_ja"], "name_en": rv["name_en"]}
                    for rk, rv in REGION_GROUPS.items()
                },
                "top_countries": {
                    ck: {
                        "name_ja": next(v[1] for v in COUNTRY_MAP.values() if v[0] == ck),
                        "name_en": next(v[2] for v in COUNTRY_MAP.values() if v[0] == ck),
                    }
                    for ck in TOP_COUNTRIES
                },
            },
            "cached": False,
            "source": "model",
            "last_updated": now_str,
        }

    def _fetch_from_eia(self, api_key: str) -> Optional[List[Dict[str, Any]]]:
        """EIA API v2 からLNG輸出データ（全国）を取得"""
        all_rows: List[Dict[str, Any]] = []
        offset = 0
        length = 5000

        while True:
            try:
                resp = requests.get(EIA_EXPORT_URL, params={
                    "api_key": api_key,
                    "frequency": "monthly",
                    "data[0]": "value",
                    "facets[process][]": "EVE",
                    "sort[0][column]": "period",
                    "sort[0][direction]": "asc",
                    "offset": offset,
                    "length": length,
                }, timeout=60, headers={"User-Agent": "Mozilla/5.0"})

                if resp.status_code != 200:
                    logger.error(f"[LngExports] EIA API error: HTTP {resp.status_code}")
                    return all_rows if all_rows else None

                data = resp.json()
                rows = data.get("response", {}).get("data", [])
                total = int(data.get("response", {}).get("total", 0))
                all_rows.extend(rows)

                if len(all_rows) >= total or len(rows) == 0:
                    break
                offset += length
            except Exception as e:
                logger.error(f"[LngExports] EIA API error: {e}")
                return all_rows if all_rows else None

        logger.info(f"[LngExports] Fetched {len(all_rows)} rows from EIA")
        return all_rows

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(REDIS_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[LngExports] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[LngExports] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(REDIS_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[LngExports] Redis load error: {e}")
        return None

    def _load_from_file(self) -> Optional[Dict[str, Any]]:
        try:
            if DATA_CACHE_FILE.exists():
                with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["cached"] = True
                data["source"] = "file"
                return data
        except Exception as e:
            logger.error(f"[LngExports] File load error: {e}")
        return None


lng_exports_by_region_service = LngExportsByRegionService()
