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
- 記事スクレイピング: ExtractRequest + html_selectors=("blockquote",) で
  outerHTML を取得 → BeautifulSoup で blockquote テキストを抽出

[2026-06-21 修正]
- URL 存在の事前チェック (旧 requests.head) は廃止。BRC が requests に
  HTTP 403 (ボット対策) を返し常に失敗していたため。候補月 (期待月→前月) を
  実ブラウザで直接スクレイプし、成功した月を採用する。
- get_brc_commentary に鮮度判定 (data_month vs 期待月) + スロットル + 劣化ガードを
  追加し、無条件キャッシュ返しによる凍結を解消。
- FMP発表スケジューラの BRC 小売売上高 release に related_services で相乗り更新。
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# キャッシュが「あるべき最新月」より古いとき、再スクレイプを試みる最小間隔（時間）。
# BRC が未公開・スクレイプ失敗のときに毎リクエストでブラウザを起動しないためのスロットル。
_STALE_RETRY_HOURS = 12

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


def _now_iso() -> str:
    return datetime.now().isoformat()


def _candidate_periods() -> List[Tuple[int, int]]:
    """
    スクレイプを試す (year, month) 候補を「期待される最新月 → 前月」の順で返す。

    旧実装は requests.head でURL存在を事前確認していたが、BRC が requests に
    HTTP 403（ボット対策）を返すため常に失敗していた。Playwright 実ブラウザは
    403 を回避できるので、事前 HEAD を廃止し、候補URLを実ブラウザで直接
    スクレイプして成功したものを採用する（_scrape_report_commentary 側で判定）。
    """
    data_year, data_month = _get_expected_data_period()
    if data_month == 1:
        prev_year, prev_month = data_year - 1, 12
    else:
        prev_year, prev_month = data_year, data_month - 1
    return [(data_year, data_month), (prev_year, prev_month)]


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
            "last_updated": _now_iso(),
            "error": "Required dependencies not available (beautifulsoup4, deep-translator, playwright)"
        }

    # 期待される最新月 → 前月の順に、実ブラウザで直接スクレイプを試す。
    # 最初に blockquote を取得できた月を採用する（事前のURL存在確認は廃止）。
    last_error: Optional[str] = None
    for data_year, data_month in _candidate_periods():
        url = _build_report_url(data_year, data_month)
        month_name = MONTH_NAMES_FULL.get(data_month, "unknown")
        logger.info("Fetching BRC commentary: %s %d at %s", month_name, data_year, url)

        try:
            english_texts = _scrape_report_commentary(url)
        except Exception as exc:
            english_texts = None
            last_error = str(exc)
            logger.warning("Scrape attempt failed for %s: %s", url, exc)

        if not english_texts:
            continue

        # Known speaker names for report page blockquotes
        speaker_names = ["Helen Dickinson (BRC)", "Linda Ellett (KPMG)"]

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
            "last_updated": _now_iso(),
            "source": "report_page"
        }

    return {
        "commentaries": None,
        "data_year": None,
        "data_month": None,
        "url": None,
        "last_updated": _now_iso(),
        "error": last_error or "Failed to scrape commentary from BRC report pages"
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


def _period_key(year: Optional[int], month: Optional[int]) -> Optional[int]:
    """(year, month) を比較可能な単一の整数に変換"""
    if not year or not month:
        return None
    return year * 12 + (month - 1)


def _cache_is_current(cached: Optional[Dict[str, Any]]) -> bool:
    """キャッシュが「あるべき最新月」に追いついているか"""
    if not cached or not cached.get("commentaries"):
        return False
    ck = _period_key(cached.get("data_year"), cached.get("data_month"))
    if ck is None:
        return False
    ey, em = _get_expected_data_period()
    return ck >= _period_key(ey, em)


def _retry_due(cached: Optional[Dict[str, Any]], hours: int = _STALE_RETRY_HOURS) -> bool:
    """前回の取得/試行から十分時間が経過し、再スクレイプして良いか"""
    if not cached:
        return True
    ts = cached.get("last_attempt") or cached.get("last_updated")
    if not ts:
        return True
    try:
        last = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return True
    return (datetime.now() - last).total_seconds() >= hours * 3600


def _deps_error() -> Dict[str, Any]:
    return {
        "commentaries": None,
        "data_year": None,
        "data_month": None,
        "url": None,
        "last_updated": _now_iso(),
        "error": "Required dependencies not available (beautifulsoup4, deep-translator, playwright)"
    }


def get_brc_commentary() -> Dict[str, Any]:
    """
    Get BRC commentary（鮮度判定つき）。

    - キャッシュが「あるべき最新月」に追いついていればそのまま返す（無駄なスクレイプをしない）。
    - 古い／無い場合のみ再スクレイプ。ただし _STALE_RETRY_HOURS のスロットルで
      未公開・失敗時の連続ブラウザ起動を防ぐ。
    - スクレイプが空（失敗）なら既存の良いキャッシュは上書きしない（劣化ガード）。
    """
    cached = _load_cache()

    # 追いついていれば即返し
    if _cache_is_current(cached):
        return cached

    if not _check_dependencies():
        # 依存が無ければ、既存キャッシュがあればそれを返す
        return cached if (cached and cached.get("commentaries")) else _deps_error()

    # 古い／無い。スロットル中なら既存キャッシュを返す
    if cached and cached.get("commentaries") and not _retry_due(cached):
        return cached

    try:
        logger.info("BRC commentary stale/missing — scraping fresh commentary...")
        data = scrape_brc_commentary()
    except Exception as exc:
        logger.error("Failed to get BRC commentary: %s", exc)
        data = None

    if data and data.get("commentaries"):
        _save_cache(data)
        return data

    # 失敗 → 劣化ガード: 既存の良いキャッシュは保持し、試行時刻だけ更新してスロットル
    if cached and cached.get("commentaries"):
        cached["last_attempt"] = _now_iso()
        _save_cache(cached)
        return cached

    # 既存キャッシュも無い → エラーペイロードを保存して返す
    fallback = data or _deps_error()
    _save_cache(fallback)
    return fallback


def refresh_brc_commentary(force_refresh: bool = True) -> Dict[str, Any]:
    """
    Force refresh BRC commentary (bypass cache)。

    スクレイプが空（失敗）の場合は既存の良いキャッシュを破壊しない（劣化ガード）。
    """
    if not _check_dependencies():
        cached = _load_cache()
        return cached if (cached and cached.get("commentaries")) else _deps_error()

    try:
        logger.info("Force refreshing BRC commentary...")
        data = scrape_brc_commentary()
    except Exception as exc:
        logger.error("Failed to refresh BRC commentary: %s", exc)
        data = None

    if data and data.get("commentaries"):
        _save_cache(data)
        return data

    # 劣化ガード: 失敗時は既存キャッシュを保持
    cached = _load_cache()
    if cached and cached.get("commentaries"):
        cached["last_attempt"] = _now_iso()
        _save_cache(cached)
        return cached

    fallback = data or {
        "commentaries": None, "data_year": None, "data_month": None,
        "url": None, "last_updated": _now_iso(),
        "error": "Failed to refresh BRC commentary",
    }
    _save_cache(fallback)
    return fallback


class _BRCCommentaryService:
    """
    FMP発表スケジューラの related_services から呼べるようにする薄いラッパー。
    （スケジューラは `instance.fetch_method(force_refresh=True)` を期待する）
    """

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        if force_refresh:
            return refresh_brc_commentary()
        return get_brc_commentary()

    def invalidate_cache(self) -> bool:
        # refresh_brc_commentary は常に再スクレイプ（force）するためキャッシュ削除は不要。
        # ファイルを消すと劣化ガード（失敗時に旧データ保持）の安全網を失うので no-op。
        return True


brc_commentary_service = _BRCCommentaryService()
