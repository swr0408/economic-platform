"""
Komtrax（車両稼働時間）Screenshot Service
コマツIRページからKomtrax PDFリンクを取得し、1ページ目を画像化

データソース:
- ページ: https://www.komatsu.jp/ja/ir/library/demand-orders
- PDF: 動的に取得（URLが変わる可能性があるため）

手順:
1. IRページにアクセスしてKomtrax PDFリンクを取得
2. PDFをダウンロード
3. PyMuPDFで1ページ目を画像化して保存
"""
import io
import re
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from zoneinfo import ZoneInfo

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

from core.redis_client import redis_client
from services.browser.stale_while_revalidate import background_revalidate


JST = ZoneInfo("Asia/Tokyo")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "global" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# スクリーンショットファイル名
SCREENSHOT_FILENAME = "komtrax.png"
SCREENSHOT_PATH = CACHE_DIR / SCREENSHOT_FILENAME

# データソース
IR_PAGE_URL = "https://www.komatsu.jp/ja/ir/library/demand-orders"
BASE_URL = "https://www.komatsu.jp"

# PDFリンクのパターン（komtrax.pdfを含むリンク）
KOMTRAX_PDF_PATTERN = re.compile(r'href="([^"]*komtrax\.pdf[^"]*)"', re.IGNORECASE)

# リクエストヘッダー
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}


class KomtraxScreenshotService:
    """Komtrax PDF Screenshot Service"""

    CACHE_KEY = "global:komtrax_screenshot:metadata"

    def __init__(self):
        pass

    def _find_pdf_url(self) -> Optional[str]:
        """IRページからKomtrax PDFのURLを取得"""
        try:
            response = requests.get(IR_PAGE_URL, headers=HEADERS, timeout=30)
            response.raise_for_status()

            match = KOMTRAX_PDF_PATTERN.search(response.text)
            if match:
                pdf_path = match.group(1)
                if pdf_path.startswith("http"):
                    pdf_url = pdf_path
                else:
                    pdf_url = BASE_URL + pdf_path
                print(f"[Komtrax] Found PDF URL: {pdf_url}")
                return pdf_url

            print("[Komtrax] PDF link not found on IR page")
            return None

        except Exception as e:
            print(f"[Komtrax] Error fetching IR page: {e}")
            return None

    def _download_and_render_pdf(self, pdf_url: str, output_path: Path) -> bool:
        """PDFをダウンロードして1ページ目を画像化"""
        if not HAS_PYMUPDF:
            print("[Komtrax] PyMuPDF (fitz) is not installed")
            return False

        try:
            # PDFダウンロード
            print(f"[Komtrax] Downloading PDF: {pdf_url}")
            response = requests.get(pdf_url, headers=HEADERS, timeout=60)
            response.raise_for_status()

            # PDFを開く
            pdf_content = io.BytesIO(response.content)
            doc = fitz.open(stream=pdf_content, filetype="pdf")

            if doc.page_count == 0:
                print("[Komtrax] PDF has no pages")
                doc.close()
                return False

            # 1ページ目を画像化（高解像度）
            page = doc[0]
            mat = fitz.Matrix(2.5, 2.5)  # 2.5倍の解像度
            pix = page.get_pixmap(matrix=mat)

            # PNGとして保存
            pix.save(str(output_path))
            doc.close()

            print(f"[Komtrax] Screenshot saved to {output_path} ({pix.width}x{pix.height})")
            return True

        except Exception as e:
            print(f"[Komtrax] Error rendering PDF: {e}")
            return False

    def capture_screenshot(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Komtrax PDFの1ページ目をキャプチャ"""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        now = datetime.now(JST)

        # キャッシュチェック（24時間）
        if not force_refresh and SCREENSHOT_PATH.exists():
            file_age = now.timestamp() - SCREENSHOT_PATH.stat().st_mtime
            if file_age < 86400:
                print(f"[Komtrax] Using cached screenshot (age: {file_age/3600:.1f} hours)")
                return {
                    "success": True,
                    "url": f"/cache/global/economy/{SCREENSHOT_FILENAME}",
                    "cached": True,
                    "last_updated": self._get_last_updated(),
                }
            # SWR: stale cache exists → return it immediately, update in background
            background_revalidate(
                f"swr:{self.CACHE_KEY}",
                lambda: self.capture_screenshot(force_refresh=True),
            )
            return {
                "success": True,
                "url": f"/cache/global/economy/{SCREENSHOT_FILENAME}",
                "cached": True,
                "last_updated": self._get_last_updated(),
                "revalidating": True,
            }

        # PDFリンクを取得
        pdf_url = self._find_pdf_url()
        if not pdf_url:
            return {
                "success": False,
                "url": None,
                "cached": False,
                "last_updated": None,
                "error": "Could not find Komtrax PDF URL",
            }

        # PDFをダウンロードして画像化
        print("[Komtrax] Capturing Komtrax PDF page 1...")
        success = self._download_and_render_pdf(pdf_url, SCREENSHOT_PATH)

        result = {
            "success": success,
            "url": f"/cache/global/economy/{SCREENSHOT_FILENAME}" if success else None,
            "cached": False,
            "last_updated": now.isoformat(),
        }

        # メタデータをRedisに保存
        redis_client.set(
            self.CACHE_KEY,
            {
                "last_updated": now.isoformat(),
                "screenshot_exists": SCREENSHOT_PATH.exists(),
                "pdf_url": pdf_url,
            },
            expire=0,
        )

        return result

    def get_screenshot_url(self) -> Dict[str, Any]:
        """Get URL for cached screenshot"""
        result = {
            "screenshot_url": None,
            "last_updated": None,
        }

        if SCREENSHOT_PATH.exists():
            result["screenshot_url"] = f"/cache/global/economy/{SCREENSHOT_FILENAME}"

        result["last_updated"] = self._get_last_updated()

        return result

    def _get_last_updated(self) -> str | None:
        """Get last updated timestamp"""
        cached_meta = redis_client.get(self.CACHE_KEY)
        if cached_meta:
            return cached_meta.get("last_updated")

        if SCREENSHOT_PATH.exists():
            mtime = datetime.fromtimestamp(SCREENSHOT_PATH.stat().st_mtime, tz=JST)
            return mtime.isoformat()

        return None

    def get_cache_status(self) -> Dict[str, Any]:
        """Get cache status"""
        cached_meta = redis_client.get(self.CACHE_KEY)
        return {
            "indicator": "Komtrax Screenshot",
            "source": "Komatsu IR",
            "cache_key": self.CACHE_KEY,
            "screenshot_exists": SCREENSHOT_PATH.exists(),
            "last_updated": self._get_last_updated(),
            "pdf_url": cached_meta.get("pdf_url") if cached_meta else None,
        }

    def invalidate_cache(self) -> bool:
        """Invalidate screenshot cache"""
        redis_client.delete(self.CACHE_KEY)
        return True


# シングルトンインスタンス
komtrax_screenshot_service = KomtraxScreenshotService()
