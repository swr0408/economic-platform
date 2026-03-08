"""
中国国債発行（Government Bond Issuance）サービス

中国財政部（MOF）の国債業務公告ページから通知（入札予定）と公告（入札結果）を
スクレイピングしてDBに蓄積し、3つのビューで提供:
  1. 今後の入札予定（upcoming）
  2. 直近の入札結果（recent_results）
  3. 月次供給量（monthly_supply）

データソース:
  - 一覧ページ: https://zwgls.mof.gov.cn/ywgg/
  - 通知: 发行工作有关事宜的通知 → mof_bond_notices テーブル
  - 公告: 国债业务公告XXXX年第N号 → mof_bond_results テーブル

更新方式:
  - 初回: 全15ページをスクレイピングしてDBに格納
  - 日次: 先頭2ページのみ確認し、新規分のみDB INSERT

MOFサイトは502エラー頻発のため10回リトライ + 指数バックオフ。
"""
import json
import re
import time
import logging
from datetime import date, datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urljoin
from collections import defaultdict

import requests
from bs4 import BeautifulSoup
from sqlalchemy import text

from core.database import SessionLocal
from core.redis_client import redis_client

logger = logging.getLogger("cn_government_bond_issuance_service")

JST = ZoneInfo("Asia/Tokyo")

# キャッシュ設定
REDIS_KEY = "china:cn_government_bond_issuance:data"
REDIS_TTL = 4 * 3600  # 4時間

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "china" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
FILE_CACHE = CACHE_DIR / "cn_government_bond_issuance_cache.json"

# MOF スクレイピング設定
MOF_BASE = "https://zwgls.mof.gov.cn/ywgg/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

MAX_RETRY = 10
RETRY_BACKOFF = 3
SLEEP_BETWEEN = 1.5

# 一覧ページの分類パターン
RE_NOTICE_TITLE = re.compile(r"发行工作有关事宜的通知")
RE_RESULT_TITLE = re.compile(r"国债业务公告")

# パース用正規表現
RE_DATE_YMD = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
RE_DATE_ISO = re.compile(r"(\d{4}-\d{2}-\d{2})")
RE_AMOUNT = re.compile(r"([\d,.]+)\s*亿元")
RE_PRICE = re.compile(r"([\d.]+)\s*元")
RE_PERCENT = re.compile(r"([\d.]+)\s*%")
RE_MATURITY_YEARS = re.compile(r"(\d+)\s*年期")
RE_MATURITY_DAYS = re.compile(r"期限\s*(\d+)\s*天|(\d+)\s*天期")
RE_TIME_RANGE = re.compile(r"(\d{1,2}):(\d{2})\s*[至到]\s*(\d{1,2}):(\d{2})")
RE_NOTICE_NUM = re.compile(r"(\d{4})\s*年\s*第\s*(\d+)\s*号")


# =============================================================================
# HTTP ユーティリティ
# =============================================================================

def _fetch_with_retry(url: str) -> Optional[str]:
    """HTTPリクエスト（リトライ付き、502対策で10回リトライ）"""
    for attempt in range(MAX_RETRY):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 502:
                wait = RETRY_BACKOFF + attempt * 2
                logger.warning(f"[BondIssuance] 502 on {url}, retry {attempt + 1}/{MAX_RETRY} in {wait}s")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return resp.text
        except requests.exceptions.RequestException as e:
            wait = RETRY_BACKOFF + attempt * 2
            logger.warning(f"[BondIssuance] Error on {url}: {e}, retry {attempt + 1}/{MAX_RETRY} in {wait}s")
            time.sleep(wait)
    logger.error(f"[BondIssuance] Failed after {MAX_RETRY} retries: {url}")
    return None


# =============================================================================
# 一覧ページ解析
# =============================================================================

def _parse_index_page(html: str) -> List[Dict[str, str]]:
    """
    一覧ページのHTMLからアイテムリストを抽出。
    各アイテム: {title, url, date, type}
    """
    soup = BeautifulSoup(html, "html.parser")
    items = []

    # <li> の中に <a> と日付がある構造
    for li in soup.find_all("li"):
        a_tag = li.find("a")
        if not a_tag or not a_tag.get("href"):
            continue
        title = a_tag.get_text(strip=True)
        if not title:
            continue

        href = a_tag["href"]
        # 相対URL → 絶対URL
        if href.startswith("./"):
            href = urljoin(MOF_BASE, href)
        elif not href.startswith("http"):
            href = urljoin(MOF_BASE, href)

        # 日付抽出（li内テキストから）
        li_text = li.get_text(strip=True)
        date_match = RE_DATE_ISO.search(li_text)
        pub_date = date_match.group(1) if date_match else None

        # 分類
        if RE_NOTICE_TITLE.search(title):
            item_type = "notice"
        elif RE_RESULT_TITLE.search(title):
            item_type = "result"
        else:
            continue  # 通知でも公告でもないものはスキップ

        items.append({
            "title": title,
            "url": href,
            "date": pub_date,
            "type": item_type,
        })

    return items


def _scrape_index_pages(max_pages: int = 2) -> List[Dict[str, str]]:
    """一覧ページを指定ページ数分スクレイピングしてアイテムリストを返す"""
    all_items = []

    for page in range(max_pages):
        if page == 0:
            url = MOF_BASE
        else:
            url = f"{MOF_BASE}index_{page}.htm"

        html = _fetch_with_retry(url)
        if not html:
            logger.warning(f"[BondIssuance] Failed to fetch index page {page}")
            continue

        items = _parse_index_page(html)
        all_items.extend(items)
        logger.info(f"[BondIssuance] Index page {page}: {len(items)} items")

        if page < max_pages - 1:
            time.sleep(SLEEP_BETWEEN)

    return all_items


# =============================================================================
# 詳細ページ解析 - 通知（入札予定）
# =============================================================================

def _classify_bond_type(title: str) -> str:
    """タイトルから国債タイプを分類"""
    if "附息" in title:
        return "interest_bearing"
    elif "贴现" in title:
        return "discount"
    elif "储蓄" in title:
        return "savings"
    return "other"


def _extract_date(text_block: str, pattern_label: str = "") -> Optional[date]:
    """テキストから日付を抽出（YYYY年MM月DD日 形式）"""
    m = RE_DATE_YMD.search(text_block)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


def _extract_amount(text_block: str) -> Optional[float]:
    """テキストから金額（億元）を抽出"""
    m = RE_AMOUNT.search(text_block)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def _parse_notice(html: str, title: str, url: str, pub_date: str) -> Optional[Dict[str, Any]]:
    """通知（入札予定）の詳細ページを解析"""
    soup = BeautifulSoup(html, "html.parser")
    # 本文テキスト取得
    content_div = soup.find("div", class_="TRS_UEDITOR") or soup.find("div", class_="pages_content") or soup.find("div", id="zoom")
    if not content_div:
        body_text = soup.get_text()
    else:
        body_text = content_div.get_text()

    bond_type = _classify_bond_type(title)
    is_reissue = "续发行" in title

    # 期限
    maturity_years = None
    maturity_days = None
    m_years = RE_MATURITY_YEARS.search(body_text)
    if m_years:
        maturity_years = float(m_years.group(1))
    m_days = RE_MATURITY_DAYS.search(body_text)
    if m_days:
        maturity_days = int(m_days.group(1) or m_days.group(2))

    # 発行額
    issue_amount = None
    for pattern in [r"面值总额\s*([\d,.]+)\s*亿元", r"发行额[^。]*?([\d,.]+)\s*亿元",
                    r"([\d,.]+)\s*亿元"]:
        m = re.search(pattern, body_text)
        if m:
            try:
                issue_amount = float(m.group(1).replace(",", ""))
                break
            except ValueError:
                pass

    # 招标日時
    bidding_date = None
    bidding_time_start = None
    bidding_time_end = None
    bidding_section = ""
    for line in body_text.split("\n"):
        if "招标时间" in line or "招标日" in line:
            bidding_section = line
            break
    if not bidding_section:
        # 全文から探す
        m_bid = re.search(r"招标时间[^。]*", body_text)
        if m_bid:
            bidding_section = m_bid.group(0)

    if bidding_section:
        bidding_date = _extract_date(bidding_section)
        m_time = RE_TIME_RANGE.search(bidding_section)
        if m_time:
            bidding_time_start = f"{int(m_time.group(1)):02d}:{m_time.group(2)}"
            bidding_time_end = f"{int(m_time.group(3)):02d}:{m_time.group(4)}"

    # 招标方式
    bidding_method = None
    m_method = re.search(r"采用(.*?)招标方式", body_text)
    if m_method:
        bidding_method = m_method.group(1).strip()

    # 计息日
    interest_start_date = None
    m_int = re.search(r"(?:自|从)?\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*(?:开始)?计息", body_text)
    if m_int:
        try:
            interest_start_date = date(int(m_int.group(1)), int(m_int.group(2)), int(m_int.group(3)))
        except ValueError:
            pass

    # 兑付日
    redemption_date = None
    m_red = re.search(r"(?:到期)?兑付日[为是]?\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", body_text)
    if not m_red:
        m_red = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日[^。]*兑付", body_text)
    if m_red:
        try:
            redemption_date = date(int(m_red.group(1)), int(m_red.group(2)), int(m_red.group(3)))
        except ValueError:
            pass

    # 上市交易日
    listing_date = None
    m_list = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*起[^。]*上市交易", body_text)
    if not m_list:
        m_list = re.search(r"上市交易[^。]*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", body_text)
    if m_list:
        try:
            listing_date = date(int(m_list.group(1)), int(m_list.group(2)), int(m_list.group(3)))
        except ValueError:
            pass

    # 付息頻度
    coupon_frequency = None
    if "按半年付息" in body_text:
        coupon_frequency = "半年"
    elif "按年付息" in body_text or "每年支付利息" in body_text:
        coupon_frequency = "年"
    elif "按季付息" in body_text:
        coupon_frequency = "季"

    # bond_name（タイトルから抽出）
    bond_name = title.replace("关于", "").replace("发行工作有关事宜的通知", "").strip()

    return {
        "url": url,
        "publish_date": pub_date,
        "title": title,
        "bond_name": bond_name,
        "bond_type": bond_type,
        "is_reissue": is_reissue,
        "maturity_years": maturity_years,
        "maturity_days": maturity_days,
        "issue_amount": issue_amount,
        "bidding_date": bidding_date.isoformat() if bidding_date else None,
        "bidding_time_start": bidding_time_start,
        "bidding_time_end": bidding_time_end,
        "bidding_method": bidding_method,
        "interest_start_date": interest_start_date.isoformat() if interest_start_date else None,
        "redemption_date": redemption_date.isoformat() if redemption_date else None,
        "listing_date": listing_date.isoformat() if listing_date else None,
        "coupon_frequency": coupon_frequency,
    }


# =============================================================================
# 詳細ページ解析 - 公告（入札結果）
# =============================================================================

def _parse_result(html: str, title: str, url: str, pub_date: str) -> Optional[Dict[str, Any]]:
    """公告（入札結果）の詳細ページを解析"""
    soup = BeautifulSoup(html, "html.parser")
    content_div = soup.find("div", class_="TRS_UEDITOR") or soup.find("div", class_="pages_content") or soup.find("div", id="zoom")
    if not content_div:
        body_text = soup.get_text()
    else:
        body_text = content_div.get_text()

    bond_type = _classify_bond_type(body_text)
    is_reissue = "续发行" in body_text or "续发行" in title

    # 公告番号
    notice_number = None
    m_num = RE_NOTICE_NUM.search(title)
    if m_num:
        notice_number = f"{m_num.group(1)}年第{m_num.group(2)}号"

    # 期限
    maturity_years = None
    maturity_days = None
    m_years = RE_MATURITY_YEARS.search(body_text)
    if m_years:
        maturity_years = float(m_years.group(1))
    m_days = RE_MATURITY_DAYS.search(body_text)
    if m_days:
        maturity_days = int(m_days.group(1) or m_days.group(2))
    # 贴现国債: 期限が日数で表記（例: 91天）
    if not maturity_days and bond_type == "discount":
        m_d2 = re.search(r"(\d{2,3})\s*天", body_text)
        if m_d2:
            maturity_days = int(m_d2.group(1))

    # 計画発行額
    planned_amount = None
    m_plan = re.search(r"计划[^。]*?([\d,.]+)\s*亿元", body_text)
    if m_plan:
        try:
            planned_amount = float(m_plan.group(1).replace(",", ""))
        except ValueError:
            pass

    # 実際発行額
    actual_amount = None
    m_actual = re.search(r"实际[^。]*?面值金额\s*([\d,.]+)\s*亿元", body_text)
    if not m_actual:
        m_actual = re.search(r"实际[^。]*?([\d,.]+)\s*亿元", body_text)
    if m_actual:
        try:
            actual_amount = float(m_actual.group(1).replace(",", ""))
        except ValueError:
            pass
    # フォールバック: 計画=実績
    if not actual_amount and planned_amount:
        actual_amount = planned_amount

    # 発行価格
    issue_price = None
    m_price = re.search(r"(?:续)?发行价格[为是]?\s*([\d.]+)\s*元", body_text)
    if m_price:
        try:
            issue_price = float(m_price.group(1))
        except ValueError:
            pass

    # 折合年収益率
    annual_yield = None
    m_yield = re.search(r"折合年收益率[为是]?\s*([\d.]+)\s*%", body_text)
    if not m_yield:
        m_yield = re.search(r"折合年收益率[为是]?\s*([\d.]+)", body_text)
    if m_yield:
        try:
            annual_yield = float(m_yield.group(1))
        except ValueError:
            pass

    # 票面利率
    coupon_rate = None
    m_coupon = re.search(r"票面利率[为是]?\s*([\d.]+)\s*%", body_text)
    if not m_coupon:
        m_coupon = re.search(r"票面利率[为是]?\s*([\d.]+)", body_text)
    if m_coupon:
        try:
            coupon_rate = float(m_coupon.group(1))
        except ValueError:
            pass

    # 计息日
    interest_start_date = None
    m_int = re.search(r"(?:起息日|计息日)[^。]*?(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", body_text)
    if not m_int:
        m_int = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*(?:开始)?计息", body_text)
    if m_int:
        try:
            interest_start_date = date(int(m_int.group(1)), int(m_int.group(2)), int(m_int.group(3)))
        except ValueError:
            pass

    # 兑付日
    redemption_date = None
    m_red = re.search(r"(?:到期)?兑付日[为是]?\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", body_text)
    if not m_red:
        m_red = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日[^。]*(?:到期)?兑付", body_text)
    if m_red:
        try:
            redemption_date = date(int(m_red.group(1)), int(m_red.group(2)), int(m_red.group(3)))
        except ValueError:
            pass

    # 上市交易日
    listing_date = None
    m_list = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*起[^。]*上市交易", body_text)
    if not m_list:
        m_list = re.search(r"上市交易[^。]*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", body_text)
    if m_list:
        try:
            listing_date = date(int(m_list.group(1)), int(m_list.group(2)), int(m_list.group(3)))
        except ValueError:
            pass

    # bond_name（本文から抽出）
    bond_name = None
    m_bond = re.search(r"(\d{4}年记账式[^，。\n]{5,40})", body_text)
    if m_bond:
        bond_name = m_bond.group(1).strip()
    if not bond_name:
        # 储蓄国债パターン
        m_sav = re.search(r"(\d{4}年第[一二三四五六七八九十]+期.*?储蓄国债)", body_text)
        if m_sav:
            bond_name = m_sav.group(1).strip()

    return {
        "url": url,
        "publish_date": pub_date,
        "title": title,
        "notice_number": notice_number,
        "bond_name": bond_name,
        "bond_type": bond_type,
        "is_reissue": is_reissue,
        "maturity_years": maturity_years,
        "maturity_days": maturity_days,
        "planned_amount": planned_amount,
        "actual_amount": actual_amount,
        "issue_price": issue_price,
        "annual_yield": annual_yield,
        "coupon_rate": coupon_rate,
        "interest_start_date": interest_start_date.isoformat() if interest_start_date else None,
        "redemption_date": redemption_date.isoformat() if redemption_date else None,
        "listing_date": listing_date.isoformat() if listing_date else None,
    }


# =============================================================================
# DB 操作
# =============================================================================

def _get_existing_urls(session) -> set:
    """DB内の全URLセットを取得"""
    urls = set()
    rows = session.execute(text("SELECT url FROM mof_bond_notices")).fetchall()
    urls.update(r[0] for r in rows)
    rows = session.execute(text("SELECT url FROM mof_bond_results")).fetchall()
    urls.update(r[0] for r in rows)
    return urls


def _insert_notice(session, data: Dict[str, Any]) -> bool:
    """通知をDBにINSERT"""
    try:
        session.execute(text("""
            INSERT INTO mof_bond_notices
                (url, publish_date, title, bond_name, bond_type, is_reissue,
                 maturity_years, maturity_days, issue_amount,
                 bidding_date, bidding_time_start, bidding_time_end, bidding_method,
                 interest_start_date, redemption_date, listing_date, coupon_frequency)
            VALUES
                (:url, :publish_date, :title, :bond_name, :bond_type, :is_reissue,
                 :maturity_years, :maturity_days, :issue_amount,
                 :bidding_date, :bidding_time_start, :bidding_time_end, :bidding_method,
                 :interest_start_date, :redemption_date, :listing_date, :coupon_frequency)
            ON CONFLICT (url) DO NOTHING
        """), data)
        return True
    except Exception as e:
        logger.error(f"[BondIssuance] Notice INSERT error: {e}")
        return False


def _insert_result(session, data: Dict[str, Any]) -> bool:
    """公告をDBにINSERT"""
    try:
        session.execute(text("""
            INSERT INTO mof_bond_results
                (url, publish_date, title, notice_number, bond_name, bond_type, is_reissue,
                 maturity_years, maturity_days, planned_amount, actual_amount,
                 issue_price, annual_yield, coupon_rate,
                 interest_start_date, redemption_date, listing_date)
            VALUES
                (:url, :publish_date, :title, :notice_number, :bond_name, :bond_type, :is_reissue,
                 :maturity_years, :maturity_days, :planned_amount, :actual_amount,
                 :issue_price, :annual_yield, :coupon_rate,
                 :interest_start_date, :redemption_date, :listing_date)
            ON CONFLICT (url) DO NOTHING
        """), data)
        return True
    except Exception as e:
        logger.error(f"[BondIssuance] Result INSERT error: {e}")
        return False


def _load_upcoming_from_db(session) -> List[Dict[str, Any]]:
    """今後の入札予定をDBから取得"""
    today = date.today().isoformat()
    rows = session.execute(text("""
        SELECT bond_name, bond_type, is_reissue, maturity_years, maturity_days,
               issue_amount, bidding_date, bidding_time_start, bidding_time_end,
               bidding_method, interest_start_date, listing_date, publish_date
        FROM mof_bond_notices
        WHERE bidding_date >= :today
        ORDER BY bidding_date ASC
    """), {"today": today}).fetchall()

    return [
        {
            "bond_name": r[0],
            "bond_type": r[1],
            "is_reissue": r[2],
            "maturity_years": float(r[3]) if r[3] else None,
            "maturity_days": r[4],
            "issue_amount": float(r[5]) if r[5] else None,
            "bidding_date": r[6].isoformat() if r[6] else None,
            "bidding_time_start": r[7],
            "bidding_time_end": r[8],
            "bidding_method": r[9],
            "interest_start_date": r[10].isoformat() if r[10] else None,
            "listing_date": r[11].isoformat() if r[11] else None,
            "publish_date": r[12].isoformat() if r[12] else None,
        }
        for r in rows
    ]


def _load_recent_results_from_db(session, limit: int = 30) -> List[Dict[str, Any]]:
    """直近の入札結果をDBから取得"""
    rows = session.execute(text("""
        SELECT notice_number, bond_name, bond_type, is_reissue,
               maturity_years, maturity_days,
               planned_amount, actual_amount, issue_price, annual_yield, coupon_rate,
               interest_start_date, redemption_date, listing_date, publish_date
        FROM mof_bond_results
        WHERE bond_type IN ('interest_bearing', 'discount')
        ORDER BY publish_date DESC
        LIMIT :limit
    """), {"limit": limit}).fetchall()

    return [
        {
            "notice_number": r[0],
            "bond_name": r[1],
            "bond_type": r[2],
            "is_reissue": r[3],
            "maturity_years": float(r[4]) if r[4] else None,
            "maturity_days": r[5],
            "planned_amount": float(r[6]) if r[6] else None,
            "actual_amount": float(r[7]) if r[7] else None,
            "issue_price": float(r[8]) if r[8] else None,
            "annual_yield": float(r[9]) if r[9] else None,
            "coupon_rate": float(r[10]) if r[10] else None,
            "interest_start_date": r[11].isoformat() if r[11] else None,
            "redemption_date": r[12].isoformat() if r[12] else None,
            "listing_date": r[13].isoformat() if r[13] else None,
            "publish_date": r[14].isoformat() if r[14] else None,
        }
        for r in rows
    ]


def _load_monthly_supply_from_db(session) -> List[Dict[str, Any]]:
    """月次供給量をDBから集計"""
    rows = session.execute(text("""
        SELECT
            TO_CHAR(publish_date, 'YYYY-MM') AS month,
            bond_type,
            SUM(COALESCE(actual_amount, planned_amount)) AS total_amount,
            COUNT(*) AS count
        FROM mof_bond_results
        WHERE bond_type IN ('interest_bearing', 'discount', 'savings')
          AND (actual_amount IS NOT NULL OR planned_amount IS NOT NULL)
        GROUP BY TO_CHAR(publish_date, 'YYYY-MM'), bond_type
        ORDER BY month ASC, bond_type
    """)).fetchall()

    # 月別に集計
    monthly: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "date": "", "interest_bearing": 0, "discount": 0, "savings": 0, "total": 0
    })
    for r in rows:
        month_str = r[0]
        btype = r[1]
        amount = float(r[2]) if r[2] else 0
        monthly[month_str]["date"] = month_str + "-01"
        if btype in ("interest_bearing", "discount", "savings"):
            monthly[month_str][btype] = round(amount, 1)
        monthly[month_str]["total"] = round(
            monthly[month_str]["interest_bearing"] +
            monthly[month_str]["discount"] +
            monthly[month_str]["savings"], 1
        )

    return sorted(monthly.values(), key=lambda x: x["date"])


# =============================================================================
# キャッシュ管理
# =============================================================================

def _load_file_cache() -> Optional[Dict[str, Any]]:
    try:
        if FILE_CACHE.exists():
            with open(FILE_CACHE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def _save_file_cache(payload: Dict[str, Any]) -> None:
    try:
        with open(FILE_CACHE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _invalidate_cache() -> None:
    try:
        redis_client.delete(REDIS_KEY)
    except Exception:
        pass
    try:
        if FILE_CACHE.exists():
            FILE_CACHE.unlink()
    except Exception:
        pass


# =============================================================================
# メインサービスクラス
# =============================================================================

class CnGovernmentBondIssuanceService:
    """中国国債発行サービス"""

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """国債発行データを返す"""
        if not force_refresh:
            try:
                cached = redis_client.get(REDIS_KEY)
                if cached:
                    return json.loads(cached) if isinstance(cached, str) else cached
            except Exception:
                pass
            fc = _load_file_cache()
            if fc:
                return fc

        return self._build_and_cache()

    def _build_and_cache(self) -> Dict[str, Any]:
        """DBからデータを読み取ってペイロード構築・キャッシュ保存"""
        session = SessionLocal()
        try:
            upcoming = _load_upcoming_from_db(session)
            recent_results = _load_recent_results_from_db(session)
            monthly_supply = _load_monthly_supply_from_db(session)

            # DB内の総件数
            notice_count = session.execute(text("SELECT COUNT(*) FROM mof_bond_notices")).scalar()
            result_count = session.execute(text("SELECT COUNT(*) FROM mof_bond_results")).scalar()
        finally:
            session.close()

        payload = {
            "upcoming": upcoming,
            "recent_results": recent_results,
            "monthly_supply": monthly_supply,
            "metadata": {
                "source": "中国財政部 (MOF)",
                "source_url": "https://zwgls.mof.gov.cn/ywgg/",
                "total_notices": notice_count,
                "total_results": result_count,
                "upcoming_count": len(upcoming),
            },
        }

        self._save_to_cache(payload)
        return payload

    def update_latest(self) -> Dict[str, Any]:
        """
        新規分のみスクレイピングしてDBに追加。
        先頭2ページ（約20件）を確認し、未登録URLの詳細ページを取得してINSERT。
        """
        session = SessionLocal()
        try:
            existing_urls = _get_existing_urls(session)
            items = _scrape_index_pages(max_pages=2)

            new_notices = 0
            new_results = 0

            for item in items:
                if item["url"] in existing_urls:
                    continue

                time.sleep(SLEEP_BETWEEN)
                html = _fetch_with_retry(item["url"])
                if not html:
                    continue

                if item["type"] == "notice":
                    parsed = _parse_notice(html, item["title"], item["url"], item["date"])
                    if parsed and _insert_notice(session, parsed):
                        new_notices += 1
                        logger.info(f"[BondIssuance] New notice: {item['title'][:40]}")
                elif item["type"] == "result":
                    parsed = _parse_result(html, item["title"], item["url"], item["date"])
                    if parsed and _insert_result(session, parsed):
                        new_results += 1
                        logger.info(f"[BondIssuance] New result: {item['title'][:40]}")

            session.commit()
            logger.info(f"[BondIssuance] Update done: {new_notices} notices, {new_results} results added")
        except Exception as e:
            session.rollback()
            logger.error(f"[BondIssuance] Update error: {e}")
        finally:
            session.close()

        _invalidate_cache()
        return self._build_and_cache()

    def initial_scrape(self, max_pages: int = 15) -> Dict[str, Any]:
        """
        全ページをスクレイピングしてDBに格納（初回用）。
        """
        session = SessionLocal()
        try:
            existing_urls = _get_existing_urls(session)
            items = _scrape_index_pages(max_pages=max_pages)

            new_notices = 0
            new_results = 0
            skipped = 0

            for item in items:
                if item["url"] in existing_urls:
                    skipped += 1
                    continue

                time.sleep(SLEEP_BETWEEN)
                html = _fetch_with_retry(item["url"])
                if not html:
                    continue

                if item["type"] == "notice":
                    parsed = _parse_notice(html, item["title"], item["url"], item["date"])
                    if parsed and _insert_notice(session, parsed):
                        new_notices += 1
                elif item["type"] == "result":
                    parsed = _parse_result(html, item["title"], item["url"], item["date"])
                    if parsed and _insert_result(session, parsed):
                        new_results += 1

            session.commit()
            logger.info(
                f"[BondIssuance] Initial scrape done: "
                f"{new_notices} notices, {new_results} results, {skipped} skipped"
            )
        except Exception as e:
            session.rollback()
            logger.error(f"[BondIssuance] Initial scrape error: {e}")
        finally:
            session.close()

        _invalidate_cache()
        return self._build_and_cache()

    def _save_to_cache(self, payload: Dict[str, Any]) -> None:
        try:
            redis_client.setex(REDIS_KEY, REDIS_TTL, json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass
        _save_file_cache(payload)

    def invalidate_cache(self) -> Dict[str, Any]:
        _invalidate_cache()
        return {"success": True, "message": "Government bond issuance cache invalidated"}

    def get_cache_status(self) -> Dict[str, Any]:
        redis_exists = False
        file_exists = FILE_CACHE.exists()
        try:
            redis_exists = redis_client.exists(REDIS_KEY) > 0
        except Exception:
            pass
        return {
            "redis_cached": redis_exists,
            "file_cached": file_exists,
            "redis_key": REDIS_KEY,
        }


# シングルトンインスタンス
cn_government_bond_issuance_service = CnGovernmentBondIssuanceService()
