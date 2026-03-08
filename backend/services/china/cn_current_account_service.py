"""
中国 経常収支（Current Account）サービス

データソース:
- SAFE (State Administration of Foreign Exchange)
- Balance of Payments quarterly(USD) シート
- Row 5: "1. Current account" = 経常収支合計
- 単位: 100 million USD（億USD）

FMP: 次回発表日 + 最新値の補完
- FMPの単位は B (十億USD) → 億USDに変換して結合

取得方法:
1. SAFE Excel (quarterly(USD)シート) → Row 5 の経常収支を取得
2. QoQ差分・YoY差分を計算
3. FMPから最新四半期の値を補完（SAFEが未更新の場合）

発表スケジュール: 四半期
"""
import io
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd
import requests

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# キャッシュ設定
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "china" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "cn_current_account_cache.json"

# SAFE Excel URL
SAFE_EXCEL_URL = (
    "https://www.safe.gov.cn/en/file/file/20251231/"
    "4fb0399bcbc74ad8a823cd1f72f0d57b.xlsx"
    "?n=The%20time-series%20data%20of%20Balance%20of%20Payments%20of%20China"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

# SAFE Excelの構造
# Row 3: ヘッダー行 (Col 0=Item, Col 1..=1998Q1, 1998Q2, ...)
# Row 5: "1. Current account" の行
SAFE_SHEET_NAME = "quarterly(USD)"
SAFE_HEADER_ROW = 3
SAFE_CURRENT_ACCOUNT_ROW = 5


def _quarter_to_date(quarter_str: str) -> Optional[str]:
    """四半期文字列(e.g. '2024Q3')をYYYY-MM-01形式に変換"""
    match = re.match(r"(\d{4})Q([1-4])", str(quarter_str).strip())
    if not match:
        return None
    year = int(match.group(1))
    q = int(match.group(2))
    month = {1: 3, 2: 6, 3: 9, 4: 12}[q]
    return f"{year}-{month:02d}-01"


class CnCurrentAccountService:
    """中国経常収支サービス"""

    DATA_CACHE_KEY = "china:cn_current_account:data"
    FMP_EVENT_PATTERN = "Current Account"
    FMP_COUNTRY = "CN"
    ECONALPHA_ID = "cn_current_account"

    def __init__(self):
        pass

    def _download_safe_excel(self) -> Optional[bytes]:
        """SAFE ExcelファイルをダウンロードW"""
        try:
            logger.info(f"Downloading SAFE Excel from {SAFE_EXCEL_URL[:80]}...")
            resp = requests.get(SAFE_EXCEL_URL, headers=HEADERS, timeout=60)
            if resp.status_code != 200:
                logger.error(f"SAFE Excel download returned HTTP {resp.status_code}")
                return None
            logger.info(f"SAFE Excel downloaded: {len(resp.content)} bytes")
            return resp.content
        except Exception as e:
            logger.error(f"Error downloading SAFE Excel: {e}")
            return None

    def _parse_excel(self, excel_bytes: bytes) -> List[Dict[str, Any]]:
        """Excelから経常収支データを抽出

        構造:
        - Sheet: quarterly(USD)
        - Row 3: ヘッダー (Item, 1998Q1, 1998Q2, ...)
        - Row 5: "1. Current account" の値
        - 単位: 100 million USD (億USD)
        """
        try:
            df = pd.read_excel(
                io.BytesIO(excel_bytes),
                sheet_name=SAFE_SHEET_NAME,
                header=None,
            )

            # ヘッダー行から四半期カラムを取得
            headers = df.iloc[SAFE_HEADER_ROW]

            # データ行
            data_row = df.iloc[SAFE_CURRENT_ACCOUNT_ROW]

            data_points = []
            for col_idx in range(1, len(headers)):
                quarter_label = headers.iloc[col_idx]
                if pd.isna(quarter_label):
                    continue

                date_str = _quarter_to_date(str(quarter_label))
                if not date_str:
                    continue

                val = data_row.iloc[col_idx]
                if pd.isna(val):
                    continue

                try:
                    value = round(float(val), 1)
                except (ValueError, TypeError):
                    continue

                data_points.append({
                    "date": date_str,
                    "value": value,
                })

            data_points.sort(key=lambda x: x["date"])
            logger.info(f"Parsed {len(data_points)} current account data points from SAFE Excel")
            if data_points:
                logger.info(f"  Range: {data_points[0]['date']} ~ {data_points[-1]['date']}")
                logger.info(f"  Latest: {data_points[-1]['date']} = {data_points[-1]['value']}")

            return data_points

        except Exception as e:
            logger.error(f"Error parsing SAFE Current Account Excel: {e}")
            return []

    def _merge_fmp_latest(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """FMPから最新四半期の値を取得してマージ

        FMPの値はB(十億USD) → 億USDに変換 (×10)
        SAFEが未更新の四半期のデータを補完する

        取得元: DB (economic_calendar_events) → FMP API フォールバック
        """
        try:
            events = self._fetch_fmp_past_events()
            if not events:
                return data

            existing_dates = {p["date"] for p in data}

            for event in events:
                actual = event.get("actual")
                if actual is None:
                    continue

                # FMP eventから四半期を抽出: "Current Account (Q3)" → Q3
                event_name = event.get("event", "")
                q_match = re.search(r"\(Q([1-4])\)", event_name)
                if not q_match:
                    continue

                # イベント日付から年を取得
                event_date = event.get("date", "")
                if not event_date:
                    continue

                # FMPの日付からイベントの実際の四半期年を推定
                # "Current Account (Q4)" released in 2026-02-14 → 2025Q4
                # "Current Account (Q1)" released in 2025-06-27 → 2025Q1
                q_num = int(q_match.group(1))
                event_year = int(event_date[:4])
                event_month = int(event_date[5:7])

                # 発表月から四半期の年を推定
                # Q1: 3月末 → 発表6月頃 → 同年
                # Q2: 6月末 → 発表8-9月頃 → 同年
                # Q3: 9月末 → 発表11-12月頃 → 同年
                # Q4: 12月末 → 発表2-4月頃 → 前年
                data_year = event_year
                if q_num == 4 and event_month <= 6:
                    data_year = event_year - 1

                data_month = {1: 3, 2: 6, 3: 9, 4: 12}[q_num]
                date_str = f"{data_year}-{data_month:02d}-01"

                if date_str in existing_dates:
                    continue

                # B (十億USD) → 億USD (×10)
                value_100m = round(actual * 10, 1)

                data.append({
                    "date": date_str,
                    "value": value_100m,
                })
                existing_dates.add(date_str)
                logger.info(f"[CA] FMP補完: {date_str} = {value_100m} (from FMP {actual}B)")

            data.sort(key=lambda x: x["date"])
            return data

        except Exception as e:
            logger.warning(f"[CA] FMP merge failed: {e}")
            return data

    def _fetch_fmp_past_events(self) -> List[Dict[str, Any]]:
        """FMP経済カレンダーから過去のCurrent Accountイベントを取得

        DBのactual値はバックフィルが遅れることがあるため、
        直近90日分はFMP APIから直接取得して補完する
        """
        all_events: Dict[str, Dict[str, Any]] = {}  # key: event_date

        # 1. DBから過去イベントを取得（高速・大量）
        try:
            from core.database import get_db_connection
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT event, datetime_utc::text AS date, actual
                    FROM economic_calendar_events
                    WHERE country = %s
                      AND event ILIKE %s
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc DESC
                    LIMIT 20
                """, (self.FMP_COUNTRY, f"%{self.FMP_EVENT_PATTERN}%"))
                rows = cursor.fetchall()
                cursor.close()

                for row in rows:
                    ev = {
                        "event": row[0],
                        "date": row[1][:10] if row[1] else "",
                        "actual": float(row[2]) if row[2] is not None else None,
                    }
                    key = f"{ev['event']}_{ev['date']}"
                    all_events[key] = ev

                if rows:
                    logger.info(f"[CA] Got {len(rows)} past events from DB")
        except Exception as e:
            logger.warning(f"[CA] DB query failed: {e}")

        # 2. FMP APIから直近90日分を取得（DBバックフィル遅延を補完）
        try:
            from services.calendar.fmp_service import fmp_service
            from datetime import date as date_type, timedelta

            today = date_type.today()
            raw_events = fmp_service.fetch_calendar(
                today - timedelta(days=90),
                today,
                country=self.FMP_COUNTRY,
            )

            pattern_lower = self.FMP_EVENT_PATTERN.lower()
            api_count = 0
            for ev in raw_events:
                if ev.get("country") != self.FMP_COUNTRY:
                    continue
                ev_name = ev.get("event", "")
                if pattern_lower not in ev_name.lower():
                    continue
                if ev.get("actual") is None:
                    continue

                entry = {
                    "event": ev_name,
                    "date": ev.get("date", "")[:10],
                    "actual": ev.get("actual"),
                }
                key = f"{entry['event']}_{entry['date']}"
                if key not in all_events:
                    all_events[key] = entry
                    api_count += 1

            if api_count:
                logger.info(f"[CA] Got {api_count} additional events from FMP API")

        except Exception as e:
            logger.warning(f"[CA] FMP API fetch failed: {e}")

        return list(all_events.values())

    def _calculate_changes(self, data: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """QoQ差分とYoY差分を算出"""
        qoq_diff = []
        yoy_diff = []
        date_map = {p["date"]: p["value"] for p in data}

        for i, point in enumerate(data):
            val = point["value"]

            # QoQ差分（前四半期との差）
            if i >= 1:
                prev_val = data[i - 1]["value"]
                if prev_val is not None:
                    qoq_diff.append({
                        "date": point["date"],
                        "value": round(val - prev_val, 1),
                    })

            # YoY差分（前年同期との差）
            dt = datetime.strptime(point["date"], "%Y-%m-%d")
            prev_year_date = f"{dt.year - 1:04d}-{dt.month:02d}-01"
            if prev_year_date in date_map:
                prev_year_val = date_map[prev_year_date]
                if prev_year_val is not None:
                    yoy_diff.append({
                        "date": point["date"],
                        "value": round(val - prev_year_val, 1),
                    })

        return {"qoq_diff": qoq_diff, "yoy_diff": yoy_diff}

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュ更新判定（FMP発表日ベース）"""
        try:
            from services.china.fmp_next_release_utils import should_refresh_by_pattern
            return should_refresh_by_pattern(
                self.FMP_EVENT_PATTERN,
                last_updated_str,
                country=self.FMP_COUNTRY,
            )
        except Exception as e:
            logger.error(f"Error in should_refresh: {e}")
            return False

    def _get_next_release(self) -> Optional[Dict[str, str]]:
        """次回発表日を取得"""
        try:
            from services.china.fmp_next_release_utils import get_next_release_by_pattern
            return get_next_release_by_pattern(
                self.FMP_EVENT_PATTERN,
                country=self.FMP_COUNTRY,
            )
        except Exception as e:
            logger.warning(f"Failed to get next release: {e}")
            return None

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """経常収支データを取得（キャッシュ付き）"""
        next_release = self._get_next_release()

        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "qoq_diff": cached_data.get("qoq_diff", []),
                        "yoy_diff": cached_data.get("yoy_diff", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                    }

        # SAFE Excelからデータ取得
        excel_bytes = self._download_safe_excel()
        if excel_bytes:
            raw_data = self._parse_excel(excel_bytes)
            if raw_data:
                # FMPから最新値を補完
                raw_data = self._merge_fmp_latest(raw_data)

                changes = self._calculate_changes(raw_data)
                latest = raw_data[-1] if raw_data else None

                result = {
                    "data": raw_data,
                    "qoq_diff": changes["qoq_diff"],
                    "yoy_diff": changes["yoy_diff"],
                    "latest": latest,
                    "metadata": {
                        "source": "SAFE (State Administration of Foreign Exchange)",
                        "indicator": "Current Account",
                        "frequency": "quarterly",
                        "unit": "100 million USD",
                    },
                    "next_release": next_release,
                }
                cache_payload = {
                    **result,
                    "last_updated": datetime.now(JST).isoformat(),
                }
                redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
                self._save_file_cache(cache_payload)

                logger.info(f"CN Current Account: {len(raw_data)} records")
                if latest:
                    logger.info(f"Latest: {latest['date']} = {latest['value']}")

                return result

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "qoq_diff": file_cache.get("qoq_diff", []),
                "yoy_diff": file_cache.get("yoy_diff", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
            }

        return {
            "data": [], "qoq_diff": [], "yoy_diff": [],
            "latest": None,
            "metadata": {"source": "SAFE", "error": "No data available"},
            "next_release": next_release,
        }

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> Dict[str, Any]:
        redis_client.delete(self.DATA_CACHE_KEY)
        if DATA_CACHE_FILE.exists():
            DATA_CACHE_FILE.unlink()
        return {"success": True, "message": "Current Account cache invalidated"}

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        return {
            "indicator": "CN Current Account",
            "source": "SAFE",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
            "next_release": self._get_next_release(),
        }


# シングルトン
cn_current_account_service = CnCurrentAccountService()
