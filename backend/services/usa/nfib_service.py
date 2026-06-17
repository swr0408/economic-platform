"""
NFIB中小企業楽観指数サービス
NFIBのPDFレポートからデータを抽出

データソース:
- NFIB PDF Report: https://www.nfib.com/news/monthly_report/sbet/

発表スケジュール:
- 毎月第2火曜日
- 発表時刻: 6:00 ET（夏時間19:00 JST / 冬時間20:00 JST）

キャッシュ方式: last_updated判定方式
- スケジュールから次回発表日を計算して判定
- 発表日を過ぎたらキャッシュを無効化して再取得
"""
import io
import re
import json
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path
from calendar import monthcalendar

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False
    print("Warning: pdfplumber not installed. NFIB PDF extraction disabled.")

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# NFIB PDF設定
NFIB_BASE_URL = "https://www.nfib.com"
NFIB_REPORTS_URL = f"{NFIB_BASE_URL}/news/monthly_report/sbet/"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "nfib_optimism_cache.json"
CACHE_FILE_CAPEX = CACHE_DIR / "nfib_capex_cache.json"
CACHE_FILE_COMPENSATION = CACHE_DIR / "nfib_compensation_cache.json"
CACHE_FILE_PRICE_PLANS = CACHE_DIR / "nfib_price_plans_cache.json"


class NFIBService:
    """NFIB中小企業楽観指数・設備投資計画・人件費雇用計画サービス"""

    CACHE_KEY = "nfib:optimism"
    CACHE_KEY_CAPEX = "nfib:capex"
    CACHE_KEY_COMPENSATION = "nfib:compensation"
    CACHE_KEY_PRICE_PLANS = "nfib:price_plans"
    ECONALPHA_ID = "nfib"  # FMPマッピング用ID

    def __init__(self):
        """初期化"""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def get_nfib_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        NFIB中小企業楽観指数データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float}, ...],
                "latest": {"date": "YYYY-MM-DD", "value": float},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    data = cached_data.get("data", [])
                    return {
                        "data": data,
                        "latest": data[-1] if data else None,
                        "next_release": get_next_release_from_fmp('nfib'),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    data = file_cache.get("data", [])

                    # Redisにも保存
                    redis_client.set(self.CACHE_KEY, {
                        "data": data,
                        "last_updated": last_updated_str
                    }, expire=0)

                    return {
                        "data": data,
                        "latest": data[-1] if data else None,
                        "next_release": get_next_release_from_fmp('nfib'),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # PDFからデータ取得
        if not HAS_PDFPLUMBER:
            # pdfplumberがない場合はファイルキャッシュから返す
            file_cache = self._load_file_cache()
            if file_cache:
                data = file_cache.get("data", [])
                return {
                    "data": data,
                    "latest": data[-1] if data else None,
                    "next_release": get_next_release_from_fmp('nfib'),
                    "cached": True,
                    "source": "file (pdfplumber not available)",
                    "last_updated": file_cache.get("last_updated")
                }
            return {
                "data": [],
                "latest": None,
                "next_release": get_next_release_from_fmp('nfib'),
                "cached": False,
                "source": "none",
                "last_updated": None,
                "error": "pdfplumber not installed"
            }

        fetched_result = self._fetch_from_pdf()

        if fetched_result and fetched_result.get("data"):
            fetched_data = fetched_result["data"]
            fetched_data.sort(key=lambda x: x["date"])
            latest = fetched_data[-1] if fetched_data else None

            cache_payload = {
                "data": fetched_data,
                "last_updated": datetime.now(JST).isoformat()
            }
            # Redisに保存
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)
            # ファイルにも保存
            self._save_file_cache(cache_payload)

            return {
                "data": fetched_data,
                "latest": latest,
                "next_release": get_next_release_from_fmp('nfib'),
                "cached": False,
                "source": "pdf",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache()
        if file_cache:
            data = file_cache.get("data", [])
            return {
                "data": data,
                "latest": data[-1] if data else None,
                "next_release": get_next_release_from_fmp('nfib'),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": get_next_release_from_fmp('nfib'),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP 3分方式）"""
        # 源泉(NFIB PDF)が発表時刻より遅れて掲載されるケースの凍結を防ぐ24hフォールバック。
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str, max_age_hours=24)


    def _fetch_from_pdf(self) -> Optional[Dict[str, Any]]:
        """NFIBのPDFレポートからデータを抽出"""
        try:
            print("Fetching NFIB Small Business Optimism from PDF...")

            # PDFのURLを取得
            pdf_url = self._extract_pdf_url_from_page()
            if not pdf_url:
                print("Could not find PDF URL")
                return None

            # PDFをダウンロード
            pdf_content = self._download_pdf(pdf_url)
            if not pdf_content:
                print("Could not download PDF")
                return None

            # データを抽出
            table_data = self._extract_optimism_index_from_pdf(pdf_content)
            if not table_data:
                print("Could not extract data from PDF")
                return None

            # 時系列データに変換
            timeseries = self._convert_to_timeseries(table_data)

            print(f"Fetched {len(timeseries)} NFIB records")

            if timeseries:
                return {"data": timeseries}

            return None

        except Exception as e:
            print(f"Error fetching NFIB from PDF: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_pdf_url_from_page(self) -> Optional[str]:
        """NFIBのレポートページからPDFのURLを取得"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(NFIB_REPORTS_URL, headers=headers, timeout=30)
            response.raise_for_status()

            pattern = r'href="(https://www\.nfib\.com/wp-content/uploads/\d{4}/\d{2}/[^"]*\.pdf)"'
            match = re.search(pattern, response.text)

            if match:
                pdf_url = match.group(1)
                print(f"Found PDF URL: {pdf_url}")
                return pdf_url

            print("PDF URL not found in page")
            return None

        except Exception as e:
            print(f"Failed to extract PDF URL: {e}")
            return None

    def _download_pdf(self, url: str) -> Optional[bytes]:
        """PDFをダウンロード"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            print(f"Downloaded PDF from {url} ({len(response.content)} bytes)")
            return response.content
        except Exception as e:
            print(f"Failed to download PDF: {e}")
            return None

    def _extract_optimism_index_from_pdf(self, pdf_content: bytes) -> List[Dict[str, Any]]:
        """PDFからOPTIMISM INDEXテーブルを抽出"""
        data = []

        try:
            with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()

                    if "OPTIMISM INDEX" not in text or "1986=100" not in text:
                        continue

                    print(f"Found OPTIMISM INDEX table on page {page_num}")

                    tables = page.extract_tables()

                    for table in tables:
                        if not table or len(table) < 2:
                            continue

                        header = table[0]
                        if not header or len(header) < 13:
                            continue

                        expected_months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                                         'jul', 'aug', 'sep', 'oct', 'nov', 'dec']

                        header_months = []
                        for i in range(1, min(13, len(header))):
                            cell = str(header[i]).strip().lower() if header[i] else ""
                            if cell in expected_months:
                                header_months.append(cell)

                        if len(header_months) < 12:
                            continue

                        print(f"Found valid table with 12 months")

                        for row in table[1:]:
                            if not row or len(row) < 13:
                                continue

                            year_cell = str(row[0]).strip() if row[0] else ""
                            year_match = re.search(r'(20\d{2})', year_cell)

                            if not year_match:
                                continue

                            year = year_match.group(1)
                            year_data = {"year": year}

                            for i in range(1, min(13, len(row))):
                                month = header_months[i-1] if i-1 < len(header_months) else None
                                if not month:
                                    continue

                                value_str = str(row[i]).strip() if row[i] else ""
                                if not value_str:
                                    continue

                                value_match = re.search(r'(\d+\.?\d*)', value_str)
                                if value_match:
                                    try:
                                        value = float(value_match.group(1))
                                        if 70.0 <= value <= 120.0:
                                            year_data[month] = value
                                    except ValueError:
                                        pass

                            if len(year_data) > 1:
                                data.append(year_data)
                                print(f"Extracted data for {year}: {len(year_data)-1} months")

                    if data:
                        break

            print(f"Total extracted records: {len(data)}")
            return data

        except Exception as e:
            print(f"Failed to extract data from PDF: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _convert_to_timeseries(self, table_data: List[Dict]) -> List[Dict[str, Any]]:
        """テーブルデータを時系列データに変換"""
        timeseries = []

        month_map = {
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
            'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
            'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
        }

        for year_data in table_data:
            year = year_data.get('year')
            if not year:
                continue

            for month_name, month_num in month_map.items():
                if month_name in year_data:
                    value = year_data[month_name]
                    date = f"{year}-{month_num}-01"
                    timeseries.append({
                        'date': date,
                        'value': value
                    })

        timeseries.sort(key=lambda x: x['date'])

        return timeseries


    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not CACHE_FILE.exists():
                return None

            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cache_exists = redis_client.exists(self.CACHE_KEY)
        cached_data = redis_client.get(self.CACHE_KEY) if cache_exists else None

        return {
            "cache_key": self.CACHE_KEY,
            "exists": cache_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("data", [])[-1] if cached_data and cached_data.get("data") else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": CACHE_FILE.exists()
        }

    # ============================================================
    # 設備投資計画 (Capital Expenditure Plans)
    # ============================================================

    def get_capex_plans_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        NFIB中小企業設備投資計画データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float}, ...],
                "latest": {"date": "YYYY-MM-DD", "value": float},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CACHE_KEY_CAPEX)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    data = cached_data.get("data", [])
                    return {
                        "data": data,
                        "latest": data[-1] if data else None,
                        "next_release": get_next_release_from_fmp('nfib'),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_capex_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    data = file_cache.get("data", [])

                    # Redisにも保存
                    redis_client.set(self.CACHE_KEY_CAPEX, {
                        "data": data,
                        "last_updated": last_updated_str
                    }, expire=0)

                    return {
                        "data": data,
                        "latest": data[-1] if data else None,
                        "next_release": get_next_release_from_fmp('nfib'),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # PDFからデータ取得
        if not HAS_PDFPLUMBER:
            file_cache = self._load_capex_file_cache()
            if file_cache:
                data = file_cache.get("data", [])
                return {
                    "data": data,
                    "latest": data[-1] if data else None,
                    "next_release": get_next_release_from_fmp('nfib'),
                    "cached": True,
                    "source": "file (pdfplumber not available)",
                    "last_updated": file_cache.get("last_updated")
                }
            return {
                "data": [],
                "latest": None,
                "next_release": get_next_release_from_fmp('nfib'),
                "cached": False,
                "source": "none",
                "last_updated": None,
                "error": "pdfplumber not installed"
            }

        fetched_result = self._fetch_capex_from_pdf()

        if fetched_result and fetched_result.get("data"):
            fetched_data = fetched_result["data"]
            fetched_data.sort(key=lambda x: x["date"])
            latest = fetched_data[-1] if fetched_data else None

            cache_payload = {
                "data": fetched_data,
                "last_updated": datetime.now(JST).isoformat()
            }
            # Redisに保存
            redis_client.set(self.CACHE_KEY_CAPEX, cache_payload, expire=0)
            # ファイルにも保存
            self._save_capex_file_cache(cache_payload)

            return {
                "data": fetched_data,
                "latest": latest,
                "next_release": get_next_release_from_fmp('nfib'),
                "cached": False,
                "source": "pdf",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_capex_file_cache()
        if file_cache:
            data = file_cache.get("data", [])
            return {
                "data": data,
                "latest": data[-1] if data else None,
                "next_release": get_next_release_from_fmp('nfib'),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": get_next_release_from_fmp('nfib'),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_capex_from_pdf(self) -> Optional[Dict[str, Any]]:
        """NFIBのPDFレポートから設備投資計画データを抽出"""
        try:
            print("Fetching NFIB Capital Expenditure Plans from PDF...")

            # PDFのURLを取得
            pdf_url = self._extract_pdf_url_from_page()
            if not pdf_url:
                print("Could not find PDF URL")
                return None

            # PDFをダウンロード
            pdf_content = self._download_pdf(pdf_url)
            if not pdf_content:
                print("Could not download PDF")
                return None

            # データを抽出
            table_data = self._extract_capex_plans_from_pdf(pdf_content)
            if not table_data:
                print("Could not extract CapEx data from PDF")
                return None

            # 時系列データに変換
            timeseries = self._convert_to_timeseries(table_data)

            print(f"Fetched {len(timeseries)} NFIB CapEx records")

            if timeseries:
                return {"data": timeseries}

            return None

        except Exception as e:
            print(f"Error fetching NFIB CapEx from PDF: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_capex_plans_from_pdf(self, pdf_content: bytes) -> List[Dict[str, Any]]:
        """
        PDFからCAPITAL EXPENDITURE PLANSテーブルを抽出
        マーカー: "CAPITAL EXPENDITURE PLANS"
        テーブルインデックス: 1（ページ内2番目のテーブル）
        値の範囲: 0-100
        """
        return self._extract_table_by_marker(
            pdf_content,
            marker="CAPITAL EXPENDITURE PLANS",
            table_index=1,
            value_range=(0, 100)
        )

    def _extract_table_by_marker(
        self,
        pdf_content: bytes,
        marker: str,
        table_index: int = 0,
        value_range: tuple = (0, 100)
    ) -> List[Dict[str, Any]]:
        """
        マーカーを含むページから指定されたインデックスのテーブルを抽出

        Args:
            pdf_content: PDFのバイトデータ
            marker: ページを識別するマーカー文字列
            table_index: ページ内のテーブルインデックス (0から始まる)
            value_range: 値の妥当な範囲 (min, max)

        Returns:
            抽出されたデータのリスト [{"year": "2024", "jan": 15, "feb": 16, ...}, ...]
        """
        data = []

        try:
            with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()

                    if marker not in text:
                        continue

                    print(f"Found {marker} on page {page_num}")

                    tables = page.extract_tables()

                    if table_index >= len(tables):
                        print(f"Table index {table_index} not found on page {page_num}")
                        continue

                    table = tables[table_index]

                    if not table or len(table) < 2:
                        continue

                    # ヘッダー行を確認（13列: 空 + 12ヶ月）
                    header = table[0]
                    if not header or len(header) < 13:
                        continue

                    # 月名を検証
                    expected_months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                                     'jul', 'aug', 'sep', 'oct', 'nov', 'dec']

                    header_months = []
                    for i in range(1, min(13, len(header))):
                        cell = str(header[i]).strip().lower() if header[i] else ""
                        if cell in expected_months:
                            header_months.append(cell)

                    if len(header_months) < 12:
                        continue

                    print(f"Found valid table with 12 months")

                    # データ行を処理
                    for row in table[1:]:
                        if not row or len(row) < 13:
                            continue

                        # 年を取得
                        year_cell = str(row[0]).strip() if row[0] else ""
                        year_match = re.search(r'(20\d{2})', year_cell)

                        if not year_match:
                            continue

                        year = year_match.group(1)
                        year_data = {"year": year}

                        # 各月のデータを抽出
                        for i in range(1, min(13, len(row))):
                            month = header_months[i-1] if i-1 < len(header_months) else None
                            if not month:
                                continue

                            value_str = str(row[i]).strip() if row[i] else ""
                            if not value_str:
                                continue

                            # 数値を抽出（負の値にも対応）
                            value_match = re.search(r'(-?\d+\.?\d*)', value_str)
                            if value_match:
                                try:
                                    value = float(value_match.group(1))
                                    # 範囲チェック
                                    if value_range[0] <= value <= value_range[1]:
                                        year_data[month] = value
                                except ValueError:
                                    pass

                        if len(year_data) > 1:
                            data.append(year_data)
                            print(f"Extracted CapEx data for {year}: {len(year_data)-1} months")

                    if data:
                        break

            print(f"Total extracted CapEx records: {len(data)}")
            return data

        except Exception as e:
            print(f"Failed to extract {marker} from PDF: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _load_capex_file_cache(self) -> Optional[Dict[str, Any]]:
        """設備投資計画のファイルキャッシュを読み込み"""
        try:
            if not CACHE_FILE_CAPEX.exists():
                return None

            with open(CACHE_FILE_CAPEX, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load CapEx file cache: {e}")
            return None

    def _save_capex_file_cache(self, data: Dict[str, Any]) -> None:
        """設備投資計画のファイルキャッシュを保存"""
        try:
            with open(CACHE_FILE_CAPEX, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"CapEx cache saved to {CACHE_FILE_CAPEX}")
        except Exception as e:
            print(f"Failed to save CapEx file cache: {e}")

    # ============================================================
    # 人件費・雇用計画 (Compensation Plans / Hiring Plans / Actual Compensation Changes)
    # ============================================================

    def get_compensation_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        NFIB中小企業人件費・雇用計画データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": str, "compensation_plans": float, "hiring_plans": float, "actual_compensation": float}, ...],
                "latest": {...},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CACHE_KEY_COMPENSATION)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    data = cached_data.get("data", [])
                    return {
                        "data": data,
                        "latest": data[-1] if data else None,
                        "next_release": get_next_release_from_fmp('nfib'),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_compensation_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    data = file_cache.get("data", [])

                    # Redisにも保存
                    redis_client.set(self.CACHE_KEY_COMPENSATION, {
                        "data": data,
                        "last_updated": last_updated_str
                    }, expire=0)

                    return {
                        "data": data,
                        "latest": data[-1] if data else None,
                        "next_release": get_next_release_from_fmp('nfib'),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # PDFからデータ取得
        if not HAS_PDFPLUMBER:
            file_cache = self._load_compensation_file_cache()
            if file_cache:
                data = file_cache.get("data", [])
                return {
                    "data": data,
                    "latest": data[-1] if data else None,
                    "next_release": get_next_release_from_fmp('nfib'),
                    "cached": True,
                    "source": "file (pdfplumber not available)",
                    "last_updated": file_cache.get("last_updated")
                }
            return {
                "data": [],
                "latest": None,
                "next_release": get_next_release_from_fmp('nfib'),
                "cached": False,
                "source": "none",
                "last_updated": None,
                "error": "pdfplumber not installed"
            }

        fetched_result = self._fetch_compensation_from_pdf()

        if fetched_result and fetched_result.get("data"):
            fetched_data = fetched_result["data"]
            fetched_data.sort(key=lambda x: x["date"])
            latest = fetched_data[-1] if fetched_data else None

            cache_payload = {
                "data": fetched_data,
                "last_updated": datetime.now(JST).isoformat()
            }
            # Redisに保存
            redis_client.set(self.CACHE_KEY_COMPENSATION, cache_payload, expire=0)
            # ファイルにも保存
            self._save_compensation_file_cache(cache_payload)

            return {
                "data": fetched_data,
                "latest": latest,
                "next_release": get_next_release_from_fmp('nfib'),
                "cached": False,
                "source": "pdf",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_compensation_file_cache()
        if file_cache:
            data = file_cache.get("data", [])
            return {
                "data": data,
                "latest": data[-1] if data else None,
                "next_release": get_next_release_from_fmp('nfib'),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": get_next_release_from_fmp('nfib'),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_compensation_from_pdf(self) -> Optional[Dict[str, Any]]:
        """NFIBのPDFレポートから人件費・雇用計画データを抽出"""
        try:
            print("Fetching NFIB Compensation/Hiring Plans from PDF...")

            # PDFのURLを取得
            pdf_url = self._extract_pdf_url_from_page()
            if not pdf_url:
                print("Could not find PDF URL")
                return None

            # PDFをダウンロード
            pdf_content = self._download_pdf(pdf_url)
            if not pdf_content:
                print("Could not download PDF")
                return None

            # 2つのテーブルを抽出
            compensation_plans = self._extract_compensation_plans_from_pdf(pdf_content)
            hiring_plans = self._extract_hiring_plans_from_pdf(pdf_content)

            # 時系列データに変換してマージ
            comp_ts = self._convert_to_timeseries(compensation_plans)
            hire_ts = self._convert_to_timeseries(hiring_plans)

            # データをマージ
            merged = self._merge_compensation_data(comp_ts, hire_ts)

            print(f"Fetched {len(merged)} NFIB Compensation records")

            if merged:
                return {"data": merged}

            return None

        except Exception as e:
            print(f"Error fetching NFIB Compensation from PDF: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_compensation_plans_from_pdf(self, pdf_content: bytes) -> List[Dict[str, Any]]:
        """
        PDFからCOMPENSATION PLANSテーブルを抽出
        マーカー: "COMPENSATION PLANS"
        テーブルインデックス: 1（ページ内2番目のテーブル）
        値の範囲: -50〜100
        """
        return self._extract_table_by_marker(
            pdf_content,
            marker="COMPENSATION PLANS",
            table_index=1,
            value_range=(-50, 100)
        )

    def _extract_hiring_plans_from_pdf(self, pdf_content: bytes) -> List[Dict[str, Any]]:
        """
        PDFからHIRING PLANSテーブルを抽出
        マーカー: "HIRING PLANS"
        テーブルインデックス: 1（ページ内2番目のテーブル）
        値の範囲: -50〜100
        """
        return self._extract_table_by_marker(
            pdf_content,
            marker="HIRING PLANS",
            table_index=1,
            value_range=(-50, 100)
        )

    def _merge_compensation_data(
        self,
        compensation_plans: List[Dict[str, Any]],
        hiring_plans: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """2つのデータソースをマージ"""
        date_map: Dict[str, Dict[str, Any]] = {}

        # Compensation Plans
        for item in compensation_plans:
            date_str = item["date"]
            if date_str not in date_map:
                date_map[date_str] = {"date": date_str}
            date_map[date_str]["compensation_plans"] = item["value"]

        # Hiring Plans
        for item in hiring_plans:
            date_str = item["date"]
            if date_str not in date_map:
                date_map[date_str] = {"date": date_str}
            date_map[date_str]["hiring_plans"] = item["value"]

        # 日付順にソート
        result = sorted(date_map.values(), key=lambda x: x["date"])
        return result

    def _load_compensation_file_cache(self) -> Optional[Dict[str, Any]]:
        """人件費・雇用計画のファイルキャッシュを読み込み"""
        try:
            if not CACHE_FILE_COMPENSATION.exists():
                return None

            with open(CACHE_FILE_COMPENSATION, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load Compensation file cache: {e}")
            return None

    def _save_compensation_file_cache(self, data: Dict[str, Any]) -> None:
        """人件費・雇用計画のファイルキャッシュを保存"""
        try:
            with open(CACHE_FILE_COMPENSATION, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Compensation cache saved to {CACHE_FILE_COMPENSATION}")
        except Exception as e:
            print(f"Failed to save Compensation file cache: {e}")

    def invalidate_compensation_cache(self) -> bool:
        """人件費・雇用計画のキャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY_COMPENSATION)

    # ============================================================
    # 実際の人件費変更（労働報酬/失業率チャート用）
    # ============================================================

    CACHE_KEY_ACTUAL_COMPENSATION = "nfib:actual_compensation"

    def get_actual_compensation_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        NFIB実際の人件費変更データを取得（労働報酬/失業率チャート用）

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float}, ...],
                "latest": {"date": "YYYY-MM-DD", "value": float},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        cache_file = CACHE_DIR / "nfib_actual_compensation_cache.json"

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CACHE_KEY_ACTUAL_COMPENSATION)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    data = cached_data.get("data", [])
                    return {
                        "data": data,
                        "latest": data[-1] if data else None,
                        "next_release": get_next_release_from_fmp('nfib'),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_actual_compensation_file_cache(cache_file)
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    data = file_cache.get("data", [])

                    redis_client.set(self.CACHE_KEY_ACTUAL_COMPENSATION, {
                        "data": data,
                        "last_updated": last_updated_str
                    }, expire=0)

                    return {
                        "data": data,
                        "latest": data[-1] if data else None,
                        "next_release": get_next_release_from_fmp('nfib'),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # PDFからデータ取得
        if not HAS_PDFPLUMBER:
            file_cache = self._load_actual_compensation_file_cache(cache_file)
            if file_cache:
                data = file_cache.get("data", [])
                return {
                    "data": data,
                    "latest": data[-1] if data else None,
                    "next_release": get_next_release_from_fmp('nfib'),
                    "cached": True,
                    "source": "file (pdfplumber not available)",
                    "last_updated": file_cache.get("last_updated")
                }
            return {
                "data": [],
                "latest": None,
                "next_release": get_next_release_from_fmp('nfib'),
                "cached": False,
                "source": "none",
                "last_updated": None,
                "error": "pdfplumber not installed"
            }

        fetched_result = self._fetch_actual_compensation_from_pdf()

        if fetched_result and fetched_result.get("data"):
            fetched_data = fetched_result["data"]
            fetched_data.sort(key=lambda x: x["date"])
            latest = fetched_data[-1] if fetched_data else None

            cache_payload = {
                "data": fetched_data,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.CACHE_KEY_ACTUAL_COMPENSATION, cache_payload, expire=0)
            self._save_actual_compensation_file_cache(cache_file, cache_payload)

            return {
                "data": fetched_data,
                "latest": latest,
                "next_release": get_next_release_from_fmp('nfib'),
                "cached": False,
                "source": "pdf",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_actual_compensation_file_cache(cache_file)
        if file_cache:
            data = file_cache.get("data", [])
            return {
                "data": data,
                "latest": data[-1] if data else None,
                "next_release": get_next_release_from_fmp('nfib'),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": get_next_release_from_fmp('nfib'),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_actual_compensation_from_pdf(self) -> Optional[Dict[str, Any]]:
        """NFIBのPDFレポートから実際の人件費変更データを抽出"""
        try:
            print("Fetching NFIB Actual Compensation Changes from PDF...")

            # PDFのURLを取得
            pdf_url = self._extract_pdf_url_from_page()
            if not pdf_url:
                print("Could not find PDF URL")
                return None

            # PDFをダウンロード
            pdf_content = self._download_pdf(pdf_url)
            if not pdf_content:
                print("Could not download PDF")
                return None

            # Actual Compensation Changesテーブルを抽出
            actual_compensation = self._extract_actual_compensation_from_pdf(pdf_content)

            # 時系列データに変換
            timeseries = self._convert_to_timeseries(actual_compensation)

            print(f"Fetched {len(timeseries)} NFIB Actual Compensation records")

            if timeseries:
                return {"data": timeseries}

            return None

        except Exception as e:
            print(f"Error fetching NFIB Actual Compensation from PDF: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_actual_compensation_from_pdf(self, pdf_content: bytes) -> List[Dict[str, Any]]:
        """
        PDFからACTUAL COMPENSATION CHANGESテーブルを抽出
        マーカー: "ACTUAL COMPENSATION CHANGES"
        テーブルインデックス: 0（ページ内1番目のテーブル）
        値の範囲: -50〜100
        """
        return self._extract_table_by_marker(
            pdf_content,
            marker="ACTUAL COMPENSATION CHANGES",
            table_index=0,
            value_range=(-50, 100)
        )

    def _load_actual_compensation_file_cache(self, cache_file: Path) -> Optional[Dict[str, Any]]:
        """実際の人件費変更のファイルキャッシュを読み込み"""
        try:
            if not cache_file.exists():
                return None

            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load Actual Compensation file cache: {e}")
            return None

    def _save_actual_compensation_file_cache(self, cache_file: Path, data: Dict[str, Any]) -> None:
        """実際の人件費変更のファイルキャッシュを保存"""
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Actual Compensation cache saved to {cache_file}")
        except Exception as e:
            print(f"Failed to save Actual Compensation file cache: {e}")

    def invalidate_actual_compensation_cache(self) -> bool:
        """実際の人件費変更のキャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY_ACTUAL_COMPENSATION)

    # ============================================================
    # 価格引き上げ計画 (Price Plans)
    # ============================================================

    def get_price_plans_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        NFIB中小企業価格引き上げ計画データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float}, ...],
                "latest": {"date": "YYYY-MM-DD", "value": float},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CACHE_KEY_PRICE_PLANS)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    data = cached_data.get("data", [])
                    return {
                        "data": data,
                        "latest": data[-1] if data else None,
                        "next_release": get_next_release_from_fmp('nfib'),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_price_plans_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    data = file_cache.get("data", [])

                    redis_client.set(self.CACHE_KEY_PRICE_PLANS, {
                        "data": data,
                        "last_updated": last_updated_str
                    }, expire=0)

                    return {
                        "data": data,
                        "latest": data[-1] if data else None,
                        "next_release": get_next_release_from_fmp('nfib'),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # PDFからデータ取得
        if not HAS_PDFPLUMBER:
            file_cache = self._load_price_plans_file_cache()
            if file_cache:
                data = file_cache.get("data", [])
                return {
                    "data": data,
                    "latest": data[-1] if data else None,
                    "next_release": get_next_release_from_fmp('nfib'),
                    "cached": True,
                    "source": "file (pdfplumber not available)",
                    "last_updated": file_cache.get("last_updated")
                }
            return {
                "data": [],
                "latest": None,
                "next_release": get_next_release_from_fmp('nfib'),
                "cached": False,
                "source": "none",
                "last_updated": None,
                "error": "pdfplumber not installed"
            }

        fetched_result = self._fetch_price_plans_from_pdf()

        if fetched_result and fetched_result.get("data"):
            fetched_data = fetched_result["data"]
            fetched_data.sort(key=lambda x: x["date"])
            latest = fetched_data[-1] if fetched_data else None

            cache_payload = {
                "data": fetched_data,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.CACHE_KEY_PRICE_PLANS, cache_payload, expire=0)
            self._save_price_plans_file_cache(cache_payload)

            return {
                "data": fetched_data,
                "latest": latest,
                "next_release": get_next_release_from_fmp('nfib'),
                "cached": False,
                "source": "pdf",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_price_plans_file_cache()
        if file_cache:
            data = file_cache.get("data", [])
            return {
                "data": data,
                "latest": data[-1] if data else None,
                "next_release": get_next_release_from_fmp('nfib'),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": get_next_release_from_fmp('nfib'),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_price_plans_from_pdf(self) -> Optional[Dict[str, Any]]:
        """NFIBのPDFレポートから価格引き上げ計画データを抽出"""
        try:
            print("Fetching NFIB Price Plans from PDF...")

            pdf_url = self._extract_pdf_url_from_page()
            if not pdf_url:
                print("Could not find PDF URL")
                return None

            pdf_content = self._download_pdf(pdf_url)
            if not pdf_content:
                print("Could not download PDF")
                return None

            table_data = self._extract_price_plans_from_pdf(pdf_content)
            if not table_data:
                print("Could not extract Price Plans data from PDF")
                return None

            timeseries = self._convert_to_timeseries(table_data)

            print(f"Fetched {len(timeseries)} NFIB Price Plans records")

            if timeseries:
                return {"data": timeseries}

            return None

        except Exception as e:
            print(f"Error fetching NFIB Price Plans from PDF: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_price_plans_from_pdf(self, pdf_content: bytes) -> List[Dict[str, Any]]:
        """
        PDFからPRICE PLANSテーブルを抽出
        マーカー: "PRICE PLANS"
        テーブルインデックス: 1（ページ内2番目のテーブル、Compensation/CapExと同じ構造）
        値の範囲: -50〜100（純割合: 引き上げ予定 - 引き下げ予定）
        """
        return self._extract_table_by_marker(
            pdf_content,
            marker="PRICE PLANS",
            table_index=1,
            value_range=(-50, 100)
        )

    def _load_price_plans_file_cache(self) -> Optional[Dict[str, Any]]:
        """価格引き上げ計画のファイルキャッシュを読み込み"""
        try:
            if not CACHE_FILE_PRICE_PLANS.exists():
                return None

            with open(CACHE_FILE_PRICE_PLANS, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load Price Plans file cache: {e}")
            return None

    def _save_price_plans_file_cache(self, data: Dict[str, Any]) -> None:
        """価格引き上げ計画のファイルキャッシュを保存"""
        try:
            with open(CACHE_FILE_PRICE_PLANS, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Price Plans cache saved to {CACHE_FILE_PRICE_PLANS}")
        except Exception as e:
            print(f"Failed to save Price Plans file cache: {e}")

    def invalidate_price_plans_cache(self) -> bool:
        """価格引き上げ計画のキャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY_PRICE_PLANS)


# シングルトンインスタンス
nfib_service = NFIBService()
