"""
ECB SPF Core (Survey of Professional Forecasters) コアインフレ期待サービス
ECBからコアインフレ期待データを取得

指標:
- コアHICP 1年先予測 (One year ahead)
- コアHICP 2年先予測 (Two years ahead)
- コアHICP 長期予測 (Longer term - five years ahead)

データソース:
- ECB Data API (SPF dataflow)

発表スケジュール:
- 発表: 1月・4月・7月・10月（四半期ごと）
- 発表日はECBサイトから自動取得

キャッシュ方式: 独自判定方式（ECBサイトから次回発表日を取得）
"""
import json
import requests
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
CET = ZoneInfo("Europe/Berlin")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_spf_core_cache.json"


class ECBSPFCoreService:
    """ECB SPF Coreサービス"""

    DATA_CACHE_KEY = "eurozone:ecb_spf_core:data"

    # ECB Data API設定
    ECB_API_BASE = "https://data-api.ecb.europa.eu/service/data"
    DATAFLOW = "SPF"

    # シリーズキー（ECB Data API）
    # Key structure: Frequency.Area.Category.Type.Horizon.Measure.Statistic
    # M = Monthly, Q = Quarterly, U2 = Euro Area
    # CORE = Core inflation (excluding energy and food)
    # POINT = Point estimate, P12M = 12 months ahead, P24M = 24 months ahead, LT = Longer term
    SERIES_KEYS = {
        "core_12m": "M.U2.CORE.POINT.P12M.Q.AVG",     # 12ヶ月先
        "core_24m": "M.U2.CORE.POINT.P24M.Q.AVG",     # 24ヶ月先
        "core_lt": "Q.U2.CORE.POINT.LT.Q.AVG",        # 長期（5年先）
    }

    # 次回発表日取得URL
    NEXT_RELEASE_URL = "https://www.ecb.europa.eu/stats/ecb_surveys/survey_of_professional_forecasters/html/index.en.html"

    def __init__(self):
        pass

    def get_ecb_spf_core_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """SPF Coreデータを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "inflation_expectations": cached_data.get("inflation_expectations", {}),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # プライマリ: ECB Data APIからデータ取得
        api_result = self._fetch_from_ecb()

        if api_result:
            next_release = self._get_next_release_from_ecb()

            cache_payload = {
                "inflation_expectations": api_result["inflation_expectations"],
                "metadata": {
                    "source": "European Central Bank (ECB) - Survey of Professional Forecasters (Core)",
                    "indicator": "SPF - Core Inflation Expectations",
                    "data_start": "2015-01-01",
                    "description": "コアインフレ期待（ユーロ圏・SPF）",
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "inflation_expectations": api_result["inflation_expectations"],
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "ecb_api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "inflation_expectations": file_cache.get("inflation_expectations", {}),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "inflation_expectations": {},
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _fetch_from_ecb(self, start_date: str = "2015-01-01") -> Optional[Dict[str, Any]]:
        """ECB APIからSPF Coreデータを取得"""
        try:
            print("[ECBSPF_CORE] Fetching SPF Core data from ECB API")

            inflation_expectations = {}

            for key, series_key in self.SERIES_KEYS.items():
                data = self._fetch_series_data(series_key, start_date, key)
                if data:
                    inflation_expectations[key] = data
                    print(f"[ECBSPF_CORE] {key}: {len(data)} data points")

            if not inflation_expectations:
                print("[ECBSPF_CORE] No data fetched from ECB API")
                return None

            return {"inflation_expectations": inflation_expectations}

        except Exception as e:
            print(f"[ECBSPF_CORE] Error fetching from ECB: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_series_data(self, series_key: str, start_date: str, data_key: str) -> Optional[List[Dict]]:
        """単一シリーズをECB APIから取得

        ECB APIのTIME_PERIODは予測対象期（Target period）を返すため、
        発表期（Survey period）に変換する必要がある:
        - core_12m: 予測対象期 - 9ヶ月 = 発表期
        - core_24m: 予測対象期 - 21ヶ月 = 発表期
        - core_lt: そのまま四半期形式（発表期）
        """
        url = f"{self.ECB_API_BASE}/{self.DATAFLOW}/{series_key}"

        params = {
            "startPeriod": start_date,
            "format": "jsondata",
            "detail": "dataonly"
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if "dataSets" not in data or len(data["dataSets"]) == 0:
                print(f"[ECBSPF_CORE] No datasets for {series_key}")
                return None

            dataset = data["dataSets"][0]
            if "series" not in dataset:
                print(f"[ECBSPF_CORE] No series in dataset for {series_key}")
                return None

            # 最初のシリーズを取得
            series_data = list(dataset["series"].values())[0]
            observations = series_data.get("observations", {})

            # 時間ディメンションを取得
            dimensions = data.get("structure", {}).get("dimensions", {}).get("observation", [])
            time_dimension = None
            for dim in dimensions:
                if dim.get("id") == "TIME_PERIOD":
                    time_dimension = dim
                    break

            if not time_dimension:
                print(f"[ECBSPF_CORE] No time dimension for {series_key}")
                return None

            time_values = time_dimension.get("values", [])

            # 結果リストを構築
            result = []
            for obs_key, obs_value in observations.items():
                time_index = int(obs_key)
                if time_index < len(time_values):
                    target_date_str = time_values[time_index].get("id")
                    value = obs_value[0] if isinstance(obs_value, list) and len(obs_value) > 0 else obs_value

                    if value is not None:
                        # 予測対象期から発表期（サーベイ期）を計算
                        survey_date = self._convert_target_to_survey_date(target_date_str, data_key)
                        result.append({
                            "date": survey_date,
                            "value": round(float(value), 2)
                        })

            # 日付でソート
            result.sort(key=lambda x: x["date"])
            return result

        except requests.exceptions.RequestException as e:
            print(f"[ECBSPF_CORE] Request error for {series_key}: {e}")
            return None
        except Exception as e:
            print(f"[ECBSPF_CORE] Parse error for {series_key}: {e}")
            return None

    def _convert_target_to_survey_date(self, target_date: str, data_key: str) -> str:
        """予測対象期から発表期（サーベイ期）を計算

        ECB SPFの発表スケジュール:
        - Q1発表（1月）: 3月を対象期とする予測
        - Q2発表（4月）: 6月を対象期とする予測
        - Q3発表（7月）: 9月を対象期とする予測
        - Q4発表（10月）: 12月を対象期とする予測

        例: 12ヶ月先予測で2026-09 → 2025年9月が起点 → 2025-Q4（10月発表）

        Args:
            target_date: 予測対象期（例: "2026-09" or "2025-Q4"）
            data_key: データキー（"core_12m", "core_24m", "core_lt"）

        Returns:
            発表期（四半期形式: "2025-Q4"）
        """
        try:
            if data_key == "core_lt":
                # 長期予測は既に四半期形式（発表期）
                return target_date

            # 月次形式（2026-09）から発表期を計算
            year, month = map(int, target_date.split('-'))

            if data_key == "core_12m":
                # 1年先予測: 予測対象期 - 9ヶ月 = 発表期
                # 例: 2026-09 → 2025-12 → 2025-Q4
                months_back = 9
            elif data_key == "core_24m":
                # 2年先予測: 予測対象期 - 21ヶ月 = 発表期
                # 例: 2027-09 → 2025-12 → 2025-Q4
                months_back = 21
            else:
                return target_date

            # 月を減算して発表月を計算
            total_months = year * 12 + month - 1 - months_back
            survey_year = total_months // 12
            survey_month = total_months % 12 + 1

            # 月から四半期を決定
            # 3月 → Q1, 6月 → Q2, 9月 → Q3, 12月 → Q4
            quarter = (survey_month - 1) // 3 + 1
            return f"{survey_year}-Q{quarter}"

        except Exception as e:
            print(f"[ECBSPF_CORE] Error converting date {target_date}: {e}")
            return target_date

    def _get_next_release_from_ecb(self) -> Optional[str]:
        """ECBサイトから次回発表日を取得"""
        try:
            response = requests.get(self.NEXT_RELEASE_URL, timeout=15)
            response.raise_for_status()

            html = response.text

            # "The next release will be published on X" パターンを検索
            # 例: "The next release will be published on 6 February 2026"
            pattern = r"next release.*?(\d{1,2}\s+\w+\s+\d{4})"
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)

            if match:
                date_str = match.group(1)
                # 日付をパース
                try:
                    parsed_date = datetime.strptime(date_str, "%d %B %Y")
                    # CET 18:00で設定
                    release_datetime = parsed_date.replace(hour=18, minute=0, tzinfo=CET)
                    return release_datetime.isoformat()
                except ValueError:
                    print(f"[ECBSPF_CORE] Could not parse date: {date_str}")

            print("[ECBSPF_CORE] Could not find next release date on ECB website")
            return self._calculate_next_release()

        except Exception as e:
            print(f"[ECBSPF_CORE] Error fetching next release from ECB: {e}")
            return self._calculate_next_release()

    def _calculate_next_release(self) -> Optional[str]:
        """次回発表日を計算（フォールバック）"""
        try:
            now = datetime.now(CET)

            # SPFは1月、4月、7月、10月に発表
            release_months = [1, 4, 7, 10]

            # 次の発表月を見つける
            current_month = now.month
            current_year = now.year

            for month in release_months:
                if month > current_month:
                    # 今年の発表月
                    release_date = datetime(current_year, month, 1, 18, 0, tzinfo=CET)
                    # 発表日は通常月初から10日以内
                    release_date = release_date.replace(day=7)
                    return release_date.isoformat()

            # 来年の1月
            release_date = datetime(current_year + 1, 1, 7, 18, 0, tzinfo=CET)
            return release_date.isoformat()

        except Exception as e:
            print(f"[ECBSPF_CORE] Error calculating next release: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 次回発表日を取得
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            next_release_str = cached_data.get("next_release") if cached_data else None

            if next_release_str:
                try:
                    next_release = datetime.fromisoformat(next_release_str)
                    if next_release.tzinfo is None:
                        next_release = next_release.replace(tzinfo=CET)

                    # 発表日を過ぎている場合、5日間は毎日チェック
                    if now > next_release:
                        days_since_release = (now - next_release).days
                        if days_since_release <= 5:
                            # 1日1回チェック（最終更新から24時間経過）
                            if (now - last_updated).total_seconds() > 86400:
                                print(f"[ECBSPF_CORE] Past release date, checking for new data")
                                return True
                        return False

                except ValueError:
                    pass

            # 発表月（1,4,7,10）の場合、1日1回チェック
            if now.month in [1, 4, 7, 10]:
                if (now - last_updated).total_seconds() > 86400:
                    print("[ECBSPF_CORE] Release month, daily check")
                    return True

            return False

        except Exception as e:
            print(f"[ECBSPF_CORE] Error in should_refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ECBSPF_CORE] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ECBSPF_CORE] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        inflation_expectations = cached_data.get("inflation_expectations", {}) if cached_data else {}

        return {
            "indicator": "ECB SPF Core",
            "source": "ECB Data API",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": {
                "core_12m": len(inflation_expectations.get("core_12m", [])),
                "core_24m": len(inflation_expectations.get("core_24m", [])),
                "core_lt": len(inflation_expectations.get("core_lt", [])),
            } if cached_data else {},
            "next_release": cached_data.get("next_release") if cached_data else self._get_next_release_from_ecb(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ecb_spf_core_service = ECBSPFCoreService()
