"""
ECB Composite Indicator of Systemic Stress (CISS) サービス
ECB Data APIからユーロ圏のシステミックストレス総合指標データを取得

指標:
- CISS: ユーロ圏のシステミックストレスを測定する総合指標
- 値は0〜1の範囲で、高いほどストレスが大きい

データソース:
- ECB Data API (CISS): CISS.D.U2.Z0Z.4F.EC.SS_CIN.IDX

発表スケジュール:
- 日次発表（営業日ベース）
- 15:00 CET

キャッシュ方式: 24時間TTL + 営業日判定
"""
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
CET = ZoneInfo("Europe/Berlin")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "monetary_policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_ciss_cache.json"


class ECBCISSService:
    """ECB Composite Indicator of Systemic Stress (CISS) サービス"""

    # ECB Legacy API（SDMX形式）- 安定したAPI
    ECB_LEGACY_API_BASE = "https://data-api.ecb.europa.eu/service/data"

    # シリーズキー
    # CISS = Composite Indicator of Systemic Stress
    # D = Daily
    # U2 = Euro Area
    # Z0Z = All countries
    # 4F = All financial intermediaries
    # EC = Euro area composite
    # SS_CIN = Systemic stress composite index
    # IDX = Index
    SERIES_KEY = "D.U2.Z0Z.4F.EC.SS_CIN.IDX"

    DATA_CACHE_KEY = "monetary_policy:ecb_ciss:data"
    ECONALPHA_ID = "ecb_ciss"

    def __init__(self):
        pass

    def _fetch_ciss_data(self, start_date: str = "2015-01-01") -> Optional[List[Dict]]:
        """ECB Legacy API（SDMX）からCISSデータを取得"""
        url = f"{self.ECB_LEGACY_API_BASE}/CISS/{self.SERIES_KEY}"
        params = {
            "startPeriod": start_date,
            "format": "jsondata"
        }

        try:
            print(f"[ECB CISS] Fetching: {url}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if "dataSets" not in data or len(data["dataSets"]) == 0:
                print("[ECB CISS] No data sets found")
                return None

            dataset = data["dataSets"][0]
            if "series" not in dataset:
                print("[ECB CISS] No series found")
                return None

            series_data = list(dataset["series"].values())[0]
            observations = series_data.get("observations", {})

            # 時間次元を取得
            dimensions = data.get("structure", {}).get("dimensions", {}).get("observation", [])
            time_dimension = None
            for dim in dimensions:
                if dim.get("id") == "TIME_PERIOD":
                    time_dimension = dim
                    break

            if not time_dimension:
                print("[ECB CISS] No time dimension found")
                return None

            time_values = time_dimension.get("values", [])

            result = []
            for obs_key, obs_value in observations.items():
                time_index = int(obs_key)
                if time_index < len(time_values):
                    period = time_values[time_index].get("id")
                    value = obs_value[0] if isinstance(obs_value, list) and len(obs_value) > 0 else obs_value

                    if value is not None and period:
                        result.append({
                            "date": period,
                            "value": float(value)
                        })

            result.sort(key=lambda x: x["date"])
            print(f"[ECB CISS] Fetched {len(result)} data points")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[ECB CISS] Request error: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[ECB CISS] Parse error: {e}")
            return None

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日時を計算

        CISSは日次発表のため、次の営業日15:00 CETを返す
        """
        now = datetime.now(CET)

        # 次の営業日を計算
        next_date = now + timedelta(days=1)

        # 土日をスキップ
        while next_date.weekday() >= 5:  # 5=土曜, 6=日曜
            next_date += timedelta(days=1)

        # 15:00 CETに設定
        release_datetime = next_date.replace(hour=15, minute=0, second=0, microsecond=0)
        release_datetime_jst = release_datetime.astimezone(JST)

        return {
            "date": release_datetime.strftime("%Y-%m-%d"),
            "datetime_cet": release_datetime.isoformat(),
            "datetime_jst": release_datetime_jst.isoformat(),
            "time_cet": "15:00",
            "time_jst": release_datetime_jst.strftime("%H:%M"),
            "label": "CISS Daily Update"
        }

    def get_ciss_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ECB CISSデータを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    next_release = self._get_next_release()
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ECB APIからデータ取得
        ciss_data = self._fetch_ciss_data() or []

        if len(ciss_data) > 0:
            next_release = self._get_next_release()
            latest = ciss_data[-1] if ciss_data else None

            cache_payload = {
                "data": ciss_data,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": ciss_data,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "ecb_api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            next_release = self._get_next_release()
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 24時間以上経過していれば更新
            if (now - last_updated) > timedelta(hours=24):
                return True

            # 今日が営業日で、15:00 CET（23:00 JST冬時間/24:00 JST夏時間）を過ぎていれば更新
            now_cet = now.astimezone(CET)
            if now_cet.weekday() < 5:  # 平日
                today_release = now_cet.replace(hour=15, minute=0, second=0, microsecond=0)
                today_release_jst = today_release.astimezone(JST)

                if now > today_release_jst and last_updated < today_release_jst:
                    return True

            return False
        except Exception as e:
            print(f"[ECB CISS] Error checking refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "ECB CISS (Composite Indicator of Systemic Stress)",
            "source": "ECB Data API",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
ecb_ciss_service = ECBCISSService()
