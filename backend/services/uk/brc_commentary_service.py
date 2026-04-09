"""
BRC Retail Sales Monitor Commentary Service

Scrapes the latest commentary from BRC's report page and translates it to Japanese.

The service fetches commentaries from 2 commentators:
- Helen Dickinson (BRC CEO)
- Linda Ellett (KPMG)

Report page URL pattern: https://brc.org.uk/market-intelligence/publications/monitors/retail-sales-monitor/YYYY/mmm/
This URL pattern is predictable and stable.

Note: This service requires optional dependencies (beautifulsoup4, deep-translator, playwright).
If not available, it will return cached data or an error message.

[移行ノート]
このサービスは backend.services.browser.PlaywrightRunner 経由に統一済み
(ARM64 / OCI 対応)。以前の async_playwright 直接利用 + ThreadPoolExecutor
ラッパーはすべて削除。
- URL 存在チェック: 軽量な requests.head() に置き換え (browser 起動不要)
- 記事スクレイピング: ExtractRequest + html_selectors=("blockquote",) で
  outerHTML を取得 → BeautifulSoup で blockquote テキストを抽出
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "consumer"
CACHE_FILE = CACHE_DIR / "brc_commentary_cache.json"

# Report page base URL
BASE_URL = "https://brc.org.uk/market-intelligence/publications/monitors/retail-sales-monitor"

# Month abbreviations for URL construction
MONTH_ABBR = {
    1: "jan", 2: "feb", 3: "mar", 4: "apr",
    5: "may", 6: "jun", 7: "jul", 8: "aug",
    9: "sep", 10: "oct", 11: "nov", 12: "dec"
}

# Month names (full) for display
MONTH_NAMES_FULL = {
    1: "january", 2: "february", 3: "march", 4: "april",
    5: "may", 6: "june", 7: "july", 8: "august",
    9: "september", 10: "october", 11: "november", 12: "december"
}

# 共通 UA (旧実装と同等)
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _build_report_url(data_year: int, data_month: int) -> str:
    """
    Build the BRC report page URL based on the data year and month.

    Report page URL pattern:
    https://brc.org.uk/market-intelligence/publications/monitors/retail-sales-monitor/YYYY/mmm/

    E.g., December 2025 data: /retail-sales-monitor/2025/dec/
    """
    month_abbr = MONTH_ABBR.get(data_month, "jan")
    return f"{BASE_URL}/{data_year}/{month_abbr}/"


def _get_expected_data_period() -> Tuple[int, int]:
    """
    Calculate the expected data period based on current date.

    BRC publishes data around day 3-20 of each month for the previous month.
    E.g., on January 14, 2026, the latest data is for December 2025.
    """
    today = datetime.now()

    # If we're in the first few days, the previous month's data might not be out yet
    if today.day < 3:
        # Go back 2 months
        if today.month <= 2:
            data_year = today.year - 1
            data_month = today.month + 10  # e.g., Jan -> Nov of prev year
        else:
            data_year = today.year
            data_month = today.month - 2
    else:
        # Data is for the previous month
        if today.month == 1:
            data_year = today.year - 1
            data_month = 12
        else:
            data_year = today.year
            data_month = today.month - 1

    return data_year, data_month


def _check_dependencies() -> bool:
    """依存パッケージが利用可能かチェック"""
    try:
        import bs4  # noqa: F401
        import deep_translator  # noqa: F401
        return True
    except ImportError:
        return False


def _check_url_exists(url: str) -> bool:
    """
    Check if a URL is accessible (returns HTTP 200).

    旧実装は Playwright で page.goto してステータスを見ていたが、
    ブラウザ起動コストを避けるため軽量な requests.head に差し替え。
    HEAD が拒否されるケースに備えて 405/403 のときは GET にフォールバック。
    """
    try:
        resp = requests.head(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=15,
            allow_redirects=True,
        )
        if resp.status_code == 200:
            return True
        if resp.status_code in (403, 405):
            # HEAD が許可されていない可能性 → GET で確認
            resp = requests.get(
                url,
                headers={"User-Agent": _USER_AGENT},
                timeout=15,
                allow_redirects=True,
            )
            return resp.status_code == 200
        return False
    except Exception as exc:
        logger.warning("Failed to check URL: %s - %s", url, exc)
        return False


def _find_latest_report_url() -> Optional[Tuple[str, int, int]]:
    """
    Find the latest report URL by trying expected data periods.

    Returns:
        tuple: (url, data_year, data_month) or None if not found
    """
    data_year, data_month = _get_expected_data_period()

    # Try current expected month first
    url = _build_report_url(data_year, data_month)
    logger.info("Trying report URL: %s", url)
    if _check_url_exists(url):
        logger.info("Found report URL: %s", url)
        return (url, data_year, data_month)

    # Try previous month as fallback
    if data_month == 1:
        prev_year = data_year - 1
        prev_month = 12
    else:
        prev_year = data_year
        prev_month = data_month - 1

    url = _build_report_url(prev_year, prev_month)
    logger.info("Trying fallback report URL: %s", url)
    if _check_url_exists(url):
        logger.info("Found fallback report URL: %s", url)
        return (url, prev_year, prev_month)

    logger.warning("Could not find report URL")
    return None


def _scrape_report_commentary(url: str) -> Optional[List[str]]:
    """
    Scrape all blockquote contents from the BRC report page using PlaywrightRunner.

    旧実装は async_playwright で page.content() → BeautifulSoup だったが、
    ExtractRequest.html_selectors=("blockquote",) で outerHTML を取得し、
    BeautifulSoup で同等のテキスト抽出を行う形に置き換え。

    Args:
        url: URL to scrape

    Returns:
        List of blockquote text contents, or None if not found
    """
    from bs4 import BeautifulSoup

    from services.browser import (
        BrowserConfig,
        BrowserRunnerError,
        ExtractRequest,
        extract_page,
    )

    logger.info("Scraping BRC report commentary from %s", url)

    request = ExtractRequest(
        url=url,
        wait_selector="blockquote",
        wait_for_load_state="networkidle",
        wait_after_load_ms=1_000,
        html_selectors=("blockquote",),
        viewport_override=(1400, 900),
    )
    config = BrowserConfig(
        viewport=(1400, 900),
        user_agent=_USER_AGENT,
    )

    try:
        result = extract_page(request, config=config)
    except BrowserRunnerError as exc:
        logger.error("Failed to scrape report commentary: %s", exc, exc_info=True)
        return None
    except Exception as exc:
        logger.error("Failed to scrape report commentary: %s", exc, exc_info=True)
        return None

    blockquote_htmls = result.html.get("blockquote", [])
    if not blockquote_htmls:
        logger.warning("No blockquote found on page")
        return None

    comments: List[str] = []
    for bq_html in blockquote_htmls:
        try:
            soup = BeautifulSoup(bq_html, "html.parser")
            bq = soup.find("blockquote")
            target = bq if bq is not None else soup
            text = target.get_text(strip=True, separator=" ")
            if text and text != "Overview" and len(text) > 20:
                comments.append(text)
        except Exception as exc:
            logger.warning("Failed to parse blockquote html: %s", exc)
            continue

    logger.info("Successfully extracted %d commentaries from report page", len(comments))
    return comments if comments else None


def _translate_to_japanese(text: str) -> str:
    """
    Translate English text to Japanese using Google Translate.

    Args:
        text: English text

    Returns:
        Japanese translation
    """
    from deep_translator import GoogleTranslator

    try:
        translator = GoogleTranslator(source='en', target='ja')

        # Google Translate has a character limit, so split if necessary
        max_length = 5000
        if len(text) <= max_length:
            return translator.translate(text)

        # Split into chunks
        chunks = []
        remaining = text
        while remaining:
            chunk = remaining[:max_length]
            # Try to break at sentence boundary
            last_period = chunk.rfind('. ')
            if last_period > max_length * 0.8:  # Only break if period is in last 20%
                chunk = chunk[:last_period + 1]
                remaining = remaining[last_period + 2:]
            else:
                remaining = remaining[max_length:]

            chunks.append(translator.translate(chunk))

        return ' '.join(chunks)

    except Exception as exc:
        logger.error("Translation failed: %s", exc)
        return text  # Return original if translation fails


def scrape_brc_commentary() -> Dict[str, Any]:
    """
    Scrape and translate the latest BRC commentary from report page.

    Report page URL pattern: /retail-sales-monitor/YYYY/mmm/
    This pattern is predictable and stable.

    Returns:
        Dictionary with commentary data including multiple commentaries
    """
    if not _check_dependencies():
        return {
            "commentaries": None,
            "data_year": None,
            "data_month": None,
            "url": None,
            "last_updated": datetime.now().isoformat(),
            "error": "Required dependencies not available (beautifulsoup4, deep-translator, playwright)"
        }

    # Find latest report URL
    logger.info("Finding latest report URL...")
    report_info = _find_latest_report_url()

    if not report_info:
        return {
            "commentaries": None,
            "data_year": None,
            "data_month": None,
            "url": None,
            "last_updated": datetime.now().isoformat(),
            "error": "Failed to find latest report URL"
        }

    url, data_year, data_month = report_info
    month_name = MONTH_NAMES_FULL.get(data_month, "unknown")

    logger.info("Fetching BRC commentary from report page: %s %d at %s", month_name, data_year, url)

    # Scrape all commentaries from report page
    english_texts = _scrape_report_commentary(url)

    if not english_texts:
        return {
            "commentaries": None,
            "data_year": data_year,
            "data_month": data_month,
            "url": url,
            "last_updated": datetime.now().isoformat(),
            "error": "Failed to scrape commentary from report page"
        }

    # Known speaker names for report page blockquotes
    speaker_names = ["Helen Dickinson (BRC)", "Linda Ellett (KPMG)"]

    # Translate each commentary
    commentaries = []
    for i, en_text in enumerate(english_texts):
        speaker = speaker_names[i] if i < len(speaker_names) else f"Commentator {i + 1}"
        ja_text = _translate_to_japanese(en_text)
        commentaries.append({
            "en": en_text,
            "ja": ja_text,
            "speaker": speaker
        })

    return {
        "commentaries": commentaries,
        "data_year": data_year,
        "data_month": data_month,
        "url": url,
        "last_updated": datetime.now().isoformat(),
        "source": "report_page"
    }


def _load_cache() -> Optional[Dict[str, Any]]:
    """Load commentary from cache file"""
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, encoding="utf-8") as f:
                return json.load(f)
    except Exception as exc:
        logger.warning("Failed to load cache: %s", exc)
    return None


def _save_cache(data: Dict[str, Any]) -> None:
    """Save commentary to cache file"""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("Commentary cached successfully")
    except Exception as exc:
        logger.warning("Failed to save cache: %s", exc)


def get_brc_commentary() -> Dict[str, Any]:
    """Get BRC commentary with caching"""
    # まずキャッシュを確認
    cached_data = _load_cache()
    if cached_data:
        return cached_data

    # 依存パッケージがない場合はエラーを返す
    if not _check_dependencies():
        return {
            "commentaries": None,
            "data_year": None,
            "data_month": None,
            "url": None,
            "last_updated": datetime.now().isoformat(),
            "error": "Required dependencies not available (beautifulsoup4, deep-translator, playwright)"
        }

    try:
        logger.info("Cache miss, scraping fresh commentary...")
        data = scrape_brc_commentary()
        _save_cache(data)
        return data
    except Exception as exc:
        logger.error("Failed to get BRC commentary: %s", exc)
        return {
            "commentaries": None,
            "data_year": None,
            "data_month": None,
            "url": None,
            "last_updated": datetime.now().isoformat(),
            "error": str(exc)
        }


def refresh_brc_commentary() -> Dict[str, Any]:
    """Force refresh BRC commentary (bypass cache)"""
    if not _check_dependencies():
        return {
            "commentaries": None,
            "data_year": None,
            "data_month": None,
            "url": None,
            "last_updated": datetime.now().isoformat(),
            "error": "Required dependencies not available (beautifulsoup4, deep-translator, playwright)"
        }

    try:
        logger.info("Force refreshing BRC commentary...")
        data = scrape_brc_commentary()
        _save_cache(data)
        return data
    except Exception as exc:
        logger.error("Failed to refresh BRC commentary: %s", exc)
        return {
            "commentaries": None,
            "data_year": None,
            "data_month": None,
            "url": None,
            "last_updated": datetime.now().isoformat(),
            "error": str(exc)
        }
