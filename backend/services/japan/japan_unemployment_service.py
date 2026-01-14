"""
日本 失業率サービス
e-Stat 労働力調査データを取得

指標:
- 完全失業率（季節調整値）

データソース:
e-Stat 労働力調査
https://www.e-stat.go.jp/stat-search/file-download

発表スケジュール:
- 毎月末（翌月分）

キャッシュ方式: FMPリリース時刻基準
"""
import json
import re
import requests
import pandas as pd
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path
import logging

from core.redis_client import redis_client
from services.japan.fmp_next_release_utils import get_next_release_from_fmp as fmp_get_next_release

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "japan" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "unemployment_cache.json"
TEMP_DIR = CACHE_DIR / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


class JapanUnemploymentService:
    """日本 失業率サービス"""

    DATA_CACHE_KEY = "japan:employment:unemployment:data"
    NEXT_RELEASE_CACHE_KEY = "japan:employment:unemployment:next_release"

    # e-Stat Excel File Download URL
    ESTAT_EXCEL_URL = "https://www.e-stat.go.jp/stat-search/file-download"

    # Fallback list of statInfIds (Labor Force Survey - 労働力調査)
    FALLBACK_STAT_INF_IDS = [
        "000032450408",  # Current
        "000031831358",  # Previous
    ]

    # FMP calendar mapping
    FMP_EVENT_NAME = "Unemployment Rate"
    FMP_COUNTRY = "JP"

    def __init__(self):
        self.temp_dir = TEMP_DIR
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def get_unemployment_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        日本失業率データを取得

        Returns:
            {
                "unemployment_rate": {"data": [...], "latest": {...}},
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
                    # 次回発表日時を取得
                    next_release = self._get_next_release_from_fmp()

                    return {
                        "unemployment_rate": cached_data.get("unemployment_rate"),
                        "next_release": next_release,
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

            # 次回発表日時を取得
            next_release = self._get_next_release_from_fmp()

            cache_payload = {
                "unemployment_rate": merged_data.get("unemployment_rate"),
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            source = "History DB + e-Stat Excel" if db_data and estat_data else (
                "e-Stat Excel" if estat_data else "History DB"
            )
            return {
                **cache_payload,
                "next_release": next_release,
                "cached": False,
                "source": source,
            }

        # 3. ファイルキャッシュからフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "unemployment_rate": file_cache.get("unemployment_rate"),
                "next_release": self._get_next_release_from_fmp(),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "unemployment_rate": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _get_next_release_from_fmp(self) -> Optional[Dict[str, Any]]:
        """FMPから次回発表日時を取得"""
        try:
            # キャッシュを確認
            cached = redis_client.get(self.NEXT_RELEASE_CACHE_KEY)
            if cached:
                return cached

            # FMPから取得（indicator_event_mappingのパターンを使用）
            next_release = fmp_get_next_release("jp_unemployment_rate")

            if next_release:
                # 1時間キャッシュ
                redis_client.set(self.NEXT_RELEASE_CACHE_KEY, next_release, expire=3600)

            return next_release

        except Exception as e:
            logger.error(f"Error getting next release from FMP: {e}")
            return None

    def _download_excel_file(self) -> Optional[Path]:
        """
        e-Statから失業率Excelをダウンロード

        Returns:
            ダウンロードしたExcelファイルのパス
        """
        last_error = None

        for stat_inf_id in self.FALLBACK_STAT_INF_IDS:
            try:
                params = {
                    "statInfId": stat_inf_id,
                    "fileKind": 0
                }

                logger.info(f"Attempting to download unemployment data with statInfId: {stat_inf_id}")

                response = requests.get(self.ESTAT_EXCEL_URL, params=params, timeout=60)

                if response.status_code == 200:
                    # Save Excel file
                    excel_path = self.temp_dir / "unemployment_seasonally_adjusted.xlsx"
                    excel_path.write_bytes(response.content)

                    logger.info(f"Successfully downloaded {len(response.content)} bytes using statInfId: {stat_inf_id}")
                    return excel_path
                else:
                    logger.warning(f"statInfId {stat_inf_id} returned status {response.status_code}, trying next...")
                    last_error = f"HTTP {response.status_code}"

            except Exception as e:
                logger.warning(f"Error with statInfId {stat_inf_id}: {e}, trying next...")
                last_error = str(e)
                continue

        logger.error(f"All statInfIds failed. Last error: {last_error}")
        return None

    def _parse_excel_file(self, excel_path: Path) -> Optional[Dict]:
        """
        失業率Excelを解析

        Args:
            excel_path: Excelファイルのパス

        Returns:
            処理済みデータ
        """
        try:
            logger.info(f"Parsing unemployment Excel file: {excel_path}")

            # Read Excel file - first sheet contains seasonally adjusted data
            # Header row is at row 8 (0-indexed row 7)
            # Data starts from row 10 (0-indexed row 9)
            df = pd.read_excel(excel_path, sheet_name=0, header=None, skiprows=10)

            logger.info(f"Excel shape: {df.shape}")

            # Process the data
            return self._process_unemployment_dataframe(df)

        except Exception as e:
            logger.error(f"Error parsing unemployment Excel: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _process_unemployment_dataframe(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        失業率データフレームを処理

        Excel structure (after header):
        Column 0: Year (和暦)
        Column 1: Month (number)
        Column 2: Month (English abbreviation)
        Column 19: Unemployment rate (%) - Both sexes - Seasonally adjusted (季節調整値)

        Args:
            df: Raw dataframe from Excel

        Returns:
            処理済みデータポイントのリスト
        """
        try:
            logger.info(f"Processing unemployment dataframe with shape: {df.shape}")

            series_data = []
            current_year = None  # Track current year across rows

            for idx, row in df.iterrows():
                try:
                    # Get year - column 0 contains year (only filled on first row of each year)
                    year_val = row[0]

                    # Update current year if this row has a year value
                    if pd.notna(year_val):
                        # Convert year to string and extract numeric part
                        year_str = str(year_val).strip()

                        # Skip non-data rows (like "備考_Notes")
                        if year_str.startswith('Notes') or '_' in year_str:
                            continue

                        # Parse year - handle both Western and Japanese era years
                        if year_str.isdigit():
                            current_year = int(year_str)
                        elif '年' in year_str:
                            # Handle Japanese era years (昭和, 平成, 令和)
                            try:
                                # Remove year character and extract numbers
                                year_num_str = year_str.replace('年', '')
                                # Extract first sequence of digits
                                match = re.search(r'\d+', year_num_str)
                                if match:
                                    era_year = int(match.group())
                                    if era_year >= 1900:
                                        # Already Western year
                                        current_year = era_year
                                    elif era_year < 100:
                                        # Assume Showa era (昭和) - most common in this data
                                        # 昭和28年 = 1953 means base is 1925
                                        current_year = 1925 + era_year
                                    else:
                                        continue
                                else:
                                    continue
                            except:
                                continue
                        else:
                            continue

                    # Use current year for this row (year is only filled on first month)
                    if current_year is None:
                        continue

                    year = current_year

                    # Get month - column 1
                    month_val = row[1]
                    if pd.isna(month_val):
                        continue

                    # Convert month to integer (handle "1月", "10月" format)
                    month_str = str(month_val).strip()
                    # Extract digits from month string
                    month_match = re.search(r'\d+', month_str)
                    if month_match:
                        month = int(month_match.group())
                    else:
                        continue

                    # Get unemployment rate - column 19 (seasonally adjusted, both sexes)
                    rate_val = row[19]

                    # Skip if rate is NaN or invalid
                    if pd.isna(rate_val):
                        continue

                    # Convert to float
                    if isinstance(rate_val, str):
                        rate_val = rate_val.strip()
                        if not rate_val or rate_val == '-':
                            continue
                        rate_value = float(rate_val)
                    else:
                        rate_value = float(rate_val)

                    # Create date string
                    date_str = f"{year}-{month:02d}-01"

                    series_data.append({
                        "date": date_str,
                        "value": round(rate_value, 1)  # Round to 1 decimal place
                    })

                except Exception as e:
                    logger.debug(f"Error processing row {idx}: {e}")
                    continue

            # Sort by date
            series_data.sort(key=lambda x: x["date"])

            # Filter to data from 2000 onwards
            if series_data:
                cutoff_date = "2000-01-01"
                series_data = [point for point in series_data if point["date"] >= cutoff_date]

            logger.info(f"Processed unemployment data: {len(series_data)} data points")
            if series_data:
                logger.info(f"Date range: {series_data[0]['date']} to {series_data[-1]['date']}")
                logger.info(f"Latest value: {series_data[-1]['value']}%")

            return series_data

        except Exception as e:
            logger.error(f"Error processing unemployment dataframe: {e}", exc_info=True)
            return []

    def _load_from_estat(self) -> Optional[Dict[str, Any]]:
        """e-Statから失業率データを取得"""
        try:
            # Download Excel file
            excel_path = self._download_excel_file()
            if not excel_path:
                return None

            # Parse Excel
            series_data = self._parse_excel_file(excel_path)
            if not series_data:
                return None

            # Clean up temp files
            try:
                for file in self.temp_dir.glob("*"):
                    if file.is_file():
                        file.unlink()
            except Exception as e:
                logger.warning(f"Error cleaning up temp files: {e}")

            logger.info(f"Loaded {len(series_data)} records from e-Stat")

            return {
                "unemployment_rate": {
                    "data": series_data,
                    "latest": series_data[-1] if series_data else None,
                },
            }

        except Exception as e:
            logger.error(f"Error loading from e-Stat: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _load_from_history_db(self) -> Optional[Dict[str, Any]]:
        """History DBから失業率データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                rows = session.execute(text("""
                    SELECT date, unemployment_rate
                    FROM japan_unemployment_history
                    ORDER BY date ASC
                """)).fetchall()

                if not rows:
                    logger.info("No data found in Unemployment History DB")
                    return None

                series_data = []

                for row in rows:
                    date_str = row[0].strftime("%Y-%m-%d") if hasattr(row[0], 'strftime') else str(row[0])

                    if row[1] is not None:
                        series_data.append({
                            "date": date_str,
                            "value": float(row[1])
                        })

                logger.info(f"Loaded {len(series_data)} records from Unemployment History DB")

                return {
                    "unemployment_rate": {
                        "data": series_data,
                        "latest": series_data[-1] if series_data else None,
                    },
                }

        except Exception as e:
            logger.error(f"Error loading from Unemployment History DB: {e}")
            return None

    def _merge_data(
        self,
        db_data: Optional[Dict[str, Any]],
        estat_data: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """DBデータとe-Statデータをマージ"""
        if not db_data and not estat_data:
            return None

        if not db_data:
            return estat_data

        if not estat_data:
            return db_data

        # マージ処理
        db_series = db_data.get("unemployment_rate", {}).get("data", []) if db_data.get("unemployment_rate") else []
        estat_series = estat_data.get("unemployment_rate", {}).get("data", []) if estat_data.get("unemployment_rate") else []

        # 日付をキーにしてマージ（e-Statが優先）
        merged_map = {}
        for item in db_series:
            merged_map[item["date"]] = item
        for item in estat_series:
            merged_map[item["date"]] = item  # 上書き

        # ソートしてリストに
        merged_list = sorted(merged_map.values(), key=lambda x: x["date"])

        return {
            "unemployment_rate": {
                "data": merged_list,
                "latest": merged_list[-1] if merged_list else None,
            },
        }

    def _save_to_history_db(self, data: Dict[str, Any]) -> None:
        """e-Statから取得したデータをHistory DBに保存"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            series_data = data.get("unemployment_rate", {}).get("data", []) if data.get("unemployment_rate") else []

            with SessionLocal() as session:
                # テーブルが存在しない場合は作成
                session.execute(text("""
                    CREATE TABLE IF NOT EXISTS japan_unemployment_history (
                        id SERIAL PRIMARY KEY,
                        date DATE NOT NULL UNIQUE,
                        unemployment_rate DECIMAL(4, 1),
                        source VARCHAR(100),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """))

                saved = 0
                for item in series_data:
                    try:
                        session.execute(text("""
                            INSERT INTO japan_unemployment_history (
                                date, unemployment_rate,
                                source, updated_at
                            ) VALUES (
                                :date, :unemployment_rate,
                                'e-Stat Excel', NOW()
                            )
                            ON CONFLICT (date) DO UPDATE SET
                                unemployment_rate = EXCLUDED.unemployment_rate,
                                source = 'e-Stat Excel',
                                updated_at = NOW()
                        """), {
                            'date': item["date"],
                            'unemployment_rate': item["value"],
                        })
                        saved += 1
                    except Exception as e:
                        logger.warning(f"Error saving {item['date']} to History DB: {e}")

                session.commit()
                logger.info(f"Saved {saved} records to Unemployment History DB")

        except Exception as e:
            logger.error(f"Error saving to Unemployment History DB: {e}")

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        FMPリリース時刻基準:
        - 次回発表日時を過ぎたら更新
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # FMPから次回発表日時を取得
            next_release = self._get_next_release_from_fmp()
            if next_release and next_release.get("datetime_jst"):
                try:
                    next_release_dt = datetime.fromisoformat(next_release["datetime_jst"])
                    if next_release_dt.tzinfo is None:
                        next_release_dt = next_release_dt.replace(tzinfo=JST)

                    # 発表日時を過ぎていて、キャッシュが発表前のものなら更新
                    if now >= next_release_dt and last_updated < next_release_dt:
                        return True

                except Exception as e:
                    logger.warning(f"Error parsing next release datetime: {e}")

            # デフォルト: 12時間経過で更新
            if (now - last_updated).total_seconds() > 12 * 3600:
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
        redis_client.delete(self.NEXT_RELEASE_CACHE_KEY)
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        data_count = 0

        if cached_data:
            unemployment = cached_data.get("unemployment_rate")
            data_count = len(unemployment.get("data", [])) if unemployment else 0

        return {
            "indicator": "JP Unemployment Rate (完全失業率)",
            "source": "e-Stat (総務省統計局)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": data_count,
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
japan_unemployment_service = JapanUnemploymentService()
