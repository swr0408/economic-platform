"""
UK経常収支サービス
Office for National Statistics (ONS) PNBP DatasetからUK Current Accountデータを取得

指標:
- HBOP: BoP Current Account Balance SA £m（経常収支、季節調整済み）
- AA6H: BoP Current Account Balance as % of GDP SA（経常収支対GDP比）

データソース:
- ONS Time Series Data (JSON API)
- https://www.ons.gov.uk/economy/nationalaccounts/balanceofpayments/timeseries/hbop/pnbp
- https://www.ons.gov.uk/economy/nationalaccounts/balanceofpayments/timeseries/aa6h/pnbp

単位:
- HBOP: £ millions（APIレスポンス）→ £ billions（表示用）
- AA6H: % of GDP

発表スケジュール:
- 四半期
- ONS nextRelease フィールドから次回発表日を取得
- FMPカレンダーで "Current Account" パターンも参照

キャッシュ方式: Redis + ファイルキャッシュ（FMP発表日時ベース更新）
"""
import json
import requests
from datetime import datetime
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client

JST = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "uk_current_account_cache.json"

# 四半期→月マッピング（四半期末の月を使用）
QUARTER_MONTH_MAP = {
    "Q1": 3, "Q2": 6, "Q3": 9, "Q4": 12,
}

# nextRelease用 フル月名→月番号
MONTH_FULL_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


class UKCurrentAccountService:
    """UK経常収支サービス"""

    DATA_CACHE_KEY = "uk:uk_current_account:data"

    # ONS JSON API - HBOP series (Current Account Balance, BOP, CP, SA)
    ONS_HBOP_URL = "https://www.ons.gov.uk/economy/nationalaccounts/balanceofpayments/timeseries/hbop/pnbp/data"
    # ONS JSON API - AA6H series (Current Account Balance as % of GDP, SA)
    ONS_AA6H_URL = "https://www.ons.gov.uk/economy/nationalaccounts/balanceofpayments/timeseries/aa6h/pnbp/data"

    # FMPカレンダー検索パターン
    FMP_EVENT_PATTERNS = ["Current Account"]

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """UK経常収支データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "qoq_change": cached_data.get("qoq_change", []),
                        "gdp_ratio": cached_data.get("gdp_ratio", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": self._get_next_release(cached_data.get("ons_next_release")),
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
                        "qoq_change": file_cache.get("qoq_change", []),
                        "gdp_ratio": file_cache.get("gdp_ratio", []),
                        "latest": file_cache.get("latest"),
                        "metadata": file_cache.get("metadata", {}),
                        "next_release": self._get_next_release(file_cache.get("ons_next_release")),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str,
                    }

        # ONSからデータを取得
        api_result = self._fetch_from_ons()

        if api_result:
            next_release_info = self._get_next_release(api_result.get("ons_next_release"))

            cache_payload = {
                "data": api_result.get("data", []),
                "qoq_change": api_result.get("qoq_change", []),
                "gdp_ratio": api_result.get("gdp_ratio", []),
                "latest": api_result.get("latest"),
                "metadata": api_result.get("metadata", {}),
                "ons_next_release": api_result.get("ons_next_release"),
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": api_result.get("data", []),
                "qoq_change": api_result.get("qoq_change", []),
                "gdp_ratio": api_result.get("gdp_ratio", []),
                "latest": api_result.get("latest"),
                "metadata": api_result.get("metadata", {}),
                "next_release": next_release_info,
                "cached": False,
                "source": "ons_api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "qoq_change": file_cache.get("qoq_change", []),
                "gdp_ratio": file_cache.get("gdp_ratio", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": self._get_next_release(file_cache.get("ons_next_release")),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "qoq_change": [],
            "gdp_ratio": [],
            "latest": None,
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _get_next_release(self, ons_next_release: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """次回発表日を取得（FMP優先、ONSフォールバック）"""
        # FMPカレンダーから検索
        try:
            from services.uk.fmp_next_release_utils import get_next_release_by_pattern
            for pattern in self.FMP_EVENT_PATTERNS:
                result = get_next_release_by_pattern(pattern, country="GB")
                if result:
                    return result
        except Exception as e:
            print(f"[UK Current Account] Error getting FMP next release: {e}")

        # ONS nextRelease フォールバック（例: "31 March 2026"）
        if ons_next_release:
            try:
                parts = ons_next_release.strip().split()
                if len(parts) == 3:
                    day = int(parts[0])
                    month = MONTH_FULL_MAP.get(parts[1].lower())
                    year = int(parts[2])
                    if month:
                        release_date = datetime(year, month, day, 7, 0, tzinfo=LONDON)
                        release_jst = release_date.astimezone(JST)
                        return {
                            "date": release_date.strftime("%Y-%m-%d"),
                            "datetime_jst": release_jst.isoformat(),
                            "time_jst": release_jst.strftime("%H:%M"),
                            "label": f"UK Current Account ({release_date.strftime('%b')})",
                        }
            except Exception as e:
                print(f"[UK Current Account] Error parsing ONS next release '{ons_next_release}': {e}")

        return None

    def _fetch_from_ons(self) -> Optional[Dict[str, Any]]:
        """ONS JSON APIからHBOP（£m）とAA6H（% of GDP）を取得"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        # HBOP（経常収支 £m）を取得
        hbop_data = None
        try:
            print(f"[UK Current Account] Fetching HBOP from {self.ONS_HBOP_URL}")
            response = requests.get(self.ONS_HBOP_URL, headers=headers, timeout=30)
            response.raise_for_status()
            hbop_data = response.json()
            print(f"[UK Current Account] Received HBOP JSON data")
        except Exception as e:
            print(f"[UK Current Account] Error fetching HBOP: {e}")
            return None

        # AA6H（経常収支対GDP比 %）を取得
        aa6h_data = None
        try:
            print(f"[UK Current Account] Fetching AA6H from {self.ONS_AA6H_URL}")
            response = requests.get(self.ONS_AA6H_URL, headers=headers, timeout=30)
            response.raise_for_status()
            aa6h_data = response.json()
            print(f"[UK Current Account] Received AA6H JSON data")
        except Exception as e:
            print(f"[UK Current Account] Warning: Failed to fetch AA6H (% of GDP): {e}")

        return self._process_json_data(hbop_data, aa6h_data)

    def _process_json_data(self, hbop_data: Dict[str, Any], aa6h_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """ONS JSONレスポンスを処理（HBOP + AA6H）"""
        try:
            description = hbop_data.get("description", {})
            quarters = hbop_data.get("quarters", [])

            if not quarters:
                print("[UK Current Account] No quarterly data found")
                return None

            # 四半期データを処理（HBOP: £ millions → £ billions）
            quarterly_data = []
            for item in quarters:
                value_str = item.get("value", "")
                if not value_str:
                    continue
                try:
                    date_label = item.get("date", "")  # "2025 Q3"

                    # 日付文字列からパース
                    parts = date_label.split()
                    if len(parts) != 2:
                        continue
                    year = int(parts[0])
                    quarter = parts[1].upper()
                    month_num = QUARTER_MONTH_MAP.get(quarter)
                    if not month_num:
                        continue

                    date_str = f"{year}-{month_num:02d}-01"
                    value_millions = float(value_str)
                    value_billions = round(value_millions / 1000, 2)

                    quarterly_data.append({
                        "date": date_str,
                        "value": value_billions,
                        "value_millions": value_millions,
                    })
                except (ValueError, IndexError):
                    continue

            # 日付でソート
            quarterly_data.sort(key=lambda x: x["date"])

            if not quarterly_data:
                print("[UK Current Account] No valid data points")
                return None

            # QoQ変化幅（前四半期との差分 = 前期増減幅、£ billions）
            qoq_change_data = []
            for i in range(1, len(quarterly_data)):
                current = quarterly_data[i]
                prev = quarterly_data[i - 1]
                change = round(current["value"] - prev["value"], 2)
                qoq_change_data.append({
                    "date": current["date"],
                    "value": change,
                })

            # AA6H（経常収支対GDP比 %）を処理
            gdp_ratio_data = []
            if aa6h_data:
                aa6h_quarters = aa6h_data.get("quarters", [])
                for item in aa6h_quarters:
                    value_str = item.get("value", "")
                    if not value_str:
                        continue
                    try:
                        date_label = item.get("date", "")
                        parts = date_label.split()
                        if len(parts) != 2:
                            continue
                        year = int(parts[0])
                        quarter = parts[1].upper()
                        month_num = QUARTER_MONTH_MAP.get(quarter)
                        if not month_num:
                            continue

                        date_str = f"{year}-{month_num:02d}-01"
                        value = round(float(value_str), 2)
                        gdp_ratio_data.append({
                            "date": date_str,
                            "value": value,
                        })
                    except (ValueError, IndexError):
                        continue

                gdp_ratio_data.sort(key=lambda x: x["date"])
                print(f"[UK Current Account] Processed {len(gdp_ratio_data)} GDP ratio data points")

            latest = quarterly_data[-1] if quarterly_data else None

            # メタデータ
            metadata = {
                "title": description.get("title", "UK Current Account Balance"),
                "cdid": description.get("cdid", "HBOP"),
                "unit": "£ billions",
                "unit_raw": description.get("unit", "m"),
                "source": "Office for National Statistics",
                "release_date": description.get("releaseDate", ""),
                "description": "Current Account Balance, BOP, Current Prices, SA",
            }

            ons_next_release = description.get("nextRelease", "")

            print(f"[UK Current Account] Processed {len(quarterly_data)} quarterly data points, latest: {latest}")

            return {
                "data": quarterly_data,
                "qoq_change": qoq_change_data,
                "gdp_ratio": gdp_ratio_data,
                "latest": latest,
                "metadata": metadata,
                "ons_next_release": ons_next_release,
            }

        except Exception as e:
            print(f"[UK Current Account] Error processing JSON: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            hours_since_update = (now - last_updated).total_seconds() / 3600

            # 7日以上経過していれば更新
            if hours_since_update >= 24 * 7:
                return True

            # FMPパターンベースの更新判定
            try:
                from services.uk.fmp_next_release_utils import should_refresh_by_pattern
                for pattern in self.FMP_EVENT_PATTERNS:
                    if should_refresh_by_pattern(pattern, last_updated_str, country="GB"):
                        print(f"[UK Current Account] FMP pattern '{pattern}' indicates refresh needed")
                        return True
            except Exception as e:
                print(f"[UK Current Account] Error checking FMP refresh: {e}")

            return False

        except Exception as e:
            print(f"[UK Current Account] Error in should_refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[UK Current Account] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[UK Current Account] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "UK Current Account",
            "source": "Office for National Statistics (PNBP)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
uk_current_account_service = UKCurrentAccountService()
