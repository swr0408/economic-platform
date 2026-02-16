"""
SOFR ボラティリティ データサービス
NY Fed Markets API から SOFR 履歴を取得し、ローリング標準偏差（ボラティリティ）を計算
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests
import numpy as np

from core.redis_client import redis_client, CACHE_TTL_DAY


class SOFRVolatilityService:
    """SOFR ボラティリティ データサービス（日次データ）"""

    CACHE_KEY = "usa:sofr_volatility:data"
    CACHE_TTL = CACHE_TTL_DAY  # 24時間
    CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "monetary_policy"
    FILE_CACHE_PATH = CACHE_DIR / "sofr_volatility_cache.json"

    # NY Fed Markets API エンドポイント
    SOFR_LAST_URL = "https://markets.newyorkfed.org/api/rates/secured/sofr/last/1.json"
    SOFR_HISTORY_URL = "https://markets.newyorkfed.org/api/rates/secured/sofr/search.json"

    # ローリングウィンドウ（営業日数）
    ROLLING_WINDOW = 20

    def __init__(self):
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def get_sofr_volatility_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        SOFR ボラティリティデータを取得

        Returns:
            {
                "data": [
                    {
                        "date": "2024-01-31",
                        "sofr": 5.31,           # SOFR レート (%)
                        "sofr_change": 0.01,    # 日次変化 (bps)
                        "volatility_20d": 0.05  # 20日ローリング標準偏差 (bps)
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
        api_data = self._fetch_and_calculate_volatility()

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

    def _fetch_and_calculate_volatility(self) -> Optional[Dict[str, Any]]:
        """NY Fed から SOFR 履歴を取得し、ボラティリティを計算"""
        try:
            print("Fetching SOFR data from NY Fed Markets API...")

            # 過去2年分のデータを取得（十分なローリング計算用）
            end_date = datetime.now()
            start_date = end_date - timedelta(days=730)

            params = {
                "startDate": start_date.strftime("%Y-%m-%d"),
                "endDate": end_date.strftime("%Y-%m-%d"),
                "type": "rate"
            }

            response = requests.get(self.SOFR_HISTORY_URL, params=params, timeout=60)
            response.raise_for_status()

            data = response.json()
            ref_rates = data.get("refRates", [])

            if not ref_rates:
                print("No SOFR data returned from API")
                return None

            # 日付順にソート（古い順）
            ref_rates.sort(key=lambda x: x.get("effectiveDate", ""))

            # DataFrameライクな処理（numpyのみ使用）
            dates = []
            sofr_rates = []

            for item in ref_rates:
                date_str = item.get("effectiveDate")
                rate = item.get("percentRate")

                if date_str and rate is not None:
                    dates.append(date_str)
                    sofr_rates.append(float(rate))

            if len(dates) < self.ROLLING_WINDOW + 1:
                print(f"Insufficient data points: {len(dates)}")
                return None

            # numpy 配列に変換
            sofr_array = np.array(sofr_rates)

            # 日次変化（bps = basis points）
            sofr_change = np.diff(sofr_array) * 100  # % to bps

            # 20日ローリング標準偏差
            volatility_20d = self._rolling_std(sofr_change, self.ROLLING_WINDOW)

            # 結果を構築（最初の ROLLING_WINDOW 日は volatility が計算できない）
            result = []
            for i in range(len(dates)):
                if i == 0:
                    # 最初のデータポイント（変化なし）
                    continue

                idx = i - 1  # sofr_change と volatility_20d のインデックス

                data_point = {
                    "date": dates[i],
                    "sofr": round(sofr_rates[i], 4),
                    "sofr_change": round(float(sofr_change[idx]), 2),
                    "volatility_20d": round(float(volatility_20d[idx]), 4) if not np.isnan(volatility_20d[idx]) else None
                }
                result.append(data_point)

            # volatility_20d が null でないもののみをフィルタ（グラフ表示用）
            result_with_vol = [r for r in result if r["volatility_20d"] is not None]

            # 最新値
            latest = result_with_vol[-1] if result_with_vol else None

            metadata = {
                "source": "NY Fed Markets API",
                "unit": "bps",
                "rolling_window": self.ROLLING_WINDOW,
                "description": "SOFR 20日ローリングボラティリティ（日次変化の標準偏差）",
                "release_time": "08:00 ET（毎営業日）"
            }

            print(f"Fetched {len(result_with_vol)} SOFR volatility records")

            return {
                "data": result_with_vol,
                "latest": latest,
                "metadata": metadata
            }

        except Exception as e:
            print(f"Error fetching SOFR data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _rolling_std(self, arr: np.ndarray, window: int) -> np.ndarray:
        """ローリング標準偏差を計算"""
        result = np.full(len(arr), np.nan)
        for i in range(window - 1, len(arr)):
            result[i] = np.std(arr[i - window + 1:i + 1], ddof=1)
        return result

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
sofr_volatility_service = SOFRVolatilityService()
