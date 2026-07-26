"""
住宅ローン金利サービス
BoE公式CSVファイルからデータを取得

指標:
- CFMZ6K6: 住宅ローン残高金利（Weighted average interest rate on all dwelling-secured loans）
- CFMZ6JV: 新規住宅ローン金利（Interest rate on new fixed-rate mortgage advances）
- IUMTLMV: 変動金利住宅ローン（Revert-to-rate mortgage to households）

データソース:
- CSV: Bank of England統計データベース
- DB: economic_calendar_events（FMP蓄積データ・フォールバック）

発表スケジュール:
- 月次（毎月5日～11日頃）

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
DATA_CACHE_FILE = CACHE_DIR / "boe_mortgage_rates_cache.json"

# BoE CSV URLs
# CFMZ6K6: Weighted average interest rate on all dwelling-secured loans
# CFMZ6JV: Interest rate on new fixed-rate mortgage advances
# IUMTLMV: Revert-to-rate mortgage to households (変動金利住宅ローン)
BOE_CFMZ6K6_URL = "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom=01/Jan/2016&Dateto=now&SeriesCodes=CFMZ6K6&UsingCodes=Y&CSVF=TT"
BOE_CFMZ6JV_URL = "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom=01/Jan/2016&Dateto=now&SeriesCodes=CFMZ6JV&UsingCodes=Y&CSVF=TT"
BOE_IUMTLMV_URL = "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom=01/Jan/2012&Dateto=now&SeriesCodes=IUMTLMV&UsingCodes=Y&CSVF=TT"


class BoEMortgageRatesService:
    """住宅ローン金利サービス"""

    DATA_CACHE_KEY = "uk:boe_mortgage_rates:data"
    ECONALPHA_ID = "boe_mortgage_rates"

    def __init__(self):
        pass

    def get_boe_mortgage_rates_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """住宅ローン金利データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "cfmz6k6": cached_data.get("cfmz6k6", []),
                        "cfmz6jv": cached_data.get("cfmz6jv", []),
                        "iumtlmv": cached_data.get("iumtlmv", []),
                        "latest_cfmz6k6": cached_data.get("latest_cfmz6k6"),
                        "latest_cfmz6jv": cached_data.get("latest_cfmz6jv"),
                        "latest_iumtlmv": cached_data.get("latest_iumtlmv"),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # CSVから取得
        csv_data = self._fetch_from_csv()

        if csv_data:
            cfmz6k6_data = csv_data.get("cfmz6k6", [])
            cfmz6jv_data = csv_data.get("cfmz6jv", [])
            iumtlmv_data = csv_data.get("iumtlmv", [])
        else:
            # CSVから取得できない場合はDBからフォールバック
            logger.warning("[BoE Mortgage Rates] CSV fetch failed, falling back to DB")
            cfmz6k6_data = self._load_from_db()
            cfmz6jv_data = []  # DBにはCFMZ6JVデータがない
            iumtlmv_data = []  # DBにはIUMTLMVデータがない

        if cfmz6k6_data or cfmz6jv_data or iumtlmv_data:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
            latest_cfmz6k6 = cfmz6k6_data[-1] if cfmz6k6_data else None
            latest_cfmz6jv = cfmz6jv_data[-1] if cfmz6jv_data else None
            latest_iumtlmv = iumtlmv_data[-1] if iumtlmv_data else None

            from services.usa.fmp_next_release_utils import guarded_last_updated_keys, _max_date_of
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated_keys(
                self.DATA_CACHE_KEY, ("cfmz6k6", "cfmz6jv", "iumtlmv"),
                _max_date_of(cfmz6k6_data, cfmz6jv_data, iumtlmv_data), now_str
            )
            cache_payload = {
                "cfmz6k6": cfmz6k6_data,
                "cfmz6jv": cfmz6jv_data,
                "iumtlmv": iumtlmv_data,
                "latest_cfmz6k6": latest_cfmz6k6,
                "latest_cfmz6jv": latest_cfmz6jv,
                "latest_iumtlmv": latest_iumtlmv,
                "next_release": next_release,
                "last_updated": last_updated
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "cfmz6k6": cfmz6k6_data,
                "cfmz6jv": cfmz6jv_data,
                "iumtlmv": iumtlmv_data,
                "latest_cfmz6k6": latest_cfmz6k6,
                "latest_cfmz6jv": latest_cfmz6jv,
                "latest_iumtlmv": latest_iumtlmv,
                "next_release": next_release,
                "cached": False,
                "source": "csv" if csv_data else "database",
                "last_updated": last_updated
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "cfmz6k6": file_cache.get("cfmz6k6", []),
                "cfmz6jv": file_cache.get("cfmz6jv", []),
                "iumtlmv": file_cache.get("iumtlmv", []),
                "latest_cfmz6k6": file_cache.get("latest_cfmz6k6"),
                "latest_cfmz6jv": file_cache.get("latest_cfmz6jv"),
                "latest_iumtlmv": file_cache.get("latest_iumtlmv"),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "cfmz6k6": [],
            "cfmz6jv": [],
            "iumtlmv": [],
            "latest_cfmz6k6": None,
            "latest_cfmz6jv": None,
            "latest_iumtlmv": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_csv(self) -> Optional[Dict[str, Any]]:
        """
        BoE公式CSVファイルからデータを取得

        Returns:
            {"cfmz6k6": [...], "cfmz6jv": [...], "iumtlmv": [...]} or None
        """
        try:
            logger.info("[BoE Mortgage Rates] Fetching data from BoE CSV")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            # CFMZ6K6を取得
            cfmz6k6_data = self._fetch_single_csv(BOE_CFMZ6K6_URL, "CFMZ6K6", headers)

            # CFMZ6JVを取得
            cfmz6jv_data = self._fetch_single_csv(BOE_CFMZ6JV_URL, "CFMZ6JV", headers)

            # IUMTLMVを取得
            iumtlmv_data = self._fetch_single_csv(BOE_IUMTLMV_URL, "IUMTLMV", headers)

            if cfmz6k6_data is None and cfmz6jv_data is None and iumtlmv_data is None:
                return None

            return {
                "cfmz6k6": cfmz6k6_data or [],
                "cfmz6jv": cfmz6jv_data or [],
                "iumtlmv": iumtlmv_data or [],
            }

        except Exception as e:
            logger.error(f"[BoE Mortgage Rates] Error fetching CSV: {e}")
            return None

    def _fetch_single_csv(self, url: str, series_code: str, headers: dict) -> Optional[List[Dict[str, Any]]]:
        """単一のCSVシリーズを取得"""
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            return self._parse_csv(response.text, series_code)

        except Exception as e:
            logger.error(f"[BoE Mortgage Rates] Error fetching {series_code}: {e}")
            return None

    def _parse_csv(self, csv_content: str, series_code: str) -> Optional[List[Dict[str, Any]]]:
        """
        CSVコンテンツを解析

        BoE CSVは3行のヘッダーがあり、DATEヘッダーの行からデータが始まる
        """
        try:
            data = []
            lines = csv_content.split('\n')

            # DATEヘッダーの行を探す
            data_start_index = None
            for i, line in enumerate(lines):
                if line.startswith('DATE,'):
                    data_start_index = i
                    break

            if data_start_index is None:
                logger.error("[BoE Mortgage Rates] Could not find DATE header in CSV")
                return None

            # DATEヘッダー以降をCSVとして解析
            csv_data = '\n'.join(lines[data_start_index:])
            csv_reader = csv.DictReader(StringIO(csv_data))

            for row in csv_reader:
                date_str = row.get('DATE', '').strip()
                value_str = row.get(series_code, '').strip()

                if not date_str or not value_str:
                    continue

                try:
                    # 日付をパース (format: "31 Jan 2016")
                    date_obj = datetime.strptime(date_str, '%d %b %Y')
                    date_formatted = date_obj.strftime('%Y-%m-01')  # 月初日に正規化

                    # 値をパース
                    value = float(value_str.replace(',', ''))

                    data.append({
                        "date": date_formatted,
                        "value": value,
                        "forecast": None,
                        "previous": None,
                    })

                except (ValueError, AttributeError) as e:
                    logger.warning(f"[BoE Mortgage Rates] Error parsing row: {date_str}, {value_str}: {e}")
                    continue

            # 日付順にソート（昇順）
            data = sorted(data, key=lambda x: x["date"])

            logger.info(f"[BoE Mortgage Rates] Processed {series_code}: {len(data)} records")

            return data if data else None

        except Exception as e:
            logger.error(f"[BoE Mortgage Rates] Error parsing CSV for {series_code}: {e}")
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
                      AND event ILIKE '%BBA Mortgage Rate%'
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

                logger.info(f"[BoE Mortgage Rates] Loaded {len(result)} records from DB")
                return result

        except Exception as e:
            logger.error(f"[BoE Mortgage Rates] Error loading from DB: {e}")
            return []

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
            logger.error(f"[BoE Mortgage Rates] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[BoE Mortgage Rates] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "BoE Mortgage Rates",
            "source": "CSV (Bank of England)",
            "series_codes": ["CFMZ6K6", "CFMZ6JV", "IUMTLMV"],
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "cfmz6k6_count": len(cached_data.get("cfmz6k6", [])) if cached_data else 0,
            "cfmz6jv_count": len(cached_data.get("cfmz6jv", [])) if cached_data else 0,
            "iumtlmv_count": len(cached_data.get("iumtlmv", [])) if cached_data else 0,
            "latest_cfmz6k6": cached_data.get("latest_cfmz6k6") if cached_data else None,
            "latest_cfmz6jv": cached_data.get("latest_cfmz6jv") if cached_data else None,
            "latest_iumtlmv": cached_data.get("latest_iumtlmv") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
boe_mortgage_rates_service = BoEMortgageRatesService()
