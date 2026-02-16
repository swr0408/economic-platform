"""
ON RRP (Overnight Reverse Repo) 残高データサービス
NY Fed Markets API から RRP オペ結果を取得
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests

from core.redis_client import redis_client, CACHE_TTL_DAY


class ONRRPService:
    """ON RRP (Overnight Reverse Repo) データサービス（日次データ）"""

    CACHE_KEY = "usa:on_rrp:data"
    CACHE_TTL = CACHE_TTL_DAY  # 24時間
    CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "monetary_policy"
    FILE_CACHE_PATH = CACHE_DIR / "on_rrp_cache.json"

    # NY Fed Markets API エンドポイント
    ON_RRP_URL = "https://markets.newyorkfed.org/api/rp/reverserepo/propositions/search.json"

    def __init__(self):
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def get_on_rrp_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        ON RRP 残高データを取得

        Returns:
            {
                "data": [
                    {
                        "date": "2024-01-31",
                        "value": 500.5,  # 十億ドル単位
                        "value_raw": 500500000000,  # 原値（ドル）
                    },
                    ...
                ],
                "latest": {...},
                "metadata": {...},
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # 1. Redis キャッシュをチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CACHE_KEY)
            if cached_data:
                return {
                    "data": cached_data.get("data", []),
                    "latest": cached_data.get("latest"),
                    "metadata": cached_data.get("metadata", {}),
                    "cached": True,
                    "source": "redis",
                    "last_updated": cached_data.get("last_updated")
                }

        # 2. 外部 API からデータを取得
        api_data = self._fetch_from_api()

        if api_data and api_data.get("data"):
            # Redis にキャッシュ
            cache_payload = {
                "data": api_data["data"],
                "latest": api_data["latest"],
                "metadata": api_data["metadata"],
                "last_updated": datetime.now().isoformat()
            }
            redis_client.set(self.CACHE_KEY, cache_payload, expire=self.CACHE_TTL)

            # ファイルキャッシュにも保存
            self._save_file_cache(cache_payload)

            return {
                "data": api_data["data"],
                "latest": api_data["latest"],
                "metadata": api_data["metadata"],
                "cached": False,
                "source": "api",
                "last_updated": datetime.now().isoformat()
            }

        # 3. フォールバック: ファイルキャッシュ
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "cached": True,
                "source": "file_cache",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_api(self) -> Optional[Dict[str, Any]]:
        """NY Fed Markets API から ON RRP データを取得"""
        try:
            print("Fetching ON RRP data from NY Fed Markets API...")

            # 過去3年分のデータを取得
            end_date = datetime.now()
            start_date = end_date - timedelta(days=1095)

            params = {
                "startDate": start_date.strftime("%Y-%m-%d"),
                "endDate": end_date.strftime("%Y-%m-%d")
            }

            response = requests.get(self.ON_RRP_URL, params=params, timeout=60)
            response.raise_for_status()

            data = response.json()
            repo_data = data.get("repo", {})
            operations = repo_data.get("operations", [])

            if not operations:
                print("No ON RRP operations data returned from API")
                return None

            # 日付ごとにデータを集計（同日複数オペがある場合）
            daily_totals: Dict[str, float] = {}

            for op in operations:
                op_date = op.get("operationDate")
                total_amt = op.get("totalAmtAccepted")

                if op_date and total_amt is not None:
                    # ドル単位の値
                    amt_value = float(total_amt)
                    if op_date in daily_totals:
                        daily_totals[op_date] += amt_value
                    else:
                        daily_totals[op_date] = amt_value

            # 結果を構築
            result = []
            for date_str, value_raw in sorted(daily_totals.items()):
                # 十億ドル単位に変換
                value_billions = value_raw / 1_000_000_000

                data_point = {
                    "date": date_str,
                    "value": round(value_billions, 2),
                    "value_raw": value_raw,
                }
                result.append(data_point)

            # 最新値
            latest = result[-1] if result else None

            metadata = {
                "source": "NY Fed Markets API",
                "unit": "billions USD",
                "description": "ON RRP (Overnight Reverse Repo) 残高",
                "operation_time": "12:45-13:15 ET（毎営業日）"
            }

            print(f"Fetched {len(result)} ON RRP records")

            return {
                "data": result,
                "latest": latest,
                "metadata": metadata
            }

        except Exception as e:
            print(f"Error fetching ON RRP data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュに保存"""
        try:
            with open(self.FILE_CACHE_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving file cache: {e}")

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュから読み込み"""
        try:
            if self.FILE_CACHE_PATH.exists():
                with open(self.FILE_CACHE_PATH, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading file cache: {e}")
        return None

    def invalidate_cache(self) -> bool:
        """Redis キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cache_exists = redis_client.exists(self.CACHE_KEY)
        ttl = redis_client.ttl(self.CACHE_KEY) if cache_exists else -1

        return {
            "cache_key": self.CACHE_KEY,
            "exists": cache_exists,
            "ttl_seconds": ttl,
            "ttl_hours": round(ttl / 3600, 2) if ttl > 0 else 0,
            "file_cache_exists": self.FILE_CACHE_PATH.exists()
        }


# シングルトンインスタンス
on_rrp_service = ONRRPService()
