"""
カナダ求人率（Job Vacancy Rate）サービス

指標:
- Job vacancy rate (%) — カナダ全体、季節調整済

データソース:
- Statistics Canada WDS API
- Table 14-10-0432-01 (pid=14100432)
- Vector: v1481212147 (Canada, Job vacancy rate, SA)

発表スケジュール:
- 毎月（Labour Force Survey発表後）
- 発表時刻: 08:30 ET

値の解釈:
- 求人率 = 求人件数 / (求人件数 + 賃金労働者数) × 100
- 上昇 = 労働市場タイト化、下落 = 労働市場緩和
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

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "canada" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ca_job_vacancy_rate_cache.json"

# Statistics Canada WDS API
WDS_BASE = "https://www150.statcan.gc.ca/t1/wds/rest"

# Vector ID: Canada, Job vacancy rate (%), SA
# Table 14-10-0432-01, coordinate 1.3.0.0.0.0.0.0.0.0
JOB_VACANCY_RATE_VECTOR_ID = 1481212147


class CaJobVacancyRateService:
    """カナダ求人率サービス"""

    DATA_CACHE_KEY = "canada:ca_job_vacancy_rate:data"
    CACHE_TTL = 86400  # 24時間

    def __init__(self):
        pass

    def get_ca_job_vacancy_rate_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダ求人率データを取得"""
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
                    "table": "14-10-0432-01",
                    "indicator": "Job Vacancy Rate",
                    "description": "カナダ求人率（季節調整済）",
                    "unit": "%",
                    "frequency": "monthly",
                    "seasonal_adjustment": "seasonally adjusted",
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
        """StatCan WDS APIから求人率データを取得"""
        try:
            url = f"{WDS_BASE}/getDataFromVectorsAndLatestNPeriods"
            payload = [{"vectorId": JOB_VACANCY_RATE_VECTOR_ID, "latestN": 200}]

            print(f"[CaJobVacancyRate] Fetching data from WDS API (vector {JOB_VACANCY_RATE_VECTOR_ID})")
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()

            data = resp.json()

            if not data or len(data) == 0:
                print("[CaJobVacancyRate] No data returned from API")
                return []

            item = data[0]
            status = item.get("status")
            if status != "SUCCESS":
                print(f"[CaJobVacancyRate] API returned status: {status}")
                return []

            obj = item.get("object", {})
            data_points = obj.get("vectorDataPoint", [])

            result = []
            for dp in data_points:
                ref_per = dp.get("refPer")
                value = dp.get("value")
                if ref_per and value is not None:
                    result.append({
                        "date": ref_per,
                        "value": round(float(value), 1),
                    })

            result.sort(key=lambda x: x["date"])

            print(f"[CaJobVacancyRate] Loaded {len(result)} monthly records")
            if result:
                print(f"[CaJobVacancyRate] Date range: {result[0]['date']} to {result[-1]['date']}")
                print(f"[CaJobVacancyRate] Latest: {result[-1]['date']} = {result[-1]['value']}%")

            return result

        except Exception as e:
            print(f"[CaJobVacancyRate] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得（WDS APIのreleaseTime情報から推定）"""
        # FMPマッピングなし。Job vacancy rateはLabour Force Surveyと同時発表ではなく
        # 独自スケジュール（月末付近）で発表される。
        # ここでは簡易的にNoneを返す
        return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)
            now = datetime.now(JST)
            age = now - last_updated
            return age.total_seconds() > 86400
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
            print(f"[CaJobVacancyRate] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaJobVacancyRate] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Canada Job Vacancy Rate",
            "source": "Statistics Canada",
            "table": "14-10-0432-01",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": cached_data.get("next_release") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ca_job_vacancy_rate_service = CaJobVacancyRateService()
