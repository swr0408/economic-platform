"""
KOF経済バロメーター（先行指標）サービス
KOF Swiss Economic Institute APIからスイス経済先行指標データを取得

指標:
- KOF Economic Barometer（KOF経済バロメーター）
- スイス経済の先行指標として広く使用される景気指数
- 100を基準とし、100超は景気拡大、100未満は景気後退を示唆

データソース:
- KOF Swiss Economic Institute API
- https://datenservice.kof.ethz.ch/api/v1/public/ts?keys=kofbarometer&mime=xlsx

発表スケジュール:
- 毎月下旬（KOF発表）
- 発表時刻: 09:00 チューリッヒ時間

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import io
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd

from core.redis_client import redis_client
from services.switzerland.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "switzerland" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "kof_economic_barometer_cache.json"


class KofEconomicBarometerService:
    """KOF経済バロメーターサービス"""

    DATA_CACHE_KEY = "switzerland:kof_economic_barometer:data"
    ECONALPHA_ID = "kof_economic_barometer"
    FMP_COUNTRY = "CH"
    FMP_EVENT_PATTERN = "KOF Leading Indicators"

    # KOF API URL
    KOF_API_URL = "https://datenservice.kof.ethz.ch/api/v1/public/ts?keys=kofbarometer&mime=xlsx"

    def __init__(self):
        pass

    def get_kof_barometer_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """KOF経済バロメーターデータを取得"""
        # 次回発表日を取得
        next_release = get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY)

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
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # KOF APIから取得
        kof_result = self._load_from_kof()
        if kof_result:
            # 最新値を取得
            latest = kof_result[-1] if kof_result else None

            cache_payload = {
                "data": kof_result,
                "latest": latest,
                "metadata": {
                    "source": "KOF Swiss Economic Institute",
                    "indicator": "KOF Economic Barometer",
                    "description": "スイス経済先行指標（KOF経済バロメーター）",
                    "base": "100 = Long-term average",
                },
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": kof_result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "kof_api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_kof(self) -> List[Dict[str, Any]]:
        """KOF APIからデータを取得"""
        try:
            print(f"[KofBarometer] Fetching data from KOF API: {self.KOF_API_URL}")

            # Excelファイルをダウンロード
            resp = requests.get(self.KOF_API_URL, timeout=60)
            resp.raise_for_status()

            # Excelファイルを読み込み
            excel_data = io.BytesIO(resp.content)
            df = pd.read_excel(excel_data)

            result = []
            current_date = datetime.now(JST).date()

            for _, row in df.iterrows():
                date_str = row.get("date")
                value = row.get("kofbarometer")

                if pd.isna(date_str) or pd.isna(value):
                    continue

                # 日付をYYYY-MM-01形式に変換
                if isinstance(date_str, str):
                    # "YYYY-MM" 形式
                    date_formatted = f"{date_str}-01"
                else:
                    continue

                # 未来のデータはスキップ
                try:
                    date_obj = datetime.strptime(date_formatted, "%Y-%m-%d").date()
                    if date_obj > current_date:
                        continue
                except ValueError:
                    continue

                result.append({
                    "date": date_formatted,
                    "value": round(float(value), 2),
                })

            # 日付でソート
            result.sort(key=lambda x: x["date"])

            print(f"[KofBarometer] Loaded {len(result)} records from KOF API")
            if result:
                print(f"[KofBarometer] Date range: {result[0]['date']} to {result[-1]['date']}")
                print(f"[KofBarometer] Latest: value={result[-1].get('value')}")

            return result

        except Exception as e:
            print(f"[KofBarometer] Error loading from KOF API: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日ベース）"""
        return should_refresh_by_pattern(
            self.FMP_EVENT_PATTERN,
            last_updated_str,
            country=self.FMP_COUNTRY
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[KofBarometer] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[KofBarometer] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "KOF Economic Barometer",
            "source": "KOF Swiss Economic Institute",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
kof_economic_barometer_service = KofEconomicBarometerService()
