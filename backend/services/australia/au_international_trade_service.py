"""
オーストラリア 国際貿易（International Trade in Goods）サービス

データソース:
- ABS SDMX API (ITGS dataflow)
- M1.170+1000+2000.20.AUS.M
  = Current Prices, Balance/Exports/Imports, Seasonally Adjusted, Australia, Monthly
- 単位: 百万AUD（M AUD）→ 十億AUD（B AUD）に変換して格納

DATA_ITEM:
- 1000 = Goods Credit (Exports)
- 2000 = Goods Debit (Imports, 負値)
- 170  = Balance on goods

発表スケジュール: 月次
"""
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# キャッシュ設定
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "australia" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "au_international_trade_cache.json"

# ABS API設定
ABS_API_BASE = "https://data.api.abs.gov.au/rest/data"
DATAFLOW = "ABS,ITGS,1.2.0"
DATA_KEY = "M1.170+1000+2000.20.AUS.M"
DATA_URL = f"{ABS_API_BASE}/{DATAFLOW}/{DATA_KEY}?startPeriod=1971-07&dimensionAtObservation=AllDimensions"


class AuInternationalTradeService:
    """オーストラリア国際貿易サービス（貿易収支・輸出・輸入）"""

    DATA_CACHE_KEY = "australia:au_international_trade:data"
    FMP_EVENT_PATTERN = "Balance of Trade"
    FMP_COUNTRY = "AU"

    def __init__(self):
        pass

    def _fetch_sdmx(self, url: str) -> Optional[Dict[str, Any]]:
        """ABS SDMX APIからデータを取得"""
        try:
            logger.info(f"Fetching ABS ITGS data from {url}")
            response = requests.get(
                url,
                headers={
                    "Accept": "application/vnd.sdmx.data+json",
                    "User-Agent": "Mozilla/5.0 (economic-platform)",
                },
                timeout=30,
            )
            if response.status_code != 200:
                logger.error(f"ABS API returned HTTP {response.status_code}")
                return None
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching ABS ITGS data: {e}")
            return None

    def _parse_sdmx_observations(self, raw_data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """SDMX JSONレスポンスをパースして3系列のデータを抽出

        Returns:
            {
                "exports": [{"date": "YYYY-MM-01", "value": float}, ...],
                "imports": [{"date": "YYYY-MM-01", "value": float}, ...],
                "balance": [{"date": "YYYY-MM-01", "value": float}, ...],
            }
        """
        result = {"exports": [], "imports": [], "balance": []}
        try:
            datasets = raw_data.get("data", {}).get("dataSets", [])
            if not datasets:
                return result
            observations = datasets[0].get("observations", {})
            if not observations:
                return result
            structures = raw_data.get("data", {}).get("structures", [])
            if not structures:
                return result
            dimensions = structures[0].get("dimensions", {}).get("observation", [])

            # ディメンションルックアップを構築
            tp_dim_idx = None
            tp_lookup = {}
            item_dim_idx = None
            item_lookup = {}

            for i, dim in enumerate(dimensions):
                if dim.get("id") == "TIME_PERIOD":
                    tp_dim_idx = i
                    tp_lookup = {str(j): v.get("id", "") for j, v in enumerate(dim.get("values", []))}
                elif dim.get("id") == "DATA_ITEM":
                    item_dim_idx = i
                    item_lookup = {str(j): v.get("id", "") for j, v in enumerate(dim.get("values", []))}

            if tp_dim_idx is None or item_dim_idx is None:
                return result

            # DATA_ITEM ID → series name マッピング
            item_id_to_series = {
                "1000": "exports",   # Goods Credit
                "2000": "imports",   # Goods Debit
                "170": "balance",    # Balance on goods
            }

            for obs_key, obs_value in observations.items():
                if obs_value is None or obs_value[0] is None:
                    continue
                value = obs_value[0]
                indices = obs_key.split(":")
                tp_idx = indices[tp_dim_idx] if tp_dim_idx < len(indices) else None
                item_idx = indices[item_dim_idx] if item_dim_idx < len(indices) else None

                if tp_idx is None or item_idx is None:
                    continue

                time_period = tp_lookup.get(tp_idx, "")
                item_id = item_lookup.get(item_idx, "")
                series_name = item_id_to_series.get(item_id)

                if not time_period or not series_name:
                    continue

                # YYYY-MM → YYYY-MM-01
                date_str = f"{time_period}-01" if len(time_period) == 7 else time_period

                # M AUD → B AUD に変換（/ 1000）
                # Imports は負値で来るので絶対値に変換
                value_b = round(abs(value) / 1000, 3)
                if series_name == "balance":
                    value_b = round(value / 1000, 3)  # Balanceは符号を保持

                result[series_name].append({
                    "date": date_str,
                    "value": value_b,
                })

            # ソート
            for key in result:
                result[key].sort(key=lambda x: x["date"])

        except Exception as e:
            logger.error(f"Error parsing SDMX ITGS data: {e}")
        return result

    def _calculate_changes(self, data: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """MoM%とYoY%を算出

        Returns:
            {
                "mom": [{"date": ..., "value": ...}, ...],
                "yoy": [{"date": ..., "value": ...}, ...],
            }
        """
        mom = []
        yoy = []
        date_map = {p["date"]: p["value"] for p in data}

        for i, point in enumerate(data):
            val = point["value"]
            # MoM%
            if i >= 1:
                prev_val = data[i - 1]["value"]
                if prev_val is not None and prev_val != 0:
                    mom.append({
                        "date": point["date"],
                        "value": round((val - prev_val) / prev_val * 100, 2),
                    })
            # YoY%
            dt = datetime.strptime(point["date"], "%Y-%m-%d")
            prev_year_date = f"{dt.year - 1:04d}-{dt.month:02d}-01"
            if prev_year_date in date_map:
                prev_year_val = date_map[prev_year_date]
                if prev_year_val is not None and prev_year_val != 0:
                    yoy.append({
                        "date": point["date"],
                        "value": round((val - prev_year_val) / prev_year_val * 100, 2),
                    })

        return {"mom": mom, "yoy": yoy}

    def _calculate_balance_mom_diff(self, balance_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """貿易収支の前月差分（増減幅）を算出"""
        result = []
        for i in range(1, len(balance_data)):
            prev = balance_data[i - 1]["value"]
            curr = balance_data[i]["value"]
            if prev is not None and curr is not None:
                result.append({
                    "date": balance_data[i]["date"],
                    "value": round(curr - prev, 3),
                })
        return result

    def _get_next_release(self) -> Optional[Dict[str, str]]:
        """次回発表日を取得"""
        try:
            from services.australia.fmp_next_release_utils import get_next_release_by_pattern
            result = get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY)
            if result:
                label = result.get("label", "")
                month_match = re.search(r"\((\w+)\)", label)
                month_str = month_match.group(1) if month_match else ""
                result["label"] = f"貿易収支 ({month_str})".strip()
            return result
        except Exception as e:
            logger.warning(f"Failed to get next release: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュ更新判定（FMP発表日ベース）"""
        try:
            from services.australia.fmp_next_release_utils import should_refresh_by_pattern
            return should_refresh_by_pattern(
                self.FMP_EVENT_PATTERN,
                last_updated_str,
                country=self.FMP_COUNTRY,
            )
        except Exception as e:
            logger.error(f"Error in should_refresh: {e}")
            return False

    def get_au_international_trade_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """国際貿易データを取得（キャッシュ付き）"""
        next_release = self._get_next_release()

        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "balance": cached_data.get("balance", []),
                        "exports": cached_data.get("exports", []),
                        "imports": cached_data.get("imports", []),
                        "balance_mom_diff": cached_data.get("balance_mom_diff", []),
                        "exports_mom": cached_data.get("exports_mom", []),
                        "exports_yoy": cached_data.get("exports_yoy", []),
                        "imports_mom": cached_data.get("imports_mom", []),
                        "imports_yoy": cached_data.get("imports_yoy", []),
                        "latest_balance": cached_data.get("latest_balance"),
                        "latest_exports": cached_data.get("latest_exports"),
                        "latest_imports": cached_data.get("latest_imports"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                    }

        raw_data = self._fetch_sdmx(DATA_URL)
        if raw_data:
            series = self._parse_sdmx_observations(raw_data)
            balance = series["balance"]
            exports = series["exports"]
            imports = series["imports"]

            if balance or exports or imports:
                # 変化率を算出
                balance_mom_diff = self._calculate_balance_mom_diff(balance)
                exports_changes = self._calculate_changes(exports)
                imports_changes = self._calculate_changes(imports)

                latest_balance = balance[-1] if balance else None
                latest_exports = exports[-1] if exports else None
                latest_imports = imports[-1] if imports else None

                result = {
                    "balance": balance,
                    "exports": exports,
                    "imports": imports,
                    "balance_mom_diff": balance_mom_diff,
                    "exports_mom": exports_changes["mom"],
                    "exports_yoy": exports_changes["yoy"],
                    "imports_mom": imports_changes["mom"],
                    "imports_yoy": imports_changes["yoy"],
                    "latest_balance": latest_balance,
                    "latest_exports": latest_exports,
                    "latest_imports": latest_imports,
                    "metadata": {
                        "source": "Australian Bureau of Statistics",
                        "indicator": "International Trade in Goods",
                        "frequency": "monthly",
                        "unit": "B AUD (Billion AUD)",
                    },
                    "next_release": next_release,
                }
                cache_payload = {**result, "last_updated": datetime.now(JST).isoformat()}
                redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
                self._save_file_cache(cache_payload)

                logger.info(
                    f"AU International Trade: balance={len(balance)}, "
                    f"exports={len(exports)}, imports={len(imports)} records"
                )
                if latest_balance:
                    logger.info(f"Latest balance: {latest_balance['date']} = {latest_balance['value']:.3f} B AUD")

                return {**result, "cached": False, "source": "abs_api"}

        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "balance": file_cache.get("balance", []),
                "exports": file_cache.get("exports", []),
                "imports": file_cache.get("imports", []),
                "balance_mom_diff": file_cache.get("balance_mom_diff", []),
                "exports_mom": file_cache.get("exports_mom", []),
                "exports_yoy": file_cache.get("exports_yoy", []),
                "imports_mom": file_cache.get("imports_mom", []),
                "imports_yoy": file_cache.get("imports_yoy", []),
                "latest_balance": file_cache.get("latest_balance"),
                "latest_exports": file_cache.get("latest_exports"),
                "latest_imports": file_cache.get("latest_imports"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
            }

        return {
            "balance": [], "exports": [], "imports": [],
            "balance_mom_diff": [], "exports_mom": [], "exports_yoy": [],
            "imports_mom": [], "imports_yoy": [],
            "latest_balance": None, "latest_exports": None, "latest_imports": None,
            "metadata": {"source": "Australian Bureau of Statistics", "error": "No data available"},
            "next_release": next_release, "cached": False, "source": "none",
        }

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        return {
            "indicator": "AU International Trade in Goods",
            "source": "ABS (ITGS)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
            "next_release": self._get_next_release(),
        }


au_international_trade_service = AuInternationalTradeService()
