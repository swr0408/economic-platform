"""
連邦財政収支（Federal Budget Balance）サービス
Treasury FiscalData API から MTS（Monthly Treasury Statement）データを取得

データソース:
- U.S. Department of the Treasury FiscalData API
- https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/

更新スケジュール:
- 翌月の第8営業日に公表
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
from calendar import monthrange

import requests

from core.redis_client import redis_client, CACHE_TTL_DAY


class FederalBudgetService:
    """連邦財政収支データサービス（月次）"""

    CACHE_KEY = "usa:federal_budget:data"
    CACHE_TTL = CACHE_TTL_DAY * 7  # 7日間（月次データ）
    CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "fiscal"
    FILE_CACHE_PATH = CACHE_DIR / "federal_budget_cache.json"

    # Treasury FiscalData API
    MTS_API_URL = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/mts/mts_table_1"

    def __init__(self):
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def get_federal_budget_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        連邦財政収支データを取得

        Returns:
            {
                "data": [
                    {
                        "date": "2024-01-31",
                        "receipts": 500.5,       # 歳入（十億ドル）
                        "outlays": 600.3,        # 歳出（十億ドル）
                        "deficit_surplus": -99.8 # 財政収支（十億ドル、マイナスは赤字）
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
        """Treasury FiscalData API から MTS データを取得"""
        try:
            print("Fetching Federal Budget data from Treasury FiscalData API...")

            # 過去10年分のデータを取得
            # record_type_cd=MTH で月次データのみ取得
            params = {
                "filter": "record_type_cd:eq:MTH",
                "sort": "-record_date",
                "page[size]": 500,
                "fields": "record_date,classification_desc,current_month_gross_rcpt_amt,current_month_gross_outly_amt,current_month_dfct_sur_amt,record_fiscal_year,record_calendar_month"
            }

            response = requests.get(self.MTS_API_URL, params=params, timeout=60)
            response.raise_for_status()

            data = response.json()
            records = data.get("data", [])

            if not records:
                print("No MTS data returned from API")
                return None

            # 月ごとにデータを集計
            monthly_data: Dict[str, Dict[str, Any]] = {}

            for record in records:
                # record_dateから年月を取得
                record_date = record.get("record_date")
                if not record_date:
                    continue

                # 月末日を日付として使用
                year_month = record_date[:7]  # "2024-12"

                # すでにその月のデータがあればスキップ（最新のレコードを使用）
                if year_month in monthly_data:
                    continue

                try:
                    receipts_str = record.get("current_month_gross_rcpt_amt", "0")
                    outlays_str = record.get("current_month_gross_outly_amt", "0")
                    deficit_str = record.get("current_month_dfct_sur_amt", "0")

                    # "null"文字列をチェック
                    if receipts_str == "null" or outlays_str == "null":
                        continue

                    receipts = float(receipts_str) / 1_000_000_000  # 十億ドルに変換
                    outlays = float(outlays_str) / 1_000_000_000
                    deficit_surplus = float(deficit_str) / 1_000_000_000

                    # 月末日を計算
                    year = int(record_date[:4])
                    month = int(record_date[5:7])
                    _, last_day = monthrange(year, month)
                    date_str = f"{year}-{month:02d}-{last_day:02d}"

                    monthly_data[year_month] = {
                        "date": date_str,
                        "receipts": round(receipts, 2),
                        "outlays": round(outlays, 2),
                        "deficit_surplus": round(-deficit_surplus, 2),  # 赤字をマイナスに
                        "fiscal_year": record.get("record_fiscal_year"),
                    }

                except (ValueError, TypeError) as e:
                    print(f"Error parsing record: {e}")
                    continue

            # 日付順にソート
            result = sorted(monthly_data.values(), key=lambda x: x["date"])

            if not result:
                print("No valid monthly data parsed")
                return None

            # 最新値
            latest = result[-1] if result else None

            metadata = {
                "source": "U.S. Department of the Treasury",
                "dataset": "Monthly Treasury Statement (MTS)",
                "unit": "billions USD",
                "description": "連邦政府の月次財政収支（歳入・歳出・財政収支）",
                "release_schedule": "翌月の第8営業日"
            }

            print(f"Fetched {len(result)} monthly budget records")

            return {
                "data": result,
                "latest": latest,
                "metadata": metadata
            }

        except Exception as e:
            print(f"Error fetching Federal Budget data: {e}")
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
            "ttl_days": round(ttl / 86400, 2) if ttl > 0 else 0,
            "file_cache_exists": self.FILE_CACHE_PATH.exists()
        }

    def get_next_release_date(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日を計算（翌月の第8営業日）

        Returns:
            {
                "date": "2024-02-12",
                "label": "MTS (Jan 2024)"
            }
        """
        try:
            now = datetime.now()
            # 次月の1日
            if now.month == 12:
                next_month = datetime(now.year + 1, 1, 1)
            else:
                next_month = datetime(now.year, now.month + 1, 1)

            # 第8営業日を計算
            business_days = 0
            current_date = next_month
            while business_days < 8:
                if current_date.weekday() < 5:  # 平日
                    business_days += 1
                    if business_days == 8:
                        break
                current_date += timedelta(days=1)

            # ラベル（前月のデータ）
            report_month = now.month
            report_year = now.year
            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

            return {
                "date": current_date.strftime("%Y-%m-%d"),
                "label": f"MTS ({month_names[report_month - 1]} {report_year})"
            }

        except Exception as e:
            print(f"Error calculating next release date: {e}")
            return None


# シングルトンインスタンス
federal_budget_service = FederalBudgetService()
