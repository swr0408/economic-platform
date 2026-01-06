"""
消費者物価指数（CPI）サービス
FREDからCPI / コアCPIデータを取得

指標:
- CPIAUCSL: CPI総合（季節調整済み）
- CPILFESL: コアCPI（食品・エネルギー除く、季節調整済み）

データソース:
- FRED: CPIAUCSL, CPILFESL

発表スケジュール:
- 毎月10-15日頃 8:30 ET（米国東部時間）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CPI_CACHE_FILE = CACHE_DIR / "cpi_cache.json"
CORE_CPI_CACHE_FILE = CACHE_DIR / "core_cpi_cache.json"

# FRED シリーズID
FRED_CPI_SERIES = "CPIAUCSL"           # CPI総合（季節調整済み）
FRED_CORE_CPI_SERIES = "CPILFESL"      # コアCPI（食品・エネルギー除く）

# CPI項目別 FREDシリーズID
CPI_CATEGORY_SERIES = {
    "food": "CPIUFDNS",           # 食品（非季節調整）
    "energy": "CPIENGNS",         # エネルギー（非季節調整）
    "core_goods": "CUUR0000SACL1E",   # コア財（商品から食品・エネルギー除く）
    "core_services": "CUUR0000SASLE", # コアサービス（サービスからエネルギー除く）
    "shelter": "CUUR0000SAH1",    # 住居費（家賃）
}

CPI_CATEGORIES_CACHE_FILE = CACHE_DIR / "cpi_categories_cache.json"


class CPIService:
    """消費者物価指数（CPI）サービス - FRED版"""

    CPI_CACHE_KEY = "inflation:cpi:data"
    CORE_CPI_CACHE_KEY = "inflation:core_cpi:data"
    CPI_CATEGORIES_CACHE_KEY = "inflation:cpi_categories:data"
    CPI_ECONALPHA_ID = "us_cpi"
    CORE_CPI_ECONALPHA_ID = "us_core_cpi"

    FRED_BASE_URL = "https://api.stlouisfed.org/fred"

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_cpi_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        CPI（総合）データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float, "yoy": float|null, "mom": float|null}, ...],
                "latest": {...},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CPI_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh_cpi(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # FREDから取得
        fred_result = self._fetch_cpi_from_fred()
        if fred_result:
            next_release = get_next_release_from_fmp(self.CPI_ECONALPHA_ID)

            latest = fred_result[-1] if fred_result else None
            cache_payload = {
                "data": fred_result,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.CPI_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload, CPI_CACHE_FILE)

            return {
                "data": fred_result,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "FRED",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache(CPI_CACHE_FILE)
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def get_core_cpi_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        コアCPI（食品・エネルギー除く）データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float, "yoy": float|null, "mom": float|null}, ...],
                "latest": {...},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CORE_CPI_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh_core_cpi(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # FREDから取得
        fred_result = self._fetch_core_cpi_from_fred()
        if fred_result:
            next_release = get_next_release_from_fmp(self.CORE_CPI_ECONALPHA_ID)

            latest = fred_result[-1] if fred_result else None
            cache_payload = {
                "data": fred_result,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.CORE_CPI_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload, CORE_CPI_CACHE_FILE)

            return {
                "data": fred_result,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "FRED",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache(CORE_CPI_CACHE_FILE)
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def get_cpi_categories_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        CPI項目別（食品、エネルギー、コア財、コアサービス、住居費）データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "food": float, "energy": float, ...}, ...],
                "latest": {...},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CPI_CATEGORIES_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh_cpi(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # FREDから各項目を取得してマージ
        merged_result = self._fetch_cpi_categories_from_fred()
        if merged_result:
            next_release = get_next_release_from_fmp(self.CPI_ECONALPHA_ID)

            latest = merged_result[-1] if merged_result else None
            cache_payload = {
                "data": merged_result,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.CPI_CATEGORIES_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload, CPI_CATEGORIES_CACHE_FILE)

            return {
                "data": merged_result,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "FRED",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache(CPI_CATEGORIES_CACHE_FILE)
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_cpi_from_fred(self) -> List[Dict[str, Any]]:
        """FREDからCPI（CPIAUCSL）データを取得し、YoY/MoMを計算"""
        return self._fetch_and_calculate_changes(FRED_CPI_SERIES)

    def _fetch_core_cpi_from_fred(self) -> List[Dict[str, Any]]:
        """FREDからコアCPI（CPILFESL）データを取得し、YoY/MoMを計算"""
        return self._fetch_and_calculate_changes(FRED_CORE_CPI_SERIES)

    def _fetch_cpi_categories_from_fred(self) -> List[Dict[str, Any]]:
        """
        FREDからCPI項目別データを取得し、前年比を計算してマージ

        各項目:
        - food: 食品
        - energy: エネルギー
        - core_goods: コア財
        - core_services: コアサービス
        - shelter: 住居費（家賃）
        """
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            # 各項目のデータを取得
            category_data: Dict[str, Dict[str, float]] = {}  # date -> {category: yoy}

            for category_name, series_id in CPI_CATEGORY_SERIES.items():
                print(f"Fetching FRED series: {series_id} ({category_name})...")

                url = f"{self.FRED_BASE_URL}/series/observations"
                params = {
                    "series_id": series_id,
                    "api_key": self.api_key,
                    "file_type": "json",
                    "observation_start": "2000-01-01",
                    "sort_order": "asc"
                }

                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                # 有効なデータのみ抽出
                raw_data = []
                for obs in data.get("observations", []):
                    if obs.get("value") and obs["value"] != ".":
                        try:
                            raw_data.append({
                                "date": obs["date"],
                                "index": float(obs["value"])
                            })
                        except (ValueError, TypeError):
                            continue

                if not raw_data:
                    print(f"No data for {series_id}")
                    continue

                # 日付でソート
                raw_data.sort(key=lambda x: x["date"])

                # 日付→インデックスのマップを作成
                date_index_map = {item["date"]: item["index"] for item in raw_data}

                # 前年比（YoY）を計算
                for item in raw_data:
                    current_date = item["date"]
                    current_index = item["index"]

                    try:
                        dt = datetime.strptime(current_date, "%Y-%m-%d")
                    except ValueError:
                        continue

                    # 前年比（YoY）- 正確に12ヶ月前の日付を計算
                    prev_year_date = f"{dt.year - 1:04d}-{dt.month:02d}-01"

                    if prev_year_date in date_index_map:
                        prev_index = date_index_map[prev_year_date]
                        if prev_index > 0:
                            yoy = round(((current_index - prev_index) / prev_index) * 100, 2)

                            if current_date not in category_data:
                                category_data[current_date] = {}
                            category_data[current_date][category_name] = yoy

                print(f"Processed {len([d for d in category_data.values() if category_name in d])} records for {category_name}")

            # データをマージして日付順にソート
            result = []
            for date_str in sorted(category_data.keys()):
                item = {"date": date_str}
                item.update(category_data[date_str])
                # 全項目が揃っているデータのみ追加（2001年以降）
                if len(item) > 3:  # date + 少なくとも3項目
                    result.append(item)

            print(f"Merged {len(result)} records for CPI categories")
            return result

        except Exception as e:
            print(f"Error fetching CPI categories from FRED: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_and_calculate_changes(self, series_id: str) -> List[Dict[str, Any]]:
        """FREDからデータを取得し、前年比・前月比を計算"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print(f"Fetching FRED series: {series_id}...")

            url = f"{self.FRED_BASE_URL}/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": "2000-01-01",
                "sort_order": "asc"
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            # 有効なデータのみ抽出
            raw_data = []
            for obs in data.get("observations", []):
                if obs.get("value") and obs["value"] != ".":
                    try:
                        raw_data.append({
                            "date": obs["date"],
                            "index": float(obs["value"])
                        })
                    except (ValueError, TypeError):
                        continue

            if not raw_data:
                return []

            # 日付でソート
            raw_data.sort(key=lambda x: x["date"])

            # 日付→インデックスのマップを作成（正確な月の比較用）
            date_index_map = {item["date"]: item["index"] for item in raw_data}

            # YoY（前年比）とMoM（前月比）を計算
            result = []
            for item in raw_data:
                current_date = item["date"]
                current_index = item["index"]

                # 日付をパース（YYYY-MM-DD形式）
                try:
                    dt = datetime.strptime(current_date, "%Y-%m-%d")
                except ValueError:
                    continue

                yoy = None
                mom = None

                # 前月比（MoM）- 正確に1ヶ月前の日付を計算
                prev_month_year = dt.year if dt.month > 1 else dt.year - 1
                prev_month_month = dt.month - 1 if dt.month > 1 else 12
                prev_month_date = f"{prev_month_year:04d}-{prev_month_month:02d}-01"

                if prev_month_date in date_index_map:
                    prev_index = date_index_map[prev_month_date]
                    if prev_index > 0:
                        mom = round(((current_index - prev_index) / prev_index) * 100, 2)
                # 前月データが欠損している場合、momはNoneのまま

                # 前年比（YoY）- 正確に12ヶ月前の日付を計算
                prev_year_date = f"{dt.year - 1:04d}-{dt.month:02d}-01"

                if prev_year_date in date_index_map:
                    prev_index = date_index_map[prev_year_date]
                    if prev_index > 0:
                        yoy = round(((current_index - prev_index) / prev_index) * 100, 2)

                # YoYがある場合のみ結果に追加（2001年以降）
                if yoy is not None:
                    result.append({
                        "date": current_date,
                        "value": yoy,  # メイン値はYoY
                        "yoy": yoy,
                        "mom": mom,  # 前月データが欠損ならNone
                        "index": round(current_index, 2),
                    })

            # 3か月年率・6か月年率を計算して追加
            result = self._calculate_annualized_rates(result, date_index_map)

            print(f"Fetched {len(result)} records from FRED ({series_id})")
            return result

        except Exception as e:
            print(f"Error fetching from FRED ({series_id}): {e}")
            import traceback
            traceback.print_exc()
            return []

    def _calculate_annualized_rates(
        self,
        result: List[Dict[str, Any]],
        date_index_map: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """
        3か月年率・6か月年率を計算して結果に追加

        計算式:
        - 3か月年率: ((current / 3monthsAgo)^4 - 1) * 100
        - 6か月年率: ((current / 6monthsAgo)^2 - 1) * 100
        """
        for item in result:
            current_date = item["date"]
            current_index = item["index"]

            try:
                dt = datetime.strptime(current_date, "%Y-%m-%d")
            except ValueError:
                item["annualized_3m"] = None
                item["annualized_6m"] = None
                continue

            # 3か月前の日付を計算
            three_months_ago_month = dt.month - 3
            three_months_ago_year = dt.year
            if three_months_ago_month <= 0:
                three_months_ago_month += 12
                three_months_ago_year -= 1
            three_months_ago_date = f"{three_months_ago_year:04d}-{three_months_ago_month:02d}-01"

            # 6か月前の日付を計算
            six_months_ago_month = dt.month - 6
            six_months_ago_year = dt.year
            if six_months_ago_month <= 0:
                six_months_ago_month += 12
                six_months_ago_year -= 1
            six_months_ago_date = f"{six_months_ago_year:04d}-{six_months_ago_month:02d}-01"

            # 3か月年率を計算
            annualized_3m = None
            if three_months_ago_date in date_index_map:
                prev_index = date_index_map[three_months_ago_date]
                if prev_index > 0:
                    # (current / prev)^4 - 1
                    ratio = current_index / prev_index
                    annualized_3m = round((pow(ratio, 4) - 1) * 100, 2)

            # 6か月年率を計算
            annualized_6m = None
            if six_months_ago_date in date_index_map:
                prev_index = date_index_map[six_months_ago_date]
                if prev_index > 0:
                    # (current / prev)^2 - 1
                    ratio = current_index / prev_index
                    annualized_6m = round((pow(ratio, 2) - 1) * 100, 2)

            item["annualized_3m"] = annualized_3m
            item["annualized_6m"] = annualized_6m

        return result

    def _should_refresh_cpi(self, last_updated_str: str) -> bool:
        """CPIキャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_fmp_schedule(self.CPI_ECONALPHA_ID, last_updated_str)

    def _should_refresh_core_cpi(self, last_updated_str: str) -> bool:
        """コアCPIキャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_fmp_schedule(self.CORE_CPI_ECONALPHA_ID, last_updated_str)

    def _load_file_cache(self, cache_file: Path) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not cache_file.exists():
                return None

            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any], cache_file: Path) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {cache_file}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        cpi_deleted = redis_client.delete(self.CPI_CACHE_KEY)
        core_cpi_deleted = redis_client.delete(self.CORE_CPI_CACHE_KEY)
        categories_deleted = redis_client.delete(self.CPI_CATEGORIES_CACHE_KEY)
        return cpi_deleted or core_cpi_deleted or categories_deleted

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cpi_exists = redis_client.exists(self.CPI_CACHE_KEY)
        core_cpi_exists = redis_client.exists(self.CORE_CPI_CACHE_KEY)
        categories_exists = redis_client.exists(self.CPI_CATEGORIES_CACHE_KEY)
        cpi_data = redis_client.get(self.CPI_CACHE_KEY) if cpi_exists else None
        core_cpi_data = redis_client.get(self.CORE_CPI_CACHE_KEY) if core_cpi_exists else None
        categories_data = redis_client.get(self.CPI_CATEGORIES_CACHE_KEY) if categories_exists else None

        return {
            "cpi": {
                "indicator": "CPI (Consumer Price Index)",
                "source": "FRED (CPIAUCSL)",
                "cache_key": self.CPI_CACHE_KEY,
                "exists": cpi_exists,
                "last_updated": cpi_data.get("last_updated") if cpi_data else None,
                "data_count": len(cpi_data.get("data", [])) if cpi_data else 0,
                "latest": cpi_data.get("latest") if cpi_data else None,
                "next_release": get_next_release_from_fmp(self.CPI_ECONALPHA_ID),
                "file_cache_exists": CPI_CACHE_FILE.exists()
            },
            "core_cpi": {
                "indicator": "Core CPI",
                "source": "FRED (CPILFESL)",
                "cache_key": self.CORE_CPI_CACHE_KEY,
                "exists": core_cpi_exists,
                "last_updated": core_cpi_data.get("last_updated") if core_cpi_data else None,
                "data_count": len(core_cpi_data.get("data", [])) if core_cpi_data else 0,
                "latest": core_cpi_data.get("latest") if core_cpi_data else None,
                "next_release": get_next_release_from_fmp(self.CORE_CPI_ECONALPHA_ID),
                "file_cache_exists": CORE_CPI_CACHE_FILE.exists()
            },
            "cpi_categories": {
                "indicator": "CPI by Category",
                "source": "FRED (CPIUFDNS, CPIENGNS, etc.)",
                "cache_key": self.CPI_CATEGORIES_CACHE_KEY,
                "exists": categories_exists,
                "last_updated": categories_data.get("last_updated") if categories_data else None,
                "data_count": len(categories_data.get("data", [])) if categories_data else 0,
                "latest": categories_data.get("latest") if categories_data else None,
                "next_release": get_next_release_from_fmp(self.CPI_ECONALPHA_ID),
                "file_cache_exists": CPI_CATEGORIES_CACHE_FILE.exists()
            }
        }


# シングルトンインスタンス
cpi_service = CPIService()
