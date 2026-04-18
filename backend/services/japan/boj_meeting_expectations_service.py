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

[移行ノート]
このサービスの Playwright 部分は backend.services.browser.PlaywrightRunner
経由に統一済み (ARM64 / OCI 対応)。以前の sync_playwright 直接利用 +
ThreadPoolExecutor ラッパーはすべて削除。
- テーブル画像 (uploads/image-*, aspect ratio > 2) を `pre_screenshot_js`
  でブラウザ内 JS で検出し data-boj-table="1" 属性を付与
- ScreenshotRequest を bytes モード (output_path=None) で実行し
  ScreenshotResult.data から PNG バイト列を取得して OCR に渡す
"""
import base64
import io
import json
import logging
import os
import re
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

from services.browser import (
    BrowserConfig,
    BrowserRunnerError,
    ScreenshotRequest,
    take_screenshot,
)
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

    # 旧 sync_playwright 実装の以下ロジックをブラウザ内 JS で再現する:
    #   1. ページ内 <img> を全走査
    #   2. src に 'uploads' と 'image-' を含むもののうち
    #      bounding rect の aspect ratio > 2 (テーブル画像) の最初の要素を採用
    #   3. data-boj-table="1" 属性を付与
    # スクショは ScreenshotRequest.clip_selector で参照し bytes モードで取得。
    _PRE_SCREENSHOT_JS = r"""
    (() => {
      document.querySelectorAll('[data-boj-table]')
        .forEach(el => el.removeAttribute('data-boj-table'));
      const imgs = Array.from(document.querySelectorAll('img'));
      for (const img of imgs) {
        const src = img.getAttribute('src') || '';
        if (src.indexOf('uploads') === -1) continue;
        if (src.indexOf('image-') === -1) continue;
        const r = img.getBoundingClientRect();
        if (r.width <= 0 || r.height <= 0) continue;
        const aspect = r.width / r.height;
        if (aspect > 2) {
          img.setAttribute('data-boj-table', '1');
          img.scrollIntoView({block: 'center'});
          return true;
        }
      }
      return false;
    })();
    """

    def _capture_table_with_playwright(self) -> Optional[bytes]:
        """Capture table image using PlaywrightRunner (bytes mode).

        旧実装は sync_playwright + ThreadPoolExecutor だったが、
        BrowserRunner 経由 (output_path=None で bytes 返却) に統一。
        テーブル画像の検出は `pre_screenshot_js` でブラウザ内 JS にて行い、
        data-boj-table="1" を付与した要素をクリップで撮影する。
        """
        request = ScreenshotRequest(
            url=self.TOKYO_TANSHI_URL,
            output_path=None,  # bytes モード
            wait_for_load_state="networkidle",
            wait_after_load_ms=1_000,
            pre_screenshot_js=self._PRE_SCREENSHOT_JS,
            wait_after_pre_js_ms=500,
            clip_selector="[data-boj-table='1']",
            scroll_into_view=True,
            viewport_override=(1400, 900),
        )
        config = BrowserConfig(
            viewport=(1400, 900),
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        try:
            result = take_screenshot(request, config=config)
        except BrowserRunnerError as e:
            logger.error(f"Error capturing with Playwright: {e}")
            return None
        except Exception as e:
            logger.error(f"Error capturing with Playwright: {e}")
            return None

        if result.data:
            logger.info(
                f"Captured table screenshot: {result.size_bytes} bytes"
            )
            return result.data
        logger.warning("PlaywrightRunner returned no screenshot data")
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

    # 東京短資テーブルは通常 5〜7 行の会合データを含む。
    # OCR 結果がこの閾値未満の場合はパース失敗とみなしフォールバックへ。
    MIN_EXPECTED_MEETINGS = 3

    def _parse_ocr_text(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """Parse OCR text to extract meeting expectations data.

        東京短資の画像テーブル構造 (2026-04 時点):
        ---------------------------------------------------------------
        2026/04  会合   0.7713   0.0443   18%   0.18   26/04/30 ~ 26/06/16
                BOJ MTG
        2026/06  会合   0.9113   0.1400   56%   0.74   26/06/17 ~ 26/07/31
                BOJ MTG
        ...
        ---------------------------------------------------------------
        OCR は行が分割されることがあるため、
        「4桁年/月」を含む行のみデータ行として扱い、
        ヘッダーは「4桁年/月」を含まない行として除外する。
        """
        try:
            logger.info(f"Parsing OCR text:\n{text}")

            # ── 全テキストを1つにまとめてから行分割 ──
            # OCR が同じデータ行を複数行に分ける場合があるため、
            # まず「4桁年/月」を含む行を起点にチャンク化する
            lines = text.strip().split('\n')

            # 4桁年 + /月 のパターン (例: 2026/04)
            meeting_date_re = re.compile(r'(20\d{2})/(\d{1,2})')
            # 小数 (2桁以上の小数部)
            decimal_re = re.compile(r'(\d+\.\d{2,})')
            # パーセント (例: 18%, 56 %)
            percent_re = re.compile(r'(\d+)\s*%')

            # チャンク化: 日付行 + 続く非日付行をまとめる
            chunks: list[str] = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if meeting_date_re.search(line):
                    chunks.append(line)
                elif chunks:
                    # 直前の日付行チャンクに追記
                    chunks[-1] += " " + line

            meeting_data = []
            for chunk in chunks:
                date_match = meeting_date_re.search(chunk)
                if not date_match:
                    continue

                year = int(date_match.group(1))
                month = int(date_match.group(2))
                if not (2020 <= year <= 2030 and 1 <= month <= 12):
                    continue

                meeting_date = f"{year}-{month:02d}-01"

                # ── 数値抽出 ──
                # 対象期間の短縮日付 (26/04/30) を除外するため、
                # 4桁年の日付部分より後ろの短縮日付を除去してからパース
                # 例: "26/04/30 ~ 26/06/16" → 除外
                chunk_clean = re.sub(
                    r'\d{2}/\d{2}/\d{2}\s*~\s*\d{2}/\d{2}/\d{2}', '', chunk
                )

                all_decimals = [float(d) for d in decimal_re.findall(chunk_clean)]
                all_percents = [int(p) for p in percent_re.findall(chunk_clean)]

                logger.info(f"Chunk: {chunk_clean}")
                logger.info(f"  Decimals: {all_decimals}, Percents: {all_percents}")

                if not all_decimals:
                    continue

                # 降順ソートして役割を割り当て:
                # 1番目 (最大): OIS rate (0.5 ~ 3.0 程度)
                # 2番目: 利上げ織込み回数 (frequency) or difference
                # 3番目 (最小): difference (0.0xxx)
                # ※ 利上げ織込み回数は frequency として別途保持
                desc = sorted(all_decimals, reverse=True)

                ois_rate = desc[0] if desc else None
                if ois_rate is None or not (0.3 <= ois_rate <= 3.0):
                    continue

                # difference と frequency を分離:
                # difference は通常 0.01〜0.15 程度、frequency は 0.1〜5.0 程度
                # テーブル上の順序: OIS → difference → probability → frequency
                # ただし OCR の順序は保証されないので、サイズで判別
                remaining = [v for v in desc if v != ois_rate]

                difference = 0.0
                frequency = None
                if len(remaining) >= 2:
                    # 小さい方が difference、大きい方が frequency
                    difference = min(remaining)
                    frequency = max(remaining)
                elif len(remaining) == 1:
                    v = remaining[0]
                    # 0.2 未満なら difference、それ以上なら frequency
                    if v < 0.2:
                        difference = v
                    else:
                        frequency = v

                probability = float(all_percents[0]) if all_percents else 0.0

                entry: Dict[str, Any] = {
                    "meeting_date": meeting_date,
                    "ois_rate": round(ois_rate, 4),
                    "difference": round(difference, 4),
                    "probability": round(probability, 1),
                }
                if frequency is not None:
                    entry["frequency"] = round(frequency, 2)

                meeting_data.append(entry)

            if not meeting_data:
                logger.warning("Could not parse meeting data from OCR text")
                return None

            # Remove duplicates and sort by date
            seen_dates: set[str] = set()
            unique_data: list[Dict[str, Any]] = []
            for item in meeting_data:
                if item["meeting_date"] not in seen_dates:
                    seen_dates.add(item["meeting_date"])
                    unique_data.append(item)

            unique_data.sort(key=lambda x: x["meeting_date"])
            logger.info(f"Parsed {len(unique_data)} meeting expectations from OCR")

            # Quality gate: OCR がほとんどの行を取りこぼした場合は失敗扱い
            if len(unique_data) < self.MIN_EXPECTED_MEETINGS:
                logger.warning(
                    f"OCR parsed only {len(unique_data)} meetings "
                    f"(min {self.MIN_EXPECTED_MEETINGS}), treating as failure"
                )
                return None

            return unique_data

        except Exception as e:
            logger.error(f"Error parsing OCR text: {e}")
            return None

    def _get_fallback_data(self) -> List[Dict[str, Any]]:
        """
        Return fallback data when scraping fails and no cache exists.
        初回起動時のみ使用される。以降は品質 OK キャッシュが優先される。
        """
        return [
            {
                "meeting_date": "2026-04-01",
                "ois_rate": 0.7713,
                "difference": 0.0443,
                "probability": 18.0,
                "frequency": 0.18,
            },
            {
                "meeting_date": "2026-06-01",
                "ois_rate": 0.9113,
                "difference": 0.1400,
                "probability": 56.0,
                "frequency": 0.74,
            },
            {
                "meeting_date": "2026-07-01",
                "ois_rate": 0.9813,
                "difference": 0.0700,
                "probability": 28.0,
                "frequency": 1.02,
            },
            {
                "meeting_date": "2026-09-01",
                "ois_rate": 1.0613,
                "difference": 0.0800,
                "probability": 32.0,
                "frequency": 1.34,
            },
            {
                "meeting_date": "2026-10-01",
                "ois_rate": 1.1388,
                "difference": 0.0775,
                "probability": 31.0,
                "frequency": 1.65,
            },
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

    def _is_data_quality_ok(self, meetings: List[Dict[str, Any]]) -> bool:
        """Check if meeting data passes quality gate"""
        if not meetings or len(meetings) < self.MIN_EXPECTED_MEETINGS:
            return False
        return True

    def _load_existing_cache(self) -> Optional[Dict[str, Any]]:
        """品質 OK な既存キャッシュを返す（Redis → ファイルの順）"""
        cached = redis_client.get(REDIS_KEY)
        if cached and self._is_data_quality_ok(cached.get("meetings", [])):
            return cached

        file_cache = load_file_cache(CACHE_FILE)
        if file_cache and self._is_data_quality_ok(file_cache.get("meetings", [])):
            return file_cache

        return None

    def _save_cache(self, data: Dict[str, Any]) -> None:
        """Redis + ファイルキャッシュに保存"""
        redis_client.set(REDIS_KEY, data, expire=0)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        save_file_cache(CACHE_FILE, data)

    def _fetch_boj_expectations(self) -> Optional[Dict[str, Any]]:
        """東京短資からデータを取得。品質 OK のデータのみ返す。"""
        html = self._fetch_html()

        if not html:
            return None

        meeting_data, data_source = self._parse_table_data(html)

        if not meeting_data or not self._is_data_quality_ok(meeting_data):
            logger.warning(
                f"Parsed data insufficient "
                f"({len(meeting_data) if meeting_data else 0} meetings), "
                f"returning None"
            )
            return None

        return {
            "meetings": meeting_data,
            "last_updated": datetime.now(JST).isoformat(),
            "source": self.TOKYO_TANSHI_URL,
            "data_source": data_source,
        }

    def get_boj_expectations(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get BOJ meeting expectations data with caching

        戦略:
        1. キャッシュが品質 OK かつ fresh → そのまま返す
        2. 東京短資から取得 → 品質 OK ならキャッシュ更新して返す
        3. 取得失敗 → 既存の品質 OK キャッシュを返す（古くても）
        4. キャッシュも無い → 初期化用 fallback

        重要: 品質 NG のデータでキャッシュを上書きしない
        """
        # 1. キャッシュチェック（品質 OK のもののみ）
        if not force_refresh:
            existing = self._load_existing_cache()
            if existing and not self.should_refresh():
                logger.info("Returning cached BOJ expectations")
                return {**existing, "cached": True}

        # 2. 新規データ取得
        fresh = self._fetch_boj_expectations()
        if fresh:
            self._save_cache(fresh)
            return {**fresh, "cached": False}

        # 3. 取得失敗 → 既存キャッシュ（古くても品質 OK なら返す）
        existing = self._load_existing_cache()
        if existing:
            logger.warning(
                "Fresh fetch failed, returning stale but quality-OK cache"
            )
            return {**existing, "cached": True}

        # 4. 初回起動等でキャッシュが一切無い場合のみ fallback
        logger.warning("No cache available, using initial fallback data")
        return {
            "meetings": self._get_fallback_data(),
            "last_updated": datetime.now(JST).isoformat(),
            "source": "fallback",
            "data_source": "fallback",
            "cached": False,
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
