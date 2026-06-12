"""
BOE Unemployment Rate Forecast Service
BOE MPRデータから失業率見通しデータを取得

データソース (November 2025以降):
- Projections Databank - {Month} {Year} MPR.xlsx
  - 4. Unemployment シート (見通し)
  - 36. Unemployment distribution シート (ファン/分布) - 任意

データソース (旧構造):
- Parameters for MPC unemployment rate projections from August 2013.xlsx

発表スケジュール: 2月・5月・8月・11月のMPR

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
    resolve_sheet,
    parse_scenario_databank_sheet,
    get_mpr_info,
    get_projections_databank,
    download_mpr_zip,
    extract_workbook_from_zip,
    list_zip_contents,
    DEFAULT_MPR_MONTHS
)

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "economic_outlook"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "boe_unemployment_forecast_cache.json"


class BOEUnemploymentForecastService:
    """BOE Unemployment Forecast サービス"""

    DATA_CACHE_KEY = "uk:boe_unemployment_forecast:data"
    SHEET_NAME = "4. Unemployment"
    DISTRIBUTION_SHEET = "36. Unemployment distribution "  # Note: trailing space in sheet name

    def __init__(self):
        pass

    def fetch_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """失業率見通しデータを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "table_data": cached_data.get("table_data", []),
                        "chart_data": cached_data.get("chart_data"),
                        "scenario_labels": cached_data.get("scenario_labels"),
                        "metadata": cached_data.get("metadata", {}),
                        "cached": True,
                        "source": "redis",
                    }

        # MPRからデータを取得
        data = self._fetch_unemployment_forecast_data()

        if data:
            cache_payload = {
                "table_data": data.get("table_data", []),
                "chart_data": data.get("chart_data"),
                "scenario_labels": data.get("scenario_labels"),
                "metadata": data.get("metadata", {}),
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "table_data": data.get("table_data", []),
                "chart_data": data.get("chart_data"),
                "scenario_labels": data.get("scenario_labels"),
                "metadata": data.get("metadata", {}),
                "cached": False,
                "source": "boe_mpr",
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "table_data": file_cache.get("table_data", []),
                "chart_data": file_cache.get("chart_data"),
                "scenario_labels": file_cache.get("scenario_labels"),
                "metadata": file_cache.get("metadata", {}),
                "cached": True,
                "source": "file (fallback)",
            }

        return self._get_fallback_data()

    def _parse_unemployment_from_databank(self, wb) -> Optional[Dict]:
        """Projections Databankから失業率データを抽出

        4. Unemployment シート構造:
        - Row 5: Column headers (quarters: 2013 Q3, 2013 Q4, ...)
        - Column 1: Date of publication
        - Data starts from row 6
        """
        try:
            # シート番号はMPRごとにドリフトするため動的解決する
            # (例: "1. CPI inflation" -> 2026年4月版 "2. CPI inflation")
            resolved = resolve_sheet(wb, self.SHEET_NAME)
            if resolved is None:
                logger.error(f"Sheet {self.SHEET_NAME} not found (even by suffix)")
                return None

            ws = wb[resolved]

            # 2026年4月MPR以降の転置シナリオ方式レイアウトを先に試す
            # (旧来: 行=公表日/列=四半期 → 新: 行=四半期/列=系列)
            scenario = parse_scenario_databank_sheet(ws)
            if scenario is not None:
                return scenario

            # Get column headers (quarters) from row 5
            quarters = []
            for col in range(2, ws.max_column + 1):
                val = ws.cell(row=5, column=col).value
                if val:
                    quarters.append((col, str(val).strip()))

            if not quarters:
                logger.error("No quarters found in Unemployment sheet")
                return None

            # Find latest and previous data rows
            latest_row = None
            previous_row = None

            for row in range(ws.max_row, 5, -1):
                date_val = ws.cell(row=row, column=1).value
                if date_val:
                    date_str = str(date_val)
                    if '2025-11' in date_str:
                        latest_row = row
                    elif '2025-08' in date_str:
                        previous_row = row

                    if latest_row and previous_row:
                        break

            # Fallback to last two rows with data
            if latest_row is None:
                data_rows = []
                for row in range(6, ws.max_row + 1):
                    if ws.cell(row=row, column=1).value:
                        data_rows.append(row)
                if len(data_rows) >= 2:
                    latest_row = data_rows[-1]
                    previous_row = data_rows[-2]
                elif len(data_rows) == 1:
                    latest_row = data_rows[0]

            def extract_row_data(row_num: int) -> Dict:
                """Extract forecast data from a row"""
                date_val = ws.cell(row=row_num, column=1).value
                date_str = str(date_val) if date_val else ""

                # Parse date
                mpr_date = ""
                if '2025-11' in date_str:
                    mpr_date = "November 2025"
                elif '2025-08' in date_str:
                    mpr_date = "August 2025"
                elif '2025-05' in date_str:
                    mpr_date = "May 2025"
                elif '2025-02' in date_str:
                    mpr_date = "February 2025"

                data = {}
                for col, quarter in quarters:
                    val = ws.cell(row=row_num, column=col).value
                    if val is not None:
                        try:
                            quarter_key = quarter.replace(' ', '')  # "2025 Q4" -> "2025Q4"
                            data[quarter_key] = float(val)
                        except (ValueError, TypeError):
                            pass

                return {
                    'date': mpr_date,
                    'data': data
                }

            # Build table_data format (quarter, latest, previous)
            table_data = []
            latest_data = extract_row_data(latest_row) if latest_row else {'data': {}}
            previous_data = extract_row_data(previous_row) if previous_row else {'data': {}}

            # Get all quarters from latest data
            all_quarters = set(latest_data['data'].keys()) | set(previous_data['data'].keys())
            sorted_quarters = sorted(all_quarters)

            # Filter to relevant quarters (2025Q2 onwards)
            for quarter in sorted_quarters:
                if quarter >= "2025Q2":
                    table_data.append({
                        'quarter': quarter,
                        'latest': latest_data['data'].get(quarter),
                        'previous': previous_data['data'].get(quarter)
                    })

            return {
                'table_data': table_data,
                'latest_forecast': latest_data.get('date', ''),
                'previous_forecast': previous_data.get('date', '')
            }

        except Exception as e:
            logger.error(f"Error parsing Unemployment from Databank: {e}")
            return None

    def _parse_old_unemployment_projections(self, wb) -> Optional[Dict]:
        """旧構造をパース"""
        try:
            # Find sheet with Unemployment projections
            sheet_name = None
            for name in wb.sheetnames:
                if 'Unemployment' in name and 'Forecast' in name:
                    sheet_name = name
                    break

            if not sheet_name:
                for name in wb.sheetnames:
                    if 'Unemployment' in name:
                        sheet_name = name
                        break

            if not sheet_name:
                logger.error("No Unemployment sheet found in workbook")
                return None

            ws = wb[sheet_name]

            # すべてのMarket Median行を検出 (D列 = 4)
            market_median_rows = []
            for row_idx in range(1, ws.max_row + 1):
                cell_value = ws.cell(row=row_idx, column=4).value
                if cell_value == "Market Median":
                    market_median_rows.append(row_idx)

            if len(market_median_rows) < 2:
                logger.error(f"Not enough Market Median rows found: {len(market_median_rows)}")
                return None

            latest_row = market_median_rows[-1]
            previous_row = market_median_rows[-2]

            # ヘッダー行 (row 5) から四半期を取得 - E列 (5) 以降
            headers = []
            header_row = 5
            for col_idx in range(5, ws.max_column + 1):
                header_value = ws.cell(row=header_row, column=col_idx).value
                if header_value and isinstance(header_value, str) and 'Q' in header_value:
                    headers.append((col_idx, header_value.strip()))
                else:
                    break

            table_data = []
            for col_idx, quarter in headers:
                latest_val = ws.cell(row=latest_row, column=col_idx).value
                previous_val = ws.cell(row=previous_row, column=col_idx).value

                table_data.append({
                    'quarter': quarter.replace(' ', ''),
                    'latest': float(latest_val) if latest_val is not None else None,
                    'previous': float(previous_val) if previous_val is not None else None
                })

            # 予測日を取得 (B列)
            latest_forecast_date = ws.cell(row=latest_row, column=2).value
            previous_forecast_date = ws.cell(row=previous_row, column=2).value

            return {
                'table_data': table_data,
                'latest_forecast': str(latest_forecast_date) if latest_forecast_date else '',
                'previous_forecast': str(previous_forecast_date) if previous_forecast_date else ''
            }

        except Exception as e:
            logger.error(f"Error parsing old Unemployment projections: {e}")
            return None

    def _fetch_unemployment_forecast_data(self) -> Optional[Dict]:
        """最新MPRから失業率見通しデータを取得"""
        try:
            mpr_info = get_mpr_info()
            latest_info = mpr_info['latest']
            previous_info = mpr_info['previous']

            logger.info(f"Fetching Unemployment forecast for {latest_info['month_name'].title()} {latest_info['year']}")

            # Try new structure first (Projections Databank)
            result = get_projections_databank(latest_info['year'], latest_info['month_name'])

            if result:
                wb, _ = result
                parsed_data = self._parse_unemployment_from_databank(wb)

                if parsed_data:
                    return {
                        "table_data": parsed_data.get("table_data", []),
                        "scenario_labels": parsed_data.get("scenario_labels"),
                        "chart_data": None,
                        "metadata": {
                            "latest_forecast": parsed_data.get("latest_forecast", ""),
                            "previous_forecast": parsed_data.get("previous_forecast", ""),
                            "last_updated": datetime.now().isoformat(),
                            "source": "Bank of England",
                            "data_source": "Projections Databank"
                        }
                    }

            # Fallback to old structure
            logger.info("Trying old structure for Unemployment projections")
            zip_content = download_mpr_zip(latest_info['year'], latest_info['month_name'])

            if zip_content:
                # Search for Unemployment file
                files = list_zip_contents(zip_content)
                unemp_file = None
                for f in files:
                    if 'unemployment rate projections' in f.lower() and f.endswith('.xlsx'):
                        unemp_file = f
                        break

                if unemp_file:
                    wb = extract_workbook_from_zip(zip_content, unemp_file)
                    if wb:
                        parsed_data = self._parse_old_unemployment_projections(wb)
                        if parsed_data:
                            return {
                                "table_data": parsed_data.get("table_data", []),
                        "scenario_labels": parsed_data.get("scenario_labels"),
                                "chart_data": None,
                                "metadata": {
                                    "latest_forecast": parsed_data.get("latest_forecast", "") or f"{latest_info['month_name'].title()} {latest_info['year']}",
                                    "previous_forecast": parsed_data.get("previous_forecast", "") or f"{previous_info['month_name'].title()} {previous_info['year']}",
                                    "last_updated": datetime.now().isoformat(),
                                    "source": "Bank of England",
                                    "data_source": "Parameters for MPC unemployment..."
                                }
                            }

            # Try previous MPR
            logger.warning(f"Unemployment data not found in {latest_info['month_name'].title()} MPR, trying previous")
            result = get_projections_databank(previous_info['year'], previous_info['month_name'])

            if result:
                wb, _ = result
                parsed_data = self._parse_unemployment_from_databank(wb)

                if parsed_data:
                    return {
                        "table_data": parsed_data.get("table_data", []),
                        "scenario_labels": parsed_data.get("scenario_labels"),
                        "chart_data": None,
                        "metadata": {
                            "latest_forecast": parsed_data.get("latest_forecast", ""),
                            "previous_forecast": parsed_data.get("previous_forecast", ""),
                            "last_updated": datetime.now().isoformat(),
                            "source": "Bank of England",
                            "note": "Using previous MPR data",
                            "data_source": "Projections Databank"
                        }
                    }

            logger.error("Failed to fetch Unemployment forecast from both MPRs")
            return None

        except Exception as e:
            logger.error(f"Error fetching BOE Unemployment forecast: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            if (now - last_updated).total_seconds() >= 7 * 24 * 3600:
                return True

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
            "table_data": [],
            "chart_data": None,
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "source": "Bank of England",
                "error": "Failed to fetch BOE unemployment forecast data"
            },
            "cached": False,
            "source": "none",
        }

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
        except Exception as e:
            logger.error(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)


# シングルトンインスタンス
boe_unemployment_forecast_service = BOEUnemploymentForecastService()
