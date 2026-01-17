"""
BOE Services Inflation Service
BOE MPRチャートデータからサービスインフレ（基調インフレ）データを取得

データソース: {Month} {Year} MPR chart data.xlsx (November 2025以降)
旧: Section 2  - Current economic conditions.xlsx
- Chart 1.5: Measures of underlying services inflation（サービスインフレ指標）

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
    find_chart_sheet_by_keywords,
)

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "economic_outlook"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class BOEServicesInflationService(BOEServiceBase):
    """BOE Services Inflation サービス"""

    DATA_CACHE_KEY = "uk:boe_services_inflation:data"
    CACHE_FILE_PATH = CACHE_DIR / "boe_services_inflation_cache.json"
    DATA_KEY = "services_inflation"

    # Chart title keywords
    PRIMARY_KEYWORDS = [
        "services price inflation",
        "annualised services",
        "underlying services inflation",
        "measures of underlying services inflation",
    ]

    def _fetch_data_from_source(self) -> Optional[Dict[str, Any]]:
        """MPRからサービスインフレデータを取得"""
        try:
            mpr_info = get_mpr_info()
            latest_info = mpr_info['latest']
            previous_info = mpr_info['previous']

            logger.info(f"Fetching services inflation for {latest_info['month_name'].title()} {latest_info['year']}")

            # Get chart data from latest MPR
            latest_wb = get_chart_data(latest_info['year'], latest_info['month_name'])

            latest_data = None
            if latest_wb:
                ws = find_chart_sheet_by_keywords(latest_wb, self.PRIMARY_KEYWORDS)
                if ws:
                    latest_data = self._extract_data_from_sheet(ws)

            # Try previous MPR if latest failed
            if latest_data is None or len(latest_data.get('date', [])) == 0:
                logger.warning("Services inflation not found in latest MPR, trying previous")
                previous_wb = get_chart_data(previous_info['year'], previous_info['month_name'])

                if previous_wb:
                    ws = find_chart_sheet_by_keywords(previous_wb, self.PRIMARY_KEYWORDS)
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
            logger.error(f"Error fetching BOE services inflation: {e}")
            return None

    def _extract_data_from_sheet(self, ws) -> Dict[str, Any]:
        """シートからサービスインフレデータを抽出"""
        data = {'date': [], 'series': {}}

        HEADER_ROW = 5
        DATA_START_ROW = 6

        # Get column headers
        series_columns = {}
        for col in range(2, 20):
            header_cell = ws.cell(row=HEADER_ROW, column=col)
            if header_cell.value is None:
                break

            series_name = str(header_cell.value).strip().replace('\n', ' ').replace('\r', '')
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
boe_services_inflation_service = BOEServicesInflationService()
