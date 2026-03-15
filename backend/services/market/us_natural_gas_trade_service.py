"""
米国天然ガス輸出入 (U.S. Natural Gas Imports and Exports by Category) サービス

データソース:
  - EIA API v2: 月次データ
  - 輸出: /v2/natural-gas/move/expc/data/
  - 輸入: /v2/natural-gas/move/impc/data/
  - duoarea=NUS-Z00 (U.S. Total)
  - units=MMCF → BCF (÷1000)

輸出系列:
  - EEX: Total Exports (N9130US2)
  - ENP: Pipeline Exports (N9132US2)
  - ENG: LNG Exports (N9133US2)
  - ERE: LNG Re-Exports

輸入系列:
  - IM0: Total Imports (N9100US2)
  - IRP: Pipeline Imports (N9102US2)
  - IML: LNG Imports (N9103US2)

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
DATA_CACHE_FILE = CACHE_DIR / "us_natural_gas_trade_cache.json"

REDIS_KEY = "market:us_natural_gas_trade:data"

EIA_EXPORT_URL = "https://api.eia.gov/v2/natural-gas/move/expc/data/"
EIA_IMPORT_URL = "https://api.eia.gov/v2/natural-gas/move/impc/data/"

# Export process codes → field names
EXPORT_PROCESS_MAP = {
    "EEX": "export_total",
    "ENP": "export_pipeline",
    "ENG": "export_lng",
    "ERE": "export_re_export",
}

# Import process codes → field names
IMPORT_PROCESS_MAP = {
    "IM0": "import_total",
    "IRP": "import_pipeline",
    "IML": "import_lng",
}

ALL_FIELDS = list(EXPORT_PROCESS_MAP.values()) + list(IMPORT_PROCESS_MAP.values()) + ["net_export"]


class UsNaturalGasTradeService:
    """米国天然ガス輸出入サービス"""

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
            logger.error(f"[NatGasTrade] Build error: {e}")
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
            resp = requests.get(
                "https://www.eia.gov/totalenergy/data/monthly/",
                timeout=15,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code == 200:
                import re
                # HTML: Next Release Date:</span> <span class="date">\n\t\tMarch 26, 2026\t\t</span>
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
            logger.warning(f"[NatGasTrade] Next release scrape error: {e}")
        return None

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """EIA API v2 から輸出・輸入データを取得してマージ"""
        logger.info("[NatGasTrade] Building data from EIA API v2...")

        api_key = os.environ.get("EIA_API_KEY", "")
        if not api_key:
            logger.warning("[NatGasTrade] EIA_API_KEY not set")
            return None

        # Fetch exports and imports
        export_rows = self._fetch_from_eia(
            api_key, EIA_EXPORT_URL, list(EXPORT_PROCESS_MAP.keys())
        )
        import_rows = self._fetch_from_eia(
            api_key, EIA_IMPORT_URL, list(IMPORT_PROCESS_MAP.keys())
        )

        if not export_rows and not import_rows:
            return None

        # Group by date, merge series
        date_map: Dict[str, Dict[str, Any]] = {}

        # Process exports
        for row in (export_rows or []):
            period = row.get("period", "")
            process = row.get("process", "")
            value = row.get("value")
            units = row.get("units", "")

            if not period or process not in EXPORT_PROCESS_MAP:
                continue
            if value is None or units != "MMCF":
                continue

            try:
                # Convert MMCF to BCF
                val = round(float(value) / 1000, 2)
            except (ValueError, TypeError):
                continue

            date_str = f"{period}-01" if len(period) == 7 else period
            if date_str not in date_map:
                date_map[date_str] = {"date": date_str}
            date_map[date_str][EXPORT_PROCESS_MAP[process]] = val

        # Process imports
        for row in (import_rows or []):
            period = row.get("period", "")
            process = row.get("process", "")
            value = row.get("value")
            units = row.get("units", "")

            if not period or process not in IMPORT_PROCESS_MAP:
                continue
            if value is None or units != "MMCF":
                continue

            try:
                val = round(float(value) / 1000, 2)
            except (ValueError, TypeError):
                continue

            date_str = f"{period}-01" if len(period) == 7 else period
            if date_str not in date_map:
                date_map[date_str] = {"date": date_str}
            date_map[date_str][IMPORT_PROCESS_MAP[process]] = val

        result_data = sorted(date_map.values(), key=lambda x: x["date"])

        # Fill missing fields and calculate net export
        for item in result_data:
            for field in ALL_FIELDS:
                if field not in item and field != "net_export":
                    item[field] = None

            exp_total = item.get("export_total")
            imp_total = item.get("import_total")
            if exp_total is not None and imp_total is not None:
                item["net_export"] = round(exp_total - imp_total, 2)
            else:
                item["net_export"] = None

        # Filter: must have at least export_total or import_total
        result_data = [
            d for d in result_data
            if d.get("export_total") is not None or d.get("import_total") is not None
        ]

        if not result_data:
            logger.error("[NatGasTrade] No data from EIA API")
            return None

        latest = result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[NatGasTrade] {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest export_total={latest.get('export_total')} "
            f"import_total={latest.get('import_total')} "
            f"net_export={latest.get('net_export')}"
        )

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "EIA",
                "frequency": "monthly",
                "unit": "BCF",
                "series": "U.S. Natural Gas Imports and Exports by Category",
                "data_count": len(result_data),
                "start_date": result_data[0]["date"],
                "end_date": result_data[-1]["date"],
            },
            "cached": False,
            "source": "model",
            "last_updated": now_str,
        }

    def _fetch_from_eia(
        self, api_key: str, url: str, process_codes: List[str]
    ) -> Optional[List[Dict[str, Any]]]:
        """EIA API v2 から月次データを取得"""
        all_rows: List[Dict[str, Any]] = []
        offset = 0
        length = 5000

        while True:
            try:
                resp = requests.get(url, params={
                    "api_key": api_key,
                    "frequency": "monthly",
                    "data[0]": "value",
                    "facets[duoarea][]": "NUS-Z00",
                    "facets[process][]": process_codes,
                    "sort[0][column]": "period",
                    "sort[0][direction]": "asc",
                    "offset": offset,
                    "length": length,
                }, timeout=60, headers={"User-Agent": "Mozilla/5.0"})

                if resp.status_code != 200:
                    logger.error(f"[NatGasTrade] EIA API error: HTTP {resp.status_code} for {url}")
                    return all_rows if all_rows else None

                data = resp.json()
                rows = data.get("response", {}).get("data", [])
                total = int(data.get("response", {}).get("total", 0))
                all_rows.extend(rows)

                if len(all_rows) >= total or len(rows) == 0:
                    break
                offset += length
            except Exception as e:
                logger.error(f"[NatGasTrade] EIA API error: {e}")
                return all_rows if all_rows else None

        logger.info(f"[NatGasTrade] Fetched {len(all_rows)} rows from {url.split('/')[-3]}")
        return all_rows

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(REDIS_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[NatGasTrade] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[NatGasTrade] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(REDIS_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[NatGasTrade] Redis load error: {e}")
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
            logger.error(f"[NatGasTrade] File load error: {e}")
        return None


us_natural_gas_trade_service = UsNaturalGasTradeService()
