"""
住宅ローン承認件数サービス
BoE公式CSVファイルからデータを取得

指標:
- 住宅ローン承認件数（Total gross mortgage lending）

データソース:
- CSV: Bank of England統計データベース（Series: LPMVTVX）
- DB: economic_calendar_events（FMP蓄積データ・フォールバック）

発表スケジュール:
- 月次（毎月28日～翌月4日頃）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import csv
import json
import logging
import requests
from io import StringIO
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "housing"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "boe_mortgage_lending_cache.json"

# BoE CSV URL (Series: LPMVTVX - Total gross mortgage lending £ millions)
BOE_CSV_URL = "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom=01/Jan/2015&Dateto=now&SeriesCodes=LPMVTVX&UsingCodes=Y&CSVF=TN"


class BoEMortgageLendingService:
    """住宅ローン承認件数サービス"""

    DATA_CACHE_KEY = "uk:boe_mortgage_lending:data"
    ECONALPHA_ID = "boe_mortgage_lending"

    def __init__(self):
        pass

    def get_boe_mortgage_lending_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """住宅ローン承認件数データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # CSVから取得
        csv_data = self._fetch_from_csv()

        if csv_data:
            data = csv_data
        else:
            # CSVから取得できない場合はDBからフォールバック
            logger.warning("[BoE Mortgage Lending] CSV fetch failed, falling back to DB")
            data = self._load_from_db()

        if data:
            # 3ヶ月移動平均・前年比を計算
            data = self._compute_derived_fields(data)

            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
            latest = data[-1] if data else None

            cache_payload = {
                "data": data,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": data,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "csv" if csv_data else "database",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": file_cache.get("next_release"),
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

    def _fetch_from_csv(self) -> Optional[List[Dict[str, Any]]]:
        """
        BoE公式CSVファイルからデータを取得

        Returns:
            List of data points or None
        """
        try:
            logger.info(f"[BoE Mortgage Lending] Fetching data from {BOE_CSV_URL}")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            response = requests.get(BOE_CSV_URL, headers=headers, timeout=30)
            response.raise_for_status()

            # CSVを解析
            return self._parse_csv(response.text)

        except Exception as e:
            logger.error(f"[BoE Mortgage Lending] Error fetching CSV: {e}")
            return None

    def _parse_csv(self, csv_content: str) -> Optional[List[Dict[str, Any]]]:
        """
        CSVコンテンツを解析

        Args:
            csv_content: CSV文字列

        Returns:
            List of data points
        """
        try:
            data = []
            csv_reader = csv.DictReader(StringIO(csv_content))

            for row in csv_reader:
                date_str = row.get('DATE', '').strip()
                value_str = row.get('LPMVTVX', '').strip()

                if not date_str or not value_str:
                    continue

                try:
                    # 日付をパース (format: "31 Jan 2015")
                    date_obj = datetime.strptime(date_str, '%d %b %Y')
                    date_formatted = date_obj.strftime('%Y-%m-01')  # 月初日に正規化

                    # 値をパース（カンマ除去）
                    value = float(value_str.replace(',', ''))

                    data.append({
                        "date": date_formatted,
                        "value": value,
                        "forecast": None,
                        "previous": None,
                    })

                except (ValueError, AttributeError) as e:
                    logger.warning(f"[BoE Mortgage Lending] Error parsing row: {date_str}, {value_str}: {e}")
                    continue

            # 日付順にソート（昇順）
            data = sorted(data, key=lambda x: x["date"])

            logger.info(f"[BoE Mortgage Lending] Processed CSV: {len(data)} records")

            return data if data else None

        except Exception as e:
            logger.error(f"[BoE Mortgage Lending] Error parsing CSV: {e}")
            return None

    def _load_from_db(self) -> List[Dict[str, Any]]:
        """DBからデータを取得（フォールバック用）"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                query = text("""
                    SELECT datetime_utc, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'UK'
                      AND event ILIKE '%Mortgage Approvals%'
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query).fetchall()

                result = []
                seen_dates = set()

                for row in rows:
                    dt_utc, actual, estimate, previous = row
                    if dt_utc:
                        date_str = dt_utc.strftime("%Y-%m-01")
                        if date_str in seen_dates:
                            continue
                        seen_dates.add(date_str)

                        result.append({
                            "date": date_str,
                            "value": float(actual) if actual else None,
                            "forecast": float(estimate) if estimate else None,
                            "previous": float(previous) if previous else None,
                        })

                logger.info(f"[BoE Mortgage Lending] Loaded {len(result)} records from DB")
                return result

        except Exception as e:
            logger.error(f"[BoE Mortgage Lending] Error loading from DB: {e}")
            return []

    def _compute_derived_fields(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """3ヶ月移動平均・前年比を計算して各データポイントに追加"""
        # Pass 1: 3ヶ月移動平均
        for i, dp in enumerate(data):
            if i >= 2 and all(data[j].get("value") is not None for j in range(i - 2, i + 1)):
                dp["ma3"] = round(sum(data[j]["value"] for j in range(i - 2, i + 1)) / 3, 1)
            else:
                dp["ma3"] = None

        # Pass 2: 3ヶ月移動平均の前年比（%）
        for i, dp in enumerate(data):
            if i >= 12 and dp.get("ma3") is not None and data[i - 12].get("ma3") is not None and data[i - 12]["ma3"] != 0:
                dp["ma3_yoy"] = round((dp["ma3"] / data[i - 12]["ma3"] - 1) * 100, 2)
            else:
                dp["ma3_yoy"] = None

        return data

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP 3分方式）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[BoE Mortgage Lending] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[BoE Mortgage Lending] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "BoE Mortgage Lending",
            "source": "CSV (Bank of England)",
            "csv_url": BOE_CSV_URL,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
boe_mortgage_lending_service = BoEMortgageLendingService()
