"""
韓国半導体輸出サービス
MOTIE ICTレポートから韓国半導体輸出データを取得

指標:
- 韓国半導体輸出（value_usd_billion, yoy_pct）

データソース:
- JSON履歴: kr_semiconductor_history.json（過去データ）
- スクレイパー: scraper.py + auto_fetch.py（最新データ）

発表スケジュール:
- 月初に수출입 동향（速報）、月中旬にICT 수출입 동향（確報）

キャッシュ方式: FMP発表日時ベース判定方式（south_korean_exportsと同一マッピング）

更新スケジュール: 月次（FMP Exports YoY イベントに連動）
"""
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "global" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "kr_semiconductor_exports_cache.json"

# 履歴JSONファイル
HISTORY_FILE = CACHE_DIR / "kr_semiconductor_history.json"


class KrSemiconductorExportsService:
    """韓国半導体輸出サービス"""

    DATA_CACHE_KEY = "global:kr_semiconductor_exports:data"
    # 韓国輸出と同タイミングなのでFMPマッピングを流用
    ECONALPHA_ID = "south_korean_exports"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """韓国半導体輸出データを取得"""

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

        # 履歴JSONから取得
        data = self._load_from_history()

        if data:
            latest = data[-1] if data else None
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            metadata = {
                "source": "MOTIE ICT 수출입 동향",
                "indicator": "South Korean Semiconductor Exports",
                "description": "韓国半導体輸出",
                "unit_value": "Billion USD",
                "unit_yoy": "%",
                "frequency": "monthly",
            }

            cache_payload = {
                "data": data,
                "latest": latest,
                "metadata": metadata,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                **cache_payload,
                "cached": False,
                "source": "history_json",
            }

        # 取得失敗時はファイルキャッシュから返す
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
        }

    def _load_from_history(self) -> List[Dict[str, Any]]:
        """履歴JSONファイルからデータを読み込み、標準形式に変換"""
        try:
            if not HISTORY_FILE.exists():
                print(f"[KrSemiconductorExports] History file not found: {HISTORY_FILE}")
                return []

            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                raw = json.load(f)

            records = raw.get("data", [])
            if not records:
                print("[KrSemiconductorExports] No data in history file")
                return []

            result = []
            for rec in records:
                ref_month = rec.get("ref_month", "")
                if not ref_month:
                    continue

                # ref_month "2024-01" → date "2024-01-01"
                date_str = f"{ref_month}-01"

                value = rec.get("value_usd_billion")
                yoy = rec.get("yoy_pct")

                result.append({
                    "date": date_str,
                    "value": float(value) if value is not None else None,
                    "yoy": float(yoy) if yoy is not None else None,
                })

            # 日付順にソート
            result.sort(key=lambda x: x["date"])

            # MoM計算（前月比）
            for i in range(1, len(result)):
                curr_val = result[i].get("value")
                prev_val = result[i - 1].get("value")
                if curr_val is not None and prev_val is not None and prev_val != 0:
                    result[i]["mom"] = round(((curr_val - prev_val) / prev_val) * 100, 2)
                else:
                    result[i]["mom"] = None
            if result:
                result[0]["mom"] = None

            print(f"[KrSemiconductorExports] Loaded {len(result)} records from history JSON")
            return result

        except Exception as e:
            print(f"[KrSemiconductorExports] Error loading from history: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP 3分方式）"""
        return should_refresh_by_fmp_schedule(
            self.ECONALPHA_ID,
            last_updated_str
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[KrSemiconductorExports] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[KrSemiconductorExports] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        data_count = 0
        latest_date = None
        if cached_data:
            data_count = len(cached_data.get("data", []))
            latest_date = cached_data.get("latest", {}).get("date") if cached_data.get("latest") else None

        return {
            "indicator": "South Korean Semiconductor Exports",
            "source": "MOTIE ICT Reports (JSON History)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "latest_date": latest_date,
            "data_count": data_count,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
kr_semiconductor_exports_service = KrSemiconductorExportsService()
