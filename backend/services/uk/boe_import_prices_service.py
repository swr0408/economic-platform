"""
BOE Import Prices Service
BOE MPRからエネルギー・輸入物価データを取得

データソース (November 2025以降):
- Projections Databank - {Month} {Year} MPR.xlsx
  - 28. Import prices シート (輸入物価)
  - 29. Import prices distrib シート (分布) - 任意
- {Month} {Year} MPR chart data.xlsx
  - Chart 1.2: Energy prices & import costs（エネルギー価格）

発表スケジュール: 2月・5月・8月・11月のMPR

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
    get_chart_data,
    DEFAULT_MPR_MONTHS
)

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "economic_outlook"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "boe_import_prices_cache.json"


class BOEImportPricesService:
    """BOE Import Prices サービス"""

    DATA_CACHE_KEY = "uk:boe_import_prices:data"

    # Projections Databank sheet names (Nov 2025)
    IMPORT_PRICES_SHEET = "28. UK import prices"
    ENERGY_PRICES_SHEET = "29. Energy prices"

    # Chart name patterns for import prices chart (A3 cell contains chart title)
    # Nov 2025: "Chart 1.2 - Import prices (percentage changes on a year earlier)"
    CHART_TITLE_KEYWORDS = [
        "import prices",
        "percentage changes on a year earlier"
    ]

    # Sheet name patterns
    SHEET_PREFIX_NEW = "Chart 1."
    SHEET_PREFIX_OLD = "Chart 2."

    def __init__(self):
        pass

    def fetch_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """輸入物価データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "import_prices": cached_data.get("import_prices", {}),
                        "energy_prices": cached_data.get("energy_prices", {}),
                        "chart_data": cached_data.get("chart_data", {}),
                        "metadata": cached_data.get("metadata", {}),
                        "cached": True,
                        "source": "redis",
                    }

        # MPRからデータを取得
        data = self._fetch_import_prices_data()

        if data:
            cache_payload = {
                "import_prices": data.get("import_prices", {}),
                "energy_prices": data.get("energy_prices", {}),
                "chart_data": data.get("chart_data", {}),
                "metadata": data.get("metadata", {}),
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "import_prices": data.get("import_prices", {}),
                "energy_prices": data.get("energy_prices", {}),
                "chart_data": data.get("chart_data", {}),
                "metadata": data.get("metadata", {}),
                "cached": False,
                "source": "boe_mpr",
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "import_prices": file_cache.get("import_prices", {}),
                "energy_prices": file_cache.get("energy_prices", {}),
                "chart_data": file_cache.get("chart_data", {}),
                "metadata": file_cache.get("metadata", {}),
                "cached": True,
                "source": "file (fallback)",
            }

        return self._get_fallback_data()

    def _parse_databank_sheet(self, wb, sheet_name: str) -> Optional[Dict]:
        """Projections Databankからシートをパース

        シート構造:
        - Row 5: Column headers (quarters: 2013 Q3, 2013 Q4, ...)
        - Column 1: Date of publication
        - Data starts from row 6
        """
        try:
            # シート番号はMPRごとにドリフトするため動的解決する。
            # 2026年4月版で "UK import prices" シート自体が廃止されたケースは
            # None を返し、呼び出し側のフォールバック (旧データ温存) に任せる
            resolved = resolve_sheet(wb, sheet_name)
            if resolved is None:
                logger.warning(f"Sheet {sheet_name} not found (even by suffix)")
                return None

            ws = wb[resolved]

            # 2026年4月MPR以降の転置シナリオ方式レイアウトを先に試す
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
                logger.error(f"No quarters found in {sheet_name} sheet")
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

            # Build table_data format
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
            logger.error(f"Error parsing {sheet_name} from Databank: {e}")
            return None

    def _parse_import_prices_from_databank(self, wb) -> Optional[Dict]:
        """Projections Databankから輸入物価データを抽出

        28. UK import prices シート構造:
        - Row 5: Column headers (quarters: 2013 Q3, 2013 Q4, ...)
        - Column 1: Date of publication
        - Data starts from row 6
        """
        return self._parse_databank_sheet(wb, self.IMPORT_PRICES_SHEET)

    def _parse_energy_prices_from_databank(self, wb) -> Optional[Dict]:
        """Projections Databankからエネルギー価格データを抽出

        29. Energy prices シート構造:
        - Row 5: Column headers (quarters)
        - Column 1: Date of publication
        - Data starts from row 6
        """
        return self._parse_databank_sheet(wb, self.ENERGY_PRICES_SHEET)

    def _find_import_prices_chart_sheet(self, wb) -> Optional[Any]:
        """輸入物価チャートシートを検索 (Chart 1.2)"""
        sheet_prefixes = [self.SHEET_PREFIX_NEW, self.SHEET_PREFIX_OLD]

        for sheet_name in wb.sheetnames:
            matches_prefix = any(sheet_name.startswith(prefix) for prefix in sheet_prefixes)
            if not matches_prefix:
                continue

            try:
                ws = wb[sheet_name]
                a3_value = ws['A3'].value

                if a3_value:
                    a3_lower = str(a3_value).lower()
                    if any(keyword in a3_lower for keyword in self.CHART_TITLE_KEYWORDS):
                        logger.info(f"Found import prices chart sheet: {sheet_name}")
                        return ws

            except (ValueError, IndexError, KeyError):
                continue

        logger.warning("Could not find sheet with import prices keywords in cell A3")
        return None

    def _extract_chart_data_from_sheet(self, ws) -> Dict[str, Any]:
        """シートからチャートデータを抽出"""
        data = {
            'date': [],
            'series': {}
        }

        HEADER_ROW = 5
        DATA_START_ROW = 6

        # Get column headers
        col_idx = 2
        series_columns = {}

        while True:
            header_cell = ws.cell(row=HEADER_ROW, column=col_idx)
            if header_cell.value is None:
                break

            series_name = str(header_cell.value).strip().replace('\n', ' ').replace('\r', '')
            series_columns[col_idx] = series_name
            data['series'][series_name] = []
            col_idx += 1

        logger.info(f"Found chart series: {list(data['series'].keys())}")

        # Extract data rows
        row_num = DATA_START_ROW

        while True:
            date_cell = ws.cell(row=row_num, column=1)

            if date_cell.value is None:
                break

            # Parse date
            if isinstance(date_cell.value, datetime):
                date_str = date_cell.value.strftime('%Y-%m')
            else:
                raw_date = str(date_cell.value).strip()
                raw_date = raw_date.replace('\n', ' ').replace('\r', '')

                try:
                    month_names = {
                        'january': 1, 'february': 2, 'march': 3, 'april': 4,
                        'may': 5, 'june': 6, 'july': 7, 'august': 8,
                        'september': 9, 'october': 10, 'november': 11, 'december': 12,
                        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
                        'jun': 6, 'jul': 7, 'aug': 8,
                        'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                    }
                    parts = raw_date.split()
                    if len(parts) >= 2:
                        month_name = parts[0].lower()
                        year = parts[-1]
                        if month_name in month_names:
                            month_num = month_names[month_name]
                            date_str = f"{year}-{month_num:02d}"
                        else:
                            if raw_date.startswith('Q') or any(f'Q{i}' in raw_date for i in range(1, 5)):
                                date_str = raw_date.replace(' ', '')
                            else:
                                row_num += 1
                                continue
                    else:
                        date_str = raw_date
                except Exception as e:
                    row_num += 1
                    continue

            data['date'].append(date_str)

            for col_idx, series_name in series_columns.items():
                value_cell = ws.cell(row=row_num, column=col_idx)
                value = value_cell.value

                if value is None or (isinstance(value, str) and value.strip().lower() in ['n.a.', 'na', '']):
                    data['series'][series_name].append(None)
                else:
                    try:
                        data['series'][series_name].append(float(value))
                    except (ValueError, TypeError):
                        data['series'][series_name].append(None)

            row_num += 1

        logger.info(f"Extracted {len(data['date'])} chart data points")
        return data

    def _fetch_import_prices_data(self) -> Optional[Dict]:
        """最新のMPRから輸入物価/エネルギー価格データを取得"""
        try:
            mpr_info = get_mpr_info()
            latest_info = mpr_info['latest']
            previous_info = mpr_info['previous']

            logger.info(f"Fetching import prices for {latest_info['month_name'].title()} {latest_info['year']}")

            import_prices_data = None
            energy_prices_data = None
            chart_data = None

            # Get data from Projections Databank
            result = get_projections_databank(latest_info['year'], latest_info['month_name'])

            if result:
                wb, zip_content = result
                import_prices_data = self._parse_import_prices_from_databank(wb)
                energy_prices_data = self._parse_energy_prices_from_databank(wb)

                # Also get chart data for import prices (Chart 1.2)
                from .boe_mpr_utils import get_chart_data
                chart_wb = get_chart_data(latest_info['year'], latest_info['month_name'], zip_content)
                if chart_wb:
                    ws = self._find_import_prices_chart_sheet(chart_wb)
                    if ws:
                        chart_data = self._extract_chart_data_from_sheet(ws)

            # Try previous MPR if latest failed
            if import_prices_data is None:
                logger.warning(f"Import prices not found in latest MPR, trying previous")
                result = get_projections_databank(previous_info['year'], previous_info['month_name'])

                if result:
                    wb, zip_content = result
                    import_prices_data = self._parse_import_prices_from_databank(wb)
                    if energy_prices_data is None:
                        energy_prices_data = self._parse_energy_prices_from_databank(wb)

                    if chart_data is None:
                        from .boe_mpr_utils import get_chart_data
                        chart_wb = get_chart_data(previous_info['year'], previous_info['month_name'], zip_content)
                        if chart_wb:
                            ws = self._find_import_prices_chart_sheet(chart_wb)
                            if ws:
                                chart_data = self._extract_chart_data_from_sheet(ws)

            return {
                "import_prices": {
                    "table_data": import_prices_data.get("table_data", []) if import_prices_data else [],
                    "latest_forecast": import_prices_data.get("latest_forecast", "") if import_prices_data else "",
                    "previous_forecast": import_prices_data.get("previous_forecast", "") if import_prices_data else ""
                },
                "energy_prices": {
                    "table_data": energy_prices_data.get("table_data", []) if energy_prices_data else [],
                    "latest_forecast": energy_prices_data.get("latest_forecast", "") if energy_prices_data else "",
                    "previous_forecast": energy_prices_data.get("previous_forecast", "") if energy_prices_data else ""
                },
                "chart_data": chart_data if chart_data else {"date": [], "series": {}},
                "metadata": {
                    "last_updated": datetime.now().isoformat(),
                    "source": "Bank of England",
                    "mpr_date": f"{latest_info['month_name'].title()} {latest_info['year']}",
                    "data_source": "Projections Databank (Sheet 28/29) + MPR Chart Data (Chart 1.2)"
                }
            }

        except Exception as e:
            logger.error(f"Error fetching BOE import prices: {e}")
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
            "import_prices": {
                "table_data": [],
                "latest_forecast": "",
                "previous_forecast": ""
            },
            "energy_prices": {
                "table_data": [],
                "latest_forecast": "",
                "previous_forecast": ""
            },
            "chart_data": {
                "date": [],
                "series": {}
            },
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "source": "Bank of England",
                "error": "Failed to fetch BOE import prices data"
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
boe_import_prices_service = BOEImportPricesService()
