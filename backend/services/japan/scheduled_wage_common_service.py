"""
日本 所定内給与サービス（共通事業所版）
毎月勤労統計調査データを取得

指標:
- 所定内給与 (Scheduled Wage): 所定内給与 前年同月比 (%)
- 一般 (General): 一般労働者 前年同月比 (%)
- パート (Part-time): パートタイム労働者 前年同月比 (%)

データソース（優先順位）:
1. MHLW Excel直接ダウンロード（共通事業所版）- 最新データ
2. History DB (japan_scheduled_wage_history) - ベースデータ
3. FMP economic_calendar_events - フォールバック

発表スケジュール:
- 1日〜10日: 速報値(p) 8:30 JST
- 17日〜月末: 確報値(r) 8:30 JST

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import re
import requests
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from zoneinfo import ZoneInfo
from pathlib import Path
import logging

from core.redis_client import redis_client
from services.japan.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "japan" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "scheduled_wage_common_cache.json"
TEMP_DIR = CACHE_DIR / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


class ScheduledWageCommonService:
    """日本 所定内給与サービス（共通事業所版）"""

    DATA_CACHE_KEY = "japan:employment:scheduled_wage_common:data"

    # FMP event mapping
    ECONALPHA_ID = "jp_average_cash_earnings_yoy"

    # MHLW Base URL for monthly labor statistics (共通事業所版)
    MHLW_BASE_URL = "https://www.mhlw.go.jp/toukei/itiran/roudou/monthly"
    SHEET_INDEX = 0  # Use first sheet (給与所定内)

    def __init__(self):
        pass

    def get_scheduled_wage_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        所定内給与データを取得

        データソース優先順位:
        1. MHLW Excel直接ダウンロード（共通事業所版）
        2. History DB - ベースデータ
        3. FMP DB - フォールバック

        Returns:
            {
                "scheduled_wage": {"data": [...], "latest": {...}},
                "general": {"data": [...], "latest": {...}},
                "part_time": {"data": [...], "latest": {...}},
                "next_release": {...},
                "cached": bool,
                "source": str
            }
        """
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "scheduled_wage": cached_data.get("scheduled_wage"),
                        "general": cached_data.get("general"),
                        "part_time": cached_data.get("part_time"),
                        "next_release": cached_data.get("next_release"),
                        "data_type": cached_data.get("data_type"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # 1. MHLW Excelから最新データを取得
        mhlw_data, data_type = self._load_from_mhlw()

        # 2. History DBからベースデータを取得
        db_data = self._load_from_history_db()

        # データをマージ（MHLW > DB）
        merged_data = self._merge_data(db_data, mhlw_data)

        if merged_data:
            # MHLWで新しいデータがあれば、DBにも保存
            if mhlw_data:
                self._save_to_history_db(mhlw_data)

            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            cache_payload = {
                "scheduled_wage": merged_data.get("scheduled_wage"),
                "general": merged_data.get("general"),
                "part_time": merged_data.get("part_time"),
                "next_release": next_release,
                "data_type": data_type,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            source = "History DB + MHLW Excel" if db_data and mhlw_data else (
                "MHLW Excel" if mhlw_data else "History DB"
            )
            return {
                **cache_payload,
                "cached": False,
                "source": source,
            }

        # 3. フォールバック: FMP DBから取得
        fmp_data = self._load_from_fmp_db()
        if fmp_data:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            cache_payload = {
                "scheduled_wage": {
                    "data": fmp_data,
                    "latest": fmp_data[-1] if fmp_data else None,
                },
                "general": None,
                "part_time": None,
                "next_release": next_release,
                "data_type": None,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                **cache_payload,
                "cached": False,
                "source": "FMP DB (fallback)",
            }

        # 4. ファイルキャッシュからフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "scheduled_wage": file_cache.get("scheduled_wage"),
                "general": file_cache.get("general"),
                "part_time": file_cache.get("part_time"),
                "next_release": file_cache.get("next_release"),
                "data_type": file_cache.get("data_type"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "scheduled_wage": None,
            "general": None,
            "part_time": None,
            "next_release": None,
            "data_type": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _get_current_url(self) -> Tuple[str, str]:
        """
        現在の日付に基づいて適切なURLを取得

        発表スケジュール:
        - 速報値(p): 毎月1-10日に前月分を公開
        - 確報値(r): 毎月17-31日に前々月分を公開

        Returns:
            Tuple of (url, data_type) where data_type is 'preliminary' or 'revised'
        """
        now = datetime.now(JST)
        day = now.day

        if 1 <= day <= 10:
            # 速報値: 前月分
            if now.month == 1:
                target_year = now.year - 1
                target_month = 12
            else:
                target_year = now.year
                target_month = now.month - 1

            reiwa_year = target_year - 2018  # 令和元年 = 2019
            year_month = f"{target_year % 100:02d}{target_month:02d}"  # YYMM format
            url = f"{self.MHLW_BASE_URL}/r{reiwa_year:02d}/{year_month}p/xls/kyo{year_month}p.xlsx"
            return url, "preliminary"
        else:
            # 確報値: 前々月分
            if now.month <= 2:
                if now.month == 1:
                    target_year = now.year - 1
                    target_month = 11
                elif now.month == 2:
                    target_year = now.year - 1
                    target_month = 12
            else:
                target_year = now.year
                target_month = now.month - 2

            reiwa_year = target_year - 2018
            year_month = f"{target_year % 100:02d}{target_month:02d}"
            url = f"{self.MHLW_BASE_URL}/r{reiwa_year:02d}/{year_month}r/xls/kyo{year_month}r.xlsx"
            return url, "revised"

    def _get_fallback_url(self) -> Tuple[str, str]:
        """
        フォールバックURLを取得（前月のデータ）

        Returns:
            Tuple of (url, data_type)
        """
        now = datetime.now(JST)
        day = now.day

        if 1 <= day <= 10:
            # 速報期間中なら、前月の確報を試す
            if now.month <= 2:
                if now.month == 1:
                    target_year = now.year - 1
                    target_month = 11
                elif now.month == 2:
                    target_year = now.year - 1
                    target_month = 12
            else:
                target_year = now.year
                target_month = now.month - 2

            reiwa_year = target_year - 2018
            year_month = f"{target_year % 100:02d}{target_month:02d}"
            url = f"{self.MHLW_BASE_URL}/r{reiwa_year:02d}/{year_month}r/xls/kyo{year_month}r.xlsx"
            return url, "revised"
        else:
            # 確報期間中なら、同月の速報を試す
            if now.month <= 2:
                if now.month == 1:
                    target_year = now.year - 1
                    target_month = 11
                elif now.month == 2:
                    target_year = now.year - 1
                    target_month = 12
            else:
                target_year = now.year
                target_month = now.month - 2

            reiwa_year = target_year - 2018
            year_month = f"{target_year % 100:02d}{target_month:02d}"
            url = f"{self.MHLW_BASE_URL}/r{reiwa_year:02d}/{year_month}p/xls/kyo{year_month}p.xlsx"
            return url, "preliminary"

    def _download_excel_file(self) -> Optional[Tuple[Path, str]]:
        """
        MHLWから毎月勤労統計Excelをダウンロード

        Returns:
            Tuple of (Path to downloaded Excel file, data_type) or (None, None) if failed
        """
        try:
            url, data_type = self._get_current_url()
            logger.info(f"Downloading monthly labor data ({data_type}) from {url}")

            response = requests.get(url, timeout=60)

            # 404の場合、フォールバックURLを試す
            if response.status_code == 404:
                logger.warning(f"404 error for {url}, trying fallback...")
                url_fallback, data_type_fallback = self._get_fallback_url()
                logger.info(f"Trying fallback URL: {url_fallback}")

                response = requests.get(url_fallback, timeout=60)
                if response.status_code != 200:
                    logger.error(f"Fallback URL also failed: {response.status_code}")
                    return None, None
                data_type = data_type_fallback
            elif response.status_code != 200:
                logger.error(f"Failed to download: {response.status_code}")
                return None, None

            # Excelファイルを保存
            excel_path = TEMP_DIR / f"monthly_labor_{data_type}.xlsx"
            excel_path.write_bytes(response.content)

            logger.info(f"Downloaded {len(response.content)} bytes")
            return excel_path, data_type

        except Exception as e:
            logger.error(f"Error downloading monthly labor data: {e}")
            return None, None

    def _load_from_mhlw(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """MHLWから所定内給与データを取得"""
        try:
            download_result = self._download_excel_file()
            if not download_result or not download_result[0]:
                return None, None

            excel_path, data_type = download_result

            # Parse Excel
            processed_data = self._parse_excel_file(excel_path)
            if not processed_data:
                return None, None

            # Clean up temp files
            try:
                for file in TEMP_DIR.glob("*"):
                    if file.is_file():
                        file.unlink()
            except Exception as e:
                logger.warning(f"Error cleaning up temp files: {e}")

            return processed_data, data_type

        except Exception as e:
            logger.error(f"Error fetching scheduled wage data from MHLW: {e}")
            import traceback
            traceback.print_exc()
            return None, None

    def _parse_excel_file(self, excel_path: Path) -> Optional[Dict[str, Any]]:
        """毎月勤労統計Excelを解析"""
        try:
            logger.info(f"Parsing monthly labor Excel file: {excel_path}")

            # Read first sheet (給与所定内) by index to avoid encoding issues
            df = pd.read_excel(excel_path, sheet_name=self.SHEET_INDEX, header=None)
            logger.info(f"Excel shape: {df.shape}")

            return self._process_scheduled_wage_dataframe(df)

        except Exception as e:
            logger.error(f"Error parsing monthly labor Excel: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _process_scheduled_wage_dataframe(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        毎月勤労統計データを処理

        Excel structure (給与所定内 sheet):
        Row 0-13: Headers
        Row 14+: Data (starting with "令和X年Y月")
        Column 1 (B): Year-Month (年月)
        Column 9 (J): 所定内給与 YoY (%)
        Column 10 (K): 一般 YoY (%)
        Column 11 (L): パート YoY (%)
        """
        try:
            logger.info(f"Processing monthly labor dataframe with shape: {df.shape}")

            scheduled_wage_data = []  # 所定内給与 (Column J)
            general_data = []  # 一般 (Column K)
            part_time_data = []  # パート (Column L)

            current_year = None
            first_year_found = False

            # Start from row 14 (data starts after headers)
            for idx in range(14, len(df)):
                try:
                    row = df.iloc[idx]

                    # Get year-month from column 1 (B)
                    date_val = row[1]

                    if pd.isna(date_val):
                        continue

                    date_str = str(date_val).strip()

                    # Check for section break (empty row or header row like "年　月")
                    if not date_str or date_str == '年　月' or date_str == '年月':
                        # If we've already processed data, this marks the start of second section
                        if first_year_found:
                            logger.info(f"Reached section break at row {idx}, stopping")
                            break
                        continue

                    # Skip note rows
                    if '注' in date_str or 'Note' in date_str:
                        continue

                    # Parse date
                    # Check if this is a year row (contains 年)
                    if '年' in date_str:
                        # Extract year
                        year_match = re.search(r'令和(\d+)年', date_str)
                        if year_match:
                            era_year = int(year_match.group(1))
                            current_year = 2018 + era_year  # 令和元年 = 2019
                            first_year_found = True
                        else:
                            # Try other patterns
                            year_match = re.search(r'(\d+)年', date_str)
                            if year_match:
                                era_year = int(year_match.group(1))
                                if era_year <= 10:  # Likely Reiwa
                                    current_year = 2018 + era_year
                                elif era_year < 100:  # Heisei
                                    current_year = 1988 + era_year
                                else:  # Western year
                                    current_year = era_year
                                first_year_found = True

                        # Check if there's also a month in this row
                        month_match = re.search(r'(\d+)月', date_str)
                        if month_match:
                            month = int(month_match.group(1))
                        else:
                            # Year-only row, skip
                            continue
                    else:
                        # Month-only row
                        month_match = re.search(r'(\d+)月', date_str)
                        if month_match:
                            month = int(month_match.group(1))
                        else:
                            continue

                    if current_year is None:
                        continue

                    # Create date string
                    date_string = f"{current_year}-{month:02d}-01"

                    # Get values from columns J, K, L (indices 9, 10, 11)
                    col_j = row[9]   # 所定内給与
                    col_k = row[10]  # 一般
                    col_l = row[11]  # パート

                    # Add scheduled wage data
                    if pd.notna(col_j) and col_j != '':
                        try:
                            value = float(col_j)
                            scheduled_wage_data.append({
                                "date": date_string,
                                "value": round(value, 1)
                            })
                        except (ValueError, TypeError):
                            pass

                    # Add general worker data
                    if pd.notna(col_k) and col_k != '':
                        try:
                            value = float(col_k)
                            general_data.append({
                                "date": date_string,
                                "value": round(value, 1)
                            })
                        except (ValueError, TypeError):
                            pass

                    # Add part-time worker data
                    if pd.notna(col_l) and col_l != '':
                        try:
                            value = float(col_l)
                            part_time_data.append({
                                "date": date_string,
                                "value": round(value, 1)
                            })
                        except (ValueError, TypeError):
                            pass

                except Exception as e:
                    logger.debug(f"Error processing row {idx}: {e}")
                    continue

            # Sort by date
            scheduled_wage_data.sort(key=lambda x: x["date"])
            general_data.sort(key=lambda x: x["date"])
            part_time_data.sort(key=lambda x: x["date"])

            # Filter to data from 2000 onwards
            cutoff_date = "2000-01-01"
            scheduled_wage_data = [point for point in scheduled_wage_data if point["date"] >= cutoff_date]
            general_data = [point for point in general_data if point["date"] >= cutoff_date]
            part_time_data = [point for point in part_time_data if point["date"] >= cutoff_date]

            logger.info(f"Processed: {len(scheduled_wage_data)} scheduled, {len(general_data)} general, {len(part_time_data)} part-time")

            if scheduled_wage_data:
                logger.info(f"Date range: {scheduled_wage_data[0]['date']} to {scheduled_wage_data[-1]['date']}")

            return {
                "scheduled_wage": {
                    "data": scheduled_wage_data,
                    "latest": scheduled_wage_data[-1] if scheduled_wage_data else None,
                },
                "general": {
                    "data": general_data,
                    "latest": general_data[-1] if general_data else None,
                },
                "part_time": {
                    "data": part_time_data,
                    "latest": part_time_data[-1] if part_time_data else None,
                },
            }

        except Exception as e:
            logger.error(f"Error processing monthly labor dataframe: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _load_from_fmp_db(self) -> List[Dict[str, Any]]:
        """FMP economic_calendar_eventsからAverage Cash Earnings YoYデータを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                query = text("""
                    SELECT datetime_utc, event, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'JP'
                      AND event ILIKE :pattern
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query, {"pattern": "%Average Cash Earnings YoY%"}).fetchall()

                result = []
                month_map = {
                    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                }

                for row in rows:
                    dt_utc, event, actual, estimate, previous = row
                    if dt_utc:
                        # イベント名から対象月を抽出 (例: "Average Cash Earnings YoY (Nov)")
                        match = re.search(r'\((\w{3})\)', event)
                        if match:
                            month_abbr = match.group(1).lower()
                            if month_abbr in month_map:
                                target_month = month_map[month_abbr]
                                target_year = dt_utc.year
                                # 発表月より対象月が大きい場合は前年
                                if target_month > dt_utc.month:
                                    target_year -= 1
                                date_str = f"{target_year}-{target_month:02d}-01"
                            else:
                                continue
                        else:
                            continue

                        # 重複チェック
                        existing_idx = None
                        for i, existing in enumerate(result):
                            if existing["date"] == date_str:
                                existing_idx = i
                                break

                        data_point = {
                            "date": date_str,
                            "value": float(actual) if actual else None,
                            "forecast": float(estimate) if estimate else None,
                            "previous": float(previous) if previous else None,
                        }

                        if existing_idx is not None:
                            result[existing_idx] = data_point
                        else:
                            result.append(data_point)

                logger.info(f"Loaded {len(result)} Average Cash Earnings YoY records from FMP DB")
                return result

        except Exception as e:
            logger.error(f"Error loading Average Cash Earnings from DB: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _load_from_history_db(self) -> Optional[Dict[str, Any]]:
        """History DBから所定内給与データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                rows = session.execute(text("""
                    SELECT date, scheduled_wage_yoy, general_yoy, part_time_yoy
                    FROM japan_scheduled_wage_history
                    WHERE scheduled_wage_yoy IS NOT NULL
                    ORDER BY date ASC
                """)).fetchall()

                if not rows:
                    logger.info("No data found in History DB")
                    return None

                scheduled_wage_data = []
                general_data = []
                part_time_data = []

                for row in rows:
                    date_str = row[0].strftime("%Y-%m-%d") if hasattr(row[0], 'strftime') else str(row[0])

                    if row[1] is not None:
                        scheduled_wage_data.append({
                            "date": date_str,
                            "value": float(row[1])
                        })

                    if row[2] is not None:
                        general_data.append({
                            "date": date_str,
                            "value": float(row[2])
                        })

                    if row[3] is not None:
                        part_time_data.append({
                            "date": date_str,
                            "value": float(row[3])
                        })

                logger.info(f"Loaded {len(scheduled_wage_data)} records from History DB")

                return {
                    "scheduled_wage": {
                        "data": scheduled_wage_data,
                        "latest": scheduled_wage_data[-1] if scheduled_wage_data else None,
                    },
                    "general": {
                        "data": general_data,
                        "latest": general_data[-1] if general_data else None,
                    },
                    "part_time": {
                        "data": part_time_data,
                        "latest": part_time_data[-1] if part_time_data else None,
                    },
                }

        except Exception as e:
            logger.error(f"Error loading from History DB: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _merge_data(
        self,
        db_data: Optional[Dict[str, Any]],
        estat_data: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        DBデータとe-Statデータをマージ
        e-Statデータで上書き（より新しいデータを優先）
        """
        if not db_data and not estat_data:
            return None

        if not db_data:
            return estat_data

        if not estat_data:
            return db_data

        # マージ処理
        result = {
            "scheduled_wage": {"data": [], "latest": None},
            "general": {"data": [], "latest": None},
            "part_time": {"data": [], "latest": None},
        }

        for key in ["scheduled_wage", "general", "part_time"]:
            db_series = db_data.get(key, {}).get("data", []) if db_data.get(key) else []
            estat_series = estat_data.get(key, {}).get("data", []) if estat_data.get(key) else []

            # 日付をキーにしてマージ（e-Statが優先）
            merged_map = {}
            for item in db_series:
                merged_map[item["date"]] = item
            for item in estat_series:
                merged_map[item["date"]] = item  # 上書き

            # ソートしてリストに
            merged_list = sorted(merged_map.values(), key=lambda x: x["date"])

            result[key] = {
                "data": merged_list,
                "latest": merged_list[-1] if merged_list else None,
            }

        return result

    def _save_to_history_db(self, data: Dict[str, Any]) -> None:
        """MHLWから取得したデータをHistory DBに保存"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            sw_data = data.get("scheduled_wage", {}).get("data", []) if data.get("scheduled_wage") else []
            gen_data = data.get("general", {}).get("data", []) if data.get("general") else []
            pt_data = data.get("part_time", {}).get("data", []) if data.get("part_time") else []

            # 日付でマージ
            date_set = set()
            for d in sw_data:
                date_set.add(d['date'])
            for d in gen_data:
                date_set.add(d['date'])
            for d in pt_data:
                date_set.add(d['date'])

            sw_map = {d['date']: d['value'] for d in sw_data}
            gen_map = {d['date']: d['value'] for d in gen_data}
            pt_map = {d['date']: d['value'] for d in pt_data}

            with SessionLocal() as session:
                saved = 0
                for date in date_set:
                    try:
                        session.execute(text("""
                            INSERT INTO japan_scheduled_wage_history (
                                date, scheduled_wage_yoy, general_yoy, part_time_yoy,
                                source, updated_at
                            ) VALUES (
                                :date, :scheduled_wage_yoy, :general_yoy, :part_time_yoy,
                                'MHLW Excel', NOW()
                            )
                            ON CONFLICT (date) DO UPDATE SET
                                scheduled_wage_yoy = COALESCE(EXCLUDED.scheduled_wage_yoy, japan_scheduled_wage_history.scheduled_wage_yoy),
                                general_yoy = COALESCE(EXCLUDED.general_yoy, japan_scheduled_wage_history.general_yoy),
                                part_time_yoy = COALESCE(EXCLUDED.part_time_yoy, japan_scheduled_wage_history.part_time_yoy),
                                source = 'MHLW Excel',
                                updated_at = NOW()
                        """), {
                            'date': date,
                            'scheduled_wage_yoy': sw_map.get(date),
                            'general_yoy': gen_map.get(date),
                            'part_time_yoy': pt_map.get(date),
                        })
                        saved += 1
                    except Exception as e:
                        logger.warning(f"Error saving {date} to History DB: {e}")

                session.commit()
                logger.info(f"Saved {saved} records to History DB")

        except Exception as e:
            logger.error(f"Error saving to History DB: {e}")

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_fmp_schedule(
            self.ECONALPHA_ID,
            last_updated_str
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            logger.error(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        scheduled_wage_count = 0
        general_count = 0
        part_time_count = 0

        if cached_data:
            sw = cached_data.get("scheduled_wage")
            gen = cached_data.get("general")
            pt = cached_data.get("part_time")
            scheduled_wage_count = len(sw.get("data", [])) if sw else 0
            general_count = len(gen.get("data", [])) if gen else 0
            part_time_count = len(pt.get("data", [])) if pt else 0

        return {
            "indicator": "JP Scheduled Wage (所定内給与 - 共通事業所版)",
            "source": "MHLW (厚生労働省) / FMP DB",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_type": cached_data.get("data_type") if cached_data else None,
            "data_count": {
                "scheduled_wage": scheduled_wage_count,
                "general": general_count,
                "part_time": part_time_count,
            },
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
scheduled_wage_common_service = ScheduledWageCommonService()
