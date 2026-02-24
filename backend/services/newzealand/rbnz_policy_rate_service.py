"""
RBNZ政策金利（Official Cash Rate）サービス

指標:
- RBNZ Official Cash Rate (OCR)

データソース:
- RBNZ Statistical Tables B2 (Wholesale Interest Rates - Daily Close)
- https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates/wholesale-interest-rates

取得方法:
- 通常: RBNZ B2 Daily Close XLSX をダウンロードしOCR列を抽出
- 発表日: FMPから発表値を検出しDBに蓄積、B2とマージ

発表スケジュール:
- 年7回（不定期）
- RBNZ Monetary Policy Statement (MPS) / Monetary Policy Review (MPR)

キャッシュ方式:
- Redis + ファイルキャッシュ
- 発表日検出: FMPベース判定
- 通常: 1日1回更新（B2は日次更新）
"""
import io
import json
import re
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd

from core.redis_client import redis_client
from services.newzealand.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)

JST = ZoneInfo("Asia/Tokyo")
AUCKLAND = ZoneInfo("Pacific/Auckland")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "newzealand" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "nz_rbnz_rate_cache.json"

# RBNZ B2 Daily Close XLSX
B2_DAILY_URL = "https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily-close.xlsx"

# OCR列名（Excelのヘッダー）
OCR_COLUMN = "Official Cash Rate (OCR)"

# FMPイベントパターン（DB: RBNZ Interest Rate Decision）
MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


class RbnzPolicyRateService:
    """RBNZ政策金利（OCR）サービス"""

    DATA_CACHE_KEY = "newzealand:nz_rbnz_rate:data"
    ECONALPHA_ID = "nz_rbnz_rate"
    FMP_COUNTRY = "NZ"
    FMP_EVENT_PATTERN = "RBNZ Interest Rate Decision"

    def __init__(self):
        pass

    def get_nz_rbnz_rate_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """RBNZ政策金利データを取得"""
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

        # データソースから取得（B2 + DB + FMP マージ）
        result = self._load_merged_data()
        if result:
            latest = result[-1] if result else None

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Reserve Bank of New Zealand",
                    "indicator": "Official Cash Rate (OCR)",
                    "description": "RBNZ政策金利",
                    "unit": "%",
                    "frequency": "daily",
                    "table": "B2 - Wholesale Interest Rates (Daily Close)",
                },
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "rbnz_b2",
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

    def _load_merged_data(self) -> List[Dict[str, Any]]:
        """B2 Excel + DB + FMP からデータをマージ"""
        merged = {}

        # 1. RBNZ B2 Excel から取得
        b2_data = self._load_from_b2_excel()
        for item in b2_data:
            merged[item["date"]] = item

        # 2. DBから蓄積データを取得
        db_data = self._load_from_db()
        for item in db_data:
            merged[item["date"]] = item

        # 3. FMPから最新を取得（発表日当日）
        fmp_data = self._fetch_from_fmp()
        for item in fmp_data:
            merged[item["date"]] = item

        result = sorted(merged.values(), key=lambda x: x["date"])

        if result:
            print(f"[RbnzPolicyRate] Total {len(result)} records after merge")
            print(f"[RbnzPolicyRate] Date range: {result[0]['date']} to {result[-1]['date']}")
            latest = result[-1]
            print(f"[RbnzPolicyRate] Latest: {latest['date']} = {latest['value']}%")

        return result

    def _load_from_b2_excel(self) -> List[Dict[str, Any]]:
        """RBNZ B2 Daily Close XLSXからOCRデータを取得

        RBNZサイトはCloudflare CDNが Python HTTP ライブラリをブロックするため、
        curl コマンドでダウンロードする。

        Excelの構造:
        - Row 0: カテゴリヘッダー（Cash rate, Bank bill yields, ...）
        - Row 1: サブヘッダー（Official Cash Rate (OCR), ...）
        - Row 2: Notes
        - Row 3: Unit (%pa)
        - Row 4: Series Id
        - Row 5+: データ（Col 0 = datetime, Col 1 = OCR value）
        """
        try:
            import subprocess
            import tempfile
            import os

            print(f"[RbnzPolicyRate] Downloading B2 via curl from: {B2_DAILY_URL}")

            # curl でダウンロード（Cloudflare対策）
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                tmp_path = tmp.name

            try:
                proc = subprocess.run(
                    [
                        "curl", "-L", "-o", tmp_path,
                        "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                        "--max-time", "120",
                        "-s",
                        B2_DAILY_URL,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=150,
                )

                if proc.returncode != 0:
                    print(f"[RbnzPolicyRate] curl failed (exit {proc.returncode}): {proc.stderr[:200]}")
                    return []

                file_size = os.path.getsize(tmp_path)
                if file_size < 10000:
                    print(f"[RbnzPolicyRate] Downloaded file too small ({file_size} bytes), likely error page")
                    return []

                print(f"[RbnzPolicyRate] Downloaded {file_size} bytes")

                # header=None で読み込み（ヘッダー行がデータに含まれる）
                df = pd.read_excel(tmp_path, engine="openpyxl", header=None)

            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

            # データ行は Row 5 以降、Col 0 = 日付, Col 1 = OCR
            DATA_START_ROW = 5
            DATE_COL = 0
            OCR_COL = 1

            # Row 1, Col 1 でOCR列の確認
            header_check = str(df.iloc[1, 1]) if df.shape[0] > 1 else ""
            print(f"[RbnzPolicyRate] Header check (Row 1, Col 1): '{header_check}'")

            result = []
            for row_idx in range(DATA_START_ROW, df.shape[0]):
                date_val = df.iloc[row_idx, DATE_COL]
                ocr_val = df.iloc[row_idx, OCR_COL]

                if pd.isna(date_val) or pd.isna(ocr_val):
                    continue

                # 日付変換
                if isinstance(date_val, datetime):
                    date_str = date_val.strftime("%Y-%m-%d")
                elif isinstance(date_val, str):
                    try:
                        dt = pd.to_datetime(date_val)
                        date_str = dt.strftime("%Y-%m-%d")
                    except Exception:
                        continue
                else:
                    continue

                try:
                    value = round(float(ocr_val), 2)
                except (ValueError, TypeError):
                    continue

                result.append({
                    "date": date_str,
                    "value": value,
                })

            result.sort(key=lambda x: x["date"])
            print(f"[RbnzPolicyRate] B2 Excel: {len(result)} daily records")
            if result:
                print(f"[RbnzPolicyRate] B2 range: {result[0]['date']} to {result[-1]['date']}")

            return result

        except Exception as e:
            print(f"[RbnzPolicyRate] Error loading B2 Excel: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _load_from_db(self) -> List[Dict[str, Any]]:
        """DBのeconomic_calendar_eventsからRBNZ金利決定の実績データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                query = text("""
                    SELECT datetime_utc, event, actual
                    FROM economic_calendar_events
                    WHERE country = :country
                      AND event ILIKE :pattern
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query, {
                    "country": self.FMP_COUNTRY,
                    "pattern": f"%{self.FMP_EVENT_PATTERN}%",
                }).fetchall()

                result = []
                for row in rows:
                    dt_utc = row[0]
                    actual = row[2]

                    if dt_utc is None or actual is None:
                        continue

                    date_str = dt_utc.strftime("%Y-%m-%d")

                    result.append({
                        "date": date_str,
                        "value": round(float(actual), 2),
                    })

                if result:
                    print(f"[RbnzPolicyRate] DB: {len(result)} records")
                return result

        except Exception as e:
            print(f"[RbnzPolicyRate] Error loading from DB: {e}")
            return []

    def _fetch_from_fmp(self) -> List[Dict[str, Any]]:
        """FMPから最新の発表データを取得"""
        try:
            from services.calendar.fmp_service import fmp_service

            today = date.today()
            from_date = today - timedelta(days=90)
            to_date = today + timedelta(days=60)

            events = fmp_service.fetch_calendar(from_date, to_date, country=self.FMP_COUNTRY)

            result = []
            for event in events:
                if event.get("country") != self.FMP_COUNTRY:
                    continue

                event_name = event.get("event", "")
                if self.FMP_EVENT_PATTERN.lower() not in event_name.lower():
                    continue

                actual = event.get("actual")
                if actual is None:
                    continue

                dt_utc, _ = fmp_service.parse_datetime(event.get("date", ""))
                if not dt_utc:
                    continue

                date_str = dt_utc.strftime("%Y-%m-%d")
                result.append({
                    "date": date_str,
                    "value": round(float(actual), 2),
                })

            if result:
                print(f"[RbnzPolicyRate] FMP: {len(result)} records")
            return result

        except Exception as e:
            print(f"[RbnzPolicyRate] Error fetching from FMP: {e}")
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        # FMP発表日ベースの更新判定
        fmp_refresh = should_refresh_by_pattern(
            self.FMP_EVENT_PATTERN,
            last_updated_str,
            country=self.FMP_COUNTRY
        )
        if fmp_refresh:
            return True

        # B2は日次更新のため、24時間以上経過したら更新
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)
            now = datetime.now(JST)
            return (now - last_updated).total_seconds() > 86400
        except Exception:
            return False

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[RbnzPolicyRate] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[RbnzPolicyRate] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "RBNZ Official Cash Rate (OCR)",
            "source": "Reserve Bank of New Zealand",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
rbnz_policy_rate_service = RbnzPolicyRateService()
