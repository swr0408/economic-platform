"""
カナダ Senior Loan Officer Survey（SLOS）サービス

指標:
- Overall Business Lending Conditions (Balance of Opinion)
- Overall Mortgage Lending Conditions (Balance of Opinion)
- Overall Non-Mortgage Lending Conditions (Balance of Opinion)

データソース:
- Bank of Canada Valet API
- SLOS Group: https://www.bankofcanada.ca/valet/observations/group/SLOS/json

発表スケジュール:
- 四半期
- 発表時刻: 10:30 ET

値の解釈:
- 正（+）= 貸出基準の厳格化（tightening）
- 負（-）= 貸出基準の緩和（easing）
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
DATA_CACHE_FILE = CACHE_DIR / "ca_slos_cache.json"

# Bank of Canada Valet API
VALET_BASE = "https://www.bankofcanada.ca/valet"

# SLOS series codes（Overall指標のみ使用）
SLOS_SERIES = {
    "business": "SLOS_BUS_LEND",
    "mortgage": "SLOS_ML_LEND",
    "non_mortgage": "SLOS_NML_LEND",
}

# 2026年のSLOS発表日（10:30 ET）
SLOS_SCHEDULE_2026 = [
    "2026-02-20",
    "2026-05-22",
    "2026-08-14",
    "2026-11-06",
]


class CaSlosService:
    """カナダSLOSサービス"""

    DATA_CACHE_KEY = "canada:ca_slos:data"
    CACHE_TTL = 86400 * 7  # 7日間（四半期データのため長め）

    def __init__(self):
        pass

    def get_ca_slos_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダSLOSデータを取得"""
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
                    "survey": "Senior Loan Officer Survey (SLOS)",
                    "description": "カナダ貸出態度調査（SLOS）",
                    "unit": "% (Balance of Opinion)",
                    "frequency": "quarterly",
                    "interpretation": "正(+)=厳格化, 負(-)=緩和",
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
        """BOC Valet APIからSLOSデータを取得"""
        try:
            series_codes = ",".join(SLOS_SERIES.values())
            url = f"{VALET_BASE}/observations/{series_codes}/json?start_date=1999-01-01"

            print(f"[CaSLOS] Fetching data from Valet API: {url}")
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()

            data = resp.json()
            observations = data.get("observations", [])

            if not observations:
                print("[CaSLOS] No observations returned from API")
                return []

            result = []
            for obs in observations:
                date_str = obs.get("d")
                if not date_str:
                    continue

                item: Dict[str, Any] = {"date": date_str}

                for field_name, series_code in SLOS_SERIES.items():
                    series_data = obs.get(series_code, {})
                    value_str = series_data.get("v") if isinstance(series_data, dict) else None
                    if value_str is not None and value_str != "":
                        try:
                            item[field_name] = round(float(value_str), 2)
                        except (ValueError, TypeError):
                            item[field_name] = None
                    else:
                        item[field_name] = None

                # businessがある場合のみ追加（最も長い系列）
                if item.get("business") is not None:
                    result.append(item)

            result.sort(key=lambda x: x["date"])

            print(f"[CaSLOS] Loaded {len(result)} quarterly records")
            if result:
                print(f"[CaSLOS] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CaSLOS] Latest: {latest['date']} "
                      f"business={latest.get('business')} "
                      f"mortgage={latest.get('mortgage')} "
                      f"non_mortgage={latest.get('non_mortgage')}")

            return result

        except Exception as e:
            print(f"[CaSLOS] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得（ハードコード + 動的判定）"""
        try:
            now = datetime.now(TORONTO)
            now_date_str = now.strftime("%Y-%m-%d")

            for date_str in SLOS_SCHEDULE_2026:
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
                        "label": "Senior Loan Officer Survey",
                    }

            return None

        except Exception as e:
            print(f"[CaSLOS] Error getting next release: {e}")
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
            print(f"[CaSLOS] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaSLOS] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Canada Senior Loan Officer Survey (SLOS)",
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
ca_slos_service = CaSlosService()
