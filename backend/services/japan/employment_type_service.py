"""
日本 雇用形態別労働者過不足判断D.I.サービス
労働経済動向調査データを取得

指標:
- 正社員等 (Regular Employee): D.I.値
- パートタイム (Part-time): D.I.値

データソース:
MHLW労働経済動向調査
https://www.mhlw.go.jp/toukei/itiran/roudou/koyou/keizai/{YYMM}/dl/8zuhyo.xlsx
Excel: 図３値シート

発表スケジュール:
- 四半期ごと（3月、6月、9月、12月）

キャッシュ方式: 四半期チェック方式
- 3,6,9,12月は毎日チェック
- 更新確認後は次の発表月までスキップ
"""
import json
import re
import requests
import pandas as pd
from datetime import datetime, date
from typing import Dict, List, Any, Optional, Tuple
from zoneinfo import ZoneInfo
from pathlib import Path
import logging

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "japan" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "employment_type_cache.json"
TEMP_DIR = CACHE_DIR / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


class EmploymentTypeService:
    """日本 雇用形態別労働者過不足判断D.I.サービス"""

    DATA_CACHE_KEY = "japan:employment:employment_type:data"

    # MHLW Base URL for labor economics survey (労働経済動向調査)
    MHLW_BASE_URL = "https://www.mhlw.go.jp/toukei/itiran/roudou/koyou/keizai"

    def __init__(self):
        pass

    def get_employment_type_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        雇用形態別労働者過不足判断D.I.データを取得

        Returns:
            {
                "regular_employee": {"data": [...], "latest": {...}},
                "part_time": {"data": [...], "latest": {...}},
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
                        "regular_employee": cached_data.get("regular_employee"),
                        "part_time": cached_data.get("part_time"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # 1. MHLWから最新データを取得
        mhlw_data = self._load_from_mhlw()

        # 2. History DBからベースデータを取得
        db_data = self._load_from_history_db()

        # データをマージ（MHLW > DB）
        merged_data = self._merge_data(db_data, mhlw_data)

        if merged_data:
            # MHLWで新しいデータがあれば、DBにも保存
            if mhlw_data:
                self._save_to_history_db(mhlw_data)

            cache_payload = {
                "regular_employee": merged_data.get("regular_employee"),
                "part_time": merged_data.get("part_time"),
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

        # 3. ファイルキャッシュからフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "regular_employee": file_cache.get("regular_employee"),
                "part_time": file_cache.get("part_time"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "regular_employee": None,
            "part_time": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _get_target_urls(self) -> List[Tuple[str, int, int]]:
        """
        取得対象のURLリストを生成

        労働経済動向調査:
        - 調査月: 2月、5月、8月、11月（年4回）
        - 発表月: 3月、6月、9月、12月
        - URLは調査月（2月、5月、8月、11月）を使用

        Returns:
            List of (url, year, survey_month) tuples
        """
        urls = []
        now = datetime.now(JST)
        current_year = now.year

        # 調査月（発表月の1ヶ月前）
        survey_months = [2, 5, 8, 11]

        # 過去5年分を取得
        for year in range(current_year - 5, current_year + 1):
            for survey_month in survey_months:
                # 発表月は調査月の翌月
                release_month = survey_month + 1 if survey_month < 12 else 1
                release_year = year if survey_month < 12 else year + 1

                # 未来の発表はスキップ
                if release_year > current_year or (release_year == current_year and release_month > now.month):
                    continue

                # YYMM format（調査月を使用）
                year_month = f"{year % 100:02d}{survey_month:02d}"

                url = f"{self.MHLW_BASE_URL}/{year_month}/dl/8zuhyo.xlsx"
                urls.append((url, year, survey_month))

        return urls

    def _download_and_parse_excel(self, url: str) -> Optional[List[Dict[str, Any]]]:
        """
        MHLWからExcelをダウンロードして解析

        Returns:
            List of data points or None if failed
        """
        try:
            logger.info(f"Downloading employment type data from {url}")

            response = requests.get(url, timeout=60)
            if response.status_code != 200:
                logger.warning(f"Failed to download {url}: {response.status_code}")
                return None

            # Excelファイルを一時保存
            excel_path = TEMP_DIR / "employment_type_temp.xlsx"
            excel_path.write_bytes(response.content)

            # Parse Excel
            return self._parse_excel_file(excel_path)

        except Exception as e:
            logger.error(f"Error downloading employment type data: {e}")
            return None

    def _parse_excel_file(self, excel_path: Path) -> Optional[List[Dict[str, Any]]]:
        """
        労働経済動向調査Excelを解析

        Excel structure (図３値 sheet):
        Row 4: 年（和暦）
        Row 5: 月
        Row 6: 正社員等
        Row 7: パートタイム
        """
        try:
            logger.info(f"Parsing employment type Excel file: {excel_path}")

            # 図３値シートを読み込み
            df = pd.read_excel(excel_path, sheet_name="図３値", header=None)
            logger.info(f"Excel shape: {df.shape}")

            return self._process_employment_type_dataframe(df)

        except Exception as e:
            logger.error(f"Error parsing employment type Excel: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _process_employment_type_dataframe(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        雇用形態別D.I.データを処理

        Excel structure (図３値 sheet):
        Row 4 (index 3): 年（和暦）- 4列ごとに配置
          - 例: "平成19年" (col 1), 20 (col 5), 21 (col 9)...
          - 例: "令和元年" (col 50), "２" (col 53), "３" (col 57)...
        Row 5 (index 4): 月 - 2, 5, 8, 11 の繰り返し
        Row 6 (index 5): 正社員等 D.I.
        Row 7 (index 6): パートタイム D.I.
        """
        try:
            logger.info(f"Processing employment type dataframe with shape: {df.shape}")

            # Get rows
            year_row = df.iloc[3]  # Row 4 (0-indexed = 3)
            month_row = df.iloc[4]  # Row 5 (0-indexed = 4)
            regular_row = df.iloc[5]  # Row 6 (0-indexed = 5)
            part_time_row = df.iloc[6]  # Row 7 (0-indexed = 6)

            data_points = []
            current_year = None
            era_base = None  # 平成 or 令和のベース年

            # Start from column 1 (B) to skip row labels
            for col_idx in range(1, len(df.columns)):
                try:
                    year_val = year_row.iloc[col_idx]
                    month_val = month_row.iloc[col_idx]
                    regular_val = regular_row.iloc[col_idx]
                    part_time_val = part_time_row.iloc[col_idx]

                    # Parse year if present (年が設定されている列)
                    if pd.notna(year_val):
                        year_str = str(year_val).strip().replace('\n', '')

                        # 令和パターン: "令和元年", "令和２年", "２", "３"...
                        if '令和' in year_str:
                            era_base = 2018  # 令和元年 = 2019
                            if '元年' in year_str:
                                current_year = 2019
                            else:
                                year_match = re.search(r'令和(\d+)年?', year_str)
                                if year_match:
                                    era_year = int(year_match.group(1))
                                    current_year = era_base + era_year

                        # 平成パターン: "平成19年", "平成20年"...
                        elif '平成' in year_str:
                            era_base = 1988  # 平成元年 = 1989
                            year_match = re.search(r'平成(\d+)年?', year_str)
                            if year_match:
                                era_year = int(year_match.group(1))
                                current_year = era_base + era_year

                        # 数字のみ: 前の元号の続き
                        else:
                            # 全角数字を半角に変換
                            year_str_normalized = year_str.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
                            num_match = re.search(r'(\d+)', year_str_normalized)
                            if num_match and era_base is not None:
                                era_year = int(num_match.group(1))
                                current_year = era_base + era_year

                    # Skip if no year determined yet
                    if current_year is None:
                        continue

                    # Parse month
                    if pd.isna(month_val):
                        continue

                    month_str = str(month_val).strip()
                    # 全角数字を半角に変換
                    month_str = month_str.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
                    month_match = re.search(r'(\d+)', month_str)
                    if not month_match:
                        continue

                    month = int(float(month_match.group(1)))

                    # Skip if no valid data
                    if pd.isna(regular_val) and pd.isna(part_time_val):
                        continue

                    # Create date string (use first day of month)
                    date_string = f"{current_year}-{month:02d}-01"

                    # Parse values
                    regular_value = None
                    part_time_value = None

                    if pd.notna(regular_val):
                        try:
                            regular_value = int(float(regular_val))
                        except (ValueError, TypeError):
                            pass

                    if pd.notna(part_time_val):
                        try:
                            part_time_value = int(float(part_time_val))
                        except (ValueError, TypeError):
                            pass

                    data_points.append({
                        "date": date_string,
                        "regular_employee": regular_value,
                        "part_time": part_time_value,
                    })

                except Exception as e:
                    logger.debug(f"Error processing column {col_idx}: {e}")
                    continue

            logger.info(f"Processed {len(data_points)} data points")
            return data_points

        except Exception as e:
            logger.error(f"Error processing employment type dataframe: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _load_from_mhlw(self) -> Optional[Dict[str, Any]]:
        """MHLWから雇用形態別D.I.データを取得"""
        try:
            all_data_points = []
            urls = self._get_target_urls()

            # 最新の3つのURLを試す（最新データを優先）
            for url, year, quarter in reversed(urls[-3:]):
                result = self._download_and_parse_excel(url)
                if result:
                    all_data_points.extend(result)
                    break  # 最新のExcelが取得できれば十分

            if not all_data_points:
                logger.warning("No data points retrieved from MHLW")
                return None

            # 重複を除去してソート
            unique_data = {}
            for point in all_data_points:
                unique_data[point["date"]] = point

            sorted_data = sorted(unique_data.values(), key=lambda x: x["date"])

            # データを分離
            regular_data = []
            part_time_data = []

            for point in sorted_data:
                if point["regular_employee"] is not None:
                    regular_data.append({
                        "date": point["date"],
                        "value": point["regular_employee"]
                    })
                if point["part_time"] is not None:
                    part_time_data.append({
                        "date": point["date"],
                        "value": point["part_time"]
                    })

            logger.info(f"Loaded {len(regular_data)} regular, {len(part_time_data)} part-time records from MHLW")

            return {
                "regular_employee": {
                    "data": regular_data,
                    "latest": regular_data[-1] if regular_data else None,
                },
                "part_time": {
                    "data": part_time_data,
                    "latest": part_time_data[-1] if part_time_data else None,
                },
            }

        except Exception as e:
            logger.error(f"Error loading from MHLW: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _load_from_history_db(self) -> Optional[Dict[str, Any]]:
        """History DBから雇用形態別D.I.データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                rows = session.execute(text("""
                    SELECT date, regular_employee_di, part_time_di
                    FROM japan_employment_type_history
                    ORDER BY date ASC
                """)).fetchall()

                if not rows:
                    logger.info("No data found in Employment Type History DB")
                    return None

                regular_data = []
                part_time_data = []

                for row in rows:
                    date_str = row[0].strftime("%Y-%m-%d") if hasattr(row[0], 'strftime') else str(row[0])

                    if row[1] is not None:
                        regular_data.append({
                            "date": date_str,
                            "value": int(row[1])
                        })

                    if row[2] is not None:
                        part_time_data.append({
                            "date": date_str,
                            "value": int(row[2])
                        })

                logger.info(f"Loaded {len(regular_data)} records from Employment Type History DB")

                return {
                    "regular_employee": {
                        "data": regular_data,
                        "latest": regular_data[-1] if regular_data else None,
                    },
                    "part_time": {
                        "data": part_time_data,
                        "latest": part_time_data[-1] if part_time_data else None,
                    },
                }

        except Exception as e:
            logger.error(f"Error loading from Employment Type History DB: {e}")
            return None

    def _merge_data(
        self,
        db_data: Optional[Dict[str, Any]],
        mhlw_data: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """DBデータとMHLWデータをマージ"""
        if not db_data and not mhlw_data:
            return None

        if not db_data:
            return mhlw_data

        if not mhlw_data:
            return db_data

        # マージ処理
        result = {
            "regular_employee": {"data": [], "latest": None},
            "part_time": {"data": [], "latest": None},
        }

        for key in ["regular_employee", "part_time"]:
            db_series = db_data.get(key, {}).get("data", []) if db_data.get(key) else []
            mhlw_series = mhlw_data.get(key, {}).get("data", []) if mhlw_data.get(key) else []

            # 日付をキーにしてマージ（MHLWが優先）
            merged_map = {}
            for item in db_series:
                merged_map[item["date"]] = item
            for item in mhlw_series:
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

            regular_data = data.get("regular_employee", {}).get("data", []) if data.get("regular_employee") else []
            pt_data = data.get("part_time", {}).get("data", []) if data.get("part_time") else []

            # 日付でマージ
            date_set = set()
            for d in regular_data:
                date_set.add(d['date'])
            for d in pt_data:
                date_set.add(d['date'])

            regular_map = {d['date']: d['value'] for d in regular_data}
            pt_map = {d['date']: d['value'] for d in pt_data}

            with SessionLocal() as session:
                # テーブルが存在しない場合は作成
                session.execute(text("""
                    CREATE TABLE IF NOT EXISTS japan_employment_type_history (
                        id SERIAL PRIMARY KEY,
                        date DATE NOT NULL UNIQUE,
                        regular_employee_di INTEGER,
                        part_time_di INTEGER,
                        source VARCHAR(100),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """))

                saved = 0
                for date_str in date_set:
                    try:
                        session.execute(text("""
                            INSERT INTO japan_employment_type_history (
                                date, regular_employee_di, part_time_di,
                                source, updated_at
                            ) VALUES (
                                :date, :regular_employee_di, :part_time_di,
                                'MHLW Excel', NOW()
                            )
                            ON CONFLICT (date) DO UPDATE SET
                                regular_employee_di = COALESCE(EXCLUDED.regular_employee_di, japan_employment_type_history.regular_employee_di),
                                part_time_di = COALESCE(EXCLUDED.part_time_di, japan_employment_type_history.part_time_di),
                                source = 'MHLW Excel',
                                updated_at = NOW()
                        """), {
                            'date': date_str,
                            'regular_employee_di': regular_map.get(date_str),
                            'part_time_di': pt_map.get(date_str),
                        })
                        saved += 1
                    except Exception as e:
                        logger.warning(f"Error saving {date_str} to History DB: {e}")

                session.commit()
                logger.info(f"Saved {saved} records to Employment Type History DB")

        except Exception as e:
            logger.error(f"Error saving to Employment Type History DB: {e}")

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        四半期チェック方式:
        - 3,6,9,12月は毎日チェック
        - 更新確認後は次の発表月までスキップ
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 発表月（3,6,9,12月）かどうか
            is_release_month = now.month in [3, 6, 9, 12]

            if is_release_month:
                # 発表月は毎日チェック（日付が変わったら更新）
                if last_updated.date() < now.date():
                    return True
            else:
                # 発表月以外は週1回チェック
                days_since_update = (now - last_updated).days
                if days_since_update >= 7:
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking refresh condition: {e}")
            return True

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

        regular_count = 0
        part_time_count = 0

        if cached_data:
            regular = cached_data.get("regular_employee")
            pt = cached_data.get("part_time")
            regular_count = len(regular.get("data", [])) if regular else 0
            part_time_count = len(pt.get("data", [])) if pt else 0

        return {
            "indicator": "JP Employment Type D.I. (雇用形態別労働者過不足判断D.I.)",
            "source": "MHLW (厚生労働省)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": {
                "regular_employee": regular_count,
                "part_time": part_time_count,
            },
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
employment_type_service = EmploymentTypeService()
