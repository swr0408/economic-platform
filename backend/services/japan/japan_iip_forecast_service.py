"""
Japan IIP Forecast Service
Fetches IIP forecast data (鉱工業生産予測指数) from METI Excel files

Data source: Ministry of Economy, Trade and Industry (METI)
URL: https://www.meti.go.jp/statistics/tyo/iip/xls/b2020_ygzosm1je.xlsx
PDF: https://www.meti.go.jp/statistics/tyo/iip/result/pdf/reference/rev_forecast.pdf
Release schedule: Same as IIP (Industrial Production Index)
"""
import json
import logging
import io
import re
import requests
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

try:
    from backend.core.redis_client import redis_client
    from backend.services.japan.estat_file_source import download_estat_excel
except ImportError:
    from core.redis_client import redis_client
    from services.japan.estat_file_source import download_estat_excel

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "japan_iip_forecast_cache.json"


class JapanIIPForecastService:
    """Service for fetching Japan IIP Forecast data from METI Excel files"""

    # 取得元: e-Stat の「鉱工業（生産・出荷・在庫）指数 …月分速報」ファイル。
    # 予測指数(生産予測指数)は確報には無く、速報ファイルの '予測指数_業種別' シートに
    # 含まれる。www.meti.go.jp は当サーバ IP をブロックするため e-Stat へ移行。
    ESTAT_STATS_CODE = "00550300"
    ESTAT_TABLE_FILTER = "分速報"  # "…年…月分速報" に一致（確報・予測無しを除外）
    ESTAT_FALLBACK_IDS = ("000040460889",)  # 2026年4月分速報
    FORECAST_SHEET_NAME = "予測指数_業種別"
    # 抽出対象の業種（総合＝製造工業）
    TARGET_INDUSTRY = "製造工業"

    # PDF reference URL（参考表示用。METI 直アクセスはブロックされるため取得はしない）
    PDF_REFERENCE_URL = "https://www.meti.go.jp/statistics/tyo/iip/result/pdf/reference/rev_forecast.pdf"

    DATA_CACHE_KEY = "japan:iip_forecast:data"

    def __init__(self):
        self.current_year = datetime.now().year

    def _parse_year_month(self, raw_text: str) -> str:
        """
        Parse year-month from raw text and convert to yyyy/mm format

        Expected formats:
        - "9月調査" -> "2025/09" (current year)
        - "20251月調査" -> "2025/01"
        - "2024年10月調査" -> "2024/10"
        """
        # Pattern 1: "YYYY年MM月" or "YYYY年M月"
        match = re.search(r'(\d{4})年(\d{1,2})月', raw_text)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            return f"{year}/{month:02d}"

        # Pattern 2: "YYYYMM月調査" or "YYYYM月調査"
        match = re.search(r'(\d{4})(\d{1,2})月', raw_text)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            return f"{year}/{month:02d}"

        # Pattern 3: "MM月調査" or "M月調査" - use current year
        match = re.search(r'(\d{1,2})月', raw_text)
        if match:
            month = int(match.group(1))
            current_month = datetime.now().month
            year = self.current_year
            if month > current_month + 3:
                year -= 1
            return f"{year}/{month:02d}"

        return raw_text

    def _download_pdf_file(self) -> Optional[bytes]:
        """Download the PDF file from METI for revision table.
        Fast-fail: 1 attempt, 20s timeout — caller must handle failure with cache fallback.
        """
        try:
            logger.info("Attempting to download revision PDF from METI")

            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            })

            response = session.get(
                self.PDF_REFERENCE_URL,
                timeout=20,
                allow_redirects=True
            )

            if response.status_code == 200:
                logger.info(f"Successfully downloaded revision PDF ({len(response.content)} bytes)")
                return response.content
            else:
                logger.warning(f"Failed to download PDF: HTTP {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error downloading PDF: {e}")
            return None

    def _parse_pdf_revisions(self, pdf_content: bytes) -> Dict:
        """Parse revision table from PDF using pdfplumber"""
        revision_data = {
            "columns": [],
            "rows": []
        }

        try:
            import pdfplumber

            pdf_file = io.BytesIO(pdf_content)
            with pdfplumber.open(pdf_file) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()

                    if tables:
                        for table in tables:
                            if len(table) > 0:
                                header_row = table[0]

                                # Look for "補正値" in header
                                if any('補正値' in str(cell) if cell else False for cell in header_row):
                                    columns = [str(cell).strip() if cell else '' for cell in header_row]
                                    revision_data["columns"] = [col for col in columns if col]

                                    for row in table[1:]:
                                        if row and any(cell for cell in row):
                                            cleaned_row = []
                                            for cell in row:
                                                if cell:
                                                    cell_str = str(cell).strip()
                                                    try:
                                                        cleaned = cell_str.replace('(', '').replace(')', '').strip()
                                                        if '~' in cleaned or '～' in cleaned:
                                                            cleaned_row.append(cell_str)
                                                        else:
                                                            num = float(cleaned)
                                                            cleaned_row.append(num)
                                                    except (ValueError, AttributeError):
                                                        cleaned_row.append(cell_str)
                                                else:
                                                    cleaned_row.append(None)

                                            if any(cell is not None for cell in cleaned_row):
                                                revision_data["rows"].append(cleaned_row)

                                    logger.info(f"Extracted revision table with {len(revision_data['rows'])} rows")
                                    return revision_data

                    # Fallback to text extraction
                    if not revision_data["rows"]:
                        text = page.extract_text()
                        if text and '補正値' in text:
                            lines = text.split('\n')
                            for i, line in enumerate(lines):
                                if '補正値' in line:
                                    for data_line in lines[i+1:i+10]:
                                        match = re.search(r'([^\d]+)\s+([-+]?\d+\.?\d*)\s*(\([^)]+\))?', data_line.strip())
                                        if match:
                                            label = match.group(1).strip()
                                            value = match.group(2)
                                            range_val = match.group(3) if match.group(3) else ''

                                            if not revision_data["columns"]:
                                                revision_data["columns"] = ["", "補正値"]

                                            try:
                                                revision_data["rows"].append([label, float(value), range_val])
                                            except ValueError:
                                                revision_data["rows"].append([label, value, range_val])

                                    if revision_data["rows"]:
                                        logger.info(f"Extracted revision data from text with {len(revision_data['rows'])} rows")
                                        return revision_data

            logger.info("No revision table found in PDF")
            return revision_data

        except ImportError:
            logger.warning("pdfplumber not available, skipping PDF parsing")
            return revision_data
        except Exception as e:
            logger.error(f"Error parsing PDF: {e}", exc_info=True)
            return revision_data

    def _download_excel_file(self) -> Optional[bytes]:
        """e-Stat から最新の「…月分速報」Excel を取得する（予測指数シートを含む）。

        statInfId はリリース毎にローテートするため Data Catalog API で動的解決する。
        取得不能時は None(呼び出し側がキャッシュにフォールバック)。
        """
        return download_estat_excel(
            stats_code=self.ESTAT_STATS_CODE,
            table_name_filter=self.ESTAT_TABLE_FILTER,
            fallback_stat_inf_ids=self.ESTAT_FALLBACK_IDS,
            timeout=40,
        )

    def _download_excel_file_legacy_meti(self) -> Optional[bytes]:
        """（旧）METI 直ダウンロード。IP ブロックで現在使用不可。参考のため残置。"""
        max_retries = 1
        timeout = 20

        for attempt in range(max_retries):
            try:
                logger.info(f"Attempting to download IIP Forecast Excel file (attempt {attempt + 1}/{max_retries})")

                session = requests.Session()
                session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,*/*',
                    'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                })

                response = session.get(
                    self.METI_IIP_FORECAST_URL,
                    timeout=timeout,
                    stream=True,
                    allow_redirects=True
                )

                if response.status_code == 200:
                    content = b''
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            content += chunk

                    logger.info(f"Successfully downloaded IIP Forecast Excel file ({len(content)} bytes)")
                    return content
                else:
                    logger.warning(f"Download attempt {attempt + 1} failed: HTTP {response.status_code}")
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(5)
                    continue

            except requests.exceptions.Timeout as e:
                logger.warning(f"Download attempt {attempt + 1} timed out: {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(5)
                continue

            except Exception as e:
                logger.error(f"Error downloading IIP Forecast Excel file (attempt {attempt + 1}): {e}", exc_info=True)
                if attempt < max_retries - 1:
                    import time
                    time.sleep(5)
                    continue
                return None

        logger.error(f"Failed to download IIP Forecast file after {max_retries} attempts")
        return None

    def _parse_excel_data(self, excel_content: bytes) -> Optional[Dict]:
        """e-Stat 速報ファイルの '予測指数_業種別' シートから生産予測指数を抽出する。

        シート構造（0-indexed 列）:
          0: 時間軸コード, 1: 業種(JP), 2: 業種(EN), 3: 調査月(例 "2026年05月調査"),
          4-6: 指数値[前月実績/当月見込み/翌月見込み],
          7-9: 前月比[前月実績/当月見込み/翌月見込み], 10: 実現率
        総合＝「製造工業」行のみを対象に、調査月ごとの
          this_month = 前月比 当月見込み(列8), next_month = 前月比 翌月見込み(列9)
        を時系列(古い順)で返す。forecast_month/next_month は最新調査の当月/翌月。
        """
        try:
            excel_file = io.BytesIO(excel_content)
            xl = pd.ExcelFile(excel_file)
            if self.FORECAST_SHEET_NAME not in xl.sheet_names:
                logger.error(
                    f"Forecast sheet '{self.FORECAST_SHEET_NAME}' not found "
                    f"(sheets: {xl.sheet_names[:10]})"
                )
                return None

            df = pd.read_excel(excel_file, sheet_name=self.FORECAST_SHEET_NAME, header=None)
            logger.info(f"Forecast sheet shape: {df.shape}")

            SURVEY_COL = 3       # 調査月
            THIS_MONTH_COL = 8   # 前月比 当月見込み(%)
            NEXT_MONTH_COL = 9   # 前月比 翌月見込み(%)

            def _num(v):
                if pd.isna(v):
                    return None
                try:
                    return float(v)
                except (ValueError, TypeError):
                    return None

            forecast_data = []
            for idx in range(len(df)):
                row = df.iloc[idx]
                industry = str(row[1]).strip() if not pd.isna(row[1]) else ""
                if industry != self.TARGET_INDUSTRY:
                    continue

                raw_survey = str(row[SURVEY_COL]).strip() if not pd.isna(row[SURVEY_COL]) else ""
                if not raw_survey:
                    continue
                item_name = self._parse_year_month(raw_survey)  # "2026年05月調査" -> "2026/05"
                if not re.match(r"\d{4}/\d{2}", item_name):
                    continue

                this_month_value = _num(row[THIS_MONTH_COL])
                next_month_value = _num(row[NEXT_MONTH_COL])
                if this_month_value is None and next_month_value is None:
                    continue

                forecast_data.append({
                    "item_name": item_name,
                    "this_month": this_month_value,
                    "next_month": next_month_value,
                })

            if not forecast_data:
                logger.error("No 製造工業 forecast rows found in sheet")
                return None

            # 時系列を古い順に整える（後段の reversed で最新が先頭になる）
            forecast_data.sort(key=lambda x: x["item_name"])

            # forecast_month/next_month: 最新調査の当月・翌月
            latest_label = forecast_data[-1]["item_name"]  # "YYYY/MM"
            forecast_month = None
            next_month = None
            m = re.match(r"(\d{4})/(\d{2})", latest_label)
            if m:
                y, mo = int(m.group(1)), int(m.group(2))
                forecast_month = f"{y}-{mo:02d}-01"
                ny, nmo = (y + 1, 1) if mo == 12 else (y, mo + 1)
                next_month = f"{ny}-{nmo:02d}-01"

            logger.info(
                f"Extracted {len(forecast_data)} forecast points "
                f"(latest survey {latest_label})"
            )

            return {
                "forecast_month": forecast_month,
                "next_month": next_month,
                "data": forecast_data,
            }

        except Exception as e:
            logger.error(f"Error parsing Excel data: {e}", exc_info=True)
            return None

    def _fetch_iip_forecast_data(self) -> Optional[Dict[str, Any]]:
        """Fetch IIP Forecast data from METI Excel file and PDF revisions"""
        try:
            logger.info("Fetching Japan IIP Forecast data from METI Excel")

            excel_content = self._download_excel_file()
            if not excel_content:
                logger.error("Failed to download Excel file")
                return None

            parsed_data = self._parse_excel_data(excel_content)
            if not parsed_data:
                logger.error("Failed to parse Excel data")
                return None

            forecast_month = parsed_data.get('forecast_month')
            next_month = parsed_data.get('next_month')
            data_points = parsed_data.get('data', [])

            # 補正値テーブルは METI の PDF 由来だが、METI 直アクセスは IP ブロックで
            # 取得不能。フロントは revision_table が空なら非表示にするため、空で返す。
            # （PDF 取得を試みると毎回 20s タイムアウトして無駄なので呼ばない）
            revision_table = {"columns": [], "rows": []}

            # Process data (reverse order so newest items are first)
            processed_data = []
            for item in reversed(data_points):
                processed_data.append({
                    "item_name": item['item_name'],
                    "this_month": round(item['this_month'], 1) if item['this_month'] is not None else None,
                    "next_month": round(item['next_month'], 1) if item['next_month'] is not None else None,
                })

            return {
                "data": processed_data,
                "forecast_month": forecast_month,
                "next_month": next_month,
                "revision_table": revision_table,
                "last_updated": datetime.now(JST).isoformat(),
                "source": "Ministry of Economy, Trade and Industry (METI)",
                "pdf_reference": self.PDF_REFERENCE_URL
            }

        except Exception as e:
            logger.error(f"Error fetching IIP Forecast data: {e}", exc_info=True)
            return None

    def get_iip_forecast_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get Japan IIP Forecast data with caching.

        Strategy:
        1. Fresh cache hit → return immediately.
        2. Circuit breaker: if METI failed in the last 5 minutes, skip fetch and serve stale cache.
        3. Otherwise try METI; on success update both caches and clear breaker.
        4. On failure set breaker (5 min cooldown) and fall back to Redis → file cache → empty.
        """
        cached_data = redis_client.get(self.DATA_CACHE_KEY)
        negative_key = self.DATA_CACHE_KEY + ":fetch_failed"

        # 1) Fresh cache hit
        if not force_refresh and cached_data:
            last_updated_str = cached_data.get("last_updated")
            if last_updated_str and not self._should_refresh(last_updated_str):
                return {
                    "data": cached_data.get("data", []),
                    "forecast_month": cached_data.get("forecast_month"),
                    "next_month": cached_data.get("next_month"),
                    "revision_table": cached_data.get("revision_table"),
                    "cached": True,
                    "source": "redis",
                    "last_updated": last_updated_str,
                    "pdf_reference": self.PDF_REFERENCE_URL
                }

        # 2) Circuit breaker: recent METI failure → skip fetch, serve any cache
        if not force_refresh and redis_client.exists(negative_key):
            if cached_data:
                return {
                    "data": cached_data.get("data", []),
                    "forecast_month": cached_data.get("forecast_month"),
                    "next_month": cached_data.get("next_month"),
                    "revision_table": cached_data.get("revision_table"),
                    "cached": True,
                    "source": "redis (stale, breaker)",
                    "last_updated": cached_data.get("last_updated"),
                    "pdf_reference": self.PDF_REFERENCE_URL
                }
            file_cache = self._load_file_cache()
            if file_cache:
                return {
                    "data": file_cache.get("data", []),
                    "forecast_month": file_cache.get("forecast_month"),
                    "next_month": file_cache.get("next_month"),
                    "revision_table": file_cache.get("revision_table"),
                    "cached": True,
                    "source": "file (stale, breaker)",
                    "last_updated": file_cache.get("last_updated"),
                    "pdf_reference": self.PDF_REFERENCE_URL
                }

        # 3) Try fresh fetch
        result = self._fetch_iip_forecast_data()
        if result:
            cache_payload = {
                "data": result["data"],
                "forecast_month": result["forecast_month"],
                "next_month": result["next_month"],
                "revision_table": result["revision_table"],
                "last_updated": result["last_updated"],
                "source": result["source"],
                "pdf_reference": result["pdf_reference"]
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)
            redis_client.delete(negative_key)

            return {
                "data": result["data"],
                "forecast_month": result["forecast_month"],
                "next_month": result["next_month"],
                "revision_table": result["revision_table"],
                "cached": False,
                "source": "meti",
                "last_updated": result["last_updated"],
                "pdf_reference": result["pdf_reference"]
            }

        # 4) Fetch failed → set breaker and serve any cache
        redis_client.set(negative_key, {"failed_at": datetime.now(JST).isoformat()}, expire=300)

        if cached_data:
            return {
                "data": cached_data.get("data", []),
                "forecast_month": cached_data.get("forecast_month"),
                "next_month": cached_data.get("next_month"),
                "revision_table": cached_data.get("revision_table"),
                "cached": True,
                "source": "redis (stale, fallback)",
                "last_updated": cached_data.get("last_updated"),
                "pdf_reference": self.PDF_REFERENCE_URL
            }
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "forecast_month": file_cache.get("forecast_month"),
                "next_month": file_cache.get("next_month"),
                "revision_table": file_cache.get("revision_table"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
                "pdf_reference": self.PDF_REFERENCE_URL
            }

        return {
            "data": [],
            "forecast_month": None,
            "next_month": None,
            "revision_table": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "pdf_reference": self.PDF_REFERENCE_URL,
            "error": "No data available"
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """Check if cache should be refreshed.

        月次指標 — 7-day freshness window aligns with release cadence and absorbs
        occasional source-API downtime without forcing every request to hit it.
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            cache_age_hours = (now - last_updated).total_seconds() / 3600

            if cache_age_hours > 24 * 7:
                return True

            return False
        except Exception:
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
        except Exception as e:
            logger.error(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Japan IIP Forecast",
            "source": "METI",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "forecast_month": cached_data.get("forecast_month") if cached_data else None,
            "next_month": cached_data.get("next_month") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# Singleton instance
japan_iip_forecast_service = JapanIIPForecastService()
