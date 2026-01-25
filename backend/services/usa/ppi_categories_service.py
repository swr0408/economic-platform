"""
PPI項目別（PPI Categories）サービス
BLS APIからPPI構成項目データを取得

指標（BLS Series ID）:
- WPSFD42213: 航空会社乗客サービス (Transportation of passengers for export)
- WPU401: ポートフォリオ管理 (Securities brokerage, dealing, investment advice)
- WPS511101: 医療ケア (Physician care)
- WPS511103: 在宅医療、ホスピスケア (Home health and hospice care)
- WPS511104: 病院外来医療 (Hospital outpatient care)
- WPS512101: 病院入院治療 (Hospital inpatient care)
- WPS512102: 特別養護老人ホームケア (Nursing home care)

データソース:
- BLS API (v2)

発表スケジュール:
- PPIと同じ（毎月9-17日頃 8:30 ET）

キャッシュ方式: FMP発表日時ベース判定方式（PPIと共通）
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
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
PPI_CATEGORIES_CACHE_FILE = CACHE_DIR / "ppi_categories_cache.json"

# BLS API設定
BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

# BLS Series ID と項目名のマッピング
# WPS形式 = Seasonally Adjusted（季節調整済み）
# WPU形式 = Not Seasonally Adjusted（季節調整なし）
# 季節調整済みデータを取得するためWPS形式を使用（一部WPU形式のみ存在）
PPI_CATEGORIES = {
    "WPSFD42213": {
        "name": "航空会社乗客サービス",
        "name_en": "Transportation of passengers for export",
        "key": "airline_passenger",
    },
    "WPU401": {
        "name": "ポートフォリオ管理",
        "name_en": "Securities brokerage, dealing, investment advice",
        "key": "portfolio_management",
        "note": "季節調整済み(WPS401)が存在しないためWPU形式を使用",
    },
    "WPS511101": {
        "name": "医療ケア",
        "name_en": "Physician care",
        "key": "medical_care",
    },
    "WPS511103": {
        "name": "在宅医療・ホスピスケア",
        "name_en": "Home health and hospice care",
        "key": "home_health_hospice",
    },
    "WPS511104": {
        "name": "病院外来医療",
        "name_en": "Hospital outpatient care",
        "key": "hospital_outpatient",
    },
    "WPS512101": {
        "name": "病院入院治療",
        "name_en": "Hospital inpatient care",
        "key": "hospital_inpatient",
    },
    "WPS512102": {
        "name": "特別養護老人ホームケア",
        "name_en": "Nursing home care",
        "key": "nursing_home",
    },
}


class PPICategoriesService:
    """PPI項目別サービス - BLS API版"""

    CACHE_KEY = "inflation:ppi_categories:data"
    # FMPイベントマッピング用ID（PPIと同じスケジュール）
    PPI_ECONALPHA_ID = "ppi"

    def __init__(self):
        self.api_key = os.environ.get("BLS_API_KEY", "")

    def get_ppi_categories_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        PPI項目別データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "categories": [{
                    "key": str,
                    "series_id": str,
                    "name": str,
                    "name_en": str,
                    "data": [{
                        "date": "YYYY-MM-DD",
                        "value": float,
                        "yoy": float|null
                    }, ...],
                    "latest": {...}
                }, ...],
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "categories": cached_data.get("categories", []),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # BLS APIから取得
        bls_result = self._fetch_from_bls()
        if bls_result:
            next_release = get_next_release_from_fmp(self.PPI_ECONALPHA_ID)

            cache_payload = {
                "categories": bls_result,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "categories": bls_result,
                "next_release": next_release,
                "cached": False,
                "source": "BLS",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "categories": file_cache.get("categories", []),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "categories": [],
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_bls(self) -> List[Dict[str, Any]]:
        """BLS APIから全カテゴリのデータを取得"""
        try:
            series_ids = list(PPI_CATEGORIES.keys())
            print(f"Fetching BLS series: {series_ids}...")

            # BLS API v2でリクエスト
            headers = {"Content-Type": "application/json"}

            # 開始年と終了年を設定（BLS APIは最大20年分まで）
            current_year = datetime.now().year
            start_year = current_year - 15  # 15年分のデータ

            payload = {
                "seriesid": series_ids,
                "startyear": str(start_year),
                "endyear": str(current_year),
                "calculations": True,  # YoY計算を含める
            }

            # APIキーがあれば追加（より多くのデータにアクセス可能）
            if self.api_key:
                payload["registrationkey"] = self.api_key

            response = requests.post(
                BLS_API_URL,
                json=payload,
                headers=headers,
                timeout=60
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "REQUEST_SUCCEEDED":
                print(f"BLS API error: {data.get('message', 'Unknown error')}")
                return []

            # 各シリーズのデータを処理
            result = []
            for series in data.get("Results", {}).get("series", []):
                series_id = series.get("seriesID")
                if series_id not in PPI_CATEGORIES:
                    continue

                category_info = PPI_CATEGORIES[series_id]
                category_data = self._process_series_data(series)

                if category_data:
                    latest = category_data[-1] if category_data else None
                    result.append({
                        "key": category_info["key"],
                        "series_id": series_id,
                        "name": category_info["name"],
                        "name_en": category_info["name_en"],
                        "data": category_data,
                        "latest": latest,
                    })

            print(f"Fetched {len(result)} PPI categories from BLS")
            return result

        except Exception as e:
            print(f"Error fetching from BLS: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _process_series_data(self, series: Dict[str, Any]) -> List[Dict[str, Any]]:
        """BLSシリーズデータを処理してYoY・MoMを計算"""
        raw_data = []

        for item in series.get("data", []):
            try:
                year = int(item.get("year", 0))
                period = item.get("period", "")

                # 月次データのみ処理（M01-M12）
                if not period.startswith("M") or period == "M13":
                    continue

                month = int(period[1:])
                value = float(item.get("value", 0))

                # 日付を作成（月初日）
                date_str = f"{year:04d}-{month:02d}-01"

                # BLS APIのcalculationsからYoY・MoMを取得（存在する場合）
                yoy = None
                mom = None
                calculations = item.get("calculations", {})
                if "pct_changes" in calculations:
                    pct_changes = calculations["pct_changes"]
                    # 前年比（12ヶ月前との比較）
                    if "12" in pct_changes:
                        try:
                            yoy = round(float(pct_changes["12"]), 2)
                        except (ValueError, TypeError):
                            pass
                    # 前月比（1ヶ月前との比較）
                    if "1" in pct_changes:
                        try:
                            mom = round(float(pct_changes["1"]), 2)
                        except (ValueError, TypeError):
                            pass

                raw_data.append({
                    "date": date_str,
                    "value": value,
                    "yoy": yoy,
                    "mom": mom,
                })
            except (ValueError, TypeError):
                continue

        # 日付でソート（昇順）
        raw_data.sort(key=lambda x: x["date"])

        # YoYが計算されていない場合、手動で計算
        if raw_data and all(item.get("yoy") is None for item in raw_data):
            raw_data = self._calculate_yoy_and_mom(raw_data)
        # MoMのみ計算されていない場合、手動で計算
        elif raw_data and all(item.get("mom") is None for item in raw_data):
            raw_data = self._calculate_mom(raw_data)

        return raw_data

    def _calculate_yoy_and_mom(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """前年比（YoY）と前月比（MoM）を手動計算"""
        # 日付→値のマップを作成
        date_value_map = {item["date"]: item["value"] for item in data}

        result = []
        for i, item in enumerate(data):
            current_date = item["date"]
            current_value = item["value"]

            try:
                dt = datetime.strptime(current_date, "%Y-%m-%d")
                prev_year_date = f"{dt.year - 1:04d}-{dt.month:02d}-01"

                # 前月の日付を計算
                if dt.month == 1:
                    prev_month_date = f"{dt.year - 1:04d}-12-01"
                else:
                    prev_month_date = f"{dt.year:04d}-{dt.month - 1:02d}-01"

                # YoY計算
                yoy = None
                if prev_year_date in date_value_map:
                    prev_value = date_value_map[prev_year_date]
                    if prev_value > 0:
                        yoy = round(((current_value - prev_value) / prev_value) * 100, 2)

                # MoM計算
                mom = None
                if prev_month_date in date_value_map:
                    prev_value = date_value_map[prev_month_date]
                    if prev_value > 0:
                        mom = round(((current_value - prev_value) / prev_value) * 100, 2)

                if yoy is not None:
                    result.append({
                        "date": current_date,
                        "value": current_value,
                        "yoy": yoy,
                        "mom": mom,
                    })
            except (ValueError, TypeError):
                continue

        return result

    def _calculate_mom(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """前月比（MoM）を手動計算（YoYはすでにある場合）"""
        # 日付→値のマップを作成
        date_value_map = {item["date"]: item["value"] for item in data}

        result = []
        for item in data:
            current_date = item["date"]
            current_value = item["value"]
            yoy = item.get("yoy")

            try:
                dt = datetime.strptime(current_date, "%Y-%m-%d")

                # 前月の日付を計算
                if dt.month == 1:
                    prev_month_date = f"{dt.year - 1:04d}-12-01"
                else:
                    prev_month_date = f"{dt.year:04d}-{dt.month - 1:02d}-01"

                # MoM計算
                mom = None
                if prev_month_date in date_value_map:
                    prev_value = date_value_map[prev_month_date]
                    if prev_value > 0:
                        mom = round(((current_value - prev_value) / prev_value) * 100, 2)

                result.append({
                    "date": current_date,
                    "value": current_value,
                    "yoy": yoy,
                    "mom": mom,
                })
            except (ValueError, TypeError):
                result.append(item)
                continue

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_fmp_schedule(self.PPI_ECONALPHA_ID, last_updated_str)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not PPI_CATEGORIES_CACHE_FILE.exists():
                return None

            with open(PPI_CATEGORIES_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(PPI_CATEGORIES_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {PPI_CATEGORIES_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        exists = redis_client.exists(self.CACHE_KEY)
        data = redis_client.get(self.CACHE_KEY) if exists else None

        return {
            "indicator": "PPI Categories",
            "source": "BLS API",
            "cache_key": self.CACHE_KEY,
            "exists": exists,
            "last_updated": data.get("last_updated") if data else None,
            "category_count": len(data.get("categories", [])) if data else 0,
            "next_release": get_next_release_from_fmp(self.PPI_ECONALPHA_ID),
            "file_cache_exists": PPI_CATEGORIES_CACHE_FILE.exists()
        }


# シングルトンインスタンス
ppi_categories_service = PPICategoriesService()
