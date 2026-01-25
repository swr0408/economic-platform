"""
日本 所定内給与サービス（e-Stat版）
毎月勤労統計調査データを取得

指標:
- 所定内給与 (Scheduled Wage): 所定内給与 前年同月比 (%)
- 一般 (General): 一般労働者 前年同月比 (%)
- パート (Part-time): パートタイム労働者 所定内給与 前年同月比 (%)
- パート時間当 (Part-time Hourly): パートタイム労働者 時間当たり所定内給与 前年同月比 (%)
  注: 厚労省は実額（円）から時間当たり給与を計算し、前年比を算出

データソース: e-Stat Excel（直接ダウンロード）
- 毎月勤労統計調査の時系列データ
- https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032189732&fileKind=4 (所定内給与)
- https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032189734&fileKind=4 (一般)
- https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032189736&fileKind=4 (パート)
- https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040187500&fileKind=4 (パート時間当: Sheet 9)

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import re
import requests
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path
from io import BytesIO
import logging

from core.redis_client import redis_client
from services.japan.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "scheduled_wage_estat_cache.json"


class ScheduledWageService:
    """日本 所定内給与サービス（e-Stat版）"""

    DATA_CACHE_KEY = "japan:employment:scheduled_wage:data"

    # FMP event mapping
    ECONALPHA_ID = "jp_average_cash_earnings_yoy"

    # e-Stat Excel直接ダウンロードURL
    # 所定内給与: https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032189732&fileKind=4
    # 一般: https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032189734&fileKind=4
    # パート: https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032189736&fileKind=4
    # パート時間当: https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040187500&fileKind=4 (Sheet 9)
    ESTAT_SCHEDULED_WAGE_URL = "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032189732&fileKind=4"
    ESTAT_GENERAL_URL = "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032189734&fileKind=4"
    ESTAT_PARTTIME_WAGE_URL = "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032189736&fileKind=4"
    ESTAT_HOURLY_WAGE_URL = "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040187500&fileKind=4"

    def __init__(self):
        pass

    def get_scheduled_wage_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        所定内給与データを取得

        Returns:
            {
                "scheduled_wage": {"data": [...], "latest": {...}},
                "general": {"data": [...], "latest": {...}},
                "part_time_wage": {"data": [...], "latest": {...}},
                "part_time_hourly": {"data": [...], "latest": {...}},
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
                        "part_time_wage": cached_data.get("part_time_wage"),
                        "part_time_hourly": cached_data.get("part_time_hourly"),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # 1. e-Statから最新データを取得
        estat_data = self._load_from_estat()

        # 2. History DBからベースデータを取得
        db_data = self._load_from_history_db()

        # データをマージ（e-Stat > DB）
        merged_data = self._merge_data(db_data, estat_data)

        if merged_data:
            # e-Statで新しいデータがあれば、DBにも保存
            if estat_data:
                self._save_to_history_db(estat_data)

            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            cache_payload = {
                "scheduled_wage": merged_data.get("scheduled_wage"),
                "general": merged_data.get("general"),
                "part_time_wage": merged_data.get("part_time_wage"),
                "part_time_hourly": merged_data.get("part_time_hourly"),
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            source = "History DB + e-Stat" if db_data and estat_data else (
                "e-Stat" if estat_data else "History DB"
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
                "part_time_wage": None,
                "part_time_hourly": None,
                "next_release": next_release,
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
                "part_time_wage": file_cache.get("part_time_wage"),
                "part_time_hourly": file_cache.get("part_time_hourly"),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "scheduled_wage": None,
            "general": None,
            "part_time_wage": None,
            "part_time_hourly": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _load_from_estat(self) -> Optional[Dict[str, Any]]:
        """e-Statから所定内給与データを取得（4系列：所定内給与、一般、パート、パート時間当）"""
        try:
            # 所定内給与、一般、パートを取得
            scheduled_wage_data = self._load_single_series(
                self.ESTAT_SCHEDULED_WAGE_URL,
                "所定内給与",
                search_start_row=80
            )
            general_data = self._load_single_series(
                self.ESTAT_GENERAL_URL,
                "一般",
                search_start_row=80
            )
            part_time_wage_data = self._load_single_series(
                self.ESTAT_PARTTIME_WAGE_URL,
                "パート",
                search_start_row=80
            )

            # パート時間当を取得（時間当たり所定内給与シート）
            part_time_hourly_data = self._load_part_time_hourly()

            if scheduled_wage_data or general_data or part_time_wage_data or part_time_hourly_data:
                return {
                    "scheduled_wage": {
                        "data": scheduled_wage_data,
                        "latest": scheduled_wage_data[-1] if scheduled_wage_data else None,
                    } if scheduled_wage_data else None,
                    "general": {
                        "data": general_data,
                        "latest": general_data[-1] if general_data else None,
                    } if general_data else None,
                    "part_time_wage": {
                        "data": part_time_wage_data,
                        "latest": part_time_wage_data[-1] if part_time_wage_data else None,
                    } if part_time_wage_data else None,
                    "part_time_hourly": {
                        "data": part_time_hourly_data,
                        "latest": part_time_hourly_data[-1] if part_time_hourly_data else None,
                    } if part_time_hourly_data else None,
                }

            return None

        except Exception as e:
            logger.error(f"Error fetching scheduled wage data from e-Stat: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _load_part_time_hourly(self) -> Optional[List[Dict[str, Any]]]:
        """
        パート時間当（時間当たり所定内給与）を取得

        e-Stat Excel（時間当たり給与シート）から直接前年比を取得
        データソース: https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040187500&fileKind=4
        注: 厚労省は実額（円）から時間当たり給与を計算し、前年比を算出
        """
        # e-Statから時間当たり給与データを取得（唯一のデータソース）
        result = self._load_hourly_wage_from_estat()

        if result:
            logger.info(f"Processed {len(result)} part-time hourly data points from e-Stat")
            if result:
                logger.info(f"Date range: {result[0]['date']} to {result[-1]['date']}")
                logger.info(f"Latest part-time hourly: {result[-1]}")

        return result

    def _load_hourly_wage_from_estat(self) -> Optional[List[Dict[str, Any]]]:
        """
        e-Statから時間当たり給与の前年比を取得

        データソース: e-Stat 毎月勤労統計調査 時間当たり給与シート
        URL: https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040187500&fileKind=4
        """
        try:
            logger.info(f"Downloading hourly wage data from e-Stat: {self.ESTAT_HOURLY_WAGE_URL}")

            response = requests.get(self.ESTAT_HOURLY_WAGE_URL, timeout=60)
            if response.status_code != 200:
                logger.error(f"Failed to download hourly wage from e-Stat: {response.status_code}")
                return None

            # Sheet 9: 時間当たり給与（パートタイム労働者）
            df = pd.read_excel(BytesIO(response.content), sheet_name=9, header=None)

            data = {}
            current_year = None

            for i in range(8, len(df)):
                row = df.iloc[i]
                period = str(row[1]).strip() if pd.notna(row[1]) else ''
                wage = row[3] if pd.notna(row[3]) else None
                yoy = row[4] if pd.notna(row[4]) else None

                if not period or wage is None:
                    continue

                # 年月を解析
                year_match = re.search(r'(\d{4})年', period)
                month_match = re.search(r'([０-９\d]+)月', period)

                if year_match:
                    current_year = int(year_match.group(1))

                if '年' in period and '月' not in period:
                    # 年平均（スキップ）
                    continue
                elif month_match:
                    month_str = month_match.group(1)
                    # 全角数字を半角に変換
                    month_str = month_str.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
                    month = int(month_str)

                    if current_year and yoy is not None:
                        date_str = f'{current_year}-{month:02d}-01'
                        data[date_str] = round(float(yoy), 1)

            # 結果を整形
            result = [{"date": date, "value": value} for date, value in sorted(data.items())]

            logger.info(f"Loaded {len(result)} hourly wage data points from e-Stat")
            return result if result else None

        except Exception as e:
            logger.error(f"Error loading hourly wage from e-Stat: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _load_single_series(self, url: str, name: str, search_start_row: int) -> Optional[List[Dict[str, Any]]]:
        """e-Stat Excelから単一系列を取得"""
        try:
            logger.info(f"Downloading {name} data from e-Stat: {url}")

            response = requests.get(url, timeout=60)
            if response.status_code != 200:
                logger.error(f"Failed to download {name} from e-Stat: {response.status_code}")
                return None

            df = pd.read_excel(BytesIO(response.content), sheet_name=0, header=None)
            return self._process_excel(df, name, search_start_row)

        except Exception as e:
            logger.error(f"Error fetching {name} data from e-Stat: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _process_excel(self, df: pd.DataFrame, name: str, search_start_row: int) -> List[Dict[str, Any]]:
        """
        所定内給与Excelデータを処理

        Excel構造:
        - 前年比セクション以降のデータを抽出
          - Column 0: 年
          - Column 1: 年平均
          - Column 8-19: 1月〜12月
        """
        try:
            logger.info(f"Processing scheduled wage Excel ({name}) with shape: {df.shape}")

            result = []

            # Find the YoY section (前年比)
            yoy_start_row = None
            for i in range(search_start_row, min(search_start_row + 30, len(df))):
                cell = str(df.iloc[i, 0]) if pd.notna(df.iloc[i, 0]) else ""
                if "前年比" in cell or "Year-on-year" in cell or "growth rate" in cell.lower():
                    yoy_start_row = i + 3  # Skip header rows
                    break

            if yoy_start_row is None:
                # Try alternative detection - look for numeric year
                for i in range(search_start_row + 10, min(search_start_row + 40, len(df))):
                    cell = df.iloc[i, 0]
                    if pd.notna(cell):
                        try:
                            year = int(cell)
                            if 1950 <= year <= 2100:
                                yoy_start_row = i
                                break
                        except (ValueError, TypeError):
                            continue

            if yoy_start_row is None:
                logger.error(f"Could not find YoY section in Excel ({name})")
                return []

            logger.info(f"YoY section starts at row {yoy_start_row} ({name})")

            # Process YoY data
            for i in range(yoy_start_row, len(df)):
                row = df.iloc[i]
                year_val = row[0]

                if pd.isna(year_val):
                    continue

                try:
                    year = int(year_val)
                except (ValueError, TypeError):
                    continue

                if year < 1950 or year > 2100:
                    continue

                # Process each month (columns 8-19 for Jan-Dec)
                for month in range(1, 13):
                    col_idx = 7 + month  # Column 8 = Jan, 9 = Feb, ..., 19 = Dec
                    value = row[col_idx]

                    if pd.isna(value) or value == '-' or value == '':
                        continue

                    try:
                        val = float(value)
                        date_str = f"{year}-{month:02d}-01"

                        # Only include data from 2000 onwards
                        if year >= 2000:
                            result.append({
                                "date": date_str,
                                "value": round(val, 1)
                            })
                    except (ValueError, TypeError):
                        continue

            # Sort by date
            result.sort(key=lambda x: x["date"])

            logger.info(f"Processed {len(result)} {name} data points")
            if result:
                logger.info(f"Date range: {result[0]['date']} to {result[-1]['date']}")
                logger.info(f"Latest value: {result[-1]}")

            return result

        except Exception as e:
            logger.error(f"Error processing Excel ({name}): {e}")
            import traceback
            traceback.print_exc()
            return []

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
                        match = re.search(r'\((\w{3})\)', event)
                        if match:
                            month_abbr = match.group(1).lower()
                            if month_abbr in month_map:
                                target_month = month_map[month_abbr]
                                target_year = dt_utc.year
                                if target_month > dt_utc.month:
                                    target_year -= 1
                                date_str = f"{target_year}-{target_month:02d}-01"
                            else:
                                continue
                        else:
                            continue

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
        """DBデータとe-Statデータをマージ

        注: part_time_wageとpart_time_hourlyはe-Statから取得するため、
        DBデータとマージせずe-Statデータのみを使用する
        """
        if not db_data and not estat_data:
            return None

        if not db_data:
            return estat_data

        if not estat_data:
            return db_data

        result = {
            "scheduled_wage": {"data": [], "latest": None},
            "general": {"data": [], "latest": None},
            "part_time_wage": {"data": [], "latest": None},
            "part_time_hourly": {"data": [], "latest": None},
        }

        # scheduled_wage と general はDBとe-Statをマージ
        for key in ["scheduled_wage", "general"]:
            db_series = db_data.get(key, {}).get("data", []) if db_data.get(key) else []
            estat_series = estat_data.get(key, {}).get("data", []) if estat_data.get(key) else []

            merged_map = {}
            for item in db_series:
                merged_map[item["date"]] = item
            for item in estat_series:
                merged_map[item["date"]] = item

            merged_list = sorted(merged_map.values(), key=lambda x: x["date"])

            result[key] = {
                "data": merged_list,
                "latest": merged_list[-1] if merged_list else None,
            }

        # part_time_wage はe-Statからのみ取得（DBデータは使わない）
        estat_ptw = estat_data.get("part_time_wage", {}) if estat_data else {}
        estat_ptw_data = estat_ptw.get("data", []) if estat_ptw else []
        result["part_time_wage"] = {
            "data": estat_ptw_data,
            "latest": estat_ptw_data[-1] if estat_ptw_data else None,
        }

        # part_time_hourly はe-Statの時間当たり給与シートのみを使用（DBデータは使わない）
        # 理由: 厚労省の計算方法（実額から時間当たり給与を計算）と異なるため
        estat_pth = estat_data.get("part_time_hourly", {}) if estat_data else {}
        estat_pth_data = estat_pth.get("data", []) if estat_pth else []
        result["part_time_hourly"] = {
            "data": estat_pth_data,
            "latest": estat_pth_data[-1] if estat_pth_data else None,
        }

        return result

    def _save_to_history_db(self, data: Dict[str, Any]) -> None:
        """e-Statから取得したデータをHistory DBに保存"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            sw_data = data.get("scheduled_wage", {}).get("data", []) if data.get("scheduled_wage") else []
            gen_data = data.get("general", {}).get("data", []) if data.get("general") else []
            pt_data = data.get("part_time", {}).get("data", []) if data.get("part_time") else []

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
                                'e-Stat', NOW()
                            )
                            ON CONFLICT (date) DO UPDATE SET
                                scheduled_wage_yoy = COALESCE(EXCLUDED.scheduled_wage_yoy, japan_scheduled_wage_history.scheduled_wage_yoy),
                                general_yoy = COALESCE(EXCLUDED.general_yoy, japan_scheduled_wage_history.general_yoy),
                                part_time_yoy = COALESCE(EXCLUDED.part_time_yoy, japan_scheduled_wage_history.part_time_yoy),
                                source = 'e-Stat',
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
        part_time_wage_count = 0
        part_time_hourly_count = 0

        if cached_data:
            sw = cached_data.get("scheduled_wage")
            gen = cached_data.get("general")
            ptw = cached_data.get("part_time_wage")
            pth = cached_data.get("part_time_hourly")
            scheduled_wage_count = len(sw.get("data", [])) if sw else 0
            general_count = len(gen.get("data", [])) if gen else 0
            part_time_wage_count = len(ptw.get("data", [])) if ptw else 0
            part_time_hourly_count = len(pth.get("data", [])) if pth else 0

        return {
            "indicator": "JP Scheduled Wage (所定内給与 - e-Stat版)",
            "source": "e-Stat / FMP DB",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": {
                "scheduled_wage": scheduled_wage_count,
                "general": general_count,
                "part_time_wage": part_time_wage_count,
                "part_time_hourly": part_time_hourly_count,
            },
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
scheduled_wage_service = ScheduledWageService()
