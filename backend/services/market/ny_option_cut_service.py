"""
NYオプションカット（FXオプション期日）サービス

データ項目:
- expiry_data: 通貨ペア別のストライク価格と想定元本
- article_body: 市場分析テキスト
- table_image_url: オプション期日テーブル画像（PlaywrightRunner経由でスクショ取得）

データソース:
- investinglive.com: https://investinglive.com/Orders

更新スケジュール: 毎営業日 JST 15:30, 16:00, 16:30, 17:00 にチェック

[移行ノート]
このサービスは backend.services.browser.PlaywrightRunner 経由に統一済み
(ARM64 / OCI 対応)。以前の Selenium / webdriver_manager / chromium-driver
依存はすべて削除。記事内の「テーブル画像」要素を特定する旧 Selenium ロジック
を `pre_screenshot_js` でブラウザ内に再現し、対象 <img> に
data-ny-option-cut-target="1" 属性を付与した上で
`clip_selector` で要素クリップする。
"""
import calendar
import json
import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from core.redis_client import redis_client
from services.browser import (
    BrowserConfig,
    BrowserRunnerError,
    ScreenshotRequest,
    take_screenshot_with_retry,
)

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")

# キャッシュ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "ny_option_cut_cache.json"

# Redis
REDIS_KEY = "market:ny_option_cut:data"
REDIS_TTL = 86400  # 24h

# HTTP
BASE_URL = "https://investinglive.com/Orders"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# スクリーンショット保存先
SCREENSHOT_FILENAME = "ny_option_cut_table.png"
SCREENSHOT_PATH = CACHE_DIR / SCREENSHOT_FILENAME

# オプションデータ正規表現
PAIR_PATTERN = re.compile(r"([A-Z]{3}/[A-Z]{3})")
STRIKE_PATTERN = re.compile(
    r"([\d]+\.?\d*)\s*\(([A-Za-z€£¥$]+\$?)\s*([\d,.]+)\s*(bn|mn|million|billion)\)",
    re.IGNORECASE,
)


class NyOptionCutService:
    """investinglive.com からFXオプション期日データを取得"""

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """データ取得（キャッシュ優先）"""
        if not force_refresh:
            cached = self._load_from_redis()
            if cached and self._is_today(cached):
                cached["cached"] = True
                cached["source"] = "redis"
                return cached

        # 取得試行
        try:
            data = self._fetch_today()
            if data and data.get("status") == "published":
                self._save_to_redis(data)
                self._save_to_file(data)
                return data
        except Exception as e:
            logger.error(f"[NYOptionCut] Fetch error: {e}")

        # フォールバック
        cached = self._load_from_redis() or self._load_from_file()
        if cached:
            cached["cached"] = True
            cached["source"] = "fallback"
            return cached

        return {
            "data": None,
            "status": "not_published",
            "cached": False,
            "source": "none",
            "last_updated": None,
        }

    def _is_today(self, cached: Dict) -> bool:
        """キャッシュが今日のデータか判定"""
        today_str = datetime.now(JST).strftime("%Y-%m-%d")
        data = cached.get("data")
        if not data:
            return False
        return data.get("date") == today_str

    def _build_article_url(self, target_date: date) -> str:
        """日付からarticle URLを構築"""
        day = target_date.day
        month = calendar.month_name[target_date.month].lower()
        date_str = target_date.strftime("%Y%m%d")
        return (
            f"{BASE_URL}/fx-option-expiries-for-"
            f"{day}-{month}-10am-new-york-cut-{date_str}/"
        )

    def _fetch_today(self) -> Dict[str, Any]:
        """今日の記事を取得"""
        today = datetime.now(JST).date()
        now_str = datetime.now(JST).isoformat()

        # 週末チェック
        if today.weekday() >= 5:
            return {
                "data": None,
                "status": "weekend",
                "cached": False,
                "source": "none",
                "last_updated": now_str,
            }

        url = self._build_article_url(today)
        logger.info(f"[NYOptionCut] Fetching: {url}")

        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
        except requests.RequestException as e:
            logger.error(f"[NYOptionCut] Request failed: {e}")
            return {
                "data": None,
                "status": "not_published",
                "cached": False,
                "source": "none",
                "last_updated": now_str,
            }

        if resp.status_code == 404:
            logger.info(f"[NYOptionCut] Article not yet published for {today}")
            return {
                "data": None,
                "status": "not_published",
                "cached": False,
                "source": "none",
                "last_updated": now_str,
            }

        resp.raise_for_status()

        parsed = self._parse_html(resp.text)
        if not parsed:
            return {
                "data": None,
                "status": "not_published",
                "cached": False,
                "source": "none",
                "last_updated": now_str,
            }

        expiry_data = self._parse_expiry_data(parsed["article_body"])

        # テーブル画像をSeleniumで取得
        table_image_url = None
        try:
            table_image_url = self._capture_table_screenshot(url)
        except Exception as e:
            logger.warning(f"[NYOptionCut] Screenshot capture failed: {e}")

        return {
            "data": {
                "date": today.isoformat(),
                "headline": parsed["headline"],
                "article_body": parsed["article_body"],
                "image_url": parsed["image_url"],
                "table_image_url": table_image_url,
                "date_published": parsed["date_published"],
                "author": parsed["author"],
                "expiry_data": expiry_data,
                "source_url": url,
            },
            "status": "published",
            "cached": False,
            "source": "api",
            "last_updated": now_str,
        }

    def _parse_html(self, html: str) -> Optional[Dict[str, str]]:
        """HTMLからJSON-LDとメタデータを抽出"""
        soup = BeautifulSoup(html, "html.parser")

        # JSON-LD抽出
        ld_scripts = soup.find_all("script", type="application/ld+json")
        article_body = ""
        date_published = ""
        thumbnail_url = ""
        headline = ""
        author = ""

        for script in ld_scripts:
            try:
                ld_data = json.loads(script.string)
                if isinstance(ld_data, list):
                    for item in ld_data:
                        if item.get("@type") == "NewsArticle":
                            ld_data = item
                            break
                    else:
                        continue
                if ld_data.get("@type") == "NewsArticle":
                    article_body = ld_data.get("articleBody", "")
                    date_published = ld_data.get("datePublished", "")
                    thumbnail_url = ld_data.get("thumbnailUrl", "")
                    headline = ld_data.get("headline", "")
                    author_data = ld_data.get("author", {})
                    if isinstance(author_data, dict):
                        author = author_data.get("name", "")
                    elif isinstance(author_data, list) and author_data:
                        author = author_data[0].get("name", "")
                    break
            except (json.JSONDecodeError, AttributeError):
                continue

        # og:imageフォールバック
        if not thumbnail_url:
            og_image = soup.find("meta", property="og:image")
            if og_image:
                thumbnail_url = og_image.get("content", "")

        if not article_body and not headline:
            return None

        return {
            "article_body": article_body,
            "image_url": thumbnail_url,
            "date_published": date_published,
            "headline": headline,
            "author": author,
        }

    def _parse_expiry_data(self, article_body: str) -> List[Dict[str, Any]]:
        """articleBodyから通貨ペア/ストライク/想定元本を抽出"""
        if not article_body:
            return []

        result = []
        current_pair = None

        # テキストをセグメント分割（通貨ペア名で分割）
        segments = PAIR_PATTERN.split(article_body)

        for i, segment in enumerate(segments):
            pair_match = PAIR_PATTERN.fullmatch(segment)
            if pair_match:
                current_pair = pair_match.group(1)
                continue

            if current_pair:
                strikes = STRIKE_PATTERN.findall(segment)
                for strike_str, currency, amount_str, unit in strikes:
                    try:
                        strike = float(strike_str)
                        amount = float(amount_str.replace(",", ""))
                        unit_lower = unit.lower()
                        amount_mn = amount
                        if unit_lower in ("bn", "billion"):
                            amount_mn = amount * 1000

                        currency_clean = currency.strip()
                        display_unit = "bn" if unit_lower in ("bn", "billion") else "mn"
                        result.append({
                            "pair": current_pair,
                            "strike": strike,
                            "amount_mn": round(amount_mn, 2),
                            "amount_str": f"{currency_clean} {amount_str} {display_unit}",
                        })
                    except (ValueError, IndexError):
                        continue

        if result:
            logger.info(
                f"[NYOptionCut] Parsed {len(result)} expiry entries "
                f"across {len(set(r['pair'] for r in result))} pairs"
            )
        return result

    # ──── スクリーンショット ────

    # 旧 Selenium ロジック (テーブル画像 = 記事内の十分なサイズの最初の <img>
    # でヘッダー/ロゴ/広告を除外したもの) をブラウザ内 JS で再現する。
    # 対象要素には ``data-ny-option-cut-target="1"`` 属性を付与し、
    # ScreenshotRequest.clip_selector でそれをクリップする。
    _PRE_SCREENSHOT_JS = r"""
    (() => {
      const sel = "article figure img, article img, .article-body img, .html-content__general-styles img";
      const figSel = "article figure, .article-body figure, .html-content__general-styles figure";

      // 既存タグを掃除
      document.querySelectorAll('[data-ny-option-cut-target]')
        .forEach(el => el.removeAttribute('data-ny-option-cut-target'));

      const isExcluded = (src) => {
        if (!src) return true;
        if (src.indexOf('FXO%20FX%20OPTION%20EXPIRIES') !== -1) return true;
        if (src.indexOf('il-logo') !== -1) return true;
        if (src.indexOf('advertisement') !== -1) return true;
        return false;
      };

      // <img> 走査
      const imgs = Array.from(document.querySelectorAll(sel));
      for (const img of imgs) {
        const src = img.getAttribute('src') || img.currentSrc || '';
        if (isExcluded(src)) continue;
        const r = img.getBoundingClientRect();
        if (r.width > 200 && r.height > 100) {
          img.setAttribute('data-ny-option-cut-target', '1');
          img.scrollIntoView({block: 'center'});
          return true;
        }
      }

      // フォールバック: <figure> 走査
      const figs = Array.from(document.querySelectorAll(figSel));
      for (const fig of figs) {
        const r = fig.getBoundingClientRect();
        if (r.width > 200 && r.height > 100) {
          fig.setAttribute('data-ny-option-cut-target', '1');
          fig.scrollIntoView({block: 'center'});
          return true;
        }
      }
      return false;
    })();
    """

    def _capture_table_screenshot(self, article_url: str) -> Optional[str]:
        """記事ページにアクセスしテーブル画像のスクショを取得 (PlaywrightRunner 経由).

        旧 Selenium 実装と同等:
            - viewport 1920x1400
            - 記事内 <img>/<figure> を走査
            - ヘッダーバナー/ロゴ/広告を除外
            - 200x100 px 以上の最初の要素を対象
            - scrollIntoView してから要素クリップでスクショ
        """
        target_selector = "[data-ny-option-cut-target='1']"
        request = ScreenshotRequest(
            url=article_url,
            output_path=str(SCREENSHOT_PATH),
            wait_selector="article figure img, article img, .article-body img",
            wait_for_load_state="networkidle",
            wait_after_load_ms=8_000,
            pre_screenshot_js=self._PRE_SCREENSHOT_JS,
            wait_after_pre_js_ms=1_000,
            clip_selector=target_selector,
            scroll_into_view=True,
            viewport_override=(1920, 1400),
        )
        config = BrowserConfig(
            viewport=(1920, 1400),
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        try:
            result = take_screenshot_with_retry(
                request,
                config=config,
                max_attempts=2,
                initial_backoff_seconds=5.0,
            )
            logger.info(
                f"[NYOptionCut] Table screenshot saved: {result.path} "
                f"({result.size_bytes} bytes)"
            )
            return f"/cache/market/{SCREENSHOT_FILENAME}"
        except BrowserRunnerError as e:
            logger.error(f"[NYOptionCut] Screenshot capture failed: {e}")
            return None

    # ──── キャッシュ ────

    def _load_from_redis(self) -> Optional[Dict]:
        try:
            data = redis_client.get(REDIS_KEY)
            return data if data else None
        except Exception:
            return None

    def _save_to_redis(self, data: Dict) -> None:
        try:
            redis_client.set(REDIS_KEY, data, ex=REDIS_TTL)
        except Exception as e:
            logger.warning(f"[NYOptionCut] Redis save failed: {e}")

    def _load_from_file(self) -> Optional[Dict]:
        try:
            if CACHE_FILE.exists():
                return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
        return None

    def _save_to_file(self, data: Dict) -> None:
        try:
            CACHE_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"[NYOptionCut] File cache save failed: {e}")


ny_option_cut_service = NyOptionCutService()
