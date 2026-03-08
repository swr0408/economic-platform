"""
中国預金準備率（Reserve Requirement Ratio, RRR）サービス

データ方式:
- 過去: CSV → pbc_rrr_history テーブル
- 最新: 中国人民銀行武漢支行ウェブサイトをスクレイピング
  https://wuhan.pbc.gov.cn/goutongjiaoliu/113456/113469/index.html
  タイトルに存款准备金率関連キーワードを含む記事だけを対象に
  本文から実施日・変更幅・除外条件を抽出し、DB に積み上げていく

対象指標: Large Bank（大型金融機関）の預金準備率

Redisキャッシュ: china:ch_rrr:data (TTL: 4時間)
ファイルキャッシュ: backend/data/cache/china/policy/ch_rrr_cache.json
"""
import json
import os
import re
import logging
import calendar
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any, List
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from sqlalchemy import text

try:
    from core.database import SessionLocal
except ImportError:
    from backend.core.database import SessionLocal

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
CST = ZoneInfo("Asia/Shanghai")

# -----------------------------------------------------------------
# キャッシュ設定
# -----------------------------------------------------------------
REDIS_KEY = "china:ch_rrr:data"
REDIS_TTL = 4 * 3600  # 4 hours

_FILE_CACHE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "cache", "china", "policy"
)
FILE_CACHE_PATH = os.path.join(_FILE_CACHE_DIR, "ch_rrr_cache.json")

# -----------------------------------------------------------------
# スクレイピング定数
# -----------------------------------------------------------------
BASE_URL = "https://wuhan.pbc.gov.cn"
LIST_URL = f"{BASE_URL}/goutongjiaoliu/113456/113469/index.html"

# タイトルキーワード (いずれかを含む記事が対象)
TITLE_KEYWORDS = [
    "存款准备金率",
    "下调金融机构存款准备金率",
    "降准",
    "上调存款准备金率",
    "调整存款准备金率",
]

# ページネーション: 11040-{N}.html
PAGE_URL_TEMPLATE = f"{BASE_URL}/goutongjiaoliu/113456/113469/11040-{{n}}.html"

# -----------------------------------------------------------------
# 正規表現パターン
# -----------------------------------------------------------------
# 実施日: 自2025年5月15日起 / 自2024年2月5日起
RE_EFFECTIVE_DATE = re.compile(r"自(\d{4})年(\d{1,2})月(\d{1,2})日起")

# 変更幅: 下调X.X个百分点 / 上调X.X个百分点
RE_CHANGE = re.compile(r"(下调|上调).*?(\d+(?:\.\d+)?)个百分点")

# 除外条件: 不含已执行5%存款准备金率的金融机构
RE_EXCLUDE_5PCT = re.compile(r"不含已执行5%存款准备金率")


# =============================================================================
# DB操作
# =============================================================================

def _load_history_from_db() -> List[Dict[str, Any]]:
    """pbc_rrr_history から全データを取得"""
    with SessionLocal() as session:
        rows = session.execute(
            text("SELECT date, large_bank FROM pbc_rrr_history ORDER BY date ASC")
        ).fetchall()
    result = []
    for row in rows:
        result.append({
            "date": row[0].strftime("%Y-%m-%d"),
            "value": float(row[1]) if row[1] is not None else None,
        })
    return result


def _get_latest_history_date() -> Optional[date]:
    """pbc_rrr_history の最新日付を取得"""
    with SessionLocal() as session:
        row = session.execute(
            text("SELECT MAX(date) FROM pbc_rrr_history")
        ).fetchone()
    if row and row[0]:
        return row[0]
    return None


def _get_last_known_rate() -> float:
    """DBの最新 large_bank レートを取得（変更計算のベース値）"""
    with SessionLocal() as session:
        row = session.execute(
            text("SELECT large_bank FROM pbc_rrr_history ORDER BY date DESC LIMIT 1")
        ).fetchone()
    if row and row[0] is not None:
        return float(row[0])
    return 7.5  # デフォルト


def _announcement_exists(effective_date: date) -> bool:
    """指定実施日の announcement が登録済みか確認"""
    with SessionLocal() as session:
        row = session.execute(
            text("SELECT 1 FROM pbc_rrr_announcements WHERE effective_date = :d"),
            {"d": effective_date},
        ).fetchone()
    return row is not None


def _insert_announcement(
    announcement_date: date,
    effective_date: date,
    change_amount: float,
    excluded_at_5pct: bool,
    source_url: str,
    article_title: str,
) -> bool:
    """
    announcement を登録し、pbc_rrr_history を effective_date 以降の月末に追加する
    Returns True if newly inserted
    """
    if _announcement_exists(effective_date):
        return False

    with SessionLocal() as session:
        # 発表前の最終レートを取得
        row = session.execute(
            text("""
                SELECT large_bank FROM pbc_rrr_history
                WHERE date < :d ORDER BY date DESC LIMIT 1
            """),
            {"d": effective_date},
        ).fetchone()
        base_rate = float(row[0]) if row and row[0] is not None else _get_last_known_rate()

        # Large Bankは除外条件がある場合でも対象
        # （CSV では Large Bank が記録されているため、除外条件は Small Bank 向け）
        new_rate = round(base_rate + change_amount, 4)

        # announcement 登録
        session.execute(
            text("""
                INSERT INTO pbc_rrr_announcements
                (announcement_date, effective_date, change_amount,
                 excluded_at_5pct, source_url, article_title)
                VALUES (:ann_date, :eff_date, :chg, :ex5, :url, :title)
                ON CONFLICT (effective_date) DO NOTHING
            """),
            {
                "ann_date": announcement_date,
                "eff_date": effective_date,
                "chg": change_amount,
                "ex5": excluded_at_5pct,
                "url": source_url,
                "title": article_title,
            },
        )

        # effective_date から現在まで月末値を追加/更新
        current = date(effective_date.year, effective_date.month, 1)
        today = date.today()
        while current <= today:
            _, last_day = calendar.monthrange(current.year, current.month)
            month_end = date(current.year, current.month, last_day)
            session.execute(
                text("""
                    INSERT INTO pbc_rrr_history (date, large_bank)
                    VALUES (:d, :v)
                    ON CONFLICT (date) DO UPDATE SET large_bank = EXCLUDED.large_bank
                """),
                {"d": month_end, "v": new_rate},
            )
            # 次の月へ
            if current.month == 12:
                current = date(current.year + 1, 1, 1)
            else:
                current = date(current.year, current.month + 1, 1)

        session.commit()
    return True


# =============================================================================
# スクレイピング
# =============================================================================

def _fetch_article_list_page(url: str) -> List[Dict[str, str]]:
    """
    記事一覧ページから記事リストを取得
    Returns: [{"title": ..., "url": ..., "date": "YYYY-MM-DD"}, ...]
    """
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        logger.warning(f"[RRR] Failed to fetch list page {url}: {e}")
        return []

    articles = []
    # <font class="newslist_style">...<a href=...>...</a></font>
    # <span class="hui12">YYYY-MM-DD</span>
    for a_tag in soup.select("font.newslist_style a"):
        href = a_tag.get("href", "")
        title = a_tag.get("title") or a_tag.get_text(strip=True)
        # 同行の日付を探す
        parent_td = a_tag.find_parent("td")
        date_span = parent_td.find("span", class_="hui12") if parent_td else None
        date_str = date_span.get_text(strip=True) if date_span else ""
        if href and title:
            full_url = BASE_URL + href if href.startswith("/") else href
            articles.append({
                "title": title,
                "url": full_url,
                "date": date_str,
            })
    return articles


def _is_rrr_article(title: str) -> bool:
    """タイトルが預金準備率関連かどうか判定"""
    for kw in TITLE_KEYWORDS:
        if kw in title:
            return True
    return False


def _fetch_article_body(url: str) -> str:
    """記事本文を取得"""
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        zoom_div = soup.find("div", id="zoom")
        if zoom_div:
            return zoom_div.get_text(separator="\n", strip=True)
        return soup.get_text(separator="\n", strip=True)
    except Exception as e:
        logger.warning(f"[RRR] Failed to fetch article {url}: {e}")
        return ""


def _parse_announcement(body: str) -> Optional[Dict[str, Any]]:
    """
    記事本文から実施日・変更幅・除外条件を抽出

    Returns:
        {"effective_date": date, "change_amount": float, "excluded_at_5pct": bool}
        or None if parsing fails
    """
    # 実施日
    m_date = RE_EFFECTIVE_DATE.search(body)
    if not m_date:
        # 即日実施のケース: "自2024年9月27日起" などが本文にない場合はスキップ
        return None
    effective_date = date(
        int(m_date.group(1)),
        int(m_date.group(2)),
        int(m_date.group(3)),
    )

    # 変更幅 (存款准备金率についての変更)
    # "下调金融机构存款准备金率0.5个百分点" パターンを優先して探す
    # 本文に複数の下調げがある場合（存款准备金率＋再貸款利率）、存款准备金率のものを選ぶ
    change_amount = None
    direction = None

    # 存款准备金率 の変更幅を探す（再貸款/再割引は除外）
    # 存款准备金率 の前後から変更幅を探す
    rrr_section = re.search(
        r"(?:下调|上调)金融机构存款准备金率(\d+(?:\.\d+)?)个百分点",
        body
    )
    if rrr_section:
        # 方向を判定
        before = body[:body.index(rrr_section.group(0))]
        direction = "下调" if "下调金融机构存款准备金率" in body[:body.index(rrr_section.group(0)) + 30] else "上调"
        change_amount = float(rrr_section.group(1))
    else:
        # フォールバック: 汎用パターン
        for m in RE_CHANGE.finditer(body):
            # 再貸款/再割引に関係しない最初のマッチを使用
            context = body[max(0, m.start()-50):m.end()+50]
            if "再贷款" in context or "再贴现" in context:
                continue
            direction = m.group(1)
            change_amount = float(m.group(2))
            break

    if change_amount is None:
        return None

    # 下調げはマイナス、上調げはプラス
    if direction == "下调":
        change_amount = -change_amount

    # 除外条件: 5%適用先を除外
    excluded_at_5pct = bool(RE_EXCLUDE_5PCT.search(body))

    return {
        "effective_date": effective_date,
        "change_amount": change_amount,
        "excluded_at_5pct": excluded_at_5pct,
    }


def fetch_and_store_latest() -> int:
    """
    武漢PBOCウェブサイトをスクレイピングして新しいRRR変更をDBに保存

    Returns: 新規登録した発表件数
    """
    new_count = 0
    latest_db_date = _get_latest_history_date()

    # 最大5ページをスキャン（1ページ15記事 × 5 = 75記事）
    for page_num in range(1, 6):
        if page_num == 1:
            url = LIST_URL
        else:
            url = PAGE_URL_TEMPLATE.format(n=page_num)

        articles = _fetch_article_list_page(url)
        if not articles:
            logger.warning(f"[RRR] No articles on page {page_num}")
            break

        found_old = False
        for art in articles:
            if not _is_rrr_article(art["title"]):
                continue

            # 記事の日付をパース
            try:
                art_date = datetime.strptime(art["date"], "%Y-%m-%d").date()
            except ValueError:
                art_date = None

            # DBの最新日より古い記事はスキップ (高速化)
            if latest_db_date and art_date and art_date < latest_db_date - timedelta(days=60):
                found_old = True
                continue

            # 既存 announcement かチェック (本文取得前に発表日でざっくり確認)
            body = _fetch_article_body(art["url"])
            if not body:
                continue

            parsed = _parse_announcement(body)
            if not parsed:
                logger.info(f"[RRR] Could not parse announcement from: {art['url']}")
                continue

            effective_date = parsed["effective_date"]
            if _announcement_exists(effective_date):
                logger.debug(f"[RRR] Already exists: effective={effective_date}")
                found_old = True
                continue

            announcement_date = art_date or date.today()
            inserted = _insert_announcement(
                announcement_date=announcement_date,
                effective_date=effective_date,
                change_amount=parsed["change_amount"],
                excluded_at_5pct=parsed["excluded_at_5pct"],
                source_url=art["url"],
                article_title=art["title"],
            )
            if inserted:
                new_count += 1
                logger.info(
                    f"[RRR] New announcement: effective={effective_date}, "
                    f"change={parsed['change_amount']:+.2f}%"
                )

        # 古い記事ページに入ったら早期終了
        if found_old and page_num >= 2:
            break

    return new_count


# =============================================================================
# サービスクラス
# =============================================================================

class ChRrrService:
    """中国預金準備率サービス (Large Bank)"""

    def __init__(self):
        self._redis = None

    def _get_redis(self):
        if self._redis is None:
            try:
                import redis
                self._redis = redis.Redis(host="localhost", port=6379, db=0, socket_timeout=2)
                self._redis.ping()
            except Exception:
                self._redis = None
        return self._redis

    def _from_redis(self) -> Optional[Dict[str, Any]]:
        r = self._get_redis()
        if not r:
            return None
        try:
            raw = r.get(REDIS_KEY)
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return None

    def _to_redis(self, payload: Dict[str, Any]) -> None:
        r = self._get_redis()
        if not r:
            return
        try:
            r.setex(REDIS_KEY, REDIS_TTL, json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass

    def _from_file(self) -> Optional[Dict[str, Any]]:
        if not os.path.exists(FILE_CACHE_PATH):
            return None
        try:
            with open(FILE_CACHE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _to_file(self, payload: Dict[str, Any]) -> None:
        os.makedirs(_FILE_CACHE_DIR, exist_ok=True)
        try:
            with open(FILE_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[RRR] File cache write error: {e}")

    def _fill_missing_months(self) -> None:
        """
        DBの最新月末から今月末まで、据え置きで月末レコードを補完する。
        変更発表がなかった月は前月と同じ値で埋める。
        """
        today = date.today()
        _, last_day = calendar.monthrange(today.year, today.month)
        current_month_end = date(today.year, today.month, last_day)

        with SessionLocal() as session:
            # 最新レコードを取得
            row = session.execute(
                text("SELECT date, large_bank FROM pbc_rrr_history ORDER BY date DESC LIMIT 1")
            ).fetchone()
            if not row:
                return

            last_date = row[0]
            last_rate = float(row[1])

            if last_date >= current_month_end:
                return  # 既に最新月末まで埋まっている

            # last_date の翌月から current_month_end まで補完
            y, m = last_date.year, last_date.month
            if m == 12:
                y, m = y + 1, 1
            else:
                m += 1

            filled = 0
            while True:
                _, ld = calendar.monthrange(y, m)
                month_end = date(y, m, ld)
                session.execute(
                    text("""
                        INSERT INTO pbc_rrr_history (date, large_bank)
                        VALUES (:d, :v)
                        ON CONFLICT (date) DO NOTHING
                    """),
                    {"d": month_end, "v": last_rate},
                )
                filled += 1
                if month_end >= current_month_end:
                    break
                if m == 12:
                    y, m = y + 1, 1
                else:
                    m += 1

            if filled > 0:
                session.commit()
                logger.info(f"[RRR] Filled {filled} missing month(s) up to {current_month_end}")

    def _build_payload(self) -> Dict[str, Any]:
        # まず月末値のギャップを補完
        self._fill_missing_months()
        records = _load_history_from_db()
        latest = records[-1] if records else None
        return {
            "data": records,
            "latest": latest,
            "metadata": {
                "unit": "%",
                "indicator": "Reserve Requirement Ratio (Large Banks)",
                "source": "PBC via Wuhan Branch",
                "total_records": len(records),
                "last_fetched": datetime.now(JST).isoformat(),
            },
        }

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """預金準備率データを取得（キャッシュ優先）"""
        if not force_refresh:
            cached = self._from_redis()
            if cached:
                return cached
            cached = self._from_file()
            if cached:
                # Redisに再登録
                self._to_redis(cached)
                return cached

        payload = self._build_payload()
        self._to_redis(payload)
        self._to_file(payload)
        return payload

    def invalidate_cache(self) -> Dict[str, Any]:
        """キャッシュを無効化"""
        r = self._get_redis()
        if r:
            try:
                r.delete(REDIS_KEY)
            except Exception:
                pass
        if os.path.exists(FILE_CACHE_PATH):
            os.remove(FILE_CACHE_PATH)
        return {"success": True, "message": "RRR cache invalidated"}

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を返す"""
        r = self._get_redis()
        redis_exists = False
        redis_ttl = None
        if r:
            try:
                redis_exists = bool(r.exists(REDIS_KEY))
                redis_ttl = r.ttl(REDIS_KEY)
            except Exception:
                pass
        file_exists = os.path.exists(FILE_CACHE_PATH)
        file_mtime = None
        if file_exists:
            file_mtime = datetime.fromtimestamp(
                os.path.getmtime(FILE_CACHE_PATH), tz=JST
            ).isoformat()
        return {
            "redis": {"exists": redis_exists, "ttl_seconds": redis_ttl},
            "file": {"exists": file_exists, "last_modified": file_mtime},
        }


# シングルトン
ch_rrr_service = ChRrrService()
