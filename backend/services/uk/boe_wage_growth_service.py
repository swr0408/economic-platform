"""
BOE Wage Growth Service
BOE MPRデータから民間セクター賃金上昇率データを取得

データソース: {Month} {Year} MPR chart data.xlsx (November 2025以降)
旧: Section 2  - Current economic conditions.xlsx

発表スケジュール:
- 2月・5月・8月・11月のMPR発表月
- 発表時刻: 12:00 GMT
- ダウンロードウィンドウ: 20:00-20:10 GMT/BST

キャッシュ方式: ファイルキャッシュ + Redisキャッシュ
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
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


class BOEWageGrowthService(BOEServiceBase):
    """BOE Wage Growth サービス"""

    DATA_CACHE_KEY = "uk:boe_wage_growth:data"
    CACHE_FILE_PATH = CACHE_DIR / "boe_wage_growth_cache.json"
    DATA_KEY = "wage_growth"

    # Chart title keywords (prioritize detailed breakdown charts)
    PRIMARY_KEYWORDS = [
        "measures of private sector wage growth",
        "measures of annual private sector regular pay growth",
        "private sector regular pay growth",
        "private sector wage indicators",
    ]

    FALLBACK_KEYWORDS = [
        "wage growth",
        "pay growth",
    ]

    # Exclude keywords (avoid average/trend-only charts)
    EXCLUDE_KEYWORDS = [
        "public sector",
    ]

    def _fetch_data_from_source(self) -> Optional[Dict[str, Any]]:
        """MPRから賃金上昇率データを取得"""
        try:
            mpr_info = get_mpr_info()
            latest_info = mpr_info['latest']
            previous_info = mpr_info['previous']

            logger.info(f"Fetching wage growth for {latest_info['month_name'].title()} {latest_info['year']}")

            # Get chart data from latest MPR
            latest_wb = get_chart_data(latest_info['year'], latest_info['month_name'])

            latest_data = None
            actual_info = latest_info

            if latest_wb:
                ws = find_chart_sheet_by_keywords(
                    latest_wb,
                    self.PRIMARY_KEYWORDS,
                    self.FALLBACK_KEYWORDS,
                    self.EXCLUDE_KEYWORDS
                )
                if ws:
                    latest_data = self._extract_data_from_sheet(ws)

            # Try previous MPR if latest failed
            if latest_data is None or len(latest_data.get('date', [])) == 0:
                logger.warning("Wage growth not found in latest MPR, trying previous")
                previous_wb = get_chart_data(previous_info['year'], previous_info['month_name'])
                actual_info = previous_info

                if previous_wb:
                    ws = find_chart_sheet_by_keywords(
                        previous_wb,
                        self.PRIMARY_KEYWORDS,
                        self.FALLBACK_KEYWORDS,
                        self.EXCLUDE_KEYWORDS
                    )
                    if ws:
                        latest_data = self._extract_data_from_sheet(ws)

            if latest_data:
                return {
                    self.DATA_KEY: {"data": latest_data},
                    "metadata": {
                        "last_updated": datetime.now().isoformat(),
                        "source": "Bank of England",
                        "mpr_date": f"{actual_info['month_name'].title()} {actual_info['year']}",
                        "data_source": "MPR Chart Data"
                    }
                }

            return None

        except Exception as e:
            logger.error(f"Error fetching BOE wage growth: {e}")
            return None

    def _extract_data_from_sheet(self, ws) -> Dict[str, List]:
        """シートから賃金上昇率データを抽出

        Nov 2025 MPR構造:
        - Row 5: Group headers
        - Row 6: Series names (Col 1 = "Date")
        - Row 7+: Data
        """
        data = {'date': [], 'series': {}}

        # Detect header structure
        if detect_multi_row_header(ws):
            HEADER_ROW = 6
            DATA_START_ROW = 7
            logger.info("Detected multi-row header structure")
        else:
            HEADER_ROW = 5
            DATA_START_ROW = 6
            logger.info("Using standard header structure")

        # Get series names from header row
        series_columns = {}
        for col in range(2, 20):
            header_cell = ws.cell(row=HEADER_ROW, column=col)
            if header_cell.value is None:
                continue

            series_name = str(header_cell.value).strip().replace('\n', ' ').replace('\r', '')

            # Skip certain patterns
            if series_name.lower() == 'date':
                continue
            if any(skip in series_name.lower() for skip in ['confidence band', 'estimated trend']):
                continue
            if series_name.startswith('='):
                continue

            series_columns[col] = series_name
            data['series'][series_name] = []

        logger.info(f"Found series: {list(data['series'].keys())}")

        # Extract data rows
        row_num = DATA_START_ROW
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
                if value is None or (isinstance(value, str) and value.strip().lower() == 'n.a.'):
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
boe_wage_growth_service = BOEWageGrowthService()
