"""
BOJ Meeting Expectations Service
Fetches and parses BOJ policy rate hike expectations from Tokyo Tanshi

データソース: 東京短資
URL: https://www.tokyotanshi.co.jp/archives/15647
更新頻度: 営業日毎、15:30 JST頃

取得データ:
- 日銀会合日
- OIS気配値（%）
- 対前会合差分（%）
- 政策金利変更織込み比率（%）

OCR: Tesseract OCR (primary) / Google Cloud Vision API (fallback)
"""
import base64
import io
import json
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from PIL import Image

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

from services.usa.fred_utils import load_file_cache, save_file_cache
from core.redis_client import redis_client

logger = logging.getLogger(__name__)

# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# キャッシュ設定
REDIS_KEY = "japan:boj:meeting_expectations"
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "monetary_policy"
CACHE_FILE = CACHE_DIR / "boj_meeting_expectations.json"

# Google Cloud Vision API (fallback)
GOOGLE_CLOUD_VISION_API_KEY = os.getenv("GOOGLE_CLOUD_VISION_API_KEY", "")
VISION_API_URL = "https://vision.googleapis.com/v1/images:annotate"


class BOJMeetingExpectationsService:
    """Service for fetching BOJ meeting expectations from Tokyo Tanshi"""

    # Tokyo Tanshi BOJ expectations page
    TOKYO_TANSHI_URL = "https://www.tokyotanshi.co.jp/archives/15647"

    # 発表時刻（JST）- 15:30頃
    RELEASE_HOUR_JST = 15
    RELEASE_MINUTE_JST = 30

    def __init__(self):
        """Initialize BOJ Meeting Expectations service"""
        pass

    def _fetch_html(self) -> Optional[str]:
        """Fetch HTML content from Tokyo Tanshi page"""
        try:
            logger.info(f"Fetching BOJ expectations from {self.TOKYO_TANSHI_URL}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(self.TOKYO_TANSHI_URL, headers=headers, timeout=30)

            if response.status_code != 200:
                logger.warning(f"Failed to fetch page: HTTP {response.status_code}")
                return None

            response.encoding = 'utf-8'
            return response.text

        except Exception as e:
            logger.error(f"Error fetching HTML: {e}")
            return None

    def _find_table_image_url(self, html: str) -> Optional[str]:
        """Find the table image URL from HTML"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            images = soup.find_all('img')

            # Collect all candidate images with their dimensions
            candidates = []
            for img in images:
                src = img.get('src', '')
                # Look for uploaded images (table data images)
                if 'uploads' in src and 'image-' in src:
                    # Make sure it's an absolute URL
                    if not src.startswith('http'):
                        src = f"https://www.tokyotanshi.co.jp{src}"

                    # Try to extract dimensions from filename (e.g., image-1439-1030x673.png)
                    import re
                    dim_match = re.search(r'-(\d+)x(\d+)\.', src)
                    if dim_match:
                        width = int(dim_match.group(1))
                        height = int(dim_match.group(2))
                        candidates.append((src, width, height))
                        logger.info(f"Found candidate image: {src} ({width}x{height})")
                    else:
                        # No dimensions in filename, add with default
                        candidates.append((src, 0, 0))
                        logger.info(f"Found candidate image: {src} (no dimensions)")

            if candidates:
                # Sort by height (ascending) - shorter images are likely tables, taller ones are charts
                # Table images typically have aspect ratio > 2 (wide), charts are more square
                table_candidates = []
                for src, width, height in candidates:
                    if height > 0 and width > 0:
                        aspect_ratio = width / height
                        # Table images are typically wider than tall (aspect ratio > 2)
                        if aspect_ratio > 2:
                            table_candidates.append((src, width, height, aspect_ratio))
                            logger.info(f"Table candidate: {src} (aspect ratio: {aspect_ratio:.2f})")

                if table_candidates:
                    # Use the one with highest aspect ratio (widest table)
                    table_candidates.sort(key=lambda x: x[3], reverse=True)
                    best_image = table_candidates[0][0]
                else:
                    # Fallback to first candidate
                    best_image = candidates[0][0]

                logger.info(f"Selected best table image: {best_image}")
                return best_image

            logger.warning("No table image found in HTML")
            return None

        except Exception as e:
            logger.error(f"Error finding table image: {e}")
            return None

    def _download_image(self, url: str) -> Optional[bytes]:
        """Download image from URL"""
        try:
            logger.info(f"Downloading image from {url}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code != 200:
                logger.warning(f"Failed to download image: HTTP {response.status_code}")
                return None

            return response.content

        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return None

    def _capture_table_with_playwright(self) -> Optional[bytes]:
        """Capture table image using Playwright in a separate thread to bypass CDN cache"""
        import concurrent.futures

        def run_playwright():
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(self.TOKYO_TANSHI_URL, wait_until='networkidle', timeout=30000)

                # Find the table image element (the one with aspect ratio > 2)
                images = page.query_selector_all('img')
                table_img = None

                for img in images:
                    src = img.get_attribute('src')
                    if src and 'uploads' in src and 'image-' in src:
                        bbox = img.bounding_box()
                        if bbox and bbox['width'] > 0 and bbox['height'] > 0:
                            aspect_ratio = bbox['width'] / bbox['height']
                            # Table images are wide (aspect ratio > 2)
                            if aspect_ratio > 2:
                                table_img = img
                                logger.info(f"Found table image: {src} (aspect ratio: {aspect_ratio:.2f})")
                                break

                screenshot_bytes = None
                if table_img:
                    screenshot_bytes = table_img.screenshot()
                    logger.info(f"Captured table screenshot: {len(screenshot_bytes)} bytes")

                browser.close()
                return screenshot_bytes

        try:
            # Run Playwright in a separate thread to avoid asyncio conflicts
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_playwright)
                return future.result(timeout=60)

        except Exception as e:
            logger.error(f"Error capturing with Playwright: {e}")
            return None

    def _preprocess_image(self, image_data: bytes) -> Image.Image:
        """Preprocess image for better OCR accuracy"""
        try:
            img = Image.open(io.BytesIO(image_data))

            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Increase image size for better OCR (3x scale for better accuracy)
            width, height = img.size
            scale = 3
            img = img.resize((width * scale, height * scale), Image.Resampling.LANCZOS)

            # Convert to grayscale for better OCR
            img = img.convert('L')

            # Apply contrast enhancement
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.5)

            return img

        except Exception as e:
            logger.error(f"Error preprocessing image: {e}")
            return Image.open(io.BytesIO(image_data))

    def _extract_text_with_tesseract(self, image_data: bytes) -> Optional[str]:
        """Extract text from image using Tesseract OCR"""
        if not TESSERACT_AVAILABLE:
            logger.warning("Tesseract not available")
            return None

        try:
            # Preprocess image
            img = self._preprocess_image(image_data)

            # Configure Tesseract for Japanese + numbers
            # Use both Japanese and English for better number recognition
            custom_config = r'--oem 3 --psm 6 -l jpn+eng'

            # Extract text
            text = pytesseract.image_to_string(img, config=custom_config)

            if text.strip():
                logger.info(f"Tesseract OCR extracted {len(text)} characters")
                return text

            logger.warning("Tesseract OCR returned empty result")
            return None

        except Exception as e:
            logger.error(f"Error with Tesseract OCR: {e}")
            return None

    def _extract_text_with_vision_api(self, image_data: bytes) -> Optional[str]:
        """Extract text from image using Google Cloud Vision API (fallback)"""
        if not GOOGLE_CLOUD_VISION_API_KEY:
            logger.info("GOOGLE_CLOUD_VISION_API_KEY not set, skipping Vision API")
            return None

        try:
            # Encode image to base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')

            # Prepare request
            request_body = {
                "requests": [
                    {
                        "image": {
                            "content": image_base64
                        },
                        "features": [
                            {
                                "type": "TEXT_DETECTION",
                                "maxResults": 1
                            }
                        ]
                    }
                ]
            }

            # Call Vision API
            response = requests.post(
                f"{VISION_API_URL}?key={GOOGLE_CLOUD_VISION_API_KEY}",
                json=request_body,
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"Vision API error: HTTP {response.status_code}, {response.text}")
                return None

            result = response.json()
            responses = result.get("responses", [])

            if responses and responses[0].get("textAnnotations"):
                full_text = responses[0]["textAnnotations"][0].get("description", "")
                logger.info(f"Vision API OCR extracted {len(full_text)} characters")
                return full_text

            logger.warning("No text found in image via Vision API")
            return None

        except Exception as e:
            logger.error(f"Error calling Vision API: {e}")
            return None

    def _parse_ocr_text(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """Parse OCR text to extract meeting expectations data"""
        try:
            logger.info(f"Parsing OCR text:\n{text}")

            lines = text.strip().split('\n')
            meeting_data = []

            # Pattern to match date like "2026/01" or "2026/03" anywhere in line
            date_pattern = re.compile(r'(\d{4})/(\d{1,2})')
            # Pattern to match decimal numbers with at least 2 digits after decimal (like 0.7275, 0.0725)
            # This excludes dates like 26/01/26 from being parsed as decimals
            decimal_pattern = re.compile(r'(\d+\.\d{2,})')
            # Pattern to match percentage (like 29%, 0%, 8%)
            percent_pattern = re.compile(r'(\d+)%')

            for line in lines:
                line = line.strip()

                # Skip header lines and footer
                if any(skip in line.lower() for skip in ['meeting', 'ois', '気配', 'courtesy', 'totan', '提供']):
                    continue

                date_match = date_pattern.search(line)

                if date_match:
                    year = int(date_match.group(1))
                    month = int(date_match.group(2))

                    # Validate year/month
                    if 2020 <= year <= 2030 and 1 <= month <= 12:
                        meeting_date = f"{year}-{month:02d}-01"

                        # Find all decimal numbers in this line
                        decimals = decimal_pattern.findall(line)
                        # Find percentage
                        percents = percent_pattern.findall(line)

                        logger.info(f"Line: {line}")
                        logger.info(f"  Decimals: {decimals}, Percents: {percents}")

                        # Filter decimals to find OIS rate (should be 0.5-2.0 range typically)
                        ois_candidates = [float(d) for d in decimals if 0.4 < float(d) < 2.5]
                        diff_candidates = [float(d) for d in decimals if 0 < float(d) < 0.2]

                        if ois_candidates:
                            ois_rate = ois_candidates[0]

                            # Difference is the small value (0.0xxx)
                            difference = diff_candidates[0] if diff_candidates else 0.0

                            # Probability from percentage pattern
                            probability = float(percents[0]) if percents else 0.0

                            meeting_data.append({
                                "meeting_date": meeting_date,
                                "ois_rate": round(ois_rate, 4),
                                "difference": round(difference, 4),
                                "probability": round(probability, 1)
                            })

            if meeting_data:
                # Remove duplicates and sort by date
                seen_dates = set()
                unique_data = []
                for item in meeting_data:
                    if item["meeting_date"] not in seen_dates:
                        seen_dates.add(item["meeting_date"])
                        unique_data.append(item)

                unique_data.sort(key=lambda x: x["meeting_date"])
                logger.info(f"Parsed {len(unique_data)} meeting expectations from OCR")
                return unique_data

            logger.warning("Could not parse meeting data from OCR text")
            return None

        except Exception as e:
            logger.error(f"Error parsing OCR text: {e}")
            return None

    def _get_fallback_data(self) -> List[Dict[str, Any]]:
        """
        Return fallback hardcoded data when scraping fails
        This data should be updated periodically from the Tokyo Tanshi website
        """
        # 最新のデータ（2026年1月時点の想定データ）
        return [
            {
                "meeting_date": "2026-01-01",
                "ois_rate": 0.7500,
                "difference": 0.0000,
                "probability": 0.0
            },
            {
                "meeting_date": "2026-03-01",
                "ois_rate": 0.8125,
                "difference": 0.0625,
                "probability": 25.0
            },
            {
                "meeting_date": "2026-04-01",
                "ois_rate": 0.8750,
                "difference": 0.0625,
                "probability": 25.0
            },
            {
                "meeting_date": "2026-06-01",
                "ois_rate": 0.9375,
                "difference": 0.0625,
                "probability": 25.0
            },
            {
                "meeting_date": "2026-07-01",
                "ois_rate": 1.0000,
                "difference": 0.0625,
                "probability": 25.0
            }
        ]

    def _fetch_with_ocr(self, html: str) -> tuple[Optional[List[Dict[str, Any]]], str]:
        """Fetch data using OCR from table image. Returns (data, source)"""
        image_data = None
        ocr_source = "fallback"

        # Try Playwright first (bypasses CDN cache)
        logger.info("Trying Playwright screenshot method...")
        image_data = self._capture_table_with_playwright()
        if image_data:
            ocr_source = "playwright"
        else:
            # Fallback to direct image download
            logger.info("Playwright failed, trying direct image download...")
            image_url = self._find_table_image_url(html)
            if image_url:
                image_data = self._download_image(image_url)
                if image_data:
                    ocr_source = "direct"

        if not image_data:
            return None, "fallback"

        # Try Tesseract OCR
        ocr_text = self._extract_text_with_tesseract(image_data)

        # Fallback to Vision API if Tesseract fails
        if not ocr_text and GOOGLE_CLOUD_VISION_API_KEY:
            ocr_text = self._extract_text_with_vision_api(image_data)
            ocr_source = f"{ocr_source}_vision"

        if not ocr_text:
            return None, "fallback"

        # Parse OCR text
        data = self._parse_ocr_text(ocr_text)
        if data:
            return data, ocr_source

        return None, "fallback"

    def _parse_table_data(self, html: str) -> tuple[Optional[List[Dict[str, Any]]], str]:
        """
        Parse BOJ meeting expectations table from HTML
        First try OCR, then fallback to HTML table parsing
        Returns (data, source)
        """
        # Try OCR
        ocr_data, source = self._fetch_with_ocr(html)
        if ocr_data:
            return ocr_data, source

        logger.info("OCR failed, trying HTML table parsing")

        # Fallback to HTML table parsing
        try:
            soup = BeautifulSoup(html, 'html.parser')
            tables = soup.find_all('table')

            if tables:
                for table in tables:
                    rows = table.find_all('tr')
                    if len(rows) > 1:
                        meeting_data = []
                        for row in rows[1:]:
                            cells = row.find_all(['td', 'th'])
                            if len(cells) >= 4:
                                try:
                                    meeting_data.append({
                                        "meeting_date": cells[0].get_text(strip=True),
                                        "ois_rate": float(cells[1].get_text(strip=True).replace('%', '')),
                                        "difference": float(cells[2].get_text(strip=True).replace('%', '').replace('+', '')),
                                        "probability": float(cells[3].get_text(strip=True).replace('%', ''))
                                    })
                                except (ValueError, IndexError):
                                    continue

                        if meeting_data:
                            logger.info(f"Parsed {len(meeting_data)} meeting expectations from HTML table")
                            return meeting_data, "html"

            logger.info("No table found in HTML")
            return None, "fallback"

        except Exception as e:
            logger.error(f"Error parsing table data: {e}")
            return None, "fallback"

    def _fetch_boj_expectations(self) -> Optional[Dict[str, Any]]:
        """Fetch BOJ meeting expectations data"""
        html = self._fetch_html()

        meeting_data = None
        data_source = "fallback"

        if html:
            meeting_data, data_source = self._parse_table_data(html)

        # Use fallback data if parsing failed
        if not meeting_data:
            logger.info("Using fallback data for BOJ meeting expectations")
            meeting_data = self._get_fallback_data()
            data_source = "fallback"

        return {
            "meetings": meeting_data,
            "last_updated": datetime.now(JST).isoformat(),
            "source": self.TOKYO_TANSHI_URL,
            "data_source": data_source
        }

    def get_boj_expectations(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get BOJ meeting expectations data with caching

        Args:
            force_refresh: キャッシュを無視して強制的に最新データを取得

        Returns:
            {
                "meetings": [{meeting_date, ois_rate, difference, probability}, ...],
                "last_updated": "ISO datetime",
                "source": "URL",
                "data_source": "tesseract" | "vision_api" | "html" | "fallback",
                "cached": bool
            }
        """
        # キャッシュチェック
        if not force_refresh:
            # Redisキャッシュチェック
            cached_data = redis_client.get(REDIS_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self.should_refresh():
                    logger.info("Returning cached BOJ expectations from Redis")
                    return {**cached_data, "cached": True}

            # ファイルキャッシュチェック
            file_cache = load_file_cache(CACHE_FILE)
            if file_cache:
                if not self.should_refresh():
                    logger.info("Returning cached BOJ expectations from file")
                    redis_client.set(REDIS_KEY, file_cache, expire=0)
                    return {**file_cache, "cached": True}

        # 新規データ取得
        data = self._fetch_boj_expectations()
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

        return {
            "meetings": self._get_fallback_data(),
            "last_updated": datetime.now(JST).isoformat(),
            "source": "fallback",
            "data_source": "fallback",
            "cached": False,
            "error": "Failed to fetch BOJ meeting expectations data"
        }

    def should_refresh(self) -> bool:
        """
        Check if cache should be refreshed
        Refresh daily at 15:30 JST on business days
        """
        file_cache = load_file_cache(CACHE_FILE)

        if not file_cache:
            return True

        try:
            last_updated_str = file_cache.get("last_updated")
            if not last_updated_str:
                return True

            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # If it's weekend, no need to refresh
            if now.weekday() >= 5:
                return False

            # If cached data is from today after 15:30, no refresh needed
            if (last_updated.date() == now.date() and
                    last_updated.hour >= self.RELEASE_HOUR_JST and
                    last_updated.minute >= self.RELEASE_MINUTE_JST):
                return False

            # If it's after 15:30 today and cache is old, refresh
            if (now.hour > self.RELEASE_HOUR_JST or
                    (now.hour == self.RELEASE_HOUR_JST and now.minute >= self.RELEASE_MINUTE_JST)):
                return last_updated.date() < now.date()

            return False

        except Exception as e:
            logger.error(f"Error checking refresh status: {e}")
            return True

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(REDIS_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        exists = redis_client.exists(REDIS_KEY)
        cached_data = redis_client.get(REDIS_KEY) if exists else None

        return {
            "indicator": "BOJ Meeting Expectations",
            "source": "Tokyo Tanshi",
            "cache_key": REDIS_KEY,
            "exists": exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_source": cached_data.get("data_source") if cached_data else None,
            "meeting_count": len(cached_data.get("meetings", [])) if cached_data else 0,
            "file_cache_exists": CACHE_FILE.exists(),
            "tesseract_available": TESSERACT_AVAILABLE,
            "vision_api_configured": bool(GOOGLE_CLOUD_VISION_API_KEY)
        }


# シングルトンインスタンス
_service_instance: Optional[BOJMeetingExpectationsService] = None


def get_boj_expectations_service() -> BOJMeetingExpectationsService:
    """Get or create BOJMeetingExpectationsService singleton instance"""
    global _service_instance
    if _service_instance is None:
        _service_instance = BOJMeetingExpectationsService()
    return _service_instance


# グローバルサービスインスタンス
boj_meeting_expectations_service = get_boj_expectations_service()
