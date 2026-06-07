"""
BOE Market Expectations Service (Bank Rate見通し)
BOE MPRデータからBank Rate期待データを取得

データソース (November 2025以降):
- Projections Databank - {Month} {Year} MPR.xlsx
  - 32. Bank Rate シート

データソース (旧構造):
- Market profiles.xlsx from MPR Charts, Slides and Data ZIP files

発表スケジュール:
- 2月・5月・8月・11月のMPR発表月
- 発表時刻: 12:00 GMT
- ダウンロードウィンドウ: 20:00-20:10 GMT/BST

キャッシュ方式: ファイルキャッシュ + Redisキャッシュ
"""
import json
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from .boe_mpr_utils import (
    get_mpr_info,
    get_projections_databank,
    download_mpr_zip,
    extract_workbook_from_zip,
    resolve_sheet_by_suffix,
    parse_date_to_yyyy_mm,
    OLD_FILES,
    DEFAULT_MPR_MONTHS
)

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "economic_outlook"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "boe_market_expectations_cache.json"


class BOEMarketExpectationsService:
    """BOE Market Expectations (Bank Rate見通し) サービス"""

    DATA_CACHE_KEY = "uk:boe_market_expectations:data"
    # MPRごとに番号がドリフトするためsuffix一致で解決
    SHEET_SUFFIX = "Bank Rate"

    def __init__(self):
        pass

    def get_market_expectations(self, force_refresh: bool = False) -> Dict[str, Any]:
        """市場期待データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "forecasts": cached_data.get("forecasts", {}),
                        "metadata": cached_data.get("metadata", {}),
                        "cached": True,
                        "source": "redis",
                    }

        # MPRからデータを取得
        data = self._fetch_market_expectations_data()

        if data:
            cache_payload = {
                "forecasts": data.get("forecasts", {}),
                "metadata": data.get("metadata", {}),
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "forecasts": data.get("forecasts", {}),
                "metadata": data.get("metadata", {}),
                "cached": False,
                "source": "boe_mpr",
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "forecasts": file_cache.get("forecasts", {}),
                "metadata": file_cache.get("metadata", {}),
                "cached": True,
                "source": "file (fallback)",
            }

        return self._get_fallback_data()

    def _parse_bank_rate_from_databank(self, wb) -> Optional[Dict]:
        """Projections DatabankからBank Rateデータを抽出

        32. Bank Rate シート構造:
        - Row 12: Column headers (quarters: 2004 Q4, 2005 Q1, ...)
        - Column 1: Date of publication (November 2004, February 2005, ...)
        - Data starts from row 13
        """
        try:
            sheet_name = resolve_sheet_by_suffix(wb, self.SHEET_SUFFIX)
            if not sheet_name:
                logger.error(f"Sheet matching '{self.SHEET_SUFFIX}' not found")
                return None

            ws = wb[sheet_name]

            # Get column headers (quarters) from row 12
            quarters = []
            for col in range(2, ws.max_column + 1):
                val = ws.cell(row=12, column=col).value
                if val:
                    quarters.append((col, str(val).strip()))

            if not quarters:
                logger.error("No quarters found in Bank Rate sheet")
                return None

            # Find data rows in publication order (last 2 = most recent + previous)
            data_rows = []
            for row in range(13, ws.max_row + 1):
                if ws.cell(row=row, column=1).value:
                    data_rows.append(row)

            latest_row = data_rows[-1] if data_rows else None
            previous_row = data_rows[-2] if len(data_rows) >= 2 else None

            def extract_row_data(row_num: int) -> Dict:
                """Extract forecast data from a row"""
                date_val = ws.cell(row=row_num, column=1).value
                date_str = str(date_val).strip() if date_val else ""

                # "(e)" / "(p)" 等の注記を除去してYYYY-MMにパース
                import re
                cleaned = re.sub(r'\s*\([a-zA-Z]\)\s*$', '', date_str).strip()
                mpr_date = parse_date_to_yyyy_mm(cleaned) or date_str

                data = []
                for col, quarter in quarters:
                    val = ws.cell(row=row_num, column=col).value
                    if val is not None:
                        try:
                            data.append({
                                'date': quarter.replace(' ', ''),  # "2025 Q4" -> "2025Q4"
                                'value': float(val)
                            })
                        except (ValueError, TypeError):
                            pass

                return {
                    'date': mpr_date,
                    'data': data
                }

            result = {}

            if latest_row:
                result['latest_forecast'] = extract_row_data(latest_row)
                logger.info(f"Extracted latest forecast from row {latest_row}: {len(result['latest_forecast']['data'])} points")

            if previous_row:
                result['previous_forecast'] = extract_row_data(previous_row)
                logger.info(f"Extracted previous forecast from row {previous_row}: {len(result['previous_forecast']['data'])} points")

            return result

        except Exception as e:
            logger.error(f"Error parsing Bank Rate from Databank: {e}")
            return None

    def _parse_market_profiles(self, wb) -> Optional[Dict]:
        """Market profiles.xlsx (旧構造) をパース"""
        try:
            ws = wb['Sheet1']

            # row 15からすべての日付列を検出
            date_row = 15
            max_col = ws.max_column
            dates = []

            for j in range(2, max_col + 1):
                val = ws.cell(row=date_row, column=j).value
                if val and isinstance(val, datetime):
                    dates.append((j, val))

            if len(dates) < 2:
                logger.error(f"Not enough date columns found: {len(dates)}")
                return None

            # 最後の2つの日付列を取得
            col_previous, date_previous = dates[-2]
            col_latest, date_latest = dates[-1]

            logger.info(f"Found forecast dates: Latest={date_latest}, Previous={date_previous}")

            # 両方の予測データを抽出
            previous_data = []
            latest_data = []

            # 最初の非Null値の行を検出
            start_row = None
            for i in range(17, ws.max_row + 1):
                val_latest = ws.cell(row=i, column=col_latest).value
                val_previous = ws.cell(row=i, column=col_previous).value
                if val_latest is not None or val_previous is not None:
                    start_row = i
                    break

            if start_row is None:
                logger.error("No data found in forecast columns")
                return None

            # すべてのデータポイントを抽出
            for i in range(start_row, ws.max_row + 1):
                quarter = ws.cell(row=i, column=1).value
                val_previous = ws.cell(row=i, column=col_previous).value
                val_latest = ws.cell(row=i, column=col_latest).value

                if val_previous is not None:
                    previous_data.append({
                        'date': str(quarter),
                        'value': float(val_previous)
                    })

                if val_latest is not None:
                    latest_data.append({
                        'date': str(quarter),
                        'value': float(val_latest)
                    })

            logger.info(f"Extracted {len(previous_data)} previous points, {len(latest_data)} latest points")

            return {
                'latest_forecast': {
                    'date': date_latest.strftime('%Y-%m'),
                    'data': latest_data
                },
                'previous_forecast': {
                    'date': date_previous.strftime('%Y-%m'),
                    'data': previous_data
                }
            }

        except Exception as e:
            logger.error(f"Error parsing Market profiles: {e}")
            return None

    def _fetch_market_expectations_data(self) -> Optional[Dict]:
        """最新MPRから市場期待データを取得"""
        try:
            mpr_info = get_mpr_info()
            latest_info = mpr_info['latest']
            previous_info = mpr_info['previous']

            logger.info(f"Fetching MPR data for {latest_info['month_name'].title()} {latest_info['year']}")

            # Try new structure first (Projections Databank)
            result = get_projections_databank(latest_info['year'], latest_info['month_name'])

            if result:
                wb, zip_content = result
                parsed_data = self._parse_bank_rate_from_databank(wb)

                if parsed_data:
                    return {
                        "forecasts": parsed_data,
                        "metadata": {
                            "last_updated": datetime.now().isoformat(),
                            "source": "Bank of England",
                            "mpr_date": f"{latest_info['month_name'].title()} {latest_info['year']}",
                            "latest_forecast_date": parsed_data.get('latest_forecast', {}).get('date', ''),
                            "previous_forecast_date": parsed_data.get('previous_forecast', {}).get('date', ''),
                            "data_source": "Projections Databank"
                        }
                    }

            # Fallback to old structure (Market profiles.xlsx)
            logger.info("Trying old structure (Market profiles.xlsx)")
            zip_content = download_mpr_zip(latest_info['year'], latest_info['month_name'])

            if zip_content:
                wb = extract_workbook_from_zip(zip_content, OLD_FILES["market_profiles"])
                if wb:
                    parsed_data = self._parse_market_profiles(wb)
                    if parsed_data:
                        return {
                            "forecasts": parsed_data,
                            "metadata": {
                                "last_updated": datetime.now().isoformat(),
                                "source": "Bank of England",
                                "mpr_date": f"{latest_info['month_name'].title()} {latest_info['year']}",
                                "latest_forecast_date": parsed_data.get('latest_forecast', {}).get('date', ''),
                                "previous_forecast_date": parsed_data.get('previous_forecast', {}).get('date', ''),
                                "data_source": "Market profiles.xlsx"
                            }
                        }

            # Try previous MPR
            logger.warning(f"Data not found in {latest_info['month_name'].title()} {latest_info['year']} MPR, trying previous")
            result = get_projections_databank(previous_info['year'], previous_info['month_name'])

            if result:
                wb, _ = result
                parsed_data = self._parse_bank_rate_from_databank(wb)

                if parsed_data:
                    return {
                        "forecasts": parsed_data,
                        "metadata": {
                            "last_updated": datetime.now().isoformat(),
                            "source": "Bank of England",
                            "mpr_date": f"{previous_info['month_name'].title()} {previous_info['year']}",
                            "latest_forecast_date": parsed_data.get('latest_forecast', {}).get('date', ''),
                            "previous_forecast_date": parsed_data.get('previous_forecast', {}).get('date', ''),
                            "note": "Using previous MPR data",
                            "data_source": "Projections Databank"
                        }
                    }

            logger.error("Failed to fetch BOE market expectations from both MPRs")
            return None

        except Exception as e:
            logger.error(f"Error fetching BOE market expectations: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 7日以上経過していれば更新
            if (now - last_updated).total_seconds() >= 7 * 24 * 3600:
                return True

            # MPR発表月の20:00-20:10はチェック
            now_london = now.astimezone(LONDON)
            if now_london.month in DEFAULT_MPR_MONTHS:
                if now_london.hour == 20 and now_london.minute <= 10:
                    if (now - last_updated).total_seconds() >= 60:
                        return True

            return False

        except Exception as e:
            logger.error(f"Error in should_refresh: {e}")
            return True

    def _get_fallback_data(self) -> Dict:
        """空のフォールバックデータを返す"""
        return {
            "forecasts": {
                'latest_forecast': {
                    'date': '',
                    'data': []
                },
                'previous_forecast': {
                    'date': '',
                    'data': []
                }
            },
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "source": "Bank of England",
                "error": "Failed to fetch BOE market expectations data"
            },
            "cached": False,
            "source": "none",
        }

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)


# シングルトンインスタンス
boe_market_expectations_service = BOEMarketExpectationsService()
