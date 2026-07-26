"""
NAHB住宅市場指数サービス
DBからNAHB Housing Market Indexデータを取得
NAHBウェブサイトのExcelから過去データを補完

指標:
- NAHB/Wells Fargo 住宅市場指数（HMI）

データソース:
- DB: economic_calendar_events（FMP蓄積データ）
- NAHB: Excelファイル（過去データ補完用）

発表スケジュール:
- 月次（毎月15日-21日頃 10:00 ET）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import tempfile
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd
import xlrd

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
    guarded_last_updated,
)


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "housing"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "nahb_hmi_cache.json"


class NAHBHMIService:
    """NAHB住宅市場指数サービス"""

    DATA_CACHE_KEY = "housing:nahb_hmi:data"
    ECONALPHA_ID = "nahb_hmi"
    BASE_URL = "https://www.nahb.org"

    def __init__(self):
        pass

    def get_nahb_hmi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        NAHB HMIデータを取得

        Args:
            force_refresh: 強制更新フラグ

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float}, ...],
                "latest": {"date": str, "value": float},
                "next_release": {...} | None,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
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

        # 結合データを取得（DB + NAHB Excel）
        combined_data = self._fetch_combined_data()

        if combined_data:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
            latest = combined_data[-1] if combined_data else None
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
            )

            cache_payload = {
                "data": combined_data,
                "latest": latest,
                "next_release": next_release,
                "last_updated": last_updated
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": combined_data,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "database + nahb",
                "last_updated": last_updated
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

    def _fetch_combined_data(self) -> List[Dict[str, Any]]:
        """DBとNAHB Excelからデータを取得して結合"""
        # DBから最近のデータを取得
        db_data = self._load_from_db()

        # NAHBから過去データを取得（キャッシュがあれば使用）
        nahb_data = self._fetch_from_nahb()

        # データを結合（DBデータ優先）
        combined = {}

        # まずNAHBデータを追加
        for item in nahb_data:
            date_key = item["date"][:7]  # YYYY-MM形式
            combined[date_key] = item

        # DBデータで上書き（より最新）
        for item in db_data:
            date_key = item["date"][:7]
            combined[date_key] = item

        # 日付順にソート
        result = sorted(combined.values(), key=lambda x: x["date"])

        # MoM/YoYを計算
        result = self._calculate_changes(result)

        return result

    def _load_from_db(self) -> List[Dict[str, Any]]:
        """DBから履歴データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text
            import re

            # 月名から月番号へのマッピング
            month_map = {
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }

            with SessionLocal() as session:
                query = text("""
                    SELECT datetime_utc, event, actual
                    FROM economic_calendar_events
                    WHERE country = 'US'
                      AND event LIKE 'NAHB Housing Market Index%'
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query).fetchall()

                result = []
                seen_dates = set()

                for row in rows:
                    dt_utc, event, actual = row
                    if not dt_utc:
                        continue

                    # イベント名から対象月を抽出
                    # "NAHB Housing Market Index (Dec)" -> Dec -> 12月
                    match = re.search(r'\((\w+)\)', event)
                    if match:
                        month_abbr = match.group(1).lower()
                        if month_abbr in month_map:
                            target_month = month_map[month_abbr]
                            year = dt_utc.year
                            # 1月に発表されたDecは前年のデータ
                            if dt_utc.month == 1 and target_month == 12:
                                year -= 1
                            date_str = f"{year}-{target_month:02d}-01"
                        else:
                            continue
                    else:
                        continue

                    date_key = date_str[:7]
                    if date_key in seen_dates:
                        continue
                    seen_dates.add(date_key)

                    result.append({
                        "date": date_str,
                        "value": float(actual) if actual else None,
                        "mom": None,
                        "yoy": None
                    })

                result.sort(key=lambda x: x["date"])
                print(f"Loaded {len(result)} nahb_hmi records from DB")
                return result

        except Exception as e:
            print(f"Error loading NAHB HMI from DB: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_from_nahb(self) -> List[Dict[str, Any]]:
        """NAHBウェブサイトからExcelデータを取得"""
        try:
            # 現在の年月から最新のExcelを探す
            now = datetime.now()
            year = now.year
            month = now.month

            for attempt in range(6):  # 最大6ヶ月前まで試行
                try:
                    url = self._build_url(year, month)
                    print(f"Fetching NAHB HMI from: {url}")

                    response = requests.get(url, timeout=30)
                    response.raise_for_status()

                    content = response.content

                    # HTMLでないことを確認
                    if b'<!DOCTYPE html>' in content or b'<html' in content:
                        raise ValueError("Received HTML instead of Excel")

                    # 一時ファイルに保存してpyexcelで読み込み
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.xls') as tmp_file:
                        tmp_file.write(content)
                        tmp_path = tmp_file.name

                    try:
                        # xlrdでExcelを読み込み
                        workbook = xlrd.open_workbook(tmp_path)
                        sheet = workbook.sheet_by_index(0)
                        records = []
                        for row_idx in range(sheet.nrows):
                            row_values = [sheet.cell_value(row_idx, col_idx) for col_idx in range(sheet.ncols)]
                            records.append(row_values)
                        df = pd.DataFrame(records)
                    finally:
                        Path(tmp_path).unlink(missing_ok=True)

                    # データを処理
                    data_points = self._process_excel_data(df)
                    print(f"Fetched {len(data_points)} NAHB HMI records from Excel")
                    return data_points

                except Exception as e:
                    print(f"Failed to fetch NAHB data for {year}-{month:02d}: {e}")
                    month -= 1
                    if month < 1:
                        month = 12
                        year -= 1

            print("Failed to fetch NAHB Excel after multiple attempts")
            return []

        except Exception as e:
            print(f"Error fetching from NAHB: {e}")
            return []

    def _build_url(self, year: int, month: int) -> str:
        """NAHBのExcelファイルURLを構築"""
        return f"{self.BASE_URL}/-/media/NAHB/news-and-economics/docs/housing-economics/hmi/{year}-{month:02d}/t2-national-hmi-history-{year}{month:02d}.xls"

    def _process_excel_data(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """ExcelデータをパースしてリストIに変換"""
        data_points = []

        # 月名マッピング
        month_map = {
            'jan': 1, 'january': 1,
            'feb': 2, 'february': 2,
            'mar': 3, 'march': 3,
            'apr': 4, 'april': 4,
            'may': 5,
            'jun': 6, 'june': 6,
            'jul': 7, 'july': 7,
            'aug': 8, 'august': 8,
            'sep': 9, 'september': 9,
            'oct': 10, 'october': 10,
            'nov': 11, 'november': 11,
            'dec': 12, 'december': 12
        }

        try:
            # Row 2 (index 2) に月名がある
            month_names = df.iloc[2].tolist()[1:]  # 最初の列はスキップ

            # Row 3以降がデータ
            for idx in range(3, len(df)):
                row = df.iloc[idx]
                year = row.iloc[0]

                try:
                    year = int(year)
                except (ValueError, TypeError):
                    continue

                for month_idx, month_name in enumerate(month_names):
                    if not month_name or month_name == '':
                        continue

                    hmi_value = row.iloc[month_idx + 1]

                    if pd.isna(hmi_value) or hmi_value == '':
                        continue

                    month_str = str(month_name).lower().strip()
                    month_num = month_map.get(month_str)
                    if month_num is None:
                        continue

                    try:
                        value = float(hmi_value)
                    except (ValueError, TypeError):
                        continue

                    date_str = f"{year}-{month_num:02d}-01"
                    data_points.append({
                        "date": date_str,
                        "value": value,
                        "mom": None,
                        "yoy": None
                    })

        except Exception as e:
            print(f"Error processing Excel data: {e}")
            import traceback
            traceback.print_exc()

        return data_points

    def _calculate_changes(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """前月比・前年比を計算（ポイント変化）"""
        result = []
        for i, item in enumerate(data):
            entry = {
                "date": item["date"],
                "value": item["value"],
                "mom": None,
                "yoy": None
            }

            if item["value"] is not None:
                # 前月比（ポイント変化）
                if i >= 1 and data[i - 1]["value"] is not None:
                    entry["mom"] = round(item["value"] - data[i - 1]["value"], 1)

                # 前年比（ポイント変化）
                if i >= 12 and data[i - 12]["value"] is not None:
                    entry["yoy"] = round(item["value"] - data[i - 12]["value"], 1)

            result.append(entry)

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP 3分方式）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "NAHB Housing Market Index",
            "source": "Database (FMP) + NAHB Excel",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
nahb_hmi_service = NAHBHMIService()
