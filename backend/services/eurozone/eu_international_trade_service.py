"""
EU国際貿易サービス
Eurostat APIからEU国際貿易（貿易収支・輸出・輸入）データを取得

指標:
- Balance of Trade (貿易収支): 輸出 - 輸入
- Exports (輸出): 百万ユーロ
- Imports (輸入): 百万ユーロ

データソース:
- Eurostat API (ei_etea_m dataset)
- Series Parameters:
  - freq: M (Monthly)
  - unit: MIO-EUR-NSA (Million euro - not seasonally adjusted)
  - indic: BAL_RT (Balance), EXP (Exports), IMP (Imports)
  - partner: EXT_EU27_2020 (Extra-EU27)
  - geo: EA20 (Euro area - 20 countries)

発表スケジュール:
- 月次（不定期）
- FMPカレンダーから次回発表日を取得

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

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "eu_international_trade_cache.json"


class EUInternationalTradeService:
    """EU国際貿易サービス（Eurostat API）"""

    # Eurostat API base URL
    EUROSTAT_API_BASE = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data"

    # Dataset code
    DATASET = "ei_etea_m"

    # 共通パラメータ
    # ディメンション順序: freq.stk_flow.unit.partner.indic.geo
    BASE_PARAMS = {
        "freq": "M",              # Monthly
        "unit": "MIO-EUR-NSA",    # Million euro - not seasonally adjusted
        # 2026: ユーロ圏が 21 か国に拡大。partner=EXT_EA20 は無効化され
        # (INVALID_QUERY_DIMENSION_VALUE)、データも EA20 系は 2025-12 で停止。EA21 へ更新。
        "partner": "EXT_EA21",    # Extra-euro area - 21 countries
        "indic": "ET-T",          # Total
        "geo": "EA21"             # Euro area - 21 countries
    }

    DATA_CACHE_KEY = "economy:eu_international_trade:data"
    ECONALPHA_ID = "eu_international_trade"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        EU国際貿易データを取得

        Returns:
            {
                "balance": [...],     # 貿易収支データ
                "exports": [...],     # 輸出データ
                "imports": [...],     # 輸入データ
                "latest_balance": {...},
                "latest_exports": {...},
                "latest_imports": {...},
                "metadata": {...},
                "next_release": {...},
                "cached": bool,
                "source": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        **{k: v for k, v in cached_data.items() if k != "last_updated"},
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
                        **{k: v for k, v in file_cache.items() if k != "last_updated"},
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str,
                    }

        # Eurostat APIから各指標を取得
        balance_data = self._fetch_eurostat_data("BAL_RT") or []
        exports_data = self._fetch_eurostat_data("EXP") or []
        imports_data = self._fetch_eurostat_data("IMP") or []

        if balance_data or exports_data or imports_data:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
            latest_balance = balance_data[-1] if balance_data else None
            latest_exports = exports_data[-1] if exports_data else None
            latest_imports = imports_data[-1] if imports_data else None

            # 前月比・前年比を計算
            balance_mom = self._calculate_mom(balance_data)
            balance_mom_diff = self._calculate_mom_diff(balance_data)
            balance_yoy = self._calculate_yoy(balance_data)
            exports_mom = self._calculate_mom(exports_data)
            exports_yoy = self._calculate_yoy(exports_data)
            imports_mom = self._calculate_mom(imports_data)
            imports_yoy = self._calculate_yoy(imports_data)

            cache_payload = {
                "balance": balance_data,
                "exports": exports_data,
                "imports": imports_data,
                "balance_mom": balance_mom,
                "balance_mom_diff": balance_mom_diff,
                "balance_yoy": balance_yoy,
                "exports_mom": exports_mom,
                "exports_yoy": exports_yoy,
                "imports_mom": imports_mom,
                "imports_yoy": imports_yoy,
                "latest_balance": latest_balance,
                "latest_exports": latest_exports,
                "latest_imports": latest_imports,
                "latest_balance_mom": balance_mom[-1] if balance_mom else None,
                "latest_balance_mom_diff": balance_mom_diff[-1] if balance_mom_diff else None,
                "latest_balance_yoy": balance_yoy[-1] if balance_yoy else None,
                "latest_exports_mom": exports_mom[-1] if exports_mom else None,
                "latest_exports_yoy": exports_yoy[-1] if exports_yoy else None,
                "latest_imports_mom": imports_mom[-1] if imports_mom else None,
                "latest_imports_yoy": imports_yoy[-1] if imports_yoy else None,
                "metadata": {
                    "source": "Eurostat - External Trade",
                    "dataset": self.DATASET,
                    "area": "Euro area",
                    "partner": "Extra-euro area (20 countries)",
                    "unit": "Million euro (not seasonally adjusted)",
                    "frequency": "Monthly",
                    "description": "International trade in goods (Total)",
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                **cache_payload,
                "cached": False,
                "source": "eurostat_api",
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                **file_cache,
                "cached": True,
                "source": "file (fallback)",
            }

        return {
            "balance": [],
            "exports": [],
            "imports": [],
            "balance_mom": [],
            "balance_mom_diff": [],
            "balance_yoy": [],
            "exports_mom": [],
            "exports_yoy": [],
            "imports_mom": [],
            "imports_yoy": [],
            "latest_balance": None,
            "latest_exports": None,
            "latest_imports": None,
            "latest_balance_mom": None,
            "latest_balance_mom_diff": None,
            "latest_balance_yoy": None,
            "latest_exports_mom": None,
            "latest_exports_yoy": None,
            "latest_imports_mom": None,
            "latest_imports_yoy": None,
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _calculate_mom(self, data: List[Dict]) -> List[Dict]:
        """前月比を計算（パーセント）"""
        if not data or len(data) < 2:
            return []

        result = []
        for i in range(1, len(data)):
            prev_value = data[i - 1].get("value")
            curr_value = data[i].get("value")

            if prev_value is not None and curr_value is not None and prev_value != 0:
                mom = ((curr_value - prev_value) / abs(prev_value)) * 100
                result.append({
                    "date": data[i]["date"],
                    "value": round(mom, 2)
                })

        return result

    def _calculate_mom_diff(self, data: List[Dict]) -> List[Dict]:
        """前月増減幅を計算（絶対値の差分）"""
        if not data or len(data) < 2:
            return []

        result = []
        for i in range(1, len(data)):
            prev_value = data[i - 1].get("value")
            curr_value = data[i].get("value")

            if prev_value is not None and curr_value is not None:
                diff = curr_value - prev_value
                result.append({
                    "date": data[i]["date"],
                    "value": round(diff, 2)
                })

        return result

    def _calculate_yoy(self, data: List[Dict]) -> List[Dict]:
        """前年比を計算"""
        if not data or len(data) < 13:
            return []

        # 日付をキーにしたマップを作成
        date_value_map = {item["date"]: item["value"] for item in data}

        result = []
        for item in data:
            curr_date = item["date"]
            curr_value = item["value"]

            # 12ヶ月前の日付を計算
            try:
                curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
                prev_year = curr_dt.year - 1
                prev_date = f"{prev_year}-{curr_dt.month:02d}-01"

                prev_value = date_value_map.get(prev_date)

                if prev_value is not None and curr_value is not None and prev_value != 0:
                    yoy = ((curr_value - prev_value) / abs(prev_value)) * 100
                    result.append({
                        "date": curr_date,
                        "value": round(yoy, 2)
                    })
            except (ValueError, KeyError):
                continue

        return result

    def _fetch_eurostat_data(self, stk_flow: str, start_period: str = "2015-01") -> Optional[List[Dict]]:
        """
        Eurostat APIから特定の指標データを取得

        Args:
            stk_flow: ストック/フローコード (BAL_RT, EXP, IMP)
            start_period: 開始期間 (YYYY-MM)

        Returns:
            データポイントのリスト
        """
        # Build series key: freq.stk_flow.unit.partner.indic.geo
        # Example: M.BAL_RT.MIO-EUR-NSA.EXT_EA20.ET-T.EA
        series_key = ".".join([
            self.BASE_PARAMS["freq"],
            stk_flow,
            self.BASE_PARAMS["unit"],
            self.BASE_PARAMS["partner"],
            self.BASE_PARAMS["indic"],
            self.BASE_PARAMS["geo"]
        ])

        url = f"{self.EUROSTAT_API_BASE}/{self.DATASET}/{series_key}/"

        params = {
            "format": "JSON",
            "startPeriod": start_period
        }

        try:
            print(f"[EUInternationalTrade] Fetching {stk_flow} from Eurostat API: {url}")
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
                print(f"[EUInternationalTrade] No data found for {stk_flow}")
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
                    # Convert YYYY-MM to YYYY-MM-01
                    date_str = f"{time_period}-01"
                    result.append({
                        "date": date_str,
                        "value": float(value)
                    })

            print(f"[EUInternationalTrade] Successfully fetched {len(result)} {stk_flow} data points")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[EUInternationalTrade] API request error for {stk_flow}: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[EUInternationalTrade] Data parsing error for {stk_flow}: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日時ベース）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[EUInternationalTrade] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[EUInternationalTrade] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "EU International Trade",
            "source": "Eurostat API (ei_etea_m)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "balance_count": len(cached_data.get("balance", [])) if cached_data else 0,
            "exports_count": len(cached_data.get("exports", [])) if cached_data else 0,
            "imports_count": len(cached_data.get("imports", [])) if cached_data else 0,
            "latest_balance": cached_data.get("latest_balance") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
eu_international_trade_service = EUInternationalTradeService()
