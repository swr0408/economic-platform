"""
J.P.Morgan Global Manufacturing PMI サービス

指標:
- J.P.Morgan Global Manufacturing PMI

データソース:
- CSV履歴データ (backend/data/csv_import/J.P.Morgan Global Manufacturing PMI.csv)
- 手動更新 → ファイルタイムスタンプ監視で自動リフレッシュ

FMPマッピング: なし

発表スケジュール: 月次
"""
import csv
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "global" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "jpmorgan_global_manufacturing_pmi_cache.json"

# CSVデータ
CSV_DIR = Path(__file__).parent.parent.parent / "data" / "csv_import"
CSV_FILE = CSV_DIR / "J.P.Morgan Global Manufacturing PMI.csv"


class GlobalManufacturingPmiService:
    """J.P.Morgan Global Manufacturing PMI サービス（CSV方式・タイムスタンプ監視）"""

    DATA_CACHE_KEY = "global:jpmorgan_global_manufacturing_pmi:data"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """グローバル製造業PMIデータを取得"""

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
                        "next_release": None,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # データ取得（CSVから）
        data = self._load_from_csv()

        latest = data[-1] if data else None

        if latest:
            print(f"[GlobalPMI] Latest: {latest['date']} value={latest['value']}")

        metadata = {
            "source": "S&P Global / J.P.Morgan",
            "indicator": "J.P.Morgan Global Manufacturing PMI",
            "description": "J.P.Morganグローバル製造業購買担当者景気指数",
            "unit": "index",
            "frequency": "monthly",
        }

        cache_payload = {
            "data": data,
            "latest": latest,
            "metadata": metadata,
            "last_updated": datetime.now(JST).isoformat(),
            "csv_mtime": self._get_csv_mtime(),
        }
        redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
        self._save_file_cache(cache_payload)

        return {
            "data": data,
            "latest": latest,
            "metadata": metadata,
            "next_release": None,
            "cached": False,
            "source": "csv",
            "last_updated": datetime.now(JST).isoformat(),
        }

    def _load_from_csv(self) -> List[Dict[str, Any]]:
        """CSVファイルから履歴データを読み込む

        CSV形式: 公表日,結果
        日付形式: YYYY/M (例: 2016/1)
        値形式: 数値 (例: 50.9)
        """
        result = []

        try:
            if not CSV_FILE.exists():
                print(f"[GlobalPMI] CSV file not found: {CSV_FILE}")
                return result

            with open(CSV_FILE, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    date_str = row.get("公表日", "").strip()
                    value_str = row.get("結果", "").strip()

                    if not date_str or not value_str:
                        continue

                    # 日付パース: "YYYY/M" → "YYYY-MM-01"
                    try:
                        parts = date_str.split("/")
                        year = int(parts[0])
                        month = int(parts[1])
                        date_formatted = f"{year}-{month:02d}-01"
                    except (ValueError, IndexError):
                        continue

                    # 値のパース
                    try:
                        value = float(value_str)
                    except ValueError:
                        continue

                    result.append({
                        "date": date_formatted,
                        "value": round(value, 1),
                    })

            print(f"[GlobalPMI] Loaded {len(result)} records from CSV")

        except Exception as e:
            print(f"[GlobalPMI] Error loading from CSV: {e}")

        return result

    def _get_csv_mtime(self) -> Optional[str]:
        """CSVファイルの最終更新時刻を取得"""
        try:
            if CSV_FILE.exists():
                mtime = os.path.getmtime(CSV_FILE)
                return datetime.fromtimestamp(mtime, tz=JST).isoformat()
        except Exception:
            pass
        return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定

        CSVファイルのタイムスタンプが変更されていたらリフレッシュ
        """
        try:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if not cached_data:
                return True

            cached_csv_mtime = cached_data.get("csv_mtime")
            current_csv_mtime = self._get_csv_mtime()

            # CSVファイルのタイムスタンプが変わっていればリフレッシュ
            if cached_csv_mtime != current_csv_mtime:
                print(f"[GlobalPMI] CSV file updated: {cached_csv_mtime} -> {current_csv_mtime}")
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
            print(f"[GlobalPMI] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[GlobalPMI] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        data_count = 0
        if cached_data:
            data_count = len(cached_data.get("data", []))

        return {
            "indicator": "J.P.Morgan Global Manufacturing PMI",
            "source": "S&P Global / J.P.Morgan (CSV)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": data_count,
            "csv_file_exists": CSV_FILE.exists(),
            "csv_mtime": self._get_csv_mtime(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
global_manufacturing_pmi_service = GlobalManufacturingPmiService()
