"""
カナダ銀行バランスシートサービス（チャータード銀行）

指標:
- Canadian dollar assets, total（カナダドル資産合計）

データソース:
- Statistics Canada Table 10-10-0109-01
- https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1010010901

発表スケジュール:
- 月次
- 発表時刻: 金曜 14:30 ET（土曜 04:30 JST 冬 / 03:30 JST 夏）
"""
import json
import zipfile
import io
from datetime import datetime
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
DATA_CACHE_FILE = CACHE_DIR / "canada_banks_balance_sheet_cache.json"

# Statistics Canada CSV URL
STATCAN_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/10100109-eng.zip"

# テーブルページURL（Release dateチェック用）
TABLE_PAGE_URL = "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1010010901"


class CanadaBanksBalanceSheetService:
    """カナダ銀行バランスシートサービス（チャータード銀行）"""

    DATA_CACHE_KEY = "canada:canada_banks_balance_sheet:data"
    CACHE_TTL = 86400  # 24時間

    def __init__(self):
        pass

    def get_canada_banks_balance_sheet_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダ銀行バランスシートデータを取得"""
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
                    "table": "10-10-0109-01",
                    "indicator": "Chartered banks - Canadian dollar assets, total",
                    "description": "カナダ銀行バランスシート（チャータード銀行・カナダドル資産合計）",
                    "unit": "millions CAD",
                    "frequency": "monthly",
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
            print(f"[CanadaBanksBalanceSheet] Fetching data from: {STATCAN_URL}")

            resp = requests.get(STATCAN_URL, timeout=60)
            resp.raise_for_status()

            # ZIPを展開
            z = zipfile.ZipFile(io.BytesIO(resp.content))
            csv_name = [n for n in z.namelist() if n.endswith('.csv') and not n.startswith('_')][0]

            with z.open(csv_name) as f:
                df = pd.read_csv(f)

            # Canadian dollar assets, total のデータを抽出
            target_series = df[df['Assets and liabilities'] == 'Canadian dollar assets, total'].copy()

            if target_series.empty:
                print("[CanadaBanksBalanceSheet] No 'Canadian dollar assets, total' data found")
                return []

            result = []
            for _, row in target_series.iterrows():
                date_str = row['REF_DATE']
                value = row['VALUE']

                if pd.isna(value):
                    continue

                try:
                    # 日付をパース（YYYY-MM形式）
                    parsed_date = datetime.strptime(date_str, "%Y-%m")

                    # 2000年以降のデータのみ
                    if parsed_date.year < 2000:
                        continue

                    # 日付を月末形式に変換
                    formatted_date = f"{date_str}-01"

                    result.append({
                        "date": formatted_date,
                        "value": float(value),  # 百万CAD
                    })
                except (ValueError, TypeError) as e:
                    print(f"[CanadaBanksBalanceSheet] Error parsing row: {e}")
                    continue

            # 日付でソート
            result.sort(key=lambda x: x["date"])

            print(f"[CanadaBanksBalanceSheet] Loaded {len(result)} monthly records")
            if result:
                print(f"[CanadaBanksBalanceSheet] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CanadaBanksBalanceSheet] Latest: {latest['date']} = {latest['value']:,.0f} million CAD")

            return result

        except Exception as e:
            print(f"[CanadaBanksBalanceSheet] Error loading data: {e}")
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

            # 月次データなので、24時間以上経過していたらリフレッシュ
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
            print(f"[CanadaBanksBalanceSheet] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CanadaBanksBalanceSheet] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Canada Banks Balance Sheet",
            "source": "Statistics Canada",
            "table": "10-10-0109-01",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
canada_banks_balance_sheet_service = CanadaBanksBalanceSheetService()
