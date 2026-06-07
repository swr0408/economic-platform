"""
BOE Average Weekly Earnings Service
BOE Projections DatabankからAverage Weekly Earnings（平均週間賃金）データを取得

データソース: Projections Databank - {Month} {Year} MPR.xlsx
- Sheet: 30. Average weekly earnings

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
from .boe_mpr_utils import get_mpr_info, get_projections_databank, resolve_sheet_by_suffix

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "economic_outlook"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class BOEAverageWeeklyEarningsService(BOEServiceBase):
    """BOE Average Weekly Earnings サービス"""

    DATA_CACHE_KEY = "uk:boe_average_weekly_earnings:data"
    CACHE_FILE_PATH = CACHE_DIR / "boe_average_weekly_earnings_cache.json"
    DATA_KEY = "average_weekly_earnings"
    # MPRごとに番号がドリフトするためsuffix一致で解決
    SHEET_SUFFIX = "Average weekly earnings"

    def _fetch_data_from_source(self) -> Optional[Dict[str, Any]]:
        """MPRからAverage Weekly Earningsデータを取得"""
        try:
            mpr_info = get_mpr_info()
            latest_info = mpr_info['latest']
            previous_info = mpr_info['previous']

            logger.info(f"Fetching AWE for {latest_info['month_name'].title()} {latest_info['year']}")

            # Get Projections Databank from latest MPR
            result = get_projections_databank(latest_info['year'], latest_info['month_name'])

            latest_data = None
            actual_mpr_info = latest_info

            if result:
                wb, _ = result
                sheet_name = resolve_sheet_by_suffix(wb, self.SHEET_SUFFIX)
                if sheet_name:
                    ws = wb[sheet_name]
                    latest_data = self._extract_data_from_sheet(ws)
                else:
                    logger.warning(f"Sheet matching '{self.SHEET_SUFFIX}' not found in Databank")

            # Try previous MPR if latest failed
            if latest_data is None or latest_data.get('latest') is None:
                logger.warning("AWE not found in latest MPR, trying previous")
                result = get_projections_databank(previous_info['year'], previous_info['month_name'])
                actual_mpr_info = previous_info

                if result:
                    wb, _ = result
                    sheet_name = resolve_sheet_by_suffix(wb, self.SHEET_SUFFIX)
                    if sheet_name:
                        ws = wb[sheet_name]
                        latest_data = self._extract_data_from_sheet(ws)

            if latest_data and latest_data.get('latest'):
                return {
                    self.DATA_KEY: latest_data,
                    "metadata": {
                        "last_updated": datetime.now().isoformat(),
                        "source": "Bank of England",
                        "mpr_date": f"{actual_mpr_info['month_name'].title()} {actual_mpr_info['year']}",
                        "data_source": "Projections Databank"
                    }
                }

            return None

        except Exception as e:
            logger.error(f"Error fetching BOE AWE: {e}")
            return None

    def _extract_data_from_sheet(self, ws) -> Dict[str, Any]:
        """シートからAverage Weekly Earningsデータを抽出"""
        data = {'quarters': [], 'latest': None, 'previous': None}

        HEADER_ROW = 5
        DATA_START_ROW = 6

        # Get column headers (quarters)
        quarters = []
        for col in range(2, ws.max_column + 1):
            val = ws.cell(row=HEADER_ROW, column=col).value
            if val:
                quarters.append((col, str(val).strip()))
            else:
                break

        data['quarters'] = [q[1] for q in quarters]
        logger.info(f"Found {len(quarters)} quarters")

        # Find data rows
        data_rows = []
        for row in range(DATA_START_ROW, ws.max_row + 1):
            date_val = ws.cell(row=row, column=1).value
            if date_val and str(date_val).strip():
                data_rows.append((row, str(date_val).strip()))

        if not data_rows:
            return data

        def extract_row_data(row_num: int, date_str: str) -> Dict[str, Any]:
            values = []
            for col, quarter in quarters:
                val = ws.cell(row=row_num, column=col).value
                try:
                    values.append({'quarter': quarter, 'value': float(val) if val is not None else None})
                except (ValueError, TypeError):
                    values.append({'quarter': quarter, 'value': None})
            return {'date': date_str, 'data': values}

        # Latest and previous data
        latest_row, latest_date = data_rows[-1]
        data['latest'] = extract_row_data(latest_row, latest_date)

        if len(data_rows) >= 2:
            previous_row, previous_date = data_rows[-2]
            data['previous'] = extract_row_data(previous_row, previous_date)

        logger.info(f"Extracted AWE data: latest={latest_date}")
        return data


# シングルトンインスタンス
boe_average_weekly_earnings_service = BOEAverageWeeklyEarningsService()
