"""
カナダCORRA（Canadian Overnight Repo Rate Average）サービス

指標:
- CORRA（カナダ翌日物レポ平均金利）

データソース:
- Bank of Canada Valet API
- https://www.bankofcanada.ca/valet/observations/group/CORRA/json

発表スケジュール:
- 日次（営業日）

キャッシュ方式:
- 日次更新
"""
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
TORONTO = ZoneInfo("America/Toronto")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "canada" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ca_corra_cache.json"


class CaCorraService:
    """カナダCORRAサービス"""

    DATA_CACHE_KEY = "canada:ca_corra:data"

    # BOC Valet API - CORRA Group
    # AVG.INTWO: CORRA平均レート
    VALET_URL = "https://www.bankofcanada.ca/valet/observations/group/CORRA/json"

    def __init__(self):
        pass

    def get_ca_corra_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダCORRAデータを取得"""
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
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # データソースから取得
        result = self._load_from_source()
        if result:
            # 最新値を取得
            latest = result[-1] if result else None

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Bank of Canada",
                    "indicator": "CORRA",
                    "description": "Canadian Overnight Repo Rate Average（カナダ翌日物レポ平均金利）",
                    "unit": "%",
                    "series_id": "AVG.INTWO",
                },
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
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
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_source(self) -> List[Dict[str, Any]]:
        """BOC Valet APIからデータを取得"""
        try:
            # 2017年から現在までのデータを取得
            today = date.today()
            start_date = "2017-01-01"
            end_date = today.strftime("%Y-%m-%d")

            url = f"{self.VALET_URL}?start_date={start_date}&end_date={end_date}"
            print(f"[CaCorra] Fetching data from: {url}")

            resp = requests.get(url, timeout=30)
            resp.raise_for_status()

            data = resp.json()
            observations = data.get("observations", [])

            result = []

            for obs in observations:
                date_str = obs.get("d")
                # CORRA平均レートを取得（AVG.INTWO）
                value_obj = obs.get("AVG.INTWO", {})
                value_str = value_obj.get("v")

                if not date_str or not value_str:
                    continue

                try:
                    value = float(value_str)
                    result.append({
                        "date": date_str,
                        "value": value,
                    })
                except (ValueError, TypeError):
                    continue

            # 日付でソート
            result.sort(key=lambda x: x["date"])

            print(f"[CaCorra] Loaded {len(result)} daily records")
            if result:
                print(f"[CaCorra] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CaCorra] Latest: {latest['date']} = {latest['value']}%")

            return result

        except Exception as e:
            print(f"[CaCorra] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（ET 11:30更新）"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            now_toronto = datetime.now(TORONTO)
            now_jst = datetime.now(JST)

            # ET 11:30 = JST 01:30（夏時間）/ 00:30（冬時間）
            # トロント時間で11:30を過ぎていて、最終更新がその前なら更新
            today_release_time = now_toronto.replace(hour=11, minute=30, second=0, microsecond=0)

            # 最終更新をトロント時間に変換
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)
            last_updated_toronto = last_updated.astimezone(TORONTO)

            # 今日のET 11:30を過ぎていて、最終更新がそれより前なら更新
            if now_toronto >= today_release_time and last_updated_toronto < today_release_time:
                return True

            # 日付が変わっていれば更新（フォールバック）
            if last_updated_toronto.date() < now_toronto.date():
                return True

            return False
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
            print(f"[CaCorra] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaCorra] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "CORRA",
            "source": "Bank of Canada",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ca_corra_service = CaCorraService()
