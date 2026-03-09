"""
中国 輸出物価指数（Export Price Index）サービス

データ項目:
- index: 輸出物価指数（原数値、前年同月=100）
- yoy: 前年比 (%) = index - 100
- mom: 前月比 (%) = 当月index - 前月index

データソース:
- DB蓄積: nbs_monthly_data テーブル（CSVインポート + GACC蓄積）
  indicator: cn_export_prices_index, cn_export_prices_yoy
- 最新値: 海関総署（GACC）ウェブサイトからスクレイピング
  http://english.customs.gov.cn/statics/report/trade.html
  "Index Number of Exports by HS2" → 総指数 → 価格指数 Unit value
- FMP: 次回発表日の取得（cn_trade_balance マッピングを利用）

更新スケジュール: 月次（毎月上旬〜中旬）
"""
import os
import json
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# パス定義
_BASE_DIR = Path(__file__).parent.parent.parent
_FILE_CACHE_DIR = _BASE_DIR / "data" / "cache" / "china" / "inflation"
FILE_CACHE_PATH = str(_FILE_CACHE_DIR / "cn_export_prices_cache.json")

REDIS_KEY = "china:cn_export_prices:data"
REDIS_TTL = 86400  # 24h

# FMP用（貿易データのマッピングを流用）
ECONALPHA_ID = "cn_trade_balance"

# DB指標ID
DB_INDICATORS = {
    "index": "cn_export_prices_index",
    "yoy": "cn_export_prices_yoy",
}

# GACC設定
GACC_BASE_URL = "http://english.customs.gov.cn"
GACC_TRADE_URLS = {
    "current": f"{GACC_BASE_URL}/statics/report/trade.html",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

# 月名 → 月番号
MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _scrape_gacc_latest() -> Dict[str, float]:
    """GACCウェブサイトから最新の輸出物価指数を取得

    trade.html → "Index Number of Exports by HS2"の各月リンクを辿り、
    詳細ページの総指数→価格指数(Unit value)を取得

    Returns:
        {date_str: index_value, ...} e.g. {"2025-12-01": 96.4}
    """
    result = {}
    current_year = datetime.now(JST).year

    # 当年と前年のページをチェック
    urls_to_check = [
        (current_year, GACC_TRADE_URLS["current"]),
    ]
    prev_year_url = f"{GACC_BASE_URL}/statics/report/trade{current_year - 1}.html"
    urls_to_check.append((current_year - 1, prev_year_url))

    for year, index_url in urls_to_check:
        try:
            month_links = _get_export_hs2_month_links(index_url, year)
            if not month_links:
                continue

            for month, detail_url in month_links.items():
                date_str = f"{year}-{month:02d}-01"
                try:
                    index_val = _scrape_detail_page(detail_url)
                    if index_val is not None:
                        result[date_str] = index_val
                        logger.info(f"[GACC] {date_str}: {index_val}")
                except Exception as e:
                    logger.warning(f"[GACC] Detail page error ({date_str}): {e}")
        except Exception as e:
            logger.warning(f"[GACC] Index page error ({year}): {e}")

    return result


def _get_export_hs2_month_links(index_url: str, year: int) -> Dict[int, str]:
    """trade.htmlから "Index Number of Exports by HS2" の月別リンクを取得

    Returns:
        {month_number: detail_url, ...}
    """
    resp = requests.get(index_url, headers=HEADERS, timeout=30)
    if resp.status_code != 200:
        logger.warning(f"[GACC] HTTP {resp.status_code} for {index_url}")
        return {}

    soup = BeautifulSoup(resp.text, "html.parser")

    # テーブルからExports by HS2の行を見つける
    month_links = {}

    for tr in soup.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue

        # 最初のセルにタイトルが入っている
        title_cell = cells[0]
        title_text = title_cell.get_text(strip=True).lower()

        if "index number of exports by hs2" not in title_text:
            continue

        # 2番目のセルに月リンクがある
        month_cell = cells[1]
        for a_tag in month_cell.find_all("a", href=True):
            link_text = a_tag.get_text(strip=True).lower().rstrip(".")
            for month_name, month_num in MONTH_MAP.items():
                if link_text.startswith(month_name):
                    href = a_tag["href"]
                    if not href.startswith("http"):
                        href = f"{GACC_BASE_URL}{href}"
                    month_links[month_num] = href
                    break

        break  # 最初のマッチだけ

    return month_links


def _scrape_detail_page(detail_url: str) -> Optional[float]:
    """詳細ページから総指数の価格指数(Unit value)を取得

    Returns:
        float: 輸出物価指数（例: 95.1）
    """
    resp = requests.get(detail_url, headers=HEADERS, timeout=30)
    if resp.status_code != 200:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # テーブルを探す
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        header_row_idx = None

        # ヘッダー行を見つける（价格指数 / Unit value を含む行）
        for i, row in enumerate(rows):
            row_text = row.get_text().lower()
            if "unit value" in row_text or "价格指数" in row_text:
                header_row_idx = i
                break

        if header_row_idx is None:
            continue

        # ヘッダー行のセルを取得して价格指数列のインデックスを特定
        header_cells = rows[header_row_idx].find_all(["td", "th"])
        unit_value_col = None
        for j, cell in enumerate(header_cells):
            cell_text = cell.get_text(strip=True).lower()
            if "unit value" in cell_text or "价格指数" in cell_text:
                unit_value_col = j
                break

        if unit_value_col is None:
            continue

        # 総指数行を見つける（header_rowの次以降の行）
        for row in rows[header_row_idx + 1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) <= unit_value_col:
                continue

            row_text = row.get_text(strip=True).lower()
            if "总指数" in row_text or "total" in row_text:
                value_text = cells[unit_value_col].get_text(strip=True)
                # 数字以外を除去
                value_clean = re.sub(r"[^\d.]", "", value_text)
                if value_clean:
                    return float(value_clean)

    return None


def _fetch_and_upsert_gacc() -> Dict[str, float]:
    """GACCから最新データを取得し、DBにUPSERT

    Returns:
        {date_str: index_value, ...}
    """
    from services.china.nbs_db_utils import upsert_nbs_data

    scraped = _scrape_gacc_latest()
    if not scraped:
        return {}

    # index値をDBに蓄積
    upsert_nbs_data(DB_INDICATORS["index"], scraped, source="api")

    # YoY (= index - 100) を計算してDBに蓄積
    yoy_data = {k: round(v - 100, 2) for k, v in scraped.items()}
    upsert_nbs_data(DB_INDICATORS["yoy"], yoy_data, source="api")

    logger.info(f"[ExportPrices] GACC scraped & upserted: {len(scraped)} records")
    return scraped


def _build_data() -> List[Dict[str, Any]]:
    """DBからデータを読み込み + GACC最新取得→DB蓄積

    手順:
    1. GACCから最新データ取得 → DB UPSERT
    2. DBから全データを読み込み
    3. 日付をキーにマージして時系列構築
    4. MoM（前月比）をindex値から計算
    """
    from services.china.nbs_db_utils import load_nbs_multi

    # --- GACC → DB蓄積 ---
    try:
        _fetch_and_upsert_gacc()
    except Exception as e:
        logger.warning(f"[ExportPrices] GACC fetch/upsert failed: {e}")

    # --- DBから全データ読み込み ---
    db_data = load_nbs_multi([
        DB_INDICATORS["index"],
        DB_INDICATORS["yoy"],
    ])
    index_data = db_data.get(DB_INDICATORS["index"], {})
    yoy_data = db_data.get(DB_INDICATORS["yoy"], {})

    logger.info(f"[ExportPrices] DB Index: {len(index_data)} records, YoY: {len(yoy_data)} records")

    # 日付をキーにマージ
    all_dates = sorted(set(index_data.keys()) | set(yoy_data.keys()))

    # MoM計算用: indexの前月値を保持
    prev_index = None
    result = []

    for date_str in all_dates:
        idx_val = index_data.get(date_str)
        yoy_val = yoy_data.get(date_str)

        if idx_val is None:
            prev_index = None
            continue

        # YoYがDBになければ計算
        if yoy_val is None:
            yoy_val = round(idx_val - 100, 2)

        # MoM = 当月index - 前月index
        mom_val = None
        if prev_index is not None:
            mom_val = round(idx_val - prev_index, 2)

        result.append({
            "date": date_str,
            "index": round(idx_val, 2),
            "yoy": yoy_val,
            "mom": mom_val,
        })

        prev_index = idx_val

    logger.info(f"[ExportPrices] Total: {len(result)} records")
    return result


def _get_next_release() -> Optional[Dict[str, Any]]:
    """FMPから次回発表日を取得（貿易データのマッピングを流用）"""
    try:
        from services.usa.fmp_next_release_utils import get_next_release_from_fmp
        return get_next_release_from_fmp(ECONALPHA_ID, country="CN")
    except Exception as e:
        logger.warning(f"[ExportPrices] Failed to get next release: {e}")
        return None


class CnExportPricesService:
    """中国輸出物価指数サービス"""

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
            logger.warning(f"[ExportPrices] File cache write error: {e}")

    def _build_payload(self) -> Dict[str, Any]:
        data = _build_data()
        latest = data[-1] if data else None
        next_release = _get_next_release()

        return {
            "data": data,
            "latest": latest,
            "metadata": {
                "indicator": "Export Price Index",
                "source": "General Administration of Customs of China (GACC)",
                "series": {
                    "index": "輸出物価指数（前年同月=100）",
                    "yoy": "前年比 (%)",
                    "mom": "前月比（index差分）",
                },
                "total_records": len(data),
                "last_fetched": datetime.now(JST).isoformat(),
            },
            "next_release": next_release,
        }

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """データ取得（キャッシュ優先）"""
        if not force_refresh:
            cached = self._from_redis()
            if cached:
                return cached
            cached = self._from_file()
            if cached:
                self._to_redis(cached)
                return cached

        payload = self._build_payload()
        self._to_redis(payload)
        self._to_file(payload)
        return payload

    def invalidate_cache(self) -> Dict[str, Any]:
        r = self._get_redis()
        if r:
            try:
                r.delete(REDIS_KEY)
            except Exception:
                pass
        if os.path.exists(FILE_CACHE_PATH):
            os.remove(FILE_CACHE_PATH)
        return {"success": True, "message": "Export Prices cache invalidated"}

    def get_cache_status(self) -> Dict[str, Any]:
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
cn_export_prices_service = CnExportPricesService()
