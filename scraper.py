"""
韓国半導体輸出データ スクレイパー v2
=============================================
MOTIE（産業通商資源部）の2種のレポートから韓国半導体輸出データを取得する。

1. 수출입 동향（輸出入動向）    → 毎月1日公開、半導体ヘッドライン値
2. ICT 수출입 동향（ICT輸出入動向）→ 毎月12〜15日公開、品目別詳細テーブル

v2: diagnose_motie.py の結果をもとに実サイト構造に対応
  - motie.go.kr → motir.go.kr リダイレクト対応
  - MOTIE 検索ページ経由の記事発見（一覧ページのセレクタ不安定のため）
  - 本文セレクタ: article
  - インライン推移データ: ('25.11월)172.7(38.6↑) → ... 形式に対応
  - 英語版は接続不安定のため韓国語のみ
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from typing import Optional

from playwright.async_api import async_playwright, Page, Browser

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# motir.go.kr が実際のドメイン（motie.go.kr はリダイレクトするが不安定）
MOTIE_BASE = "https://www.motir.go.kr"

# タイムアウト設定（ミリ秒）
PAGE_TIMEOUT = 30_000
NAV_TIMEOUT = 30_000


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class SemiconductorExportRecord:
    """半導体輸出の1ヶ月分レコード"""
    ref_month: str                    # "2025-03" 形式
    value_usd_billion: float          # 10億ドル単位
    yoy_pct: Optional[float] = None   # 前年同月比 %
    source_report: str = ""           # "TRADE" or "ICT"
    published_at: Optional[str] = None
    source_url: str = ""
    raw_text: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScrapeResult:
    """スクレイピング結果"""
    records: list[SemiconductorExportRecord] = field(default_factory=list)
    report_title: str = ""
    report_url: str = ""
    report_date: str = ""
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Browser Helpers
# ---------------------------------------------------------------------------

async def create_browser() -> tuple:
    """Playwright ブラウザを起動"""
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-setuid-sandbox"],
    )
    context = await browser.new_context(
        locale="ko-KR",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    page = await context.new_page()
    page.set_default_timeout(PAGE_TIMEOUT)
    return pw, browser, page


async def close_browser(pw, browser):
    """ブラウザを閉じる"""
    await browser.close()
    await pw.stop()


# ---------------------------------------------------------------------------
# 記事発見（フィルタ済み一覧ページ — 主導線）
# ---------------------------------------------------------------------------

# フィルタ済みURL（ユーザー提供: 「수출입 동향」でフィルタ済みの報道資料一覧）
FILTERED_LIST_URL = (
    "https://www.motir.go.kr/kor/article/ATCL3f49a5a8c"
    "?searchCondition=1&searchKeyword=%EC%88%98%EC%B6%9C%EC%9E%85+%EB%8F%99%ED%96%A5"
)


async def _navigate_safe(page: Page, url: str, max_retries: int = 3) -> bool:
    """
    安全なナビゲーション。
    
    motir.go.kr は初回接続が ERR_CONNECTION_RESET で必ず失敗し、
    2回目以降は成功するパターンのため、リトライ間隔を置いて再試行する。
    """
    for attempt in range(max_retries):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
            return True
        except Exception as e:
            logger.warning(f"Attempt {attempt+1}/{max_retries} failed: {str(e)[:100]}")
            await asyncio.sleep(2)  # リトライ前に待機
    return False


async def find_articles(
    page: Page,
    keyword: str,
    max_count: int = 10,
) -> list[dict]:
    """
    フィルタ済み一覧ページから記事を取得する。

    重要: 全リンクの href が # （JS遷移）なので、
    クリック → 遷移先URL取得 → 戻る の方式で記事URLを特定する。

    構造（check結果）:
      table tbody tr が10行、各行に <a> でタイトルリンク（href=#）
      行テキスト: "280 | 보도자료 | 2026년 2월 정보통신산업(ICT) 수출입 동향 | ... 2026-03-12 | 537"
    """
    logger.info(f"Loading filtered list for keyword '{keyword}'")
    if not await _navigate_safe(page, FILTERED_LIST_URL):
        logger.error("Could not navigate to filtered list page")
        return []
    await asyncio.sleep(2)

    # Step 1: 行をスキャンして、キーワードに合致する行のインデックスとメタデータを記録
    rows = await page.query_selector_all("table tbody tr")
    logger.info(f"Filtered list has {len(rows)} rows")

    matching_indices = []
    for i, row in enumerate(rows):
        try:
            link = await row.query_selector("a")
            if not link:
                continue
            title = (await link.inner_text()).strip()

            kw_words = keyword.split()
            if not all(w in title for w in kw_words):
                continue

            row_text = (await row.inner_text()).strip()
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", row_text)
            date_str = date_match.group(1) if date_match else ""

            matching_indices.append({
                "index": i,
                "title": title[:200],
                "date": date_str,
            })
            logger.info(f"  Match [{i}]: {title[:60]} ({date_str})")

            if len(matching_indices) >= max_count:
                break
        except Exception:
            continue

    # Step 2: 各マッチ行のリンクをクリックして遷移先URLを取得
    articles = []
    for match in matching_indices:
        try:
            # 一覧ページに戻る（2回目以降）
            if articles:
                if not await _navigate_safe(page, FILTERED_LIST_URL):
                    break
                await asyncio.sleep(2)

            rows = await page.query_selector_all("table tbody tr")
            if match["index"] >= len(rows):
                continue

            link = await rows[match["index"]].query_selector("a")
            if not link:
                continue

            # クリックして記事ページに遷移
            await link.click()
            await page.wait_for_load_state("domcontentloaded", timeout=NAV_TIMEOUT)
            await asyncio.sleep(2)

            article_url = page.url
            logger.info(f"  Navigated to: {article_url}")

            articles.append({
                "title": match["title"],
                "url": article_url,
                "date": match["date"],
            })

        except Exception as e:
            logger.warning(f"  Click failed for [{match['index']}]: {str(e)[:100]}")

    logger.info(f"Found {len(articles)} articles matching '{keyword}'")
    return articles


# ---------------------------------------------------------------------------
# 記事本文取得
# ---------------------------------------------------------------------------

async def get_article_content(page: Page, url: str) -> str:
    """
    記事ページに遷移し、本文テキストを返す。
    診断結果: article セレクタが本文コンテナ（5860文字、반도체あり）
    """
    logger.info(f"Fetching article: {url}")
    if not await _navigate_safe(page, url):
        logger.error(f"Could not navigate to article: {url}")
        return ""
    await asyncio.sleep(2)

    # 本文コンテナ: article が最適（診断で確認済み）
    for sel in ["article", "div.view_cont", "div.bbs_view_cont"]:
        el = await page.query_selector(sel)
        if el:
            text = await el.inner_text()
            if len(text) > 200:
                logger.info(f"Content found with '{sel}' ({len(text)} chars)")
                return text

    text = await page.inner_text("body")
    logger.warning(f"Using full body ({len(text)} chars)")
    return text


# ---------------------------------------------------------------------------
# パーサー：수출입 동향（輸出入動向 - ヘッドライン）
# ---------------------------------------------------------------------------

def parse_trade_report_ko(text: str) -> list[SemiconductorExportRecord]:
    """
    韓国語の「수출입 동향」本文から半導体輸出データを抽出。

    対応パターン:
      반도체 수출은 131억 달러(+11.9%)
      반도체(252억 달러, 160.9%↑)
      반도체 수출은 72억 달러(△36.2%)
    """
    records = []

    month_match = re.search(r"(\d{4})년\s*(\d{1,2})월\s*수출입\s*동향", text)
    ref_month = ""
    if month_match:
        y, m = month_match.group(1), month_match.group(2)
        ref_month = f"{y}-{int(m):02d}"

    patterns = [
        r"반도체\s*수출은?\s*.*?(\d+(?:\.\d+)?)\s*억\s*(?:달러|불)\s*\(([+\-△▲]?\s*\d+(?:\.\d+)?)\s*%\s*[↑↓]?\)",
        r"반도체\s*\(\s*(\d+(?:\.\d+)?)\s*억\s*(?:달러|불)\s*[,，]\s*([+\-△▲]?\s*\d+(?:\.\d+)?)\s*%\s*([↑↓])?\s*\)",
    ]

    for pat in patterns:
        for m in re.finditer(pat, text, re.DOTALL):
            groups = m.groups()
            value_100m = float(groups[0])

            if len(groups) == 3 and groups[2]:
                yoy = float(groups[1]) * (-1 if groups[2] == "↓" else 1)
            else:
                yoy_str = groups[1].replace("△", "-").replace("▲", "-").replace(" ", "")
                yoy = float(yoy_str)

            records.append(SemiconductorExportRecord(
                ref_month=ref_month,
                value_usd_billion=round(value_100m / 10, 2),
                yoy_pct=yoy,
                source_report="TRADE",
                raw_text=m.group(0)[:200],
            ))
            break
        if records:
            break

    return records


# ---------------------------------------------------------------------------
# パーサー：ICT 수출입 동향（ICT輸出入動向）
# ---------------------------------------------------------------------------

def parse_ict_report_text(text: str) -> list[SemiconductorExportRecord]:
    """
    ICT 수출입 동향 の本文テキストから半導体データを抽出。

    実際のデータ形式（診断結果より）:

    1. インライン推移（最重要 — 過去数ヶ月分が一度に取れる）:
       반도체 수출 추이(억 달러, %) : ('25.11월)172.7(38.6↑) → ('26.2월)251.7(160.8↑)

    2. メイン値:
       ○ (반도체 : 251.7억 달러, 160.8%↑)

    3. テーブル形式（PDF本文がテキスト化された場合）
    """
    records = []

    # レポート対象月
    month_match = re.search(
        r"(\d{4})년\s*(\d{1,2})월\s*정보통신산업\s*\(?\s*ICT\s*\)?\s*수출입\s*동향",
        text,
    )
    report_ref = ""
    if month_match:
        y, m = month_match.group(1), month_match.group(2)
        report_ref = f"{y}-{int(m):02d}"

    # 方法1: インライン推移（最も信頼性が高い — 過去数ヶ月分）
    _parse_inline_trend(text, records)

    # 方法2: メイン値 ○ (반도체 : 251.7억 달러, 160.8%↑)
    if not any(r.ref_month == report_ref for r in records):
        _parse_main_value(text, records, report_ref)

    # 方法3: トレンドテーブル（PDF本文テキスト化時）
    if not records:
        _parse_trend_table(text, records, report_ref)

    # 方法4: その他のインライン記述
    if not records:
        _parse_other_inline(text, records, report_ref)

    return records


def _parse_inline_trend(text: str, records: list[SemiconductorExportRecord]):
    """
    インライン推移データをパース。

    実データ（診断結果）:
      반도체 수출 추이(억 달러, %) : ('25.11월)172.7(38.6↑) → ('25.12월)207.7(43.2↑)
      → ('26.1월)205.5(102.7↑) → ('26.2월)251.7(160.8↑)

    各エントリ: ('YY.MM월)VALUE(YOY↑/↓)
    """
    # 반도체 수출 추이/실적 セクションを見つける
    # 改行をまたぐので DOTALL、終端は次のセクション開始まで
    trend_match = re.search(
        r"반도체\s*수출\s*(?:추이|실적).*?:\s*(.*?)(?:\n\s*[○□●■•]|\n\s*\n|\n\s*\d+\.\s|\Z)",
        text,
        re.DOTALL,
    )
    if not trend_match:
        return

    trend_text = trend_match.group(1)
    logger.info(f"Found inline trend: {trend_text[:300]}")

    # 各エントリを抽出: ('YY.MM월)VALUE(YOY↑/↓)
    # 注意: ' は ASCII(U+0027)、'(U+2018)、'(U+2019) のいずれかの場合がある
    pattern = r"\(['\u2018\u2019\u0027]?(\d{2})\.(\d{1,2})월\)\s*(\d+(?:\.\d+)?)\s*\((\d+(?:\.\d+)?)\s*([↑↓])\)"
    matches = re.findall(pattern, trend_text)

    for yy, mm, value_str, yoy_str, direction in matches:
        year = 2000 + int(yy)
        month = int(mm)
        ref = f"{year}-{month:02d}"
        value_100m = float(value_str)
        yoy = float(yoy_str) * (-1 if direction == "↓" else 1)

        records.append(SemiconductorExportRecord(
            ref_month=ref,
            value_usd_billion=round(value_100m / 10, 2),
            yoy_pct=yoy,
            source_report="ICT",
            raw_text=f"('{yy}.{mm}월){value_str}({yoy_str}{direction})",
        ))

    if records:
        logger.info(f"Parsed {len(records)} records from inline trend")


def _parse_main_value(
    text: str,
    records: list[SemiconductorExportRecord],
    report_ref: str,
):
    """
    メイン値をパース。

    実データ（診断結果）:
      ○ (반도체 : 251.7억 달러, 160.8%↑)
    """
    pattern = r"\(반도체\s*:\s*(\d+(?:\.\d+)?)\s*억\s*(?:달러|불)\s*[,，]\s*(\d+(?:\.\d+)?)\s*%\s*([↑↓])\)"
    m = re.search(pattern, text)
    if m:
        value_100m = float(m.group(1))
        yoy = float(m.group(2)) * (-1 if m.group(3) == "↓" else 1)

        records.append(SemiconductorExportRecord(
            ref_month=report_ref,
            value_usd_billion=round(value_100m / 10, 2),
            yoy_pct=yoy,
            source_report="ICT",
            raw_text=m.group(0)[:200],
        ))
        logger.info(f"Parsed main value: {report_ref} ${value_100m / 10:.2f}B ({yoy}%)")


def _parse_trend_table(
    text: str,
    records: list[SemiconductorExportRecord],
    report_ref: str,
):
    """トレンドテーブルをパース（PDF本文テキスト化時）。"""
    header_match = re.search(r"구분\s+(.+)", text)
    if not header_match:
        return

    months = _parse_month_headers(header_match.group(1).strip())
    if not months:
        return

    value_match = re.search(r"반도체\s+([\d.]+(?:\s+[\d.]+)*)", text)
    if not value_match:
        return

    values = [float(v) for v in value_match.group(1).split()]

    after = text[value_match.end():]
    yoy_matches = re.findall(r"\(([+\-△▲]?\s*\d+(?:\.\d+)?)\s*[↑↓]?\)", after)
    yoy_values = []
    for ym in yoy_matches:
        cleaned = ym.replace("△", "-").replace("▲", "-").replace(" ", "")
        try:
            yoy_values.append(float(cleaned))
        except ValueError:
            yoy_values.append(None)

    n = min(len(months), len(values))
    for i in range(n):
        yoy = yoy_values[i] if i < len(yoy_values) else None
        records.append(SemiconductorExportRecord(
            ref_month=months[i],
            value_usd_billion=round(values[i] / 10, 2),
            yoy_pct=yoy,
            source_report="ICT",
            raw_text=f"table: value={values[i]}",
        ))


def _parse_month_headers(header_text: str) -> list[str]:
    """テーブルヘッダーの月をパース。 "'24.10  11  12  '25.1  2" → ["2024-10", ...]"""
    months = []
    tokens = re.findall(r"['\']?(\d{2,4})\.(\d{1,2})|(\d{1,2})", header_text)

    current_year = None
    current_month = None

    for token in tokens:
        if token[0] and token[1]:
            year_str = token[0]
            current_year = 2000 + int(year_str) if len(year_str) == 2 else int(year_str)
            current_month = int(token[1])
        elif token[2]:
            if current_year is None:
                continue
            next_month = int(token[2])
            if current_month is not None and next_month < current_month:
                current_year += 1
            current_month = next_month
        else:
            continue

        if current_year and current_month:
            months.append(f"{current_year}-{current_month:02d}")

    return months


def _parse_other_inline(
    text: str,
    records: list[SemiconductorExportRecord],
    report_ref: str,
):
    """その他のインライン記述。"""
    named_patterns = [
        ("amount_paren",
         r"반도체\s*\(\s*(\d+(?:\.\d+)?)\s*억\s*(?:달러|불)\s*[,，]\s*([+\-△▲]?\s*\d+(?:\.\d+)?)\s*%\s*([↑↓])?\s*\)"),
        ("pct_first_man",
         r"반도체\s+수출.*?(\d+(?:\.\d+)?)\s*%\s*(?:증가|감소|↑|↓).*?(\d+)억\s*(\d+)\s*만\s*(?:달러|불)"),
        ("pct_first",
         r"반도체\s+수출.*?(\d+(?:\.\d+)?)\s*%\s*(증가|감소|↑|↓).*?(\d+(?:\.\d+)?)\s*억\s*(?:달러|불)"),
    ]

    for pat_name, pat in named_patterns:
        m = re.search(pat, text, re.DOTALL)
        if not m:
            continue
        groups = m.groups()

        if pat_name == "amount_paren":
            value_100m = float(groups[0])
            yoy_str = groups[1].replace("△", "-").replace("▲", "-").replace(" ", "")
            yoy = float(yoy_str)
            if len(groups) >= 3 and groups[2] == "↓":
                yoy = -abs(yoy)
        elif pat_name == "pct_first_man":
            yoy = float(groups[0])
            value_100m = float(groups[1]) + float(groups[2]) / 10000
            if "감소" in m.group(0) or "↓" in m.group(0):
                yoy = -abs(yoy)
        elif pat_name == "pct_first":
            yoy = float(groups[0])
            if groups[1] in ("감소", "↓"):
                yoy = -abs(yoy)
            value_100m = float(groups[2])
        else:
            continue

        records.append(SemiconductorExportRecord(
            ref_month=report_ref,
            value_usd_billion=round(value_100m / 10, 2),
            yoy_pct=yoy,
            source_report="ICT",
            raw_text=m.group(0)[:200],
        ))
        break


# ---------------------------------------------------------------------------
# メイン取得関数
# ---------------------------------------------------------------------------

async def scrape_all() -> tuple[ScrapeResult, ScrapeResult]:
    """
    単一ブラウザセッションで수출입 동향 + ICT 수출입 동향の両方を取得。
    
    1回目の接続でセッションが確立されるため、
    ブラウザを使い回すことで接続エラーを回避する。
    """
    trade_result = ScrapeResult()
    ict_result = ScrapeResult()
    pw, browser, page = await create_browser()

    try:
        # --- Step 1: 一覧から全記事を発見（1回のリスト読み込みで両方取得） ---
        all_articles = await find_articles(page, "수출입 동향")

        trade_articles = [
            a for a in all_articles
            if "ICT" not in a["title"] and "정보통신" not in a["title"]
        ]
        ict_articles = [
            a for a in all_articles
            if "ICT" in a["title"] or "정보통신" in a["title"]
        ]
        logger.info(f"Split: {len(trade_articles)} trade, {len(ict_articles)} ICT")

        # --- Step 2: ICTレポート取得（優先） ---
        if ict_articles:
            latest = ict_articles[0]
            ict_result.report_title = latest["title"]
            ict_result.report_url = latest["url"]
            ict_result.report_date = latest["date"]

            text = await get_article_content(page, latest["url"])
            records = parse_ict_report_text(text)
            for r in records:
                r.source_url = latest["url"]
                r.published_at = latest["date"]
            ict_result.records = records
            if not records:
                ict_result.errors.append("Could not parse semiconductor data from ICT report")
        else:
            ict_result.errors.append("No ICT report articles found")

        # --- Step 3: 수출입 동향取得 ---
        if trade_articles:
            latest = trade_articles[0]
            trade_result.report_title = latest["title"]
            trade_result.report_url = latest["url"]
            trade_result.report_date = latest["date"]

            text = await get_article_content(page, latest["url"])
            records = parse_trade_report_ko(text)
            for r in records:
                r.source_url = latest["url"]
                r.published_at = latest["date"]
            trade_result.records = records
            if not records:
                trade_result.errors.append("Could not parse semiconductor data from trade report")
        else:
            trade_result.errors.append("No trade report articles found")

    except Exception as e:
        logger.exception("Error in scrape_all")
        trade_result.errors.append(str(e))
        ict_result.errors.append(str(e))
    finally:
        await close_browser(pw, browser)

    return trade_result, ict_result


# 後方互換性のために個別関数も残す
async def scrape_latest_trade_report() -> ScrapeResult:
    trade, _ = await scrape_all()
    return trade

async def scrape_latest_ict_report() -> ScrapeResult:
    _, ict = await scrape_all()
    return ict


async def scrape_ict_reports_backfill(max_pages: int = 3) -> list[ScrapeResult]:
    """過去のICTレポートを複数取得して時系列をバックフィルする。"""
    results = []
    pw, browser, page = await create_browser()

    try:
        for page_idx in range(1, max_pages + 1):
            # フィルタ済み一覧のページネーション
            backfill_url = (
                "https://www.motir.go.kr/kor/article/ATCL3f49a5a8c"
                f"?searchCondition=1&searchKeyword=%EC%88%98%EC%B6%9C%EC%9E%85+%EB%8F%99%ED%96%A5"
                f"&pageIndex={page_idx}"
            )
            logger.info(f"Backfill page {page_idx}: {backfill_url}")

            if not await _navigate_safe(page, backfill_url):
                logger.error(f"Could not load backfill page {page_idx}")
                break
            await asyncio.sleep(2)

            # Step 1: ICT記事の行インデックスを特定
            rows = await page.query_selector_all("table tbody tr")
            ict_indices = []
            for i, row in enumerate(rows):
                try:
                    link = await row.query_selector("a")
                    if not link:
                        continue
                    title = (await link.inner_text()).strip()
                    if ("ICT" in title or "정보통신" in title) and "수출입" in title:
                        ict_indices.append({"index": i, "title": title[:200]})
                except Exception:
                    continue

            # Step 2: 各行をクリックしてURL取得 → 本文取得
            for idx_info in ict_indices:
                try:
                    # 一覧に戻る
                    if not await _navigate_safe(page, backfill_url):
                        break
                    await asyncio.sleep(2)

                    rows = await page.query_selector_all("table tbody tr")
                    if idx_info["index"] >= len(rows):
                        continue
                    link = await rows[idx_info["index"]].query_selector("a")
                    if not link:
                        continue

                    await link.click()
                    await page.wait_for_load_state("domcontentloaded", timeout=NAV_TIMEOUT)
                    await asyncio.sleep(2)
                    article_url = page.url

                    # 本文取得（すでに記事ページにいる）
                    text = ""
                    for sel in ["article", "div.view_cont", "div.bbs_view_cont"]:
                        el = await page.query_selector(sel)
                        if el:
                            text = await el.inner_text()
                            if len(text) > 200:
                                break
                    if not text:
                        text = await page.inner_text("body")

                    recs = parse_ict_report_text(text)

                    sr = ScrapeResult(
                        records=recs,
                        report_title=idx_info["title"],
                        report_url=article_url,
                    )
                    for r in recs:
                        r.source_url = article_url
                    if not recs:
                        sr.errors.append("No data parsed")

                    results.append(sr)
                    logger.info(f"Backfill: {idx_info['title'][:60]} -> {len(recs)} records")
                    await asyncio.sleep(1)

                except Exception as e:
                    logger.warning(f"Error: {e}")
                    results.append(ScrapeResult(
                        report_title=idx_info["title"],
                        errors=[str(e)],
                    ))

    except Exception as e:
        logger.exception("Error during backfill")
    finally:
        await close_browser(pw, browser)

    return results


# ---------------------------------------------------------------------------
# 重複排除
# ---------------------------------------------------------------------------

def deduplicate_records(
    records: list[SemiconductorExportRecord],
) -> list[SemiconductorExportRecord]:
    """同一月のレコードを重複排除。ICT > TRADE の優先度。"""
    by_month: dict[str, SemiconductorExportRecord] = {}
    priority = {"ICT": 3, "TRADE": 2, "VERIFIED_SEED": 1, "TRADE_EN": 0}

    for r in records:
        if not r.ref_month:
            continue
        existing = by_month.get(r.ref_month)
        if existing is None:
            by_month[r.ref_month] = r
        else:
            r_pri = priority.get(r.source_report, 0)
            e_pri = priority.get(existing.source_report, 0)
            if r_pri > e_pri:
                by_month[r.ref_month] = r
            elif r_pri == e_pri and r.value_usd_billion > 0 and existing.value_usd_billion == 0:
                by_month[r.ref_month] = r

    return sorted(by_month.values(), key=lambda x: x.ref_month)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print("=" * 60)
    print("韓国半導体輸出データ スクレイパー v2")
    print("=" * 60)

    all_records = []

    # 単一ブラウザセッションで両レポートを取得
    trade_result, ict_result = await scrape_all()

    # 1. 수출입 동향
    print("\n--- [1] 수출입 동향（ヘッドライン）---")
    print(f"Report: {trade_result.report_title}")
    print(f"URL:    {trade_result.report_url}")
    print(f"Records: {len(trade_result.records)}")
    for r in trade_result.records:
        print(f"  {r.ref_month}: ${r.value_usd_billion}B (YoY {r.yoy_pct}%)")
    if trade_result.errors:
        print(f"Errors: {trade_result.errors}")
    all_records.extend(trade_result.records)

    # 2. ICT 수출입 동향
    print("\n--- [2] ICT 수출입 동향（詳細）---")
    print(f"Report: {ict_result.report_title}")
    print(f"URL:    {ict_result.report_url}")
    print(f"Records: {len(ict_result.records)}")
    for r in ict_result.records:
        print(f"  {r.ref_month}: ${r.value_usd_billion}B (YoY {r.yoy_pct}%)")
    if ict_result.errors:
        print(f"Errors: {ict_result.errors}")
    all_records.extend(ict_result.records)

    # 3. 統合
    print("\n--- 統合結果 ---")
    merged = deduplicate_records(all_records)
    for r in merged:
        print(f"  {r.ref_month}: ${r.value_usd_billion}B (YoY {r.yoy_pct}%) [{r.source_report}]")

    output = {
        "scraped_at": datetime.now().isoformat(),
        "records": [r.to_dict() for r in merged],
    }
    with open("kr_semiconductor_exports.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(merged)} records to kr_semiconductor_exports.json")


if __name__ == "__main__":
    asyncio.run(main())
