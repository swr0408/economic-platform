"""
BOE CPI Projections Service
BOE MPRデータからCPIインフレ見通しデータを取得

データソース (November 2025以降):
- Projections Databank - {Month} {Year} MPR.xlsx
  - 1. CPI inflation シート (見通し)
  - 35. CPI inflation distribution シート (ファン/分布) - 任意

データソース (旧構造):
- Parameters for MPC CPI inflation projections from February 2004.xlsx

発表スケジュール: Market Expectationsと同じ (2月・5月・8月・11月のMPR)

キャッシュ方式: ファイルキャッシュ + Redisキャッシュ
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
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
    OLD_FILES,
    DEFAULT_MPR_MONTHS
)

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "economic_outlook"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "boe_cpi_projections_cache.json"


class BOECPIProjectionsService:
    """BOE CPI Projections サービス"""

    DATA_CACHE_KEY = "uk:boe_cpi_projections:data"
    SHEET_NAME = "1. CPI inflation"
    DISTRIBUTION_SHEET = "35. CPI inflation distribution"

    def __init__(self):
        pass

    def get_cpi_projections(self, force_refresh: bool = False) -> Dict[str, Any]:
        """CPI見通しデータを取得"""
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
        data = self._fetch_cpi_projections_data()

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

    def _parse_cpi_from_databank(self, wb) -> Optional[Dict]:
        """Projections DatabankからCPI inflationデータを抽出

        1. CPI inflation シート構造:
        - Row 5: Column headers (quarters: 2004 Q1, 2004 Q2, ...)
        - Column 1: Date of publication (2004-02-01, 2004-05-01, ...)
        - Data starts from row 6

        Returns data in table_data format (same as GDP/Unemployment forecasts)
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
                logger.error("No quarters found in CPI inflation sheet")
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
                """Extract projection data from a row"""
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

            # Build table_data format (quarter, latest, previous) - same as GDP/Unemployment
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

            logger.info(f"Extracted CPI projection: {len(table_data)} quarters (2025Q2 onwards)")

            return {
                'table_data': table_data,
                'latest_forecast': latest_data.get('date', ''),
                'previous_forecast': previous_data.get('date', '')
            }

        except Exception as e:
            logger.error(f"Error parsing CPI from Databank: {e}")
            return None

    def _parse_old_cpi_projections(self, wb) -> Optional[Dict]:
        """旧構造 (Parameters for MPC CPI...) をパース"""
        try:
            ws = wb['CPI Forecast']

            # すべてのMarket Median行を検出
            market_median_rows = []
            for i in range(1, ws.max_row + 1):
                cell_d = ws.cell(row=i, column=4).value
                cell_c = ws.cell(row=i, column=3).value
                if cell_d == 'Market Median' and cell_c == 'Market':
                    market_median_rows.append(i)

            if len(market_median_rows) < 2:
                logger.error(f"Not enough Market Median rows found: {len(market_median_rows)}")
                return None

            latest_row = market_median_rows[-1]
            previous_row = market_median_rows[-2]

            logger.info(f"Found Market Median rows: Latest={latest_row}, Previous={previous_row}")

            # row 5から四半期ラベルを取得
            quarters = []
            for j in range(91, ws.max_column + 1):
                quarter_label = ws.cell(row=5, column=j).value
                if quarter_label:
                    quarters.append((j, str(quarter_label)))
                else:
                    break

            logger.info(f"Found {len(quarters)} quarters")

            # 最新と前回のデータを抽出
            latest_data = []
            previous_data = []

            for col_idx, quarter in quarters:
                # Latest Market Median
                val = ws.cell(row=latest_row, column=col_idx).value
                if val is not None:
                    latest_data.append({
                        'date': quarter,
                        'value': float(val)
                    })

                # Previous Market Median
                val_prev = ws.cell(row=previous_row, column=col_idx).value
                if val_prev is not None:
                    previous_data.append({
                        'date': quarter,
                        'value': float(val_prev)
                    })

            # レポート日を取得
            latest_month = ws.cell(row=latest_row, column=2).value
            previous_month = ws.cell(row=previous_row, column=2).value

            return {
                'latest_projection': {
                    'date': str(latest_month) if latest_month else '',
                    'data': latest_data
                },
                'previous_projection': {
                    'date': str(previous_month) if previous_month else '',
                    'data': previous_data
                }
            }

        except Exception as e:
            logger.error(f"Error parsing old CPI projections: {e}")
            return None

    def _fetch_cpi_projections_data(self) -> Optional[Dict]:
        """最新MPRからCPI見通しデータを取得"""
        try:
            mpr_info = get_mpr_info()
            latest_info = mpr_info['latest']
            previous_info = mpr_info['previous']

            logger.info(f"Fetching CPI projections for {latest_info['month_name'].title()} {latest_info['year']}")

            # Try new structure first (Projections Databank)
            result = get_projections_databank(latest_info['year'], latest_info['month_name'])

            if result:
                wb, _ = result
                parsed_data = self._parse_cpi_from_databank(wb)

                if parsed_data and parsed_data.get('table_data'):
                    return {
                        "table_data": parsed_data.get('table_data', []),
                        "scenario_labels": parsed_data.get("scenario_labels"),
                        "chart_data": None,  # Chart data not used for CPI projections table
                        "metadata": {
                            "last_updated": datetime.now().isoformat(),
                            "source": "Bank of England",
                            "mpr_date": f"{latest_info['month_name'].title()} {latest_info['year']}",
                            "latest_forecast": parsed_data.get('latest_forecast', ''),
                            "previous_forecast": parsed_data.get('previous_forecast', ''),
                            "data_source": "Projections Databank"
                        }
                    }

            # Fallback to old structure
            logger.info("Trying old structure (Parameters for MPC CPI...)")
            zip_content = download_mpr_zip(latest_info['year'], latest_info['month_name'])

            if zip_content:
                wb = extract_workbook_from_zip(zip_content, OLD_FILES["cpi_projections"])
                if wb:
                    parsed_data = self._parse_old_cpi_projections(wb)
                    if parsed_data:
                        # Convert old format to table_data format
                        table_data = self._convert_old_to_table_data(parsed_data)
                        return {
                            "table_data": table_data,
                            "chart_data": None,
                            "metadata": {
                                "last_updated": datetime.now().isoformat(),
                                "source": "Bank of England",
                                "mpr_date": f"{latest_info['month_name'].title()} {latest_info['year']}",
                                "latest_forecast": parsed_data.get('latest_projection', {}).get('date', ''),
                                "previous_forecast": parsed_data.get('previous_projection', {}).get('date', ''),
                                "data_source": "Parameters for MPC CPI..."
                            }
                        }

            # Try previous MPR
            logger.warning(f"CPI data not found in {latest_info['month_name'].title()} MPR, trying previous")
            result = get_projections_databank(previous_info['year'], previous_info['month_name'])

            if result:
                wb, _ = result
                parsed_data = self._parse_cpi_from_databank(wb)

                if parsed_data and parsed_data.get('table_data'):
                    return {
                        "table_data": parsed_data.get('table_data', []),
                        "scenario_labels": parsed_data.get("scenario_labels"),
                        "chart_data": None,
                        "metadata": {
                            "last_updated": datetime.now().isoformat(),
                            "source": "Bank of England",
                            "mpr_date": f"{previous_info['month_name'].title()} {previous_info['year']}",
                            "latest_forecast": parsed_data.get('latest_forecast', ''),
                            "previous_forecast": parsed_data.get('previous_forecast', ''),
                            "note": "Using previous MPR data",
                            "data_source": "Projections Databank"
                        }
                    }

            logger.error("Failed to fetch CPI projections from both MPRs")
            return None

        except Exception as e:
            logger.error(f"Error fetching BOE CPI projections: {e}")
            return None

    def _convert_old_to_table_data(self, parsed_data: Dict) -> List[Dict]:
        """旧形式のデータをtable_data形式に変換"""
        table_data = []
        latest_proj = parsed_data.get('latest_projection', {}).get('data', [])
        previous_proj = parsed_data.get('previous_projection', {}).get('data', [])

        # Build lookup for previous data
        prev_lookup = {item['date']: item['value'] for item in previous_proj}

        for item in latest_proj:
            quarter = item['date'].replace(' ', '')  # "2025 Q4" -> "2025Q4"
            if quarter >= "2025Q2":
                table_data.append({
                    'quarter': quarter,
                    'latest': item['value'],
                    'previous': prev_lookup.get(item['date'])
                })

        return table_data

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
                "error": "Failed to fetch BOE CPI projections data"
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
boe_cpi_projections_service = BOECPIProjectionsService()
