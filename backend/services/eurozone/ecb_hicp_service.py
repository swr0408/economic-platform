"""
ECB HICP (Harmonised Index of Consumer Prices) サービス
ECBからユーロ圏HICPインフレデータを取得

指標:
- Total HICP (ICP.M.U2.N.000000.4.INX): 総合HICP指数
- Core HICP excl. energy & food (ICP.M.U2.N.XEF000.4.INX): コアHICP指数
- Core excl. unprocessed food (ICP.M.U2.Y.XEFUN0.3.INX): コアHICP（未加工食品除く）指数
- Goods (ICP.M.U2.N.GOODS0.4.INX): 財指数
- Food (ICP.M.U2.Y.FOOD00.3.INX): 食品指数
- Energy (ICP.M.U2.N.NRGY00.4.INX): エネルギー指数
- Services (ICP.M.U2.Y.SERV00.3.INX): サービス指数

データソース:
- ECB Data API

発表スケジュール:
- 速報: 毎月28日〜翌月7日 18:00-18:10 CET (冬時間: 19:00-19:10 JST)
- 改定: 毎月14日〜25日 18:00-18:10 CET

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
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_hicp_cache.json"


class ECBHICPService:
    """ECB HICPインフレサービス"""

    DATA_CACHE_KEY = "eurozone:ecb_hicp:data"
    ECONALPHA_ID = "ecb_hicp"
    FMP_EVENT_PATTERNS = ["HICP MoM", "HICP YoY"]
    FMP_COUNTRY = "EU"

    # ECB Data API設定
    # 2026: ユーロ圏拡大 (ブルガリア加盟=EA21) により ECB ICP / Eurostat prc_hicp_*
    # の euro圏集計は 2025-12 で停止し、EA21 系列は未公表。現行データは Eurostat の
    # euro-indicators HICP テーブル ei_cphi_m にあり、geo=EA は「可変構成」で 2026 以降
    # 自動的に EA21 を指す。指数単位は HICP2025 (2025=100) に変更されたが、YoY/MoM は
    # 指数の比なのでリベースは出力に影響しない (既存の計算ロジックを流用)。
    EUROSTAT_HICP_BASE = (
        "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/ei_cphi_m"
    )
    HICP_GEO = "EA"          # 可変構成 (2026 以降 EA21)
    HICP_INDEX_UNIT = "HICP2025"  # 指数 (2025=100)

    # 旧 ECB ICP のカテゴリ → Eurostat ei_cphi_m の indic コード対応
    #   TOTAL=総合, CP-HI00XEF=コア(エネルギー・食品・酒類煙草除く),
    #   CP-HI00XEFU=エネルギー・未加工食品除く, CP-HIG=財, CP-HIF=食品,
    #   CP-HIE=エネルギー, CP-HIS=サービス
    SERIES_KEYS = {
        "total_hicp_index": "TOTAL",
        "core_hicp_index": "CP-HI00XEF",
        "core_excl_unprocessed_food_index": "CP-HI00XEFU",
        "goods_index": "CP-HIG",
        "food_index": "CP-HIF",
        "energy_index": "CP-HIE",
        "services_index": "CP-HIS",
    }

    def __init__(self):
        pass

    def get_ecb_hicp_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """HICPデータを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "annual_rates": cached_data.get("annual_rates", {}),
                        "monthly_changes": cached_data.get("monthly_changes", {}),
                        "breakdown_annual_rates": cached_data.get("breakdown_annual_rates", {}),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # ECB APIから取得
        api_result = self._fetch_all_from_ecb()
        if api_result:
            next_release = get_next_release_by_pattern(
                self.FMP_EVENT_PATTERNS[0],
                country=self.FMP_COUNTRY
            )

            from services.usa.fmp_next_release_utils import guarded_last_updated_keys, _max_date_of
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated_keys(
                self.DATA_CACHE_KEY, ("annual_rates", "monthly_changes"),
                _max_date_of(api_result["annual_rates"], api_result["monthly_changes"]), now_str
            )
            cache_payload = {
                "annual_rates": api_result["annual_rates"],
                "monthly_changes": api_result["monthly_changes"],
                "breakdown_annual_rates": api_result["breakdown_annual_rates"],
                "metadata": {
                    "source": "European Central Bank (ECB)",
                    "indicator": "HICP - Harmonised Index of Consumer Prices",
                    "data_start": "2015-01-01",
                    "description": "ユーロ圏消費者物価調和指数（HICP）",
                },
                "next_release": next_release,
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "annual_rates": api_result["annual_rates"],
                "monthly_changes": api_result["monthly_changes"],
                "breakdown_annual_rates": api_result["breakdown_annual_rates"],
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "ecb_api",
                "last_updated": last_updated,
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "annual_rates": file_cache.get("annual_rates", {}),
                "monthly_changes": file_cache.get("monthly_changes", {}),
                "breakdown_annual_rates": file_cache.get("breakdown_annual_rates", {}),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "annual_rates": {},
            "monthly_changes": {},
            "breakdown_annual_rates": {},
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _fetch_all_from_ecb(self, start_date: str = "2015-01-01") -> Optional[Dict[str, Any]]:
        """ECB APIから全データを取得"""
        try:
            print("[ECBHICP] Fetching all HICP data from ECB")

            # 各指数データを取得
            total_hicp_index = self._fetch_series_data(self.SERIES_KEYS["total_hicp_index"], start_date)
            core_hicp_index = self._fetch_series_data(self.SERIES_KEYS["core_hicp_index"], start_date)
            core_excl_unprocessed_food_index = self._fetch_series_data(self.SERIES_KEYS["core_excl_unprocessed_food_index"], start_date)
            goods_index = self._fetch_series_data(self.SERIES_KEYS["goods_index"], start_date)
            food_index = self._fetch_series_data(self.SERIES_KEYS["food_index"], start_date)
            energy_index = self._fetch_series_data(self.SERIES_KEYS["energy_index"], start_date)
            services_index = self._fetch_series_data(self.SERIES_KEYS["services_index"], start_date)

            # 前年比を計算
            total_hicp_annual = self._calculate_year_on_year_change(total_hicp_index or [])
            core_hicp_annual = self._calculate_year_on_year_change(core_hicp_index or [])
            core_excl_unprocessed_food_annual = self._calculate_year_on_year_change(core_excl_unprocessed_food_index or [])
            goods_annual = self._calculate_year_on_year_change(goods_index or [])
            food_annual = self._calculate_year_on_year_change(food_index or [])
            energy_annual = self._calculate_year_on_year_change(energy_index or [])
            services_annual = self._calculate_year_on_year_change(services_index or [])

            # 前月比を計算
            total_hicp_monthly = self._calculate_monthly_change(total_hicp_index or [])
            core_hicp_monthly = self._calculate_monthly_change(core_hicp_index or [])

            result = {
                "annual_rates": {
                    "total_hicp": total_hicp_annual or [],
                    "core_hicp": core_hicp_annual or [],
                    "core_excl_unprocessed_food": core_excl_unprocessed_food_annual or [],
                },
                "monthly_changes": {
                    "total_hicp": total_hicp_monthly or [],
                    "core_hicp": core_hicp_monthly or [],
                },
                "breakdown_annual_rates": {
                    "goods": goods_annual or [],
                    "food": food_annual or [],
                    "energy": energy_annual or [],
                    "services": services_annual or [],
                },
            }

            print(f"[ECBHICP] Fetched data - Total YoY: {len(total_hicp_annual)}, Core YoY: {len(core_hicp_annual)}")
            return result

        except Exception as e:
            print(f"[ECBHICP] Error fetching all data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_series_data(self, indic_code: str, start_date: str = "2015-01-01") -> Optional[List[Dict]]:
        """Eurostat ei_cphi_m から単一系列(指数, geo=EA)を取得して [{date,value}] を返す。

        date は "YYYY-MM" 形式 (旧 ECB ICP と同じ) なので下流の YoY/MoM 計算は無改修。
        """
        try:
            params = {
                "format": "JSON",
                "lang": "EN",
                "geo": self.HICP_GEO,
                "indic": indic_code,
                "unit": self.HICP_INDEX_UNIT,
                "freq": "M",
                "sinceTimePeriod": start_date[:7],
            }
            print(f"[ECBHICP] Fetching series (Eurostat ei_cphi_m): indic={indic_code}")
            response = requests.get(self.EUROSTAT_HICP_BASE, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            # JSON-stat: value(index->数値) と dimension.time.category.index(date->index)
            time_index = (
                data.get("dimension", {}).get("time", {})
                .get("category", {}).get("index", {})
            )
            idx_to_date = {v: k for k, v in time_index.items()}
            values = data.get("value", {})

            result = []
            for idx_str, value in values.items():
                date = idx_to_date.get(int(idx_str))
                if date and value is not None:
                    result.append({"date": date, "value": float(value)})

            result.sort(key=lambda x: x["date"])
            print(f"[ECBHICP] Fetched {len(result)} data points for indic={indic_code}")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[ECBHICP] Request error for {indic_code}: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[ECBHICP] Parse error for {indic_code}: {e}")
            return None

    def _calculate_monthly_change(self, index_data: List[Dict]) -> List[Dict]:
        """指数データから前月比変化率を計算"""
        if not index_data or len(index_data) < 2:
            return []

        result = []
        for i in range(1, len(index_data)):
            current = index_data[i]
            previous = index_data[i - 1]

            if previous["value"] is not None and current["value"] is not None and previous["value"] != 0:
                monthly_change = ((current["value"] - previous["value"]) / previous["value"]) * 100
                result.append({
                    "date": current["date"],
                    "value": round(monthly_change, 2)
                })
            else:
                result.append({
                    "date": current["date"],
                    "value": None
                })

        return result

    def _calculate_year_on_year_change(self, index_data: List[Dict]) -> List[Dict]:
        """指数データから前年比変化率を計算"""
        if not index_data or len(index_data) < 13:
            return []

        result = []
        for i in range(12, len(index_data)):
            current = index_data[i]
            year_ago = index_data[i - 12]

            if year_ago["value"] is not None and current["value"] is not None and year_ago["value"] != 0:
                yoy_change = ((current["value"] - year_ago["value"]) / year_ago["value"]) * 100
                result.append({
                    "date": current["date"],
                    "value": round(yoy_change, 2)
                })
            else:
                result.append({
                    "date": current["date"],
                    "value": None
                })

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_pattern(
            self.FMP_EVENT_PATTERNS[0],
            last_updated_str,
            country=self.FMP_COUNTRY
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ECBHICP] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ECBHICP] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "ECB HICP",
            "source": "ECB API",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": {
                "total_hicp_yoy": len(cached_data.get("annual_rates", {}).get("total_hicp", [])) if cached_data else 0,
                "core_hicp_yoy": len(cached_data.get("annual_rates", {}).get("core_hicp", [])) if cached_data else 0,
            } if cached_data else {},
            "next_release": get_next_release_by_pattern(
                self.FMP_EVENT_PATTERNS[0],
                country=self.FMP_COUNTRY
            ),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ecb_hicp_service = ECBHICPService()
