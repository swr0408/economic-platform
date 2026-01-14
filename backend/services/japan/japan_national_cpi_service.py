"""
日本 全国消費者物価指数 (National CPI) サービス

e-Stat API から全国CPI（Consumer Price Index）データを取得

指標:
- 総合 (All Items)
- 生鮮食品を除く総合 (Core CPI)
- 食料及びエネルギーを除く総合 (Core-Core CPI)

データソース:
- e-Stat API (統計局): 指数、前年同月比
- e-Stat CSV (季節調整済み): 前月比
- FMP: 次回発表日のみ

前月比データについて:
- e-Stat APIのcdTab=2は原系列（非季節調整）の前月比
- 総務省発表の「前月比」は季節調整済み指数ベース
- 季節調整済み前月比はCSVファイルから取得

発表スケジュール:
- 毎月18日〜21日頃 8:30 JST
- 前月分のデータを発表

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
DATA_CACHE_FILE = CACHE_DIR / "national_cpi_cache.json"


class JapanNationalCPIService:
    """日本全国消費者物価指数サービス"""

    DATA_CACHE_KEY = "japan:national_cpi:data"
    ECONALPHA_ID = "jp_national_cpi"

    # e-Stat API Configuration
    ESTAT_BASE_URL = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
    CPI_STATS_ID = "0003427113"  # 2020年基準 消費者物価指数

    # 季節調整済み前月比CSVのURL (e-Stat)
    # 全国 季節調整済指数・前月比
    SEASONALLY_ADJUSTED_MOM_CSV_URL = (
        "https://www.e-stat.go.jp/stat-search/file-download"
        "?statInfId=000032103931&fileKind=1"
    )

    def __init__(self):
        self.api_key = os.getenv("ESTAT_API_KEY", "")

    def get_national_cpi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """全国CPIデータを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    cached_data["cached"] = True
                    cached_data["source"] = "redis"
                    cached_data["next_release"] = get_next_release_from_fmp(self.ECONALPHA_ID)
                    return cached_data

        # e-Stat APIから取得
        result = self._fetch_from_estat()
        if result and result.get("data"):
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
            latest = result["data"][-1] if result["data"] else None

            cache_payload = {
                "data": result["data"],
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result["data"],
                "latest": latest,
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
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _fetch_from_estat(self) -> Optional[Dict[str, Any]]:
        """e-Stat APIからCPIデータを取得"""
        if not self.api_key:
            print("e-Stat API key not found")
            return None

        try:
            print("Fetching Japan National CPI data from e-Stat API")

            # Fetch YoY data (前年同月比) - cdTab=3
            all_items_yoy = self._fetch_cpi_series("0001", "3")
            core_yoy = self._fetch_cpi_series("0161", "3")  # 生鮮食品を除く総合
            core_core_yoy = self._fetch_cpi_series("0178", "3")  # 食料及びエネルギーを除く総合

            # Fetch seasonally adjusted MoM data from CSV
            # (e-Stat APIのcdTab=2は原系列なので、CSVから季節調整済みを取得)
            sa_mom_data = self._fetch_seasonally_adjusted_mom()

            # Fetch index data (指数) - cdTab=1
            all_items_index = self._fetch_cpi_series("0001", "1")
            core_index = self._fetch_cpi_series("0161", "1")
            core_core_index = self._fetch_cpi_series("0178", "1")

            if not all_items_yoy:
                print("Failed to fetch CPI data")
                return None

            # Combine data
            combined_data = self._combine_cpi_data(
                all_items_yoy,
                core_yoy,
                core_core_yoy,
                sa_mom_data,  # 季節調整済み前月比
                all_items_index,
                core_index,
                core_core_index,
            )

            return {"data": combined_data}

        except Exception as e:
            print(f"Error fetching CPI data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_seasonally_adjusted_mom(self) -> Optional[Dict[str, Dict[str, float]]]:
        """
        e-Stat CSVから季節調整済み前月比データを取得

        Returns:
            日付をキー、各系列の前月比を値とする辞書
            例: {"2025-11-01": {"all": 0.4, "core": 0.3, "core_core": 0.2}}
        """
        try:
            print("Fetching seasonally adjusted MoM data from e-Stat CSV")

            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            })

            response = session.get(self.SEASONALLY_ADJUSTED_MOM_CSV_URL, timeout=60)

            if response.status_code != 200:
                print(f"Failed to fetch CSV: status {response.status_code}")
                return None

            # Shift_JISでデコード
            content = response.content.decode("shift_jis")
            lines = content.strip().split("\n")

            # ヘッダー行をスキップ（最初の6行はメタデータ）
            # 類・品目,総合（季節調整済）,生鮮食品を除く総合（季節調整済）,...
            # データは7行目以降、形式: YYYYMM,値,値,...
            result = {}

            for line in lines[6:]:  # データ行から処理
                parts = line.split(",")
                if len(parts) < 4:
                    continue

                time_code = parts[0].strip()

                # 時間コードをパース (YYYYMM形式)
                if len(time_code) != 6 or not time_code.isdigit():
                    continue

                year = time_code[:4]
                month = time_code[4:6]
                date_str = f"{year}-{month}-01"

                # 値を取得
                try:
                    all_mom = float(parts[1]) if parts[1].strip() else None
                    core_mom = float(parts[2]) if parts[2].strip() else None
                    core_core_mom = float(parts[3]) if parts[3].strip() else None

                    result[date_str] = {
                        "all": all_mom,
                        "core": core_mom,
                        "core_core": core_core_mom,
                    }
                except (ValueError, IndexError):
                    continue

            print(f"Fetched {len(result)} seasonally adjusted MoM data points")
            return result

        except Exception as e:
            print(f"Error fetching seasonally adjusted MoM: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_cpi_series(
        self, category_code: str, tab_code: str = "3"
    ) -> Optional[List[Dict]]:
        """
        e-Stat APIから特定のCPI系列を取得

        Args:
            category_code: カテゴリコード (0001=総合, 0161=コア, 0178=コアコア)
            tab_code: テーブルタイプ (1=指数, 2=前月比, 3=前年同月比)

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
                "limit": 240,  # 過去20年分（月次データ）
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

            print(f"Fetched {len(parsed_data)} data points for category {category_code}")
            return parsed_data

        except Exception as e:
            print(f"Error fetching CPI series {category_code}: {e}")
            return None

    def _combine_cpi_data(
        self,
        all_items_yoy: List[Dict],
        core_yoy: Optional[List[Dict]],
        core_core_yoy: Optional[List[Dict]],
        sa_mom_data: Optional[Dict[str, Dict[str, float]]],
        all_items_index: Optional[List[Dict]],
        core_index: Optional[List[Dict]],
        core_core_index: Optional[List[Dict]],
    ) -> List[Dict]:
        """異なるCPI系列を結合"""
        # 日付でインデックス化
        core_yoy_dict = {item["date"]: item["value"] for item in (core_yoy or [])}
        core_core_yoy_dict = {
            item["date"]: item["value"] for item in (core_core_yoy or [])
        }
        index_dict = {item["date"]: item["value"] for item in (all_items_index or [])}
        core_index_dict = {item["date"]: item["value"] for item in (core_index or [])}
        core_core_index_dict = {
            item["date"]: item["value"] for item in (core_core_index or [])
        }

        # 季節調整済み前月比データ
        sa_mom = sa_mom_data or {}

        # 日付順にソート
        all_items_sorted = sorted(all_items_yoy, key=lambda x: x["date"])

        combined = []
        for item in all_items_sorted:
            date = item["date"]
            yoy_value = item["value"]

            # 季節調整済み前月比を取得
            mom_values = sa_mom.get(date, {})

            combined.append(
                {
                    "date": date,
                    "index": index_dict.get(date),
                    "yoy": round(yoy_value, 2) if yoy_value is not None else None,
                    "mom": (
                        round(mom_values.get("all"), 2)
                        if mom_values.get("all") is not None
                        else None
                    ),
                    "core_index": core_index_dict.get(date),
                    "core_yoy": (
                        round(core_yoy_dict.get(date), 2)
                        if core_yoy_dict.get(date) is not None
                        else None
                    ),
                    "core_mom": (
                        round(mom_values.get("core"), 2)
                        if mom_values.get("core") is not None
                        else None
                    ),
                    "core_core_index": core_core_index_dict.get(date),
                    "core_core_yoy": (
                        round(core_core_yoy_dict.get(date), 2)
                        if core_core_yoy_dict.get(date) is not None
                        else None
                    ),
                    "core_core_mom": (
                        round(mom_values.get("core_core"), 2)
                        if mom_values.get("core_core") is not None
                        else None
                    ),
                }
            )

        return combined

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

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
            "indicator": "Japan National CPI",
            "source": "e-Stat API",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
japan_national_cpi_service = JapanNationalCPIService()
