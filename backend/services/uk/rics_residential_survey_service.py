"""
RICS UK Residential Market Survey Service
Fetches and processes RICS Residential Market Survey PDFs
Extracts page 6 showing price balance expectations chart

データソース: RICS (Royal Institution of Chartered Surveyors)
URL: https://www.rics.org/news-insights/market-surveys/uk-residential-market-survey
発表: 月次（通常月中旬）

取得データ:
- Price Balance Expectations Chart (PDF 6ページ目)

キャッシュ方式: 30日経過後にリフレッシュ
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any
from zoneinfo import ZoneInfo

import fitz  # PyMuPDF
import requests

from services.usa.fred_utils import load_file_cache, save_file_cache
from core.redis_client import redis_client

logger = logging.getLogger(__name__)

# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")

# キャッシュ設定
REDIS_KEY = "uk:rics:residential_survey"
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "housing"
CACHE_FILE = CACHE_DIR / "rics_residential_survey.json"
IMAGE_CACHE_DIR = CACHE_DIR / "rics_survey_images"


class RICSResidentialSurveyService:
    """Service for fetching and processing RICS UK Residential Market Survey

    取得方法:
    1. URLパターンから自動取得を試行（Incapsula保護により通常失敗）
    2. ローカルPDFファイルにフォールバック

    注意: RICSサイトはIncapsula(Imperva)ボット保護があり、
    URLパターンでの自動取得は通常ブロックされます。
    PDFファイルを手動で配置することを推奨します。

    手動配置方法:
    1. RICSサイトからPDFをダウンロード:
       https://www.rics.org/news-insights/market-surveys/uk-residential-market-survey
    2. PDFをローカルに配置:
       backend/data/pdf/uk/rics_residential_survey_YYYYMM.pdf
       例: rics_residential_survey_202412.pdf (2024年12月のレポート)
    """

    # RICS survey page URL (参考用・手動ダウンロード用)
    SURVEY_PAGE_URL = "https://www.rics.org/news-insights/market-surveys/uk-residential-market-survey"

    # ローカルPDF配置ディレクトリ
    PDF_DIR = Path(__file__).parent.parent.parent / "data" / "pdf" / "uk"

    # キャッシュ有効期間（日）
    CACHE_DAYS = 30

    # PDF抽出対象ページ (0-indexed)
    TARGET_PAGE = 5  # Page 6

    def __init__(self):
        """Initialize RICS Residential Survey service"""
        IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.PDF_DIR.mkdir(parents=True, exist_ok=True)

    def _get_url_patterns(self, year: int, month: int) -> list[str]:
        """
        Generate URL patterns for RICS PDF based on year and month

        Args:
            year: 年（例: 2024）
            month: 月（1-12）

        Returns:
            List of possible PDF URLs
        """
        month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        month_name = month_names[month - 1]

        base_url = "https://www.rics.org/content/dam/ricsglobal/documents/market-surveys/uk-residential-market-survey"

        return [
            # Pattern 1: Month number + WEB format (e.g., May 2025)
            f"{base_url}/{month}_WEB_{month_name}_{year}_RICS_UK_Residential_Market_Survey_tp.pdf",
            # Pattern 2: Residential-Market-Survey with hyphens (e.g., September 2025)
            f"{base_url}/Residential-Market-Survey-{month_name}-{year}.pdf",
            # Pattern 3: WEB with hyphens (e.g., June 2025)
            f"{base_url}/WEB-{month_name}-{year}-RICS-UK-Residential-Market-Survey-tp.pdf",
            # Pattern 4: Simple month_year format (e.g., March 2025)
            f"{base_url}/{month_name}_{year}_RICS_UK_Residential_Market_Survey.pdf",
            # Pattern 5: Month-Year with hyphens (e.g., October 2024)
            f"{base_url}/{month_name}-{year}_UK-Residential-Market-Survey.pdf",
            # Pattern 6: Simple underscore format (e.g., December 2024)
            f"{base_url}/{month_name}_{year}_RICS_UK_Residential_Market_Survey.pdf",
            # Pattern 7: Month-Year RICS format (e.g., July 2024)
            f"{base_url}/{month_name}-{year}-RICS-UK-Residential-Market-Survey.pdf",
            # Pattern 8: Month_Year UK format (e.g., April 2024)
            f"{base_url}/UK-Residential-Market-Survey_{month_name}-{year}.pdf",
            # Pattern 9: WEB prefix without month number (e.g., August 2024)
            f"{base_url}/{month_name}-{year}_UK-Residential-Market-Survey.pdf",
            # Pattern 10: UK Residential Survey with underscore (e.g., Dec 24)
            f"{base_url}/UK%20Residential%20Survey_{month_name[:3]}%20{str(year)[2:]}.pdf",
        ]

    def _try_download_pdf_from_patterns(self, year: int, month: int) -> Optional[tuple[Path, str]]:
        """
        Try to download PDF using URL patterns

        Args:
            year: 年
            month: 月

        Returns:
            Tuple of (pdf_path, report_date) or None
        """
        report_date = f"{year}-{month:02d}-01"
        date_str = f"{year}{month:02d}"
        pdf_path = IMAGE_CACHE_DIR / f"rics_survey_{date_str}.pdf"

        # 既にダウンロード済みの場合はスキップ
        if pdf_path.exists():
            logger.info(f"PDF already exists: {pdf_path}")
            return pdf_path, report_date

        url_patterns = self._get_url_patterns(year, month)

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/pdf,*/*',
        }

        for url in url_patterns:
            try:
                logger.info(f"Trying URL: {url}")
                response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)

                if response.status_code == 200:
                    content_type = response.headers.get('Content-Type', '')
                    if 'pdf' in content_type.lower() or 'octet-stream' in content_type.lower():
                        # PDFが見つかった - ダウンロード
                        logger.info(f"Found PDF at: {url}")
                        pdf_response = requests.get(url, headers=headers, timeout=120)

                        if pdf_response.status_code == 200 and pdf_response.content[:4] == b'%PDF':
                            with open(pdf_path, 'wb') as f:
                                f.write(pdf_response.content)
                            logger.info(f"Downloaded PDF to: {pdf_path}")
                            return pdf_path, report_date

            except requests.RequestException as e:
                logger.debug(f"Failed to fetch {url}: {e}")
                continue

        return None

    def _find_latest_pdf(self) -> Optional[tuple[Path, str]]:
        """
        Find the latest PDF by trying URL patterns for recent months,
        then falling back to local files

        Returns:
            Tuple of (pdf_path, report_date) or None
        """
        import re
        from dateutil.relativedelta import relativedelta

        # 最新3ヶ月分のURLパターンを試す
        now = datetime.now(LONDON)
        for months_ago in range(3):
            target_date = now - relativedelta(months=months_ago)
            result = self._try_download_pdf_from_patterns(target_date.year, target_date.month)
            if result:
                return result

        # URLパターンで見つからない場合、ローカルファイルをチェック
        logger.info("No PDF found via URL patterns, checking local files...")
        return self._get_latest_local_pdf()

    def _get_latest_local_pdf(self) -> Optional[tuple[Path, str]]:
        """
        Find the latest locally stored PDF file

        PDFファイル名形式: rics_residential_survey_YYYYMM.pdf
        例: rics_residential_survey_202412.pdf

        Returns:
            Tuple of (pdf_path, report_date) or None
        """
        import re

        # Check both PDF_DIR and IMAGE_CACHE_DIR for PDFs
        pdf_files = list(self.PDF_DIR.glob("rics_residential_survey_*.pdf"))
        pdf_files.extend(list(IMAGE_CACHE_DIR.glob("rics_survey_*.pdf")))

        if not pdf_files:
            logger.warning(f"No RICS PDF files found in {self.PDF_DIR} or {IMAGE_CACHE_DIR}")
            logger.info(f"Please download PDF from {self.SURVEY_PAGE_URL} and save as rics_residential_survey_YYYYMM.pdf")
            return None

        # ファイル名から日付を抽出してソート
        pdf_with_dates = []
        for pdf_path in pdf_files:
            # Try both naming patterns
            match = re.search(r'rics_(?:residential_survey_|survey_)(\d{6})\.pdf', pdf_path.name)
            if match:
                date_str = match.group(1)  # YYYYMM
                report_date = f"{date_str[:4]}-{date_str[4:6]}-01"
                pdf_with_dates.append((pdf_path, report_date, date_str))

        if not pdf_with_dates:
            logger.warning("No valid PDF files found (expected format: rics_residential_survey_YYYYMM.pdf or rics_survey_YYYYMM.pdf)")
            return None

        # 最新のPDFを選択
        pdf_with_dates.sort(key=lambda x: x[2], reverse=True)
        latest_pdf, report_date, _ = pdf_with_dates[0]

        logger.info(f"Found latest local PDF: {latest_pdf}, date: {report_date}")
        return latest_pdf, report_date

    def _download_pdf(self, url: str, report_date: str) -> Optional[Path]:
        """Download PDF to cache directory"""
        try:
            logger.info(f"Downloading PDF from {url}")

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            }

            response = requests.get(url, headers=headers, timeout=120)

            if response.status_code != 200:
                logger.warning(f"Failed to download PDF: HTTP {response.status_code}")
                return None

            # Check content type
            content_type = response.headers.get('Content-Type', '')
            if 'pdf' not in content_type.lower() and 'octet-stream' not in content_type.lower():
                logger.warning(f"Unexpected content type: {content_type}")
                # Still try to save if it looks like PDF content
                if not response.content[:4] == b'%PDF':
                    logger.error("Downloaded content is not a PDF")
                    return None

            date_str = report_date.replace('-', '')[:6]  # YYYYMM format
            pdf_path = IMAGE_CACHE_DIR / f"rics_survey_{date_str}.pdf"

            with open(pdf_path, 'wb') as f:
                f.write(response.content)

            logger.info(f"PDF downloaded to {pdf_path}")
            return pdf_path

        except Exception as e:
            logger.error(f"Error downloading PDF: {e}")
            return None

    def _extract_page_as_image(self, pdf_path: Path, report_date: str) -> Optional[Dict[str, str]]:
        """
        Extract page 6 of the PDF as PNG image

        Returns:
            Dictionary with forecast_image path
        """
        try:
            logger.info(f"Extracting page {self.TARGET_PAGE + 1} from {pdf_path}")

            doc = fitz.open(pdf_path)
            total_pages = len(doc)

            if total_pages <= self.TARGET_PAGE:
                logger.warning(f"PDF has only {total_pages} pages, cannot extract page {self.TARGET_PAGE + 1}")
                # Try to extract the last page as fallback
                target_page = total_pages - 1
            else:
                target_page = self.TARGET_PAGE

            page = doc[target_page]
            pix = page.get_pixmap(dpi=150)

            date_str = report_date.replace('-', '')[:6]
            image_path = IMAGE_CACHE_DIR / f"rics_survey_{date_str}_forecast.png"
            pix.save(str(image_path))
            logger.info(f"Saved forecast chart to {image_path}")

            doc.close()

            # Return relative path from backend directory for API serving
            backend_dir = Path(__file__).parent.parent.parent
            return {
                "forecast_image": str(image_path.relative_to(backend_dir))
            }

        except Exception as e:
            logger.error(f"Error extracting page: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_survey_data(self) -> Optional[Dict[str, Any]]:
        """Fetch RICS Residential Survey data from URL patterns or local PDF"""
        # Try URL patterns first, then fall back to local files
        result = self._find_latest_pdf()
        if not result:
            return None

        pdf_path, report_date = result
        date_str = report_date.replace('-', '')[:6]

        # Check if image already exists for this date
        image_path = IMAGE_CACHE_DIR / f"rics_survey_{date_str}_forecast.png"

        if image_path.exists():
            logger.info(f"Using cached image for {date_str}")
            backend_dir = Path(__file__).parent.parent.parent
            image_paths = {
                "forecast_image": str(image_path.relative_to(backend_dir))
            }
        else:
            # Extract target page as image from local PDF
            image_paths = self._extract_page_as_image(pdf_path, report_date)
            if not image_paths:
                return None

        return {
            "report_date": report_date,
            "date_str": date_str,
            "pdf_url": self.SURVEY_PAGE_URL,  # RICSサイトへのリンク（ダウンロード用）
            "forecast_image": image_paths["forecast_image"],
            "last_updated": datetime.now(JST).isoformat()
        }

    def get_survey_report(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get RICS Residential Survey data with caching

        Args:
            force_refresh: キャッシュを無視して強制的に最新データを取得

        Returns:
            {
                "report_date": "2025-12-01",
                "date_str": "202512",
                "pdf_url": "https://...",
                "forecast_image": "cache/uk/housing/rics_survey_images/...",
                "last_updated": "ISO datetime",
                "cached": bool
            }
        """
        # キャッシュチェック
        if not force_refresh:
            # Redisキャッシュチェック
            cached_data = redis_client.get(REDIS_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    logger.info("Returning cached RICS survey from Redis")
                    return {**cached_data, "cached": True}

            # ファイルキャッシュチェック
            file_cache = load_file_cache(CACHE_FILE)
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    logger.info("Returning cached RICS survey from file")
                    redis_client.set(REDIS_KEY, file_cache, expire=0)
                    return {**file_cache, "cached": True}

        # 新規データ取得
        data = self._fetch_survey_data()
        if data:
            # キャッシュに保存
            redis_client.set(REDIS_KEY, data, expire=0)
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            save_file_cache(CACHE_FILE, data)
            return {**data, "cached": False}

        # フォールバック
        file_cache = load_file_cache(CACHE_FILE)
        if file_cache:
            logger.warning("Returning fallback data from file cache")
            return {**file_cache, "cached": True, "source": "file (fallback)"}

        return self._get_fallback_data()

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        Check if cache should be refreshed
        Refresh if more than 30 days old
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            days_old = (now - last_updated).days

            return days_old > self.CACHE_DAYS

        except Exception as e:
            logger.error(f"Error checking refresh status: {e}")
            return True

    def _get_fallback_data(self) -> Dict[str, Any]:
        """Return empty fallback data"""
        return {
            "report_date": None,
            "date_str": None,
            "pdf_url": None,
            "forecast_image": None,
            "last_updated": datetime.now(JST).isoformat(),
            "cached": False,
            "error": "No data available"
        }

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(REDIS_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(REDIS_KEY)
        cached_data = redis_client.get(REDIS_KEY) if data_exists else None

        return {
            "indicator": "RICS UK Residential Market Survey",
            "source": "RICS",
            "cache_key": REDIS_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "report_date": cached_data.get("report_date") if cached_data else None,
            "file_cache_exists": CACHE_FILE.exists()
        }


# シングルトンインスタンス
rics_residential_survey_service = RICSResidentialSurveyService()
