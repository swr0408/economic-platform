"""
カナダ Business Outlook Survey（BOS）サービス

指標:
- Future Sales Growth (Balance of Opinion)
- Investment in M&E (Balance of Opinion)
- Employment Intentions (Balance of Opinion)
- Input Price Inflation (Balance of Opinion)
- Output Price Inflation (Balance of Opinion)

データソース:
- Bank of Canada Valet API
- BOS Group: https://www.bankofcanada.ca/valet/observations/group/BOS/json

発表スケジュール:
- 四半期（1月, 4月, 7月, 10月）
- 発表時刻: 10:30 ET
"""
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
TORONTO = ZoneInfo("America/Toronto")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "canada" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ca_bos_cache.json"

# Bank of Canada Valet API
VALET_BASE = "https://www.bankofcanada.ca/valet"

# Balance of Opinion series codes
BOS_SERIES = {
    "future_sales": "FUTURESALES",
    "investment": "INVESTMACHEQUIP",
    "employment": "EMPLOY",
    "input_prices": "INPUTS",
    "output_prices": "OUTPUTS",
    "credit": "CREDIT",
}

# 2026年のBOS発表日（10:30 ET）
BOS_SCHEDULE_2026 = [
    "2026-01-19",
    "2026-04-20",
    "2026-07-06",
    "2026-10-19",
]


class CaBosService:
    """カナダBOSサービス"""

    DATA_CACHE_KEY = "canada:ca_bos:data"
    CACHE_TTL = 86400 * 7  # 7日間（四半期データのため長め）

    def __init__(self):
        pass

    def get_ca_bos_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダBOSデータを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # データソースから取得
        result = self._load_from_source()
        if result:
            latest = result[-1] if result else None
            next_release = self._get_next_release()

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Bank of Canada",
                    "survey": "Business Outlook Survey (BOS)",
                    "description": "カナダ企業景況感調査（BOS）",
                    "unit": "% (Balance of Opinion)",
                    "frequency": "quarterly",
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=self.CACHE_TTL)
            self._save_file_cache(cache_payload)

            return {
                "data": result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_source(self) -> List[Dict[str, Any]]:
        """BOC Valet APIからBOSデータを取得"""
        try:
            series_codes = ",".join(BOS_SERIES.values())
            url = f"{VALET_BASE}/observations/{series_codes}/json?start_date=1998-01-01"

            print(f"[CaBOS] Fetching data from Valet API: {url}")
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()

            data = resp.json()
            observations = data.get("observations", [])

            if not observations:
                print("[CaBOS] No observations returned from API")
                return []

            # 各観測値をマージ
            result = []
            for obs in observations:
                date_str = obs.get("d")
                if not date_str:
                    continue

                item: Dict[str, Any] = {"date": date_str}

                # Balance of Opinion系列を取得
                for field_name, series_code in BOS_SERIES.items():
                    series_data = obs.get(series_code, {})
                    value_str = series_data.get("v") if isinstance(series_data, dict) else None
                    if value_str is not None and value_str != "":
                        try:
                            item[field_name] = float(value_str)
                        except (ValueError, TypeError):
                            item[field_name] = None
                    else:
                        item[field_name] = None

                # future_salesがある場合のみ追加（メイン系列）
                if item.get("future_sales") is not None:
                    result.append(item)

            result.sort(key=lambda x: x["date"])

            print(f"[CaBOS] Loaded {len(result)} quarterly records")
            if result:
                print(f"[CaBOS] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CaBOS] Latest: {latest['date']} future_sales={latest.get('future_sales')} "
                      f"investment={latest.get('investment')} employment={latest.get('employment')} "
                      f"input_prices={latest.get('input_prices')} output_prices={latest.get('output_prices')}")

            return result

        except Exception as e:
            print(f"[CaBOS] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得（ハードコード + 動的判定）"""
        try:
            now = datetime.now(TORONTO)
            now_date_str = now.strftime("%Y-%m-%d")

            for date_str in BOS_SCHEDULE_2026:
                if date_str > now_date_str:
                    # 10:30 ET
                    release_dt_toronto = datetime.strptime(date_str, "%Y-%m-%d").replace(
                        hour=10, minute=30, tzinfo=TORONTO
                    )
                    release_dt_jst = release_dt_toronto.astimezone(JST)

                    return {
                        "date": date_str,
                        "datetime_jst": release_dt_jst.isoformat(),
                        "time_jst": release_dt_jst.strftime("%H:%M"),
                        "datetime_toronto": release_dt_toronto.isoformat(),
                        "time_toronto": "10:30",
                        "label": "Business Outlook Survey",
                    }

            return None

        except Exception as e:
            print(f"[CaBOS] Error getting next release: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)
            now = datetime.now(JST)
            age = now - last_updated
            return age.total_seconds() > 86400 * 7
        except Exception:
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CaBOS] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaBOS] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Canada Business Outlook Survey (BOS)",
            "source": "Bank of Canada",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": cached_data.get("next_release") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ca_bos_service = CaBosService()
