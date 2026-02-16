"""
ECB Consumer Expectations Survey（CES）賃金期待サービス
ECB Data APIからCES家計所得期待データを取得

指標:
- Household income expectations 12 months ahead (% change)
  - 加重平均（WA）: 回答者全体の平均期待値
  - 加重中央値（WM）: 回答者全体の中央値

データソース:
- ECB Data Portal (SDMX): CES/M.Z18.ALL.T.C3220.NUM_VAR.WA
  - M = Monthly
  - Z18 = Euro area 11 (DE, IT, ES, FR, NL, BE, FI, AT, GR, PT, IE)
  - ALL = No specific breakdown
  - T = Total
  - C3220 = Household income expectations 12 months ahead (% change)
  - NUM_VAR = Numeric variable
  - WA = Weighted average / WM = Weighted median

発表スケジュール:
- 月次（毎月下旬、月末の最後の10日間）
- 次回発表日はECB CESトップページからスクレイピングで取得

キャッシュ方式: 発表日ベース判定
- 次回発表日を過ぎたらデータを再取得
- 発表日取得失敗時は24時間フォールバック
"""
import re
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
CET = ZoneInfo("Europe/Berlin")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_ces_wage_expectations_cache.json"


class ECBCesWageExpectationsService:
    """ECB CES 賃金期待サービス"""

    # ECB Legacy API（SDMX形式）
    ECB_LEGACY_API_BASE = "https://data-api.ecb.europa.eu/service/data"

    # シリーズキー（CESデータセット）
    # C3220 = Household income expectations 12 months ahead (% change)
    SERIES_KEY_WA = "M.Z18.ALL.T.C3220.NUM_VAR.WA"   # 加重平均
    SERIES_KEY_WM = "M.Z18.ALL.T.C3220.NUM_VAR.WM"   # 加重中央値

    # ECB CES トップページ（次回発表日スクレイピング用）
    CES_PAGE_URL = "https://www.ecb.europa.eu/stats/ecb_surveys/consumer_exp_survey/html/index.en.html"

    DATA_CACHE_KEY = "employment:ecb_ces_wage_expectations:data"
    NEXT_RELEASE_CACHE_KEY = "employment:ecb_ces_wage_expectations:next_release"

    def __init__(self):
        pass

    def _fetch_next_release(self) -> Optional[Dict[str, Any]]:
        """
        ECB CESトップページから次回発表日を取得

        ページ内の "Next publication of CES results and press release: DD Month YYYY"
        テキストを正規表現で抽出する
        """
        # Redisキャッシュチェック（6時間キャッシュ）
        cached = redis_client.get(self.NEXT_RELEASE_CACHE_KEY)
        if cached:
            return cached

        try:
            print(f"[ECB CES Wage] Fetching next release from: {self.CES_PAGE_URL}")
            response = requests.get(self.CES_PAGE_URL, timeout=15)
            response.raise_for_status()

            text = response.text
            # パターン: "Next publication of CES results and press release: 27 February 2026."
            match = re.search(
                r"Next publication.*?(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})",
                text, re.IGNORECASE
            )

            if match:
                day = int(match.group(1))
                month_str = match.group(2)
                year = int(match.group(3))

                # 月名→数値変換
                month_map = {
                    "january": 1, "february": 2, "march": 3, "april": 4,
                    "may": 5, "june": 6, "july": 7, "august": 8,
                    "september": 9, "october": 10, "november": 11, "december": 12,
                }
                month = month_map.get(month_str.lower())
                if not month:
                    return None

                release_date = datetime(year, month, day, tzinfo=CET)
                release_date_jst = release_date.astimezone(JST)

                result = {
                    "date": release_date.strftime("%Y-%m-%d"),
                    "datetime_jst": release_date_jst.isoformat(),
                    "time_jst": release_date_jst.strftime("%H:%M"),
                    "label": "ECB CES Results & Press Release",
                }

                # 6時間キャッシュ
                redis_client.set(self.NEXT_RELEASE_CACHE_KEY, result, expire=21600)
                print(f"[ECB CES Wage] Next release: {result['date']}")
                return result

            print("[ECB CES Wage] Could not find next publication date on CES page")
            return None

        except Exception as e:
            print(f"[ECB CES Wage] Error fetching next release: {e}")
            return None

    def _fetch_series_data(self, series_key: str, start_date: str = "2022-01") -> Optional[List[Dict]]:
        """ECB Legacy API（SDMX）からシリーズデータを取得"""
        url = f"{self.ECB_LEGACY_API_BASE}/CES/{series_key}"
        params = {
            "startPeriod": start_date,
            "format": "jsondata"
        }

        try:
            print(f"[ECB CES Wage] Fetching: {url}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if "dataSets" not in data or len(data["dataSets"]) == 0:
                print(f"[ECB CES Wage] No data sets found for {series_key}")
                return None

            dataset = data["dataSets"][0]
            if "series" not in dataset:
                print(f"[ECB CES Wage] No series found for {series_key}")
                return None

            series_data = list(dataset["series"].values())[0]
            observations = series_data.get("observations", {})

            # 時間次元を取得
            dimensions = data.get("structure", {}).get("dimensions", {}).get("observation", [])
            time_dimension = None
            for dim in dimensions:
                if dim.get("id") == "TIME_PERIOD":
                    time_dimension = dim
                    break

            if not time_dimension:
                print(f"[ECB CES Wage] No time dimension found for {series_key}")
                return None

            time_values = time_dimension.get("values", [])

            result = []
            for obs_key, obs_value in observations.items():
                time_index = int(obs_key)
                if time_index < len(time_values):
                    period = time_values[time_index].get("id")
                    value = obs_value[0] if isinstance(obs_value, list) and len(obs_value) > 0 else obs_value

                    if value is not None and period:
                        # 月次データ: "2024-01" → "2024-01-01"
                        date_str = f"{period}-01" if len(period) == 7 else period
                        result.append({
                            "date": date_str,
                            "value": float(value)
                        })

            result.sort(key=lambda x: x["date"])
            print(f"[ECB CES Wage] Fetched {len(result)} data points for {series_key}")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[ECB CES Wage] Request error for {series_key}: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[ECB CES Wage] Parse error for {series_key}: {e}")
            return None

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ECB CES 賃金期待データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": cached_data.get("next_release"),
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
                        "data": file_cache.get("data", []),
                        "latest": file_cache.get("latest"),
                        "next_release": file_cache.get("next_release"),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str,
                    }

        # ECB APIからデータ取得（加重平均のみ使用）
        wa_data = self._fetch_series_data(self.SERIES_KEY_WA) or []

        if wa_data:
            latest = wa_data[-1] if wa_data else None
            next_release = self._fetch_next_release()

            cache_payload = {
                "data": wa_data,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": wa_data,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "ecb_api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        発表日ベース判定:
        - 次回発表日を過ぎたら && last_updated が発表日前 → 更新
        - 発表日取得失敗時は24時間フォールバック
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)
            now = datetime.now(JST)

            # 次回発表日を取得して判定
            next_release = self._fetch_next_release()
            if next_release and next_release.get("datetime_jst"):
                release_dt = datetime.fromisoformat(next_release["datetime_jst"])
                # 発表日がまだ来ていない → 更新不要
                if now < release_dt:
                    return False
                # 発表日を過ぎた && last_updated が発表日前 → 更新
                if last_updated < release_dt:
                    return True
                # 発表日を過ぎた && last_updated が発表日後 → 更新不要（既に最新）
                return False

            # 発表日取得失敗 → 24時間フォールバック
            return (now - last_updated).total_seconds() > 86400
        except Exception:
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "ECB CES Wage Expectations (Household Income 12m ahead)",
            "source": "ECB Data API (CES)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._fetch_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ecb_ces_wage_expectations_service = ECBCesWageExpectationsService()
