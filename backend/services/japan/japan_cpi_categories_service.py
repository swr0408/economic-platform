"""
日本 全国CPI 10大費目別データサービス

e-Stat API から全国CPI（Consumer Price Index）の10大費目データを取得

10大費目:
- 食料 (Food)
- 住居 (Housing)
- 光熱・水道 (Fuel, light & water charges)
- 家具・家事用品 (Furniture & household utensils)
- 被服及び履物 (Clothes & footwear)
- 保健医療 (Medical care)
- 交通・通信 (Transportation & communication)
- 教育 (Education)
- 教養娯楽 (Culture & recreation)
- 諸雑費 (Miscellaneous)

データソース:
- e-Stat API (統計局): 指数、前年同月比
- FMP: 次回発表日のみ

発表スケジュール:
- 全国CPIに準拠（毎月18日〜21日頃 8:30 JST）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import os
import requests
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client
from services.japan.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "price"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "national_cpi_categories_cache.json"


class JapanCPICategoriesService:
    """日本 全国CPI 10大費目別サービス"""

    DATA_CACHE_KEY = "japan:national_cpi_categories:data"
    ECONALPHA_ID = "jp_national_cpi"  # 全国CPIと同じスケジュール

    # e-Stat API Configuration
    ESTAT_BASE_URL = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
    CPI_STATS_ID = "0003427113"  # 2020年基準 消費者物価指数

    # 10大費目 (10 Major Categories)
    # Format: {code: (name, weight)}
    # Weights are approximate values based on 2020 base year (per 10,000)
    MAJOR_CATEGORIES = {
        "0002": ("食料", 2633),
        "0045": ("住居", 2076),
        "0054": ("光熱・水道", 744),
        "0060": ("家具・家事用品", 354),
        "0082": ("被服及び履物", 382),
        "0107": ("保健医療", 433),
        "0111": ("交通・通信", 1465),
        "0118": ("教育", 316),
        "0122": ("教養娯楽", 995),
        "0145": ("諸雑費", 602),
    }

    def __init__(self):
        self.api_key = os.getenv("ESTAT_API_KEY", "")

    def get_cpi_categories_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """CPI 10大費目データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    cached_data["cached"] = True
                    cached_data["source"] = "redis"
                    cached_data["next_release"] = get_next_release_from_fmp(
                        self.ECONALPHA_ID
                    )
                    return cached_data

        # e-Stat APIから取得
        result = self._fetch_from_estat()
        if result and result.get("data"):
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            cache_payload = {
                "data": result["data"],
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result["data"],
                "next_release": next_release,
                "cached": False,
                "source": "e-stat",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            file_cache["cached"] = True
            file_cache["source"] = "file (fallback)"
            file_cache["next_release"] = get_next_release_from_fmp(self.ECONALPHA_ID)
            return file_cache

        return {
            "data": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _fetch_from_estat(self) -> Optional[Dict[str, Any]]:
        """e-Stat APIから10大費目データを取得"""
        if not self.api_key:
            print("e-Stat API key not found")
            return None

        try:
            print("Fetching Japan CPI 10 major categories data from e-Stat API")

            all_data = {}

            for category_code, (category_name, weight) in self.MAJOR_CATEGORIES.items():
                # 指数データ (cdTab=1)
                index_data = self._fetch_category_series(category_code, "1")
                # 前年同月比データ (cdTab=3)
                yoy_data = self._fetch_category_series(category_code, "3")

                if index_data and yoy_data:
                    all_data[category_code] = {
                        "name": category_name,
                        "weight": weight,
                        "index": index_data,
                        "yoy": yoy_data,
                    }

            if not all_data:
                print("Failed to fetch CPI categories data")
                return None

            # 直近2か月のデータを抽出
            recent_data = self._extract_recent_months(all_data)

            return {"data": recent_data}

        except Exception as e:
            print(f"Error fetching CPI categories data: {e}")
            import traceback

            traceback.print_exc()
            return None

    def _fetch_category_series(
        self, category_code: str, tab_code: str = "1"
    ) -> Optional[List[Dict]]:
        """
        e-Stat APIから特定カテゴリの系列を取得

        Args:
            category_code: カテゴリコード
            tab_code: テーブルタイプ (1=指数, 3=前年同月比)

        Returns:
            データポイントのリスト
        """
        try:
            params = {
                "appId": self.api_key,
                "statsDataId": self.CPI_STATS_ID,
                "cdCat01": category_code,
                "cdTab": tab_code,
                "cdArea": "00000",  # 全国
                "metaGetFlg": "N",
                "limit": 3,  # 直近3か月分のみ
            }

            response = requests.get(self.ESTAT_BASE_URL, params=params, timeout=30)

            if response.status_code != 200:
                print(f"e-Stat API returned status {response.status_code}")
                return None

            data = response.json()

            # レスポンスのパース
            result = data.get("GET_STATS_DATA", {})
            if result.get("RESULT", {}).get("STATUS") != 0:
                error_msg = result.get("RESULT", {}).get("ERROR_MSG", "Unknown error")
                print(f"e-Stat API error: {error_msg}")
                return None

            # データ値の抽出
            values = (
                result.get("STATISTICAL_DATA", {})
                .get("DATA_INF", {})
                .get("VALUE", [])
            )

            parsed_data = []
            for item in values:
                try:
                    time_code = item.get("@time")  # Format: YYYYNNMMDD
                    value_str = item.get("$")

                    if not value_str or value_str == "***":
                        continue

                    value = float(value_str)

                    if time_code and len(time_code) == 10:
                        year = time_code[:4]
                        month = time_code[6:8]
                        date_str = f"{year}-{month}-01"

                        parsed_data.append({"date": date_str, "value": value})
                except Exception:
                    continue

            return parsed_data

        except Exception as e:
            print(f"Error fetching category series {category_code}: {e}")
            return None

    def _extract_recent_months(self, all_data: Dict) -> Dict:
        """
        直近2か月のデータを抽出

        Args:
            all_data: 全カテゴリデータの辞書

        Returns:
            直近2か月のデータを含む辞書
        """
        # 最初のカテゴリから日付を取得
        first_category_code = list(self.MAJOR_CATEGORIES.keys())[0]
        if first_category_code not in all_data:
            return {}

        index_data = all_data[first_category_code]["index"]
        if not index_data or len(index_data) < 2:
            return {}

        # 日付でソートして直近2か月を取得
        sorted_dates = sorted([item["date"] for item in index_data], reverse=True)
        current_month = sorted_dates[0] if len(sorted_dates) > 0 else None
        previous_month = sorted_dates[1] if len(sorted_dates) > 1 else None

        if not current_month or not previous_month:
            return {}

        # 2か月分のデータを抽出
        result = {
            "current_month": current_month,
            "previous_month": previous_month,
            "categories": [],
        }

        for category_code, (category_name, weight) in self.MAJOR_CATEGORIES.items():
            if category_code not in all_data:
                continue

            cat_data = all_data[category_code]
            index_list = cat_data["index"]
            yoy_list = cat_data["yoy"]

            # ルックアップ用の辞書を作成
            index_dict = {item["date"]: item["value"] for item in index_list}
            yoy_dict = {item["date"]: item["value"] for item in yoy_list}

            # 当月データを取得
            current_index = index_dict.get(current_month)
            current_yoy = yoy_dict.get(current_month)

            # 前月データを取得
            previous_index = index_dict.get(previous_month)
            previous_yoy = yoy_dict.get(previous_month)

            # 寄与度を計算
            # 公式: (前年比% × ウェイト) / 10,000
            current_contribution = (
                round(current_yoy * weight / 10000, 2)
                if current_yoy is not None
                else None
            )
            previous_contribution = (
                round(previous_yoy * weight / 10000, 2)
                if previous_yoy is not None
                else None
            )

            result["categories"].append(
                {
                    "code": category_code,
                    "name": category_name,
                    "current": {
                        "index": round(current_index, 1)
                        if current_index is not None
                        else None,
                        "yoy": round(current_yoy, 2)
                        if current_yoy is not None
                        else None,
                        "contribution": current_contribution,
                    },
                    "previous": {
                        "index": round(previous_index, 1)
                        if previous_index is not None
                        else None,
                        "yoy": round(previous_yoy, 2)
                        if previous_yoy is not None
                        else None,
                        "contribution": previous_contribution,
                    },
                }
            )

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定

        max_age_hours=24: e-Statは全国CPI公表当日(8:30 JST)に必ず反映されるため、
        FMPカレンダーに全国CPIの発表イベントが欠落していてもmax-ageネットで翌日には
        追従させる(過去にFMPが中旬の全国CPIリリースを取りこぼし数日凍結した実績あり)。
        """
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str, max_age_hours=24)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Japan CPI 10 Major Categories",
            "source": "e-Stat API",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "categories_count": len(
                cached_data.get("data", {}).get("categories", [])
            )
            if cached_data
            else 0,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
japan_cpi_categories_service = JapanCPICategoriesService()
