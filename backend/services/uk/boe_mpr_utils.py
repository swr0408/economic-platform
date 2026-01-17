"""
BOE MPR Utilities
MPRデータ取得のための共通ユーティリティ

November 2025以降、BOEはMPRファイル構造を変更:
- 旧構造: 個別のParameters for MPC...xlsxファイル + Market profiles.xlsx
- 新構造: Projections Databank - {Month} {Year} MPR.xlsx に統合

このユーティリティは両方の構造に対応
"""
import logging
import requests
import io
import zipfile
import openpyxl
import time
from datetime import datetime
from typing import Dict, Optional, Tuple, List, Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

LONDON = ZoneInfo("Europe/London")

# MPR publication months
DEFAULT_MPR_MONTHS = [2, 5, 8, 11]

# Month name mapping
MONTH_NAMES = {
    1: "january", 2: "february", 3: "march", 4: "april",
    5: "may", 6: "june", 7: "july", 8: "august",
    9: "september", 10: "october", 11: "november", 12: "december"
}

# URL patterns for MPR data
MPR_URL_PATTERNS = [
    "https://www.bankofengland.co.uk/-/media/boe/files/monetary-policy-report/{year}/{month}/mpr-{month}-{year}-charts-slides-and-data.zip",
    "https://www.bankofengland.co.uk/-/media/boe/files/monetary-policy-report/{year}/{month}/mpr-{month}-{year}-chart-slides-and-data.zip"
]

# File patterns (new structure from Nov 2025)
PROJECTIONS_DATABANK_PATTERN = "Projections Databank - {month} {year} MPR.xlsx"
CHART_DATA_PATTERN = "{month} {year} MPR chart data.xlsx"

# Old file names (pre-Nov 2025)
OLD_FILES = {
    "cpi_projections": "Parameters for MPC CPI inflation projections from February 2004.xlsx",
    "gdp_projections": "Parameters for MPC GDP growth projections based on market interest rate expectations.xlsx",
    "unemployment_projections": "Parameters for MPC unemployment rate projections from August 2013.xlsx",
    "market_profiles": "Market profiles.xlsx",
    "section2_chart": "Section 2  - Current economic conditions.xlsx"
}


def get_mpr_info(reference_date: Optional[datetime] = None) -> Dict[str, Any]:
    """最新と前回のMPR情報を取得"""
    if reference_date is None:
        reference_date = datetime.now()

    current_year = reference_date.year
    current_month = reference_date.month
    current_day = reference_date.day

    # MPRは通常月の6日以降に発表
    if current_month in DEFAULT_MPR_MONTHS and current_day < 6:
        current_month_for_search = current_month - 1
    else:
        current_month_for_search = current_month

    # 最新のMPR月を特定
    latest_mpr_month = None
    for month in reversed(DEFAULT_MPR_MONTHS):
        if current_month_for_search >= month:
            latest_mpr_month = month
            break

    if latest_mpr_month is None:
        latest_mpr_month = DEFAULT_MPR_MONTHS[-1]
        current_year -= 1

    # 前回のMPR月を特定
    previous_mpr_month_idx = DEFAULT_MPR_MONTHS.index(latest_mpr_month) - 1
    if previous_mpr_month_idx < 0:
        previous_mpr_month = DEFAULT_MPR_MONTHS[-1]
        previous_year = current_year - 1
    else:
        previous_mpr_month = DEFAULT_MPR_MONTHS[previous_mpr_month_idx]
        previous_year = current_year

    return {
        'latest': {
            'year': current_year,
            'month': latest_mpr_month,
            'month_name': MONTH_NAMES[latest_mpr_month]
        },
        'previous': {
            'year': previous_year,
            'month': previous_mpr_month,
            'month_name': MONTH_NAMES[previous_mpr_month]
        }
    }


def download_mpr_zip(year: int, month_name: str, max_retries: int = 3, retry_delay: int = 5) -> Optional[bytes]:
    """MPR ZIPファイルをダウンロード"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    for pattern_index, url_pattern in enumerate(MPR_URL_PATTERNS):
        url = url_pattern.format(year=year, month=month_name)
        logger.info(f"Trying URL pattern {pattern_index + 1}/{len(MPR_URL_PATTERNS)}: {url}")

        for attempt in range(max_retries):
            try:
                logger.info(f"Attempt {attempt + 1}/{max_retries}: Downloading {url}")
                response = requests.get(url, headers=headers, timeout=60)

                if response.status_code == 404:
                    logger.warning(f"MPR file not found (404): {url}")
                    break

                if response.status_code == 403:
                    logger.warning(f"Access forbidden (403): {url}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    break

                if response.status_code != 200:
                    logger.warning(f"HTTP {response.status_code} on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    break

                return response.content

            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout on attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                continue

            except Exception as e:
                logger.error(f"Error downloading from {url}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                continue

    return None


def extract_workbook_from_zip(zip_content: bytes, filename: str) -> Optional[openpyxl.Workbook]:
    """ZIPからワークブックを抽出"""
    try:
        with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
            if filename in z.namelist():
                with z.open(filename) as excel_file:
                    wb = openpyxl.load_workbook(io.BytesIO(excel_file.read()), data_only=True)
                    logger.info(f"Successfully loaded {filename}")
                    return wb
            else:
                logger.warning(f"{filename} not found in ZIP")
                return None
    except zipfile.BadZipFile:
        logger.error("Invalid ZIP file")
        return None
    except Exception as e:
        logger.error(f"Error extracting {filename}: {e}")
        return None


def list_zip_contents(zip_content: bytes) -> List[str]:
    """ZIP内のファイル一覧を取得"""
    try:
        with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
            return z.namelist()
    except Exception as e:
        logger.error(f"Error listing ZIP contents: {e}")
        return []


def find_file_in_zip(zip_content: bytes, patterns: List[str]) -> Optional[str]:
    """ZIP内でパターンに一致するファイルを検索"""
    files = list_zip_contents(zip_content)
    for pattern in patterns:
        for f in files:
            if pattern.lower() in f.lower():
                return f
    return None


def get_projections_databank(year: int, month_name: str) -> Optional[Tuple[openpyxl.Workbook, bytes]]:
    """Projections Databankファイルを取得

    Returns:
        Tuple of (workbook, zip_content) or None
    """
    zip_content = download_mpr_zip(year, month_name)
    if zip_content is None:
        return None

    # New format: Projections Databank - {Month} {Year} MPR.xlsx
    databank_filename = PROJECTIONS_DATABANK_PATTERN.format(
        month=month_name.title(),
        year=year
    )

    wb = extract_workbook_from_zip(zip_content, databank_filename)
    if wb:
        return (wb, zip_content)

    # Try to find with flexible matching
    files = list_zip_contents(zip_content)
    for f in files:
        if 'projections databank' in f.lower() and f.endswith('.xlsx'):
            wb = extract_workbook_from_zip(zip_content, f)
            if wb:
                return (wb, zip_content)

    return None


def get_chart_data(year: int, month_name: str, zip_content: Optional[bytes] = None) -> Optional[openpyxl.Workbook]:
    """Chart Data ファイルを取得"""
    if zip_content is None:
        zip_content = download_mpr_zip(year, month_name)
        if zip_content is None:
            return None

    # New format: {Month} {Year} MPR chart data.xlsx
    chart_filename = CHART_DATA_PATTERN.format(
        month=month_name.title(),
        year=year
    )

    wb = extract_workbook_from_zip(zip_content, chart_filename)
    if wb:
        return wb

    # Try old format
    wb = extract_workbook_from_zip(zip_content, OLD_FILES["section2_chart"])
    if wb:
        return wb

    # Flexible matching
    files = list_zip_contents(zip_content)
    for f in files:
        if 'chart data' in f.lower() and f.endswith('.xlsx'):
            return extract_workbook_from_zip(zip_content, f)
        if 'current economic conditions' in f.lower() and f.endswith('.xlsx'):
            return extract_workbook_from_zip(zip_content, f)

    return None


def parse_databank_sheet(wb: openpyxl.Workbook, sheet_name: str) -> Optional[Dict[str, Any]]:
    """Projections Databankのシートをパース

    共通フォーマット:
    - Row 5 or 12: Column headers (quarters)
    - Column 1: Date of publication
    - Data starts from row 6 or 13
    """
    if sheet_name not in wb.sheetnames:
        logger.error(f"Sheet {sheet_name} not found")
        return None

    ws = wb[sheet_name]

    # Determine header row (Bank Rate uses row 12, others use row 5)
    header_row = 12 if sheet_name == "32. Bank Rate" else 5
    data_start_row = header_row + 1

    # Get column headers (quarters)
    quarters = []
    for col in range(2, ws.max_column + 1):
        val = ws.cell(row=header_row, column=col).value
        if val:
            quarters.append((col, str(val).strip()))

    if not quarters:
        logger.error(f"No quarters found in {sheet_name}")
        return None

    # Find latest and previous data rows
    latest_row = None
    previous_row = None

    for row in range(ws.max_row, data_start_row - 1, -1):
        date_val = ws.cell(row=row, column=1).value
        if date_val:
            date_str = str(date_val)
            # Check for 2025-11, November 2025, etc
            if '2025-11' in date_str or 'November 2025' in date_str or '2025-11-01' in date_str:
                latest_row = row
            elif '2025-08' in date_str or 'August 2025' in date_str or '2025-08-01' in date_str:
                previous_row = row

            if latest_row and previous_row:
                break

    # If not found with specific dates, use last two rows
    if latest_row is None:
        data_rows = []
        for row in range(data_start_row, ws.max_row + 1):
            if ws.cell(row=row, column=1).value:
                data_rows.append(row)
        if len(data_rows) >= 2:
            latest_row = data_rows[-1]
            previous_row = data_rows[-2]
        elif len(data_rows) == 1:
            latest_row = data_rows[0]

    def extract_row_data(row_num: int) -> Tuple[str, List[Dict]]:
        """Extract data from a row"""
        date_val = ws.cell(row=row_num, column=1).value
        date_str = str(date_val) if date_val else ""

        data = []
        for col, quarter in quarters:
            val = ws.cell(row=row_num, column=col).value
            if val is not None:
                try:
                    data.append({
                        'date': quarter,
                        'value': float(val)
                    })
                except (ValueError, TypeError):
                    pass

        return date_str, data

    result = {
        'latest': None,
        'previous': None
    }

    if latest_row:
        date_str, data = extract_row_data(latest_row)
        result['latest'] = {
            'date': date_str,
            'data': data
        }

    if previous_row:
        date_str, data = extract_row_data(previous_row)
        result['previous'] = {
            'date': date_str,
            'data': data
        }

    return result


def parse_chart_sheet(wb: openpyxl.Workbook, sheet_name: str) -> Optional[Dict[str, Any]]:
    """Chart Dataのシートをパース

    共通フォーマット:
    - Row 6: Column headers
    - Data starts from row 7
    - Column 1: Date
    """
    if sheet_name not in wb.sheetnames:
        logger.error(f"Sheet {sheet_name} not found")
        return None

    ws = wb[sheet_name]

    # Get column headers
    headers = []
    for col in range(1, ws.max_column + 1):
        val = ws.cell(row=6, column=col).value
        if val:
            headers.append((col, str(val).strip().replace('\n', ' ')))

    if not headers:
        logger.error(f"No headers found in {sheet_name}")
        return None

    # Extract all data
    series_data = {header: [] for _, header in headers}
    dates = []

    for row in range(7, ws.max_row + 1):
        row_has_data = False
        for col, header in headers:
            val = ws.cell(row=row, column=col).value
            if val is not None and str(val).lower() != 'n.a.':
                row_has_data = True
                if header == 'Date' or col == 1:
                    dates.append(str(val))
                else:
                    try:
                        series_data[header].append(float(val))
                    except (ValueError, TypeError):
                        series_data[header].append(None)
            else:
                if header != 'Date' and col != 1:
                    series_data[header].append(None)

        if not row_has_data:
            break

    return {
        'dates': dates,
        'series': {k: v for k, v in series_data.items() if k != 'Date'}
    }


# =============================================================================
# 共通日付パーシング・ヘッダー検出ユーティリティ
# =============================================================================

# 月名マッピング（フル名＋省略名）
MONTH_NAME_TO_NUM = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
    'jun': 6, 'jul': 7, 'aug': 8,
    'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}


def parse_date_to_yyyy_mm(date_val: Any) -> Optional[str]:
    """日付を YYYY-MM 形式にパース

    対応フォーマット:
    - datetime オブジェクト
    - "January 2025", "Jan 2025" (月名 年)
    - "2025-01", "2025-01-15" (ISO形式)

    Args:
        date_val: 日付値（datetime, str）

    Returns:
        YYYY-MM形式の文字列、パース失敗時はNone
    """
    if date_val is None:
        return None

    # datetime オブジェクト
    if isinstance(date_val, datetime):
        return date_val.strftime('%Y-%m')

    raw_date = str(date_val).strip()
    raw_date = raw_date.replace('\n', ' ').replace('\r', '')

    # "Date" ヘッダー行をスキップ
    if raw_date.lower() == 'date':
        return None

    # 特殊文字列を除去
    raw_date = raw_date.replace('(Bank staff projections)', '').strip()

    # ISO形式: 2025-01 or 2025-01-15
    import re
    iso_match = re.match(r'^(\d{4})-(\d{2})(?:-\d{2})?', raw_date)
    if iso_match:
        return f"{iso_match.group(1)}-{iso_match.group(2)}"

    # 月名 年 形式: "January 2025", "Jan 2025"
    parts = raw_date.split()
    if len(parts) >= 2:
        month_name = parts[0].lower()
        year = parts[-1]
        if month_name in MONTH_NAME_TO_NUM and year.isdigit():
            month_num = MONTH_NAME_TO_NUM[month_name]
            return f"{year}-{month_num:02d}"

    return None


def detect_multi_row_header(ws) -> bool:
    """ワークシートがマルチ行ヘッダー構造かどうかを検出

    Nov 2025+ MPR構造:
    - Row 5: グループヘッダー
    - Row 6: シリーズ名（Col 1 = "Date"）
    - Row 7+: データ

    Args:
        ws: openpyxl ワークシート

    Returns:
        マルチ行ヘッダー構造の場合True
    """
    row6_col1 = ws.cell(row=6, column=1).value
    return bool(row6_col1 and str(row6_col1).strip().lower() == 'date')


def find_chart_sheet_by_keywords(
    wb: openpyxl.Workbook,
    primary_keywords: List[str],
    fallback_keywords: Optional[List[str]] = None,
    exclude_keywords: Optional[List[str]] = None,
    prefer_multi_column: bool = True
) -> Optional[Any]:
    """キーワードでチャートシートを検索

    A3セルのチャートタイトルに基づいてシートを検索。
    複数候補がある場合は列数が多いシートを優先。

    Args:
        wb: ワークブック
        primary_keywords: 優先キーワードリスト
        fallback_keywords: フォールバックキーワードリスト
        exclude_keywords: 除外キーワードリスト
        prefer_multi_column: True の場合、列数が多いシートを優先

    Returns:
        見つかったワークシート、なければNone
    """
    candidates = []

    for sheet_name in wb.sheetnames:
        if not sheet_name.startswith("Chart"):
            continue

        try:
            ws = wb[sheet_name]
            a3_value = ws['A3'].value

            if not a3_value:
                continue

            a3_lower = str(a3_value).lower()

            # 除外キーワードチェック
            if exclude_keywords and any(kw in a3_lower for kw in exclude_keywords):
                continue

            # 列数をカウント（row 5とrow 6の両方をチェック）
            col_count_row5 = sum(1 for col in range(2, 20) if ws.cell(row=5, column=col).value is not None)
            col_count_row6 = sum(1 for col in range(2, 20) if ws.cell(row=6, column=col).value is not None)
            col_count = max(col_count_row5, col_count_row6)

            # キーワードマッチング
            is_primary = any(kw in a3_lower for kw in primary_keywords)
            is_fallback = fallback_keywords and any(kw in a3_lower for kw in fallback_keywords)

            if is_primary or is_fallback:
                candidates.append({
                    'sheet': ws,
                    'name': sheet_name,
                    'title': a3_value,
                    'col_count': col_count,
                    'is_primary': is_primary,
                })

        except Exception as e:
            logger.warning(f"Error checking sheet {sheet_name}: {e}")

    if not candidates:
        return None

    # ソート: primary優先、列数優先
    def sort_key(c):
        score = 0
        if c['is_primary']:
            score += 1000
        if prefer_multi_column:
            score += c['col_count'] * 10
        return -score

    candidates.sort(key=sort_key)
    best = candidates[0]
    logger.info(f"Selected sheet: {best['name']} with {best['col_count']} columns, title: {best['title']}")
    return best['sheet']
