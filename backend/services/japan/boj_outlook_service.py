"""
BOJ Outlook Report Service
Fetches and processes BOJ Outlook Report (展望レポート) PDFs
Extracts the last 2 pages showing Policy Board member forecasts

データソース: 日本銀行
URL: https://www.boj.or.jp/mopo/outlook/gor{YYMM}a.pdf
発表月: 1月、4月、7月、10月（年4回）

取得データ:
- 政策委員の大勢見通し（PDF最終2ページ目）
- 政策委員の経済・物価見通しとリスク評価（PDF最終ページ）

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

# キャッシュ設定
REDIS_KEY = "japan:boj:outlook_report"
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "japan" / "monetary_policy"
CACHE_FILE = CACHE_DIR / "boj_outlook_report.json"
IMAGE_CACHE_DIR = CACHE_DIR / "outlook_images"


class BOJOutlookService:
    """Service for fetching and processing BOJ Outlook Report"""

    # BOJ Outlook Report URL pattern
    # Format: https://www.boj.or.jp/mopo/outlook/gorYYMMa.pdf
    # Where YYMM is the year and month (e.g., 2507 for July 2025)
    BOJ_OUTLOOK_BASE_URL = "https://www.boj.or.jp/mopo/outlook/gor{yymm}a.pdf"

    # Outlook reports are published in January, April, July, and October
    OUTLOOK_MONTHS = [1, 4, 7, 10]

    # キャッシュ有効期間（日）
    CACHE_DAYS = 30

    def __init__(self):
        """Initialize BOJ Outlook service"""
        IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _get_latest_outlook_url(self) -> Optional[tuple[str, str]]:
        """
        Get the URL of the latest available outlook report
        Tries current and previous outlook months

        Returns:
            Tuple of (url, yymm) or None
        """
        now = datetime.now(JST)
        current_year = now.year
        current_month = now.month

        # Find the most recent outlook month
        # Try current year's outlook months in reverse order
        for year in [current_year, current_year - 1]:
            for month in reversed(self.OUTLOOK_MONTHS):
                # Skip future months in current year
                if year == current_year and month > current_month:
                    continue

                # Format YYMM (e.g., 2507 for July 2025)
                yy = str(year)[2:]
                mm = str(month).zfill(2)
                yymm = f"{yy}{mm}"

                url = self.BOJ_OUTLOOK_BASE_URL.format(yymm=yymm)

                # Check if URL exists
                try:
                    response = requests.head(url, timeout=10)
                    if response.status_code == 200:
                        logger.info(f"Found latest outlook report: {url}")
                        return url, yymm
                except Exception:
                    continue

        logger.warning("No outlook report URL found")
        return None

    def _download_pdf(self, url: str, yymm: str) -> Optional[Path]:
        """Download PDF to cache directory"""
        try:
            logger.info(f"Downloading PDF from {url}")
            response = requests.get(url, timeout=60)

            if response.status_code != 200:
                logger.warning(f"Failed to download PDF: HTTP {response.status_code}")
                return None

            pdf_path = IMAGE_CACHE_DIR / f"boj_outlook_{yymm}.pdf"

            with open(pdf_path, 'wb') as f:
                f.write(response.content)

            logger.info(f"PDF downloaded to {pdf_path}")
            return pdf_path

        except Exception as e:
            logger.error(f"Error downloading PDF: {e}")
            return None

    def _extract_last_pages_as_images(self, pdf_path: Path, yymm: str) -> Optional[Dict[str, str]]:
        """
        Extract the last 2 pages of the PDF as PNG images

        Returns:
            Dictionary with forecasts_image and risks_image paths
        """
        try:
            logger.info(f"Extracting last 2 pages from {pdf_path}")

            doc = fitz.open(pdf_path)
            total_pages = len(doc)

            if total_pages < 2:
                logger.warning(f"PDF has less than 2 pages: {total_pages}")
                doc.close()
                return None

            # Extract second-to-last page (forecasts table)
            page_forecasts_index = total_pages - 2
            page_forecasts = doc[page_forecasts_index]
            pix_forecasts = page_forecasts.get_pixmap(dpi=150)
            forecasts_path = IMAGE_CACHE_DIR / f"outlook_{yymm}_forecasts.png"
            pix_forecasts.save(str(forecasts_path))
            logger.info(f"Saved forecast table to {forecasts_path}")

            # Extract last page (risk assessment)
            page_risks_index = total_pages - 1
            page_risks = doc[page_risks_index]
            pix_risks = page_risks.get_pixmap(dpi=150)
            risks_path = IMAGE_CACHE_DIR / f"outlook_{yymm}_risks.png"
            pix_risks.save(str(risks_path))
            logger.info(f"Saved risk assessment to {risks_path}")

            doc.close()

            # Return relative paths from backend directory for API serving
            backend_dir = Path(__file__).parent.parent.parent
            return {
                "forecasts_image": str(forecasts_path.relative_to(backend_dir)),
                "risks_image": str(risks_path.relative_to(backend_dir))
            }

        except Exception as e:
            logger.error(f"Error extracting pages: {e}")
            return None

    def _fetch_outlook_data(self) -> Optional[Dict[str, Any]]:
        """Fetch BOJ Outlook Report data"""
        # Get latest outlook URL
        result = self._get_latest_outlook_url()
        if not result:
            return None

        url, yymm = result

        # Check if images already exist for this yymm
        forecasts_path = IMAGE_CACHE_DIR / f"outlook_{yymm}_forecasts.png"
        risks_path = IMAGE_CACHE_DIR / f"outlook_{yymm}_risks.png"

        if forecasts_path.exists() and risks_path.exists():
            logger.info(f"Using cached images for {yymm}")
            backend_dir = Path(__file__).parent.parent.parent
            image_paths = {
                "forecasts_image": str(forecasts_path.relative_to(backend_dir)),
                "risks_image": str(risks_path.relative_to(backend_dir))
            }
        else:
            # Download PDF
            pdf_path = self._download_pdf(url, yymm)
            if not pdf_path:
                return None

            # Extract last 2 pages as images
            image_paths = self._extract_last_pages_as_images(pdf_path, yymm)
            if not image_paths:
                return None

        # Parse year and month for display
        year = int("20" + yymm[:2])
        month = int(yymm[2:])

        return {
            "report_date": f"{year}-{month:02d}-01",
            "yymm": yymm,
            "pdf_url": url,
            "forecasts_image": image_paths["forecasts_image"],
            "risks_image": image_paths["risks_image"],
            "last_updated": datetime.now(JST).isoformat()
        }

    def get_outlook_report(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get BOJ Outlook Report data with caching

        Args:
            force_refresh: キャッシュを無視して強制的に最新データを取得

        Returns:
            {
                "report_date": "2025-07-01",
                "yymm": "2507",
                "pdf_url": "https://...",
                "forecasts_image": "cache/japan/monetary_policy/outlook_images/...",
                "risks_image": "cache/japan/monetary_policy/outlook_images/...",
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
                    logger.info("Returning cached BOJ outlook from Redis")
                    return {**cached_data, "cached": True}

            # ファイルキャッシュチェック
            file_cache = load_file_cache(CACHE_FILE)
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    logger.info("Returning cached BOJ outlook from file")
                    redis_client.set(REDIS_KEY, file_cache, expire=0)
                    return {**file_cache, "cached": True}

        # 新規データ取得
        data = self._fetch_outlook_data()
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

    def should_refresh(self) -> bool:
        """Check if cache should be refreshed (public method)"""
        file_cache = load_file_cache(CACHE_FILE)
        if not file_cache:
            return True

        last_updated_str = file_cache.get("last_updated")
        if not last_updated_str:
            return True

        return self._should_refresh(last_updated_str)

    def _get_fallback_data(self) -> Dict[str, Any]:
        """Return empty fallback data"""
        return {
            "report_date": None,
            "yymm": None,
            "pdf_url": None,
            "forecasts_image": None,
            "risks_image": None,
            "last_updated": datetime.now(JST).isoformat(),
            "cached": False,
            "error": "Failed to fetch BOJ Outlook Report"
        }

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(REDIS_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        exists = redis_client.exists(REDIS_KEY)
        cached_data = redis_client.get(REDIS_KEY) if exists else None

        return {
            "indicator": "BOJ Outlook Report",
            "source": "Bank of Japan",
            "cache_key": REDIS_KEY,
            "exists": exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "report_date": cached_data.get("report_date") if cached_data else None,
            "yymm": cached_data.get("yymm") if cached_data else None,
            "file_cache_exists": CACHE_FILE.exists(),
            "image_cache_dir": str(IMAGE_CACHE_DIR)
        }


# シングルトンインスタンス
_service_instance: Optional[BOJOutlookService] = None


def get_boj_outlook_service() -> BOJOutlookService:
    """Get or create BOJOutlookService singleton instance"""
    global _service_instance
    if _service_instance is None:
        _service_instance = BOJOutlookService()
    return _service_instance


# グローバルサービスインスタンス
boj_outlook_service = get_boj_outlook_service()
