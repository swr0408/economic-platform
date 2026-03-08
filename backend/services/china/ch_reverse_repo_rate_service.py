"""
中国人民銀行 逆回購金利（Reverse Repo Rate）サービス

指標:
- ch_reverse_repo_rate: 7日物逆回購金利（%）

データソース:
- DB: pbc_reverse_repo テーブル
  - 過去データ: backend/data/csv_import/pbc_reverse_repo.csv から一括インポート済み
  - 新規データ: PBOCウェブサイトからスクレイピングして日次蓄積

更新方式:
- 毎日 JTC 16:00（JST）に自動実行
- 一覧ページを確認し、DB未登録分のみ詳細ページを取得してINSERT

URL:
- 一覧: https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/17081-1.html
- 詳細: 各公告ページ

キャッシュ方式: Redisキャッシュ（TTL 4時間）
"""
import json
import re
import time
import logging
from datetime import date, datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from sqlalchemy import text

from core.database import SessionLocal
from core.redis_client import redis_client

logger = logging.getLogger("ch_reverse_repo_rate_service")

# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
CST = ZoneInfo("Asia/Shanghai")

# キャッシュ設定
REDIS_KEY = "china:ch_reverse_repo_rate:data"
REDIS_TTL = 4 * 3600  # 4時間

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "china" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
FILE_CACHE = CACHE_DIR / "ch_reverse_repo_rate_cache.json"

# PBOCスクレイピング設定
PBC_BASE = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/"
PBC_ROOT = "https://www.pbc.gov.cn"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
MAX_RETRY = 3
SLEEP_SECONDS = 0.8
MAX_LIST_PAGES = 3

# 正規表現
RE_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")
RE_DETAIL_PATH = re.compile(r"/125475/\d{5,}/")
RE_NUM = re.compile(r"([\d.]+)")


# =============================================================================
# スクレイピングユーティリティ
# =============================================================================

def _fetch_html(url: str) -> str:
    """HTMLを取得（リトライ付き）"""
    for attempt in range(MAX_RETRY):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            r.encoding = r.apparent_encoding
            time.sleep(SLEEP_SECONDS)
            return r.text
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt < MAX_RETRY - 1:
                time.sleep((attempt + 1) * 5)
            else:
                raise


def _parse_list_page(html: str) -> List[tuple]:
    """一覧HTMLから (detail_url, date_str) を抽出"""
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not RE_DETAIL_PATH.search(href):
            continue
        td = a.find_parent("td")
        if not td:
            continue
        span = td.find("span", class_="hui12")
        if span:
            m = RE_DATE.search(span.get_text(strip=True))
        else:
            m = RE_DATE.search(td.get_text(" ", strip=True))
        if not m:
            continue
        items.append((urljoin(PBC_ROOT, href), m.group(1)))
    return items


def _extract_number(text: str) -> Optional[float]:
    """テキストから数値を抽出"""
    m = RE_NUM.search(text.replace(",", ""))
    return float(m.group(1)) if m else None


def _parse_detail(html: str) -> Optional[tuple]:
    """詳細ページから (rate, bid, win) を抽出。逆回購がない日はNoneを返す"""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.find("div", id="zoom") or soup.find("div", class_="zoom1") or soup
    full_text = content.get_text("", strip=True)

    if "逆回购" not in full_text:
        return None
    if "不开展逆回购" in full_text or "不开展 逆回购" in full_text:
        return None
    if "操作量为零" in full_text:
        return None

    for tbl in content.find_all("table"):
        rows = tbl.find_all("tr")
        if len(rows) < 2:
            continue
        header_cells = [td.get_text(strip=True) for td in rows[0].find_all(["td", "th"])]
        col_map = {}
        for i, h in enumerate(header_cells):
            hc = h.replace("\n", "").replace(" ", "")
            if "期限" in hc:
                col_map["tenor"] = i
            elif "操作量" in hc or "投标量" in hc:
                col_map["bid"] = i
            elif "中标量" in hc or "交易量" in hc:
                col_map["win"] = i
            elif "操作利率" in hc or "中标利率" in hc:
                col_map["rate"] = i
        if "rate" not in col_map:
            continue
        for data_row in rows[1:]:
            cells = [td.get_text(strip=True) for td in data_row.find_all(["td", "th"])]
            if len(cells) <= max(col_map.values()):
                continue
            rate = _extract_number(cells[col_map["rate"]])
            if rate is None:
                continue
            bid, win = None, None
            if "bid" in col_map and "win" in col_map:
                bid = _extract_number(cells[col_map["bid"]])
                win = _extract_number(cells[col_map["win"]])
            elif "bid" in col_map:
                val = _extract_number(cells[col_map["bid"]])
                bid = win = val
            elif "win" in col_map:
                win = _extract_number(cells[col_map["win"]])
            return (rate, bid, win)

    # フォールバック: テキスト解析
    compact = re.sub(r'\s+', '', full_text)
    m = re.search(r'开展了([\d.]+)亿元(\d+)天期?逆回购', compact)
    if m:
        win_val = float(m.group(1))
        rate_m = re.search(r'([\d.]+)%', compact)
        if rate_m:
            return (float(rate_m.group(1)), win_val, win_val)

    return None


# =============================================================================
# DBアクセス
# =============================================================================

def _load_from_db() -> List[Dict[str, Any]]:
    """DBから全データを取得（昇順）"""
    with SessionLocal() as session:
        rows = session.execute(text("""
            SELECT date, rate, bid_amount, win_amount
            FROM pbc_reverse_repo
            ORDER BY date ASC
        """)).fetchall()

    result = []
    for row in rows:
        result.append({
            "date": row[0].isoformat(),
            "value": row[1],
            "bid_amount": row[2],
            "win_amount": row[3],
        })
    return result


def fetch_and_store_latest() -> int:
    """
    PBOCウェブサイトからDB未登録の新しいデータを取得してINSERT

    Returns:
        追加件数
    """
    with SessionLocal() as session:
        # DB内の最新日付を確認
        row = session.execute(text(
            "SELECT MAX(date) FROM pbc_reverse_repo"
        )).scalar()
        latest_date = row if row else date(2015, 1, 1)
        logger.info(f"[PBC] DB最新日付: {latest_date}")

        new_count = 0
        for page in range(1, MAX_LIST_PAGES + 1):
            if page == 1:
                list_url = urljoin(PBC_BASE, "index.html")
            else:
                list_url = urljoin(PBC_BASE, f"17081-{page}.html")

            try:
                html = _fetch_html(list_url)
            except Exception as e:
                logger.error(f"[PBC] 一覧取得失敗 page={page}: {e}")
                break

            items = _parse_list_page(html)
            all_old = True

            for detail_url, dt_str in items:
                dt = date.fromisoformat(dt_str)
                if dt <= latest_date:
                    continue
                all_old = False

                # 既存チェック
                exists = session.execute(text(
                    "SELECT 1 FROM pbc_reverse_repo WHERE date = :d"
                ), {"d": dt}).scalar()
                if exists:
                    continue

                try:
                    dhtml = _fetch_html(detail_url)
                    parsed = _parse_detail(dhtml)
                    if parsed:
                        rate, bid, win = parsed
                        session.execute(text("""
                            INSERT INTO pbc_reverse_repo (date, rate, bid_amount, win_amount)
                            VALUES (:d, :rate, :bid, :win)
                            ON CONFLICT (date) DO NOTHING
                        """), {"d": dt, "rate": rate, "bid": bid, "win": win})
                        new_count += 1
                        logger.info(f"[PBC] 追加: {dt} rate={rate}%")
                except Exception as e:
                    logger.warning(f"[PBC] 詳細取得失敗 {dt_str}: {e}")

            if all_old:
                break

        session.commit()

    if new_count > 0:
        logger.info(f"[PBC] 完了: {new_count}件追加 → キャッシュ無効化")
        _invalidate_cache()

    return new_count


# =============================================================================
# メインサービスクラス
# =============================================================================

class ChReverseRepoRateService:
    """
    中国逆回購金利サービス

    DBからデータを取得し、Redisキャッシュで高速提供。
    """

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """逆回購金利データを取得"""
        # キャッシュ確認
        if not force_refresh:
            cached = self._get_from_cache()
            if cached:
                return cached

        # DBから取得
        try:
            data = _load_from_db()
        except Exception as e:
            logger.error(f"[PBC] DB取得エラー: {e}")
            cached = self._get_from_file_cache()
            if cached:
                return cached
            return {"data": [], "latest": None, "metadata": {}}

        if not data:
            return {"data": [], "latest": None, "metadata": {}}

        latest = data[-1] if data else None
        metadata = {
            "source": "PBC（中国人民銀行）",
            "unit": "%",
            "frequency": "daily",
            "total_records": len(data),
        }

        result = {
            "data": data,
            "latest": latest,
            "metadata": metadata,
        }

        self._save_to_cache(result)
        return result

    def _get_from_cache(self) -> Optional[Dict[str, Any]]:
        """Redisキャッシュから取得"""
        try:
            cached = redis_client.get(REDIS_KEY)
            if cached:
                return json.loads(cached)
        except Exception:
            pass
        return self._get_from_file_cache()

    def _get_from_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュから取得"""
        try:
            if FILE_CACHE.exists():
                with open(FILE_CACHE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        """Redisとファイルキャッシュに保存"""
        try:
            redis_client.setex(REDIS_KEY, REDIS_TTL, json.dumps(data, ensure_ascii=False))
        except Exception:
            pass
        try:
            with open(FILE_CACHE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def invalidate_cache(self) -> Dict[str, Any]:
        """キャッシュ無効化"""
        _invalidate_cache()
        return {"success": True, "message": "Reverse repo rate cache invalidated"}

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態確認"""
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


def _invalidate_cache() -> None:
    """内部キャッシュ無効化"""
    try:
        redis_client.delete(REDIS_KEY)
    except Exception:
        pass
    try:
        if FILE_CACHE.exists():
            FILE_CACHE.unlink()
    except Exception:
        pass


# シングルトン
ch_reverse_repo_rate_service = ChReverseRepoRateService()
