"""
カナダ家計債務返済比率（DSR）サービス

指標:
- 家計債務返済比率（Total DSR）
- 住宅ローンDSR（Mortgage DSR）
- 非住宅ローンDSR（Non-mortgage DSR）

データソース:
- Statistics Canada Table 11-10-0065-01
- Debt service indicators of households, national balance sheet accounts
- WDS API (vectorId: 1001696813 = Total DSR, SA)

発表スケジュール:
- 四半期（対象四半期の約2.5ヶ月後）
- 発表時刻: 08:30 ET
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

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "canada" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ca_debt_service_ratio_cache.json"

# Statistics Canada WDS API
STATCAN_WDS_BASE = "https://www150.statcan.gc.ca/t1/wds/rest"

# Vector IDs (Seasonally adjusted at annual rates)
# Table 11-10-0065-01
VECTOR_TOTAL_DSR = 1001696813       # Debt service ratio (total)
VECTOR_MORTGAGE_DSR = 1001696814    # Mortgage debt service ratio
VECTOR_NON_MORTGAGE_DSR = 1001696815  # Non-mortgage debt service ratio

DSR_PRODUCT_ID = 11100065


class CaDebtServiceRatioService:
    """カナダ家計債務返済比率サービス"""

    DATA_CACHE_KEY = "canada:ca_debt_service_ratio:data"
    CACHE_TTL = 86400 * 7  # 7日間（四半期データのため長め）

    def __init__(self):
        pass

    def get_ca_debt_service_ratio_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダ家計DSRデータを取得"""
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
                    "source": "Statistics Canada",
                    "table": "11-10-0065-01",
                    "indicator": "Debt Service Ratio",
                    "description": "カナダ家計債務返済比率",
                    "unit": "%",
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
        """Statistics Canada WDS APIからDSRデータを取得"""
        try:
            print(f"[CaDSR] Fetching data from WDS API (3 vectors)")

            # 3つの系列を一括取得
            payload = [
                {"vectorId": VECTOR_TOTAL_DSR, "latestN": 200},
                {"vectorId": VECTOR_MORTGAGE_DSR, "latestN": 200},
                {"vectorId": VECTOR_NON_MORTGAGE_DSR, "latestN": 200},
            ]
            resp = requests.post(
                f"{STATCAN_WDS_BASE}/getDataFromVectorsAndLatestNPeriods",
                json=payload,
                timeout=30
            )
            resp.raise_for_status()

            data = resp.json()
            if not data or len(data) < 3:
                print("[CaDSR] Incomplete response from WDS API")
                return []

            # 各系列のデータを辞書に変換
            total_map: Dict[str, float] = {}
            mortgage_map: Dict[str, float] = {}
            non_mortgage_map: Dict[str, float] = {}

            for i, (series_data, target_map) in enumerate(
                zip(data, [total_map, mortgage_map, non_mortgage_map])
            ):
                if series_data.get("status") != "SUCCESS":
                    print(f"[CaDSR] WDS API error for series {i}: {series_data.get('object')}")
                    continue

                obj = series_data.get("object", {})
                data_points = obj.get("vectorDataPoint", [])

                for point in data_points:
                    ref_per = point.get("refPer")  # 形式: "2024-01-01"
                    value = point.get("value")

                    if ref_per and value is not None:
                        target_map[ref_per] = float(value)

            print(f"[CaDSR] Extracted: total={len(total_map)}, mortgage={len(mortgage_map)}, non_mortgage={len(non_mortgage_map)}")

            # マージして結果を構築
            all_dates = sorted(set(total_map.keys()))
            result = []

            for date_str in all_dates:
                total = total_map.get(date_str)
                if total is None:
                    continue

                item: Dict[str, Any] = {
                    "date": date_str,
                    "value": round(total, 2),
                    "mortgage": round(mortgage_map[date_str], 2) if date_str in mortgage_map else None,
                    "non_mortgage": round(non_mortgage_map[date_str], 2) if date_str in non_mortgage_map else None,
                }

                result.append(item)

            print(f"[CaDSR] Loaded {len(result)} quarterly records")
            if result:
                print(f"[CaDSR] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CaDSR] Latest: {latest['date']} total={latest.get('value')}% mortgage={latest.get('mortgage')}% non_mortgage={latest.get('non_mortgage')}%")

            return result

        except Exception as e:
            print(f"[CaDSR] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得（FMPマッピングなしのため簡易実装）"""
        cache_key = "canada:ca_debt_service_ratio:next_release"
        cached = redis_client.get(cache_key)
        if cached:
            return cached
        return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)
            now = datetime.now(JST)
            age = now - last_updated
            # 四半期データのため7日間キャッシュ有効
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
            print(f"[CaDSR] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaDSR] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Canada Debt Service Ratio",
            "source": "Statistics Canada",
            "table": "11-10-0065-01",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ca_debt_service_ratio_service = CaDebtServiceRatioService()
