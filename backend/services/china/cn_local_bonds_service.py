"""
中国 地方政府債券サービス

中国財政部（MOF）の「地方政府债券发行和债务余额情况」からデータを取得

4つの派生系列を算出:
- 新規比率 (new_ratio): 当月新増合計 / 当月総発行額 × 100 (%)
- 新規専項比率 (special_ratio): 当月新増専項 / 当月新増合計 × 100 (%)
- 枠余地 (headroom): 債務限額合計 − 債務残高合計 (億元)
- コスト (cost): (当月平均発行利率 + 年初来平均発行利率) / 2 (%)

データソース: 中国財政部 https://yss.mof.gov.cn/zhuantilanmu/dfzgl/sjtj/

発表スケジュール: 月次（翌月末〜翌々月初）
"""
import json
import logging
import re
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "china" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "cn_local_bonds_cache.json"

CSV_PATH = Path(__file__).parent.parent.parent / "data" / "csv_import" / "中国地方政府債券発行・債務残高.csv"

# MOF 地方政府債券統計ページ
MOF_INDEX_BASE = "https://yss.mof.gov.cn/zhuantilanmu/dfzgl/sjtj/"

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
RETRY_BACKOFF = 3  # seconds
SLEEP_BETWEEN_REQUESTS = 1.5

# CSV列名 → インデックスマッピング
CSV_COLUMNS = [
    "period",                    # 0: 公表月
    "monthly_total",             # 1: 当月総発行額(億元)
    "monthly_new_total",         # 2: 当月新増合計(億元)
    "monthly_new_general",       # 3: 当月新増一般(億元)
    "monthly_new_special",       # 4: 当月新増専項(億元)
    "monthly_refi_total",        # 5: 当月再融資合計(億元)
    "monthly_refi_general",      # 6: 当月再融資一般(億元)
    "monthly_refi_special",      # 7: 当月再融資専項(億元)
    "monthly_avg_term",          # 8: 当月平均発行期限(年)
    "monthly_avg_rate",          # 9: 当月平均発行利率(%)
    "ytd_total",                 # 10: 年初来総発行額(億元)
    "ytd_new_total",             # 11: 年初来新増合計(億元)
    "ytd_new_general",           # 12: 年初来新増一般(億元)
    "ytd_new_special",           # 13: 年初来新増専項(億元)
    "ytd_refi_total",            # 14: 年初来再融資合計(億元)
    "ytd_refi_general",          # 15: 年初来再融資一般(億元)
    "ytd_refi_special",          # 16: 年初来再融資専項(億元)
    "ytd_avg_term",              # 17: 年初来平均発行期限(年)
    "ytd_avg_rate",              # 18: 年初来平均発行利率(%)
    "debt_limit_total",          # 19: 債務限額合計(億元)
    "debt_limit_general",        # 20: 債務限額一般(億元)
    "debt_limit_special",        # 21: 債務限額専項(億元)
    "debt_balance_total",        # 22: 債務残高合計(億元)
    "debt_balance_general",      # 23: 債務残高一般(億元)
    "debt_balance_special",      # 24: 債務残高専項(億元)
]


def _fetch_with_retry(url: str) -> Optional[str]:
    """HTTPリクエスト（リトライ付き、502対策で10回リトライ）"""
    for attempt in range(MAX_RETRY):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 502:
                wait = RETRY_BACKOFF + attempt * 2
                logger.warning(f"[LocalBonds] 502 on {url}, retry {attempt + 1}/{MAX_RETRY} in {wait}s")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return resp.text
        except requests.exceptions.RequestException as e:
            wait = RETRY_BACKOFF + attempt * 2
            logger.warning(f"[LocalBonds] Error on {url}: {e}, retry {attempt + 1}/{MAX_RETRY} in {wait}s")
            time.sleep(wait)
    logger.error(f"[LocalBonds] Failed after {MAX_RETRY} retries: {url}")
    return None


def _num(text: str) -> Optional[float]:
    """テキストから数値を抽出"""
    if not text:
        return None
    text = text.replace(",", "").replace("，", "").replace(" ", "").replace("\xa0", "")
    m = re.search(r'([\d]+\.?\d*)', text)
    if m:
        return float(m.group(1))
    return None


def _find_num(pattern: str, text: str) -> Optional[float]:
    """パターンで検索し、最初のキャプチャグループを数値として返す"""
    m = re.search(pattern, text)
    if m:
        return _num(m.group(1))
    return None


def _find_two_nums(pattern: str, text: str) -> Tuple[Optional[float], Optional[float]]:
    """パターンで検索し、2つのキャプチャグループを数値として返す"""
    m = re.search(pattern, text)
    if m:
        return _num(m.group(1)), _num(m.group(2))
    return None, None


def _extract_text(html: str) -> str:
    """HTMLからテキストを抽出"""
    soup = BeautifulSoup(html, "html.parser")
    content_div = (
        soup.find("div", class_="TRS_Editor")
        or soup.find("div", class_="my_doccontent")
        or soup.find("div", class_="content")
        or soup.find("div", id="zoom")
    )
    if not content_div:
        text = soup.get_text()
    else:
        text = content_div.get_text()
    text = re.sub(r'[\t ]+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n', text)
    return text.strip()


def _split_monthly_ytd(text: str, year: int, month: int) -> Tuple[str, str]:
    """テキストを当月部分とYTD部分に分割"""
    if month == 1:
        return text, text

    patterns = [
        rf'[（(]二[）)]\s*1\s*[-—]\s*{month}\s*月',
        rf'{year}年1\s*[-—]\s*{month}\s*月',
        rf'1\s*[-—]\s*{month}\s*月发行情况',
    ]
    split_pos = None
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            split_pos = m.start()
            break

    if split_pos is None:
        m = re.search(rf'1[-—]{month}月', text)
        if m:
            split_pos = m.start()

    if split_pos and split_pos > 50:
        return text[:split_pos], text[split_pos:]
    else:
        return text, text


def _parse_report(html: str, year: int, month: int) -> Optional[Dict[str, Any]]:
    """レポートHTMLから地方債データを抽出"""
    text = _extract_text(html)
    data: Dict[str, Any] = {}

    monthly_text, ytd_text = _split_monthly_ytd(text, year, month)

    # ===== 当月データ =====
    data["monthly_new_total"] = _find_num(
        r'发行新增债券\s*([\d,.]+)\s*亿元', monthly_text)

    g, s = _find_two_nums(
        r'发行新增债券\s*[\d,.]+\s*亿元[，,]\s*其中[，,]?\s*一般债券\s*([\d,.]+)\s*亿元[、，,]\s*专项债券\s*([\d,.]+)\s*亿元',
        monthly_text)
    data["monthly_new_general"] = g
    data["monthly_new_special"] = s

    data["monthly_refi_total"] = _find_num(
        r'发行再融资债券\s*([\d,.]+)\s*亿元', monthly_text)

    g, s = _find_two_nums(
        r'发行再融资债券\s*[\d,.]+\s*亿元[，,]\s*其中[，,]?\s*一般债券\s*([\d,.]+)\s*亿元[、，,]\s*专项债券\s*([\d,.]+)\s*亿元',
        monthly_text)
    data["monthly_refi_general"] = g
    data["monthly_refi_special"] = s

    data["monthly_total"] = _find_num(
        r'合计[，,]?\s*全国发行地方政府债券\s*([\d,.]+)\s*亿元', monthly_text)
    if data["monthly_total"] is None:
        data["monthly_total"] = _find_num(
            rf'{month}月[，,]\s*全国发行地方政府债券\s*([\d,.]+)\s*亿元', monthly_text)
    if data["monthly_total"] is None:
        if data["monthly_new_total"] is not None and data["monthly_refi_total"] is not None:
            data["monthly_total"] = data["monthly_new_total"] + data["monthly_refi_total"]

    data["monthly_avg_term"] = _find_num(
        r'地方政府债券平均发行期限\s*([\d.]+)\s*年', monthly_text)
    if data["monthly_avg_term"] is None:
        data["monthly_avg_term"] = _find_num(
            r'平均发行期限\s*([\d.]+)\s*年', monthly_text)

    data["monthly_avg_rate"] = _find_num(
        r'地方政府债券平均发行利率\s*([\d.]+)\s*%', monthly_text)
    if data["monthly_avg_rate"] is None:
        data["monthly_avg_rate"] = _find_num(
            r'平均发行利率\s*([\d.]+)\s*%', monthly_text)

    # ===== YTDデータ =====
    if month == 1:
        for key in ["total", "new_total", "new_general", "new_special",
                     "refi_total", "refi_general", "refi_special",
                     "avg_term", "avg_rate"]:
            data[f"ytd_{key}"] = data[f"monthly_{key}"]
    else:
        data["ytd_new_total"] = _find_num(
            r'发行新增(?:地方政府)?债券\s*([\d,.]+)\s*亿元', ytd_text)

        g, s = _find_two_nums(
            r'发行新增(?:地方政府)?债券\s*[\d,.]+\s*亿元[，,]\s*其中[，,]?\s*一般债券\s*([\d,.]+)\s*亿元[、，,]\s*专项债券\s*([\d,.]+)\s*亿元',
            ytd_text)
        data["ytd_new_general"] = g
        data["ytd_new_special"] = s

        data["ytd_refi_total"] = _find_num(
            r'发行再融资债券\s*([\d,.]+)\s*亿元', ytd_text)

        g, s = _find_two_nums(
            r'发行再融资债券\s*[\d,.]+\s*亿元[，,]\s*其中[，,]?\s*一般债券\s*([\d,.]+)\s*亿元[、，,]\s*专项债券\s*([\d,.]+)\s*亿元',
            ytd_text)
        data["ytd_refi_general"] = g
        data["ytd_refi_special"] = s

        data["ytd_total"] = _find_num(
            r'发行地方政府债券合计\s*([\d,.]+)\s*亿元', ytd_text)
        if data["ytd_total"] is None:
            data["ytd_total"] = _find_num(
                r'全国发行地方政府债券\s*([\d,.]+)\s*亿元', ytd_text)
        if data["ytd_total"] is None and data.get("ytd_new_total") and data.get("ytd_refi_total"):
            data["ytd_total"] = data["ytd_new_total"] + data["ytd_refi_total"]

        data["ytd_avg_term"] = _find_num(
            r'平均发行期限\s*([\d.]+)\s*年', ytd_text)
        data["ytd_avg_rate"] = _find_num(
            r'平均发行利率\s*([\d.]+)\s*%', ytd_text)

    # ===== 債務限額・残高 =====
    data["debt_limit_total"] = _find_num(
        r'地方政府债务限额[为]?\s*([\d,.]+)\s*亿元', text)
    data["debt_limit_general"] = _find_num(
        r'一般债务限额[为]?\s*([\d,.]+)\s*亿元', text)
    data["debt_limit_special"] = _find_num(
        r'专项债务限额[为]?\s*([\d,.]+)\s*亿元', text)

    data["debt_balance_total"] = _find_num(
        r'地方政府债务余额\s*([\d,.]+)\s*亿元', text)

    balance_pos = text.find('债务余额情况')
    if balance_pos == -1:
        balance_pos = text.find('债务余额')
    balance_text = text[balance_pos:] if balance_pos >= 0 else text

    data["debt_balance_general"] = _find_num(
        r'一般债务\s*([\d,.]+)\s*亿元', balance_text)
    data["debt_balance_special"] = _find_num(
        r'专项债务\s*([\d,.]+)\s*亿元', balance_text)

    return data


class CnLocalBondsService:
    """中国地方政府債券サービス"""

    DATA_CACHE_KEY = "china:cn_local_bonds:data"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """地方債データを取得"""
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": None,
                    }

        result = self._build_data(force_refresh=force_refresh)
        if result and result.get("data"):
            cache_payload = {
                **result,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)
            return result

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": None,
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "中国財政部", "error": "No data available"},
            "next_release": None,
        }

    def _build_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """CSVデータ + MOFスクレイピングでデータ構築"""
        # 1. CSV読み込み
        csv_records = self._load_csv()
        logger.info(f"[LocalBonds] CSV: {len(csv_records)} records")

        # 2. MOFスクレイピングはforce_refresh時のみ実行
        scraped_records: List[Dict[str, Any]] = []
        if force_refresh:
            scraped_records = self._scrape_mof(csv_records)
            logger.info(f"[LocalBonds] Scraped: {len(scraped_records)} records")

        # 3. マージ（スクレイピングが優先）
        merged: Dict[str, Dict[str, Any]] = {}
        for rec in csv_records:
            merged[rec["date"]] = rec
        for rec in scraped_records:
            merged[rec["date"]] = rec

        # 4. CSVに書き戻し（新データがあれば）
        if scraped_records:
            self._update_csv(merged)

        # 5. ソートして整形
        all_records = sorted(merged.values(), key=lambda x: x["date"])

        # 6. 派生系列を算出
        data_with_computed = self._compute_series(all_records)

        if not data_with_computed:
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

        latest = data_with_computed[-1]

        return {
            "data": data_with_computed,
            "latest": latest,
            "metadata": {
                "source": "中国財政部",
                "indicator": "地方政府債券発行・債務残高",
                "unit_pct": "%",
                "unit_amount": "億元",
                "frequency": "monthly",
            },
            "next_release": None,
        }

    def _load_csv(self) -> List[Dict[str, Any]]:
        """CSVから履歴データ読み込み"""
        records = []
        try:
            if not CSV_PATH.exists():
                return records
            with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
                lines = f.readlines()
            if len(lines) < 2:
                return records

            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(",")
                if len(parts) < 25:
                    continue

                # 日付変換: "2023/3" → "2023-03-01"
                date_str = self._parse_csv_date(parts[0].strip())
                if not date_str:
                    continue

                record: Dict[str, Any] = {"date": date_str}
                for i, col_name in enumerate(CSV_COLUMNS[1:], start=1):
                    val = parts[i].strip() if i < len(parts) else ""
                    record[col_name] = float(val) if val else None

                records.append(record)
        except Exception as e:
            logger.error(f"[LocalBonds] CSV load error: {e}")
        return records

    def _parse_csv_date(self, raw: str) -> Optional[str]:
        """CSV日付解析: '2023/3' → '2023-03-01'"""
        try:
            parts = raw.split("/")
            if len(parts) != 2:
                return None
            year = int(parts[0])
            month = int(parts[1])
            return f"{year}-{month:02d}-01"
        except (ValueError, IndexError):
            return None

    def _compute_series(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """4つの派生系列を算出"""
        result = []
        for rec in records:
            date = rec["date"]
            monthly_total = rec.get("monthly_total")
            monthly_new_total = rec.get("monthly_new_total")
            monthly_new_special = rec.get("monthly_new_special")
            monthly_avg_rate = rec.get("monthly_avg_rate")
            ytd_avg_rate = rec.get("ytd_avg_rate")
            debt_limit_total = rec.get("debt_limit_total")
            debt_balance_total = rec.get("debt_balance_total")

            # 新規比率 (%)
            new_ratio = None
            if monthly_new_total is not None and monthly_total and monthly_total > 0:
                new_ratio = round(monthly_new_total / monthly_total * 100, 1)

            # 新規専項比率 (%)
            special_ratio = None
            if monthly_new_special is not None and monthly_new_total and monthly_new_total > 0:
                special_ratio = round(monthly_new_special / monthly_new_total * 100, 1)

            # 枠余地 (億元)
            headroom = None
            if debt_limit_total is not None and debt_balance_total is not None:
                headroom = round(debt_limit_total - debt_balance_total, 1)

            # コスト (%)
            cost = None
            if monthly_avg_rate is not None and ytd_avg_rate is not None:
                cost = round((monthly_avg_rate + ytd_avg_rate) / 2, 2)
            elif monthly_avg_rate is not None:
                cost = monthly_avg_rate
            elif ytd_avg_rate is not None:
                cost = ytd_avg_rate

            entry = {
                "date": date,
                "new_ratio": new_ratio,
                "special_ratio": special_ratio,
                "headroom": headroom,
                "cost": cost,
                # 生データも含める（詳細表示やオーバーレイ用）
                "monthly_total": monthly_total,
                "monthly_new_total": monthly_new_total,
                "monthly_new_special": monthly_new_special,
                "monthly_avg_rate": monthly_avg_rate,
                "ytd_avg_rate": ytd_avg_rate,
                "debt_limit_total": debt_limit_total,
                "debt_balance_total": debt_balance_total,
            }
            result.append(entry)

        return result

    def _scrape_mof(self, existing_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """MOFインデックスページからスクレイピング"""
        records = []
        existing_dates = {r["date"] for r in existing_records}

        try:
            report_links = self._collect_report_links()
            logger.info(f"[LocalBonds] Found {len(report_links)} report links")

            scraped_count = 0
            for url, title, year, month in report_links:
                date_str = f"{year}-{month:02d}-01"

                # 既にCSVにあるデータはスキップ（直近6件のみスクレイピング）
                if date_str in existing_dates and scraped_count >= 6:
                    break
                if scraped_count >= 6:
                    break

                time.sleep(SLEEP_BETWEEN_REQUESTS)
                html = _fetch_with_retry(url)
                if not html:
                    continue

                data = _parse_report(html, year, month)
                if data:
                    record: Dict[str, Any] = {"date": date_str}
                    # CSV_COLUMNS[1:]のフィールド名でマッピング
                    for col_name in CSV_COLUMNS[1:]:
                        record[col_name] = data.get(col_name)
                    records.append(record)
                    scraped_count += 1
                    logger.info(f"[LocalBonds] Scraped {title}: total={data.get('monthly_total')}")

        except Exception as e:
            logger.error(f"[LocalBonds] Scraping error: {e}")
            import traceback
            traceback.print_exc()
        return records

    def _collect_report_links(self) -> List[Tuple[str, str, int, int]]:
        """インデックスページからレポートリンクを収集
        Returns: [(url, title, year, month), ...]
        """
        links = []
        # タイトルから年月を抽出するパターン
        re_title = re.compile(r'(\d{4})年(\d{1,2})月')

        for page_idx in range(3):
            if page_idx == 0:
                page_url = MOF_INDEX_BASE + "index.htm"
            else:
                page_url = MOF_INDEX_BASE + f"index_{page_idx}.htm"

            time.sleep(SLEEP_BETWEEN_REQUESTS)
            html = _fetch_with_retry(page_url)
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")
            li_box = soup.find("ul", class_="liBox")
            if not li_box:
                continue

            for li in li_box.find_all("li"):
                a_tag = li.find("a", href=True)
                if not a_tag:
                    continue
                href = a_tag["href"]
                title = a_tag.get("title", "") or a_tag.get_text(strip=True)

                # 地方政府债券レポートのみ対象
                if "地方政府债券" not in title:
                    continue

                # タイトルから年月を抽出
                m = re_title.search(title)
                if not m:
                    continue
                year = int(m.group(1))
                month = int(m.group(2))

                # 相対URL→絶対URL
                if href.startswith("./"):
                    full_url = MOF_INDEX_BASE + href[2:]
                elif href.startswith("http"):
                    full_url = href
                else:
                    full_url = MOF_INDEX_BASE + href

                links.append((full_url, title, year, month))

        return links

    def _update_csv(self, merged: Dict[str, Dict[str, Any]]) -> None:
        """マージ済みデータをCSVに書き戻す"""
        try:
            sorted_records = sorted(merged.values(), key=lambda x: x["date"])

            csv_headers = [
                "公表月",
                "当月総発行額(億元)",
                "当月新増合計(億元)", "当月新増一般(億元)", "当月新増専項(億元)",
                "当月再融資合計(億元)", "当月再融資一般(億元)", "当月再融資専項(億元)",
                "当月平均発行期限(年)", "当月平均発行利率(%)",
                "年初来総発行額(億元)",
                "年初来新増合計(億元)", "年初来新増一般(億元)", "年初来新増専項(億元)",
                "年初来再融資合計(億元)", "年初来再融資一般(億元)", "年初来再融資専項(億元)",
                "年初来平均発行期限(年)", "年初来平均発行利率(%)",
                "債務限額合計(億元)", "債務限額一般(億元)", "債務限額専項(億元)",
                "債務残高合計(億元)", "債務残高一般(億元)", "債務残高専項(億元)",
            ]

            lines = [",".join(csv_headers)]
            for rec in sorted_records:
                date_str = rec["date"]
                year = int(date_str[:4])
                month = int(date_str[5:7])
                csv_date = f"{year}/{month}"

                row_values = [csv_date]
                for col_name in CSV_COLUMNS[1:]:
                    val = rec.get(col_name)
                    if val is None:
                        row_values.append("")
                    elif isinstance(val, float) and val == int(val):
                        row_values.append(str(int(val)))
                    else:
                        row_values.append(str(val))
                lines.append(",".join(row_values))

            CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
            CSV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
            logger.info(f"[LocalBonds] Updated CSV with {len(sorted_records)} records")
        except Exception as e:
            logger.warning(f"[LocalBonds] CSV update failed: {e}")

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュ更新判定 - 1日1回(JST 12:00以降)"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)
            now = datetime.now(JST)

            today_noon = now.replace(hour=12, minute=0, second=0, microsecond=0)
            if last_updated >= today_noon:
                return False
            if now >= today_noon:
                return True
            return False
        except Exception:
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[LocalBonds] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[LocalBonds] Failed to save file cache: {e}")

    def invalidate_cache(self) -> Dict[str, Any]:
        redis_client.delete(self.DATA_CACHE_KEY)
        if DATA_CACHE_FILE.exists():
            DATA_CACHE_FILE.unlink()
        return {"success": True, "message": "Local bonds cache invalidated"}

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        return {
            "indicator": "CN Local Bonds",
            "source": "中国財政部",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトン
cn_local_bonds_service = CnLocalBondsService()
