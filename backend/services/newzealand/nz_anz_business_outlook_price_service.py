"""
NZ ANZ企業景況感物価関連 サービス（PDF Page 2 スクリーンショット方式）
ANZ Business Outlook - Price Related Charts (PDF Page 2 Screenshot)

PDFのPage 2を画像として取得し表示する。
PDFは発表日からURL構築して自動ダウンロード。

データソース:
- ANZ Business Outlook PDF
- https://www.anz.co.nz/about-us/economic-markets-research/business-outlook/

PDF URLパターン:
- https://www.anz.co.nz/content/dam/anzconz/documents/economics-and-market-research/{yyyy}/ANZ-BusinessOutlook-{yyyymmdd}.pdf

FMPマッピング:
- ANZ Business Confidence (econalpha_id: nz_anz_corporate business_sentiment)

発表スケジュール: 毎月
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.newzealand.fmp_next_release_utils import get_next_release_by_pattern

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# キャッシュディレクトリ（画像保存先）
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "newzealand" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# FMPパターン
FMP_EVENT_PATTERN = "ANZ Business Confidence"
FMP_COUNTRY = "NZ"

# スクリーンショット設定
SCREENSHOT_FILE = "anz_business_outlook_page2.png"
SCREENSHOT_PATH = CACHE_DIR / SCREENSHOT_FILE

# PDF URLテンプレート
PDF_URL_TEMPLATE = (
    "https://www.anz.co.nz/content/dam/anzconz/documents/"
    "economics-and-market-research/{yyyy}/ANZ-BusinessOutlook-{yyyymmdd}.pdf"
)

_scraper = None


def _get_scraper():
    """cloudscraper インスタンスを遅延初期化"""
    global _scraper
    if _scraper is None:
        import cloudscraper
        _scraper = cloudscraper.create_scraper()
    return _scraper


class NzAnzBusinessOutlookPriceService:
    """NZ ANZ企業景況感物価関連サービス（PDF Page 2 スクリーンショット）"""

    CACHE_KEY = "newzealand:anz_business_outlook_price:metadata"

    def __init__(self):
        pass

    def _get_past_release_dates(self) -> List[str]:
        """DBから直近の発表日リスト（yyyymmdd形式）を取得"""
        try:
            from core.database import get_db_connection

            dates = []
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT datetime_utc FROM economic_calendar_events "
                    "WHERE country = 'NZ' AND event ILIKE '%%ANZ Business Confidence%%' "
                    "AND actual IS NOT NULL "
                    "ORDER BY datetime_utc DESC LIMIT 5"
                )
                rows = cur.fetchall()
                for r in rows:
                    dates.append(r[0].strftime("%Y%m%d"))
                cur.close()
            return dates
        except Exception as e:
            print(f"[AnzBizPrice] Error getting past release dates: {e}")
            return []

    def _build_pdf_url(self, yyyymmdd: str) -> str:
        """発表日からPDF URLを構築"""
        yyyy = yyyymmdd[:4]
        return PDF_URL_TEMPLATE.format(yyyy=yyyy, yyyymmdd=yyyymmdd)

    def _download_and_extract(self) -> bool:
        """最新PDFをダウンロードしPage 2を画像化"""
        try:
            import pdfplumber
            import io

            # 直近の発表日からURL候補を生成
            dates = self._get_past_release_dates()
            if not dates:
                print("[AnzBizPrice] No past release dates found")
                return False

            scraper = _get_scraper()
            pdf_content = None
            used_date = None

            for yyyymmdd in dates:
                url = self._build_pdf_url(yyyymmdd)
                print(f"[AnzBizPrice] Trying: {url}")
                try:
                    resp = scraper.get(url, timeout=60)
                    if resp.status_code == 200 and len(resp.content) > 50000:
                        content_type = resp.headers.get("Content-Type", "")
                        if "pdf" in content_type or len(resp.content) > 100000:
                            pdf_content = resp.content
                            used_date = yyyymmdd
                            print(f"[AnzBizPrice] Downloaded: {len(resp.content)} bytes ({yyyymmdd})")
                            break
                    print(f"[AnzBizPrice] Failed: HTTP {resp.status_code}, {len(resp.content)} bytes")
                except Exception as e:
                    print(f"[AnzBizPrice] Download error for {yyyymmdd}: {e}")
                    continue

            if not pdf_content:
                print("[AnzBizPrice] Could not download any PDF")
                return False

            # Page 2 を画像化
            with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                if len(pdf.pages) < 2:
                    print(f"[AnzBizPrice] PDF has only {len(pdf.pages)} pages")
                    return False

                page = pdf.pages[1]  # Page 2 (0-indexed)
                page_image = page.to_image(resolution=200)
                pil_image = page_image.original

                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                pil_image.save(str(SCREENSHOT_PATH))
                print(f"[AnzBizPrice] Page 2 saved: {SCREENSHOT_PATH} ({pil_image.size})")

            # メタデータをRedisに保存
            now = datetime.now(JST)
            redis_client.set(self.CACHE_KEY, {
                "last_updated": now.isoformat(),
                "pdf_date": used_date,
                "page2_exists": SCREENSHOT_PATH.exists(),
            }, expire=0)

            return True

        except ImportError as e:
            print(f"[AnzBizPrice] Missing dependency: {e}")
            return False
        except Exception as e:
            print(f"[AnzBizPrice] Error extracting page 2: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _should_refresh(self) -> bool:
        """キャッシュを更新すべきか判定"""
        cached_meta = redis_client.get(self.CACHE_KEY)
        if not cached_meta:
            return True

        last_updated_str = cached_meta.get("last_updated")
        if not last_updated_str:
            return True

        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)
            # 1日以上経過していたら更新
            return (now - last_updated).total_seconds() > 86400
        except Exception:
            return True

    def get_screenshot_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """スクリーンショットデータを取得"""
        if force_refresh or self._should_refresh():
            self._download_and_extract()

        # 画像がなければ初回取得を試みる
        if not SCREENSHOT_PATH.exists():
            self._download_and_extract()

        cached_meta = redis_client.get(self.CACHE_KEY)
        next_release = self._get_next_release()

        return {
            "page2_exists": SCREENSHOT_PATH.exists(),
            "last_updated": cached_meta.get("last_updated") if cached_meta else None,
            "pdf_date": cached_meta.get("pdf_date") if cached_meta else None,
            "next_release": next_release,
        }

    def get_screenshot_path(self) -> Optional[Path]:
        """Page 2 スクリーンショットパスを取得"""
        return SCREENSHOT_PATH if SCREENSHOT_PATH.exists() else None

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得"""
        try:
            return get_next_release_by_pattern(FMP_EVENT_PATTERN, country=FMP_COUNTRY)
        except Exception as e:
            print(f"[AnzBizPrice] Error getting next release: {e}")
            return None

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        redis_client.delete(self.CACHE_KEY)
        return True

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        cached_meta = redis_client.get(self.CACHE_KEY)
        return {
            "indicator": "NZ ANZ Business Outlook Price Related",
            "source": "ANZ",
            "cache_key": self.CACHE_KEY,
            "last_updated": cached_meta.get("last_updated") if cached_meta else None,
            "pdf_date": cached_meta.get("pdf_date") if cached_meta else None,
            "page2_exists": SCREENSHOT_PATH.exists(),
            "next_release": self._get_next_release(),
        }


# シングルトンインスタンス
nz_anz_business_outlook_price_service = NzAnzBusinessOutlookPriceService()
