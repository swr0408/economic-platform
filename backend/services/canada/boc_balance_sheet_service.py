"""
BOCバランスシートサービス

指標:
- Total assets（総資産）
- Total liabilities（総負債）

データソース:
- Statistics Canada Table 10-10-0136-01
- https://www150.statcan.gc.ca/n1/tbl/csv/10100136-eng.zip

発表スケジュール:
- 週次（水曜日時点のデータ）
- 発表時刻: 金曜 14:30 ET（土曜 04:30 JST 冬 / 03:30 JST 夏）
"""
import json
import zipfile
import io
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
TORONTO = ZoneInfo("America/Toronto")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "canada" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "boc_balance_sheet_cache.json"

# Statistics Canada CSV URL
STATCAN_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/10100136-eng.zip"


class BocBalanceSheetService:
    """BOCバランスシートサービス"""

    DATA_CACHE_KEY = "canada:boc_balance_sheet:data"
    CACHE_TTL = 86400  # 24時間

    def __init__(self):
        pass

    def get_boc_balance_sheet_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """BOCバランスシートデータを取得"""
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
            latest = result[-1] if result else None

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Statistics Canada",
                    "table": "10-10-0136-01",
                    "indicator": "BOC Balance Sheet - Total Assets",
                    "description": "カナダ中央銀行バランスシート（総資産）",
                    "unit": "millions CAD",
                    "frequency": "weekly",
                },
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=self.CACHE_TTL)
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
        """Statistics CanadaからCSVデータを取得"""
        try:
            print(f"[BocBalanceSheet] Fetching data from: {STATCAN_URL}")

            resp = requests.get(STATCAN_URL, timeout=60)
            resp.raise_for_status()

            # ZIPを展開
            z = zipfile.ZipFile(io.BytesIO(resp.content))
            csv_name = [n for n in z.namelist() if n.endswith('.csv') and not n.startswith('_')][0]

            with z.open(csv_name) as f:
                df = pd.read_csv(f)

            # Total assetsのデータを抽出
            total_assets = df[df['Assets and liabilities'] == 'Total assets'].copy()

            if total_assets.empty:
                print("[BocBalanceSheet] No Total assets data found")
                return []

            result = []
            for _, row in total_assets.iterrows():
                date_str = row['REF_DATE']
                value = row['VALUE']

                if pd.isna(value):
                    continue

                try:
                    # 日付をパース（YYYY-MM-DD形式）
                    parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()

                    # 2015年以降のデータのみ
                    if parsed_date.year < 2015:
                        continue

                    result.append({
                        "date": date_str,
                        "value": float(value),  # 百万CAD
                    })
                except (ValueError, TypeError) as e:
                    print(f"[BocBalanceSheet] Error parsing row: {e}")
                    continue

            # 日付でソート
            result.sort(key=lambda x: x["date"])

            print(f"[BocBalanceSheet] Loaded {len(result)} weekly records")
            if result:
                print(f"[BocBalanceSheet] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[BocBalanceSheet] Latest: {latest['date']} = {latest['value']:,.0f} million CAD")

            return result

        except Exception as e:
            print(f"[BocBalanceSheet] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 週次データなので、金曜日以降に前回更新が金曜日前ならリフレッシュ
            # 簡略化: 24時間以上経過していたらリフレッシュ
            age = now - last_updated
            if age.total_seconds() > 86400:  # 24時間
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
            print(f"[BocBalanceSheet] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[BocBalanceSheet] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "BOC Balance Sheet",
            "source": "Statistics Canada",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
boc_balance_sheet_service = BocBalanceSheetService()
