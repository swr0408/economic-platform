"""
UK貿易収支サービス
Office for National Statistics (ONS) MRET DatasetからUK Trade Balanceデータを取得

指標:
- IKBJ: Total Trade (TT): WW: Balance: BOP: CP: SA（総合貿易収支、季節調整済み）

データソース:
- ONS Time Series Data (JSON API)
- https://www.ons.gov.uk/economy/nationalaccounts/balanceofpayments/timeseries/ikbj/mret

単位: £ millions（APIレスポンス）→ £ billions（表示用）

発表スケジュール:
- 月次
- ONS nextRelease フィールドから次回発表日を取得
- FMPカレンダーで "Trade Balance" パターンも参照

キャッシュ方式: Redis + ファイルキャッシュ（FMP発表日時ベース更新）
"""
import json
import requests
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client

JST = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "uk_trade_balance_cache.json"

# 月略称→月番号マッピング
MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4,
    "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8,
    "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

# nextRelease用 フル月名→月番号
MONTH_FULL_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


class UKTradeBalanceService:
    """UK貿易収支サービス"""

    DATA_CACHE_KEY = "uk:uk_trade_balance:data"

    # ONS JSON API - IKBJ series (Total Trade Balance, BOP, CP, SA)
    ONS_JSON_URL = "https://www.ons.gov.uk/economy/nationalaccounts/balanceofpayments/timeseries/ikbj/mret/data"

    # FMPカレンダー検索パターン
    FMP_EVENT_PATTERNS = ["Trade Balance"]

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """UK貿易収支データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "mom_change": cached_data.get("mom_change", []),
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
                        "mom_change": file_cache.get("mom_change", []),
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

            from services.usa.fmp_next_release_utils import guarded_last_updated_keys, _max_date_of
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated_keys(
                self.DATA_CACHE_KEY, ("data",),
                _max_date_of(api_result.get("data", [])), now_str
            )
            cache_payload = {
                "data": api_result.get("data", []),
                "mom_change": api_result.get("mom_change", []),
                "latest": api_result.get("latest"),
                "metadata": api_result.get("metadata", {}),
                "ons_next_release": api_result.get("ons_next_release"),
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": api_result.get("data", []),
                "mom_change": api_result.get("mom_change", []),
                "latest": api_result.get("latest"),
                "metadata": api_result.get("metadata", {}),
                "next_release": next_release_info,
                "cached": False,
                "source": "ons_api",
                "last_updated": last_updated,
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "mom_change": file_cache.get("mom_change", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": self._get_next_release(file_cache.get("ons_next_release")),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "mom_change": [],
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
            print(f"[UK Trade Balance] Error getting FMP next release: {e}")

        # ONS nextRelease フォールバック（例: "13 March 2026"）
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
                            "label": f"UK Trade ({release_date.strftime('%b')})",
                        }
            except Exception as e:
                print(f"[UK Trade Balance] Error parsing ONS next release '{ons_next_release}': {e}")

        return None

    def _fetch_from_ons(self) -> Optional[Dict[str, Any]]:
        """ONS JSON APIからデータを取得"""
        try:
            print(f"[UK Trade Balance] Fetching from {self.ONS_JSON_URL}")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(self.ONS_JSON_URL, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()
            print(f"[UK Trade Balance] Received JSON data")

            return self._process_json_data(data)

        except requests.exceptions.RequestException as e:
            print(f"[UK Trade Balance] Request error: {e}")
            return None
        except Exception as e:
            print(f"[UK Trade Balance] Error fetching from ONS: {e}")
            return None

    def _process_json_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """ONS JSONレスポンスを処理"""
        try:
            description = data.get("description", {})
            months = data.get("months", [])

            if not months:
                print("[UK Trade Balance] No monthly data found")
                return None

            # 月次データを処理
            monthly_data = []
            for item in months:
                value_str = item.get("value", "")
                if not value_str:
                    continue
                try:
                    date_label = item.get("date", "")  # "2025 DEC"
                    year_str = item.get("year", "")
                    month_name = item.get("month", "")  # "December"

                    # 日付文字列から月番号を取得
                    parts = date_label.split()
                    if len(parts) != 2:
                        continue
                    year = int(parts[0])
                    month_abbr = parts[1].upper()
                    month_num = MONTH_MAP.get(month_abbr)
                    if not month_num:
                        continue

                    date_str = f"{year}-{month_num:02d}-01"
                    value_millions = float(value_str)
                    value_billions = round(value_millions / 1000, 2)

                    monthly_data.append({
                        "date": date_str,
                        "value": value_billions,
                        "value_millions": value_millions,
                    })
                except (ValueError, IndexError):
                    continue

            # 日付でソート
            monthly_data.sort(key=lambda x: x["date"])

            if not monthly_data:
                print("[UK Trade Balance] No valid data points")
                return None

            # MoM変化幅（前月との差分 = 前月増減幅、£ billions）
            mom_change_data = []
            for i in range(1, len(monthly_data)):
                current = monthly_data[i]
                prev = monthly_data[i - 1]
                change = round(current["value"] - prev["value"], 2)
                mom_change_data.append({
                    "date": current["date"],
                    "value": change,
                })

            latest = monthly_data[-1] if monthly_data else None

            # メタデータ
            metadata = {
                "title": description.get("title", "UK Trade Balance"),
                "cdid": description.get("cdid", "IKBJ"),
                "unit": "£ billions",
                "unit_raw": description.get("unit", "m"),
                "source": "Office for National Statistics",
                "release_date": description.get("releaseDate", ""),
                "description": "Total Trade Balance (Goods + Services), BOP, Current Prices, SA",
            }

            ons_next_release = description.get("nextRelease", "")

            print(f"[UK Trade Balance] Processed {len(monthly_data)} monthly data points, latest: {latest}")

            return {
                "data": monthly_data,
                "mom_change": mom_change_data,
                "latest": latest,
                "metadata": metadata,
                "ons_next_release": ons_next_release,
            }

        except Exception as e:
            print(f"[UK Trade Balance] Error processing JSON: {e}")
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
                        print(f"[UK Trade Balance] FMP pattern '{pattern}' indicates refresh needed")
                        return True
            except Exception as e:
                print(f"[UK Trade Balance] Error checking FMP refresh: {e}")

            return False

        except Exception as e:
            print(f"[UK Trade Balance] Error in should_refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[UK Trade Balance] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[UK Trade Balance] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "UK Trade Balance",
            "source": "Office for National Statistics (MRET)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
uk_trade_balance_service = UKTradeBalanceService()
