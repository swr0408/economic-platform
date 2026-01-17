"""
BOE Inflation Expectations Service
BOE MPRチャートデータからインフレ期待データを取得

データソース: {Month} {Year} MPR chart data.xlsx (November 2025以降)
旧: Section 2  - Current economic conditions.xlsx
- Chart 1.6: Inflation expectations（家計/企業インフレ期待）

発表スケジュール:
- 2月・5月・8月・11月のMPR発表月
- 発表時刻: 12:00 GMT
- ダウンロードウィンドウ: 20:00-20:10 GMT/BST

キャッシュ方式: ファイルキャッシュ + Redisキャッシュ
"""
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from pathlib import Path

from .boe_base import BOEServiceBase
from .boe_mpr_utils import (
    get_mpr_info,
    get_chart_data,
    parse_date_to_yyyy_mm,
    detect_multi_row_header,
    find_chart_sheet_by_keywords,
)

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "economic_outlook"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class BOEInflationExpectationsService(BOEServiceBase):
    """BOE Inflation Expectations サービス"""

    DATA_CACHE_KEY = "uk:boe_inflation_expectations:data"
    CACHE_FILE_PATH = CACHE_DIR / "boe_inflation_expectations_cache.json"
    DATA_KEY = "inflation_expectations"

    # Chart title keywords (prioritize multi-series charts)
    PRIMARY_KEYWORDS = [
        "survey-based measures of household and business inflation expectations",
        "selected measures of inflation expectations",
        "household and business inflation expectations",
        "households and firms inflation expectations",
    ]

    FALLBACK_KEYWORDS = [
        "inflation expectations",
        "household inflation expectations",
    ]

    def _fetch_data_from_source(self) -> Optional[Dict[str, Any]]:
        """MPRからインフレ期待データを取得"""
        try:
            mpr_info = get_mpr_info()
            latest_info = mpr_info['latest']
            previous_info = mpr_info['previous']

            logger.info(f"Fetching inflation expectations for {latest_info['month_name'].title()} {latest_info['year']}")

            # Get chart data from latest MPR
            latest_wb = get_chart_data(latest_info['year'], latest_info['month_name'])

            latest_data = None
            if latest_wb:
                ws = find_chart_sheet_by_keywords(
                    latest_wb,
                    self.PRIMARY_KEYWORDS,
                    self.FALLBACK_KEYWORDS
                )
                if ws:
                    latest_data = self._extract_data_from_sheet(ws)

            # Try previous MPR if latest failed
            if latest_data is None or len(latest_data.get('date', [])) == 0:
                logger.warning("Inflation expectations not found in latest MPR, trying previous")
                previous_wb = get_chart_data(previous_info['year'], previous_info['month_name'])

                if previous_wb:
                    ws = find_chart_sheet_by_keywords(
                        previous_wb,
                        self.PRIMARY_KEYWORDS,
                        self.FALLBACK_KEYWORDS
                    )
                    if ws:
                        latest_data = self._extract_data_from_sheet(ws)

            if latest_data:
                return {
                    self.DATA_KEY: {"data": latest_data},
                    "metadata": {
                        "last_updated": datetime.now().isoformat(),
                        "source": "Bank of England",
                        "mpr_date": f"{latest_info['month_name'].title()} {latest_info['year']}",
                        "data_source": "MPR Chart Data"
                    }
                }

            return None

        except Exception as e:
            logger.error(f"Error fetching BOE inflation expectations: {e}")
            return None

    def _extract_data_from_sheet(self, ws) -> Dict[str, Any]:
        """シートからインフレ期待データを抽出

        Nov 2025 MPR構造:
        - Row 5: Group headers
        - Row 6: Series names (Col 1 = "Date")
        - Row 7+: Data

        重要: HouseholdsとBusinessesは別々の日付列を持つ
        """
        if not detect_multi_row_header(ws):
            return self._extract_data_simple(ws)

        logger.info("Detected multi-row header structure with separate date columns")
        DATA_START_ROW = 7

        # Find date columns and group headers
        date_columns = []
        column_group_map = {}

        # Scan row 5 for group headers
        last_group = None
        for col in range(1, 20):
            group_cell = ws.cell(row=5, column=col).value
            if group_cell:
                last_group = str(group_cell).strip()
            column_group_map[col] = last_group

        # Scan row 6 for date columns
        for col in range(1, 20):
            cell_val = ws.cell(row=6, column=col).value
            if cell_val and str(cell_val).strip().lower() == 'date':
                date_columns.append(col)

        logger.info(f"Found date columns at: {date_columns}")

        # Build groups
        groups = []
        for i, date_col in enumerate(date_columns):
            end_col = date_columns[i + 1] if i + 1 < len(date_columns) else 20

            # Find group name
            group_name = None
            for col in range(date_col, end_col):
                group_cell = ws.cell(row=5, column=col).value
                if group_cell:
                    group_name = str(group_cell).strip()
                    break

            if not group_name and date_col > 1:
                group_name = column_group_map.get(date_col - 1)

            group_info = {
                'date_col': date_col,
                'group_name': group_name,
                'series': []
            }

            # Find series columns
            for col in range(date_col + 1, end_col):
                series_cell = ws.cell(row=6, column=col).value
                if series_cell:
                    series_name = str(series_cell).strip().replace('\n', ' ').replace('\r', '')
                    if series_name.lower() != 'date' and not series_name.startswith('='):
                        is_average = 'average' in series_name.lower()
                        group_info['series'].append({
                            'col': col,
                            'name': series_name,
                            'is_average': is_average
                        })

            groups.append(group_info)
            logger.info(f"Group: {group_name}, date_col: {date_col}, series: {[s['name'] for s in group_info['series']]}")

        # Extract data from each group
        all_data = {}

        for group in groups:
            group_name = group['group_name'] or ''
            # Shorten group name
            if 'households' in group_name.lower():
                group_short = '家計'
            elif 'businesses' in group_name.lower() or 'firms' in group_name.lower():
                group_short = '企業'
            else:
                group_short = group_name

            date_col = group['date_col']
            row_num = DATA_START_ROW

            while True:
                date_cell = ws.cell(row=row_num, column=date_col)
                if date_cell.value is None:
                    break

                date_str = parse_date_to_yyyy_mm(date_cell.value)
                if date_str is None:
                    row_num += 1
                    continue

                if date_str not in all_data:
                    all_data[date_str] = {}

                for series_info in group['series']:
                    col = series_info['col']
                    series_name = series_info['name']
                    is_average = series_info['is_average']

                    # Build series name
                    if is_average:
                        full_name = f"{group_short} - {series_name}"
                    else:
                        clean_name = series_name.replace('expectations', '').strip()
                        if clean_name.lower().startswith('short-term'):
                            clean_name = '短期'
                        elif clean_name.lower().startswith('medium-term'):
                            clean_name = '中期'
                        full_name = f"{group_short} - {clean_name}"

                    value = ws.cell(row=row_num, column=col).value

                    if value is None or (isinstance(value, str) and value.strip().lower() in ['n.a.', 'na', '']):
                        all_data[date_str][full_name] = None
                    else:
                        try:
                            all_data[date_str][full_name] = float(value)
                        except (ValueError, TypeError):
                            all_data[date_str][full_name] = None

                row_num += 1

        # Convert to output format
        sorted_dates = sorted(all_data.keys())
        all_series = set()
        for date_data in all_data.values():
            all_series.update(date_data.keys())

        data = {
            'date': sorted_dates,
            'series': {name: [] for name in sorted(all_series)}
        }

        for date_str in sorted_dates:
            date_data = all_data.get(date_str, {})
            for series_name in data['series'].keys():
                value = date_data.get(series_name)
                data['series'][series_name].append(value)

        logger.info(f"Extracted {len(sorted_dates)} dates, series: {list(data['series'].keys())}")
        return data

    def _extract_data_simple(self, ws) -> Dict[str, Any]:
        """シンプルな単一日付列構造用のフォールバック抽出"""
        data = {'date': [], 'series': {}}

        # Get headers from row 5
        series_columns = {}
        for col in range(2, 20):
            header_cell = ws.cell(row=5, column=col)
            if header_cell.value is None:
                continue
            series_name = str(header_cell.value).strip().replace('\n', ' ').replace('\r', '')
            series_columns[col] = series_name
            data['series'][series_name] = []

        logger.info(f"Simple extraction - Found series: {list(data['series'].keys())}")

        row_num = 6
        while True:
            date_cell = ws.cell(row=row_num, column=1)
            if date_cell.value is None:
                break

            date_str = parse_date_to_yyyy_mm(date_cell.value)
            if date_str is None:
                row_num += 1
                continue

            data['date'].append(date_str)

            for col_idx, series_name in series_columns.items():
                value = ws.cell(row=row_num, column=col_idx).value
                if value is None or (isinstance(value, str) and value.strip().lower() in ['n.a.', 'na', '']):
                    data['series'][series_name].append(None)
                else:
                    try:
                        data['series'][series_name].append(float(value))
                    except (ValueError, TypeError):
                        data['series'][series_name].append(None)

            row_num += 1

        logger.info(f"Extracted {len(data['date'])} data points")
        return data


# シングルトンインスタンス
boe_inflation_expectations_service = BOEInflationExpectationsService()
