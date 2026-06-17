"""
中国 土地売却収入サービス

中国財政部（MOF）の「財政収支情况」レポートから国有土地使用権出譲収入データを取得

指標:
- 国有土地使用権出譲収入（累計、亿元）
- 前年比（%）
- 前月比（%、累計差分から算出）

データソース: 中国財政部 https://gks.mof.gov.cn/tongjishuju/

発表スケジュール: 月次（15日〜翌月1日）
"""
import json
import logging
import re
import time
from datetime import datetime, timedelta
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
DATA_CACHE_FILE = CACHE_DIR / "cn_land_sales_income_cache.json"

CSV_PATH = Path(__file__).parent.parent.parent / "data" / "csv_import" / "中国土地売却収入.csv"

# MOF 統計データページ
MOF_INDEX_BASE = "https://gks.mof.gov.cn/tongjishuju/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

MAX_RETRY = 3            # 旧10。502継続時の過剰な待機（最大165秒/URL）を防ぐ
RETRY_BACKOFF = 3        # seconds
MAX_BACKOFF = 8          # 1回あたりの待機上限（3,6,8s で打ち切り）
SLEEP_BETWEEN_REQUESTS = 1.0

# サーキットブレーカー: 源泉(gks.mof.gov.cn)が落ちている(502/接続不可)とき、
# 1 URL でリトライを使い切ったら「源泉ダウン」とみなし、一定時間スクレイプを停止する。
# これにより 502 が続く間に多数の URL を無駄打ちしてイベントループ/スレッドを
# 数十分占有する事態を防ぐ。データは CSV 履歴にフォールバックするため取りこぼしは無く、
# 源泉復旧後（クールダウン経過後）の次回 force_refresh で通常どおり取得される。
SOURCE_DOWN_COOLDOWN_SEC = 3600  # 1時間
_source_down_until: Optional[datetime] = None

# 正規表現パターン
# 収入: "国有土地使用权出让收入41518亿元，比上年下降14.7%"
# または "国有土地使用权出让收入41518亿元，同比增长14.7%"
# または "国有土地使用权出让收入41518亿元，同比下降14.7%"
RE_LAND_INCOME = re.compile(
    r"国有土地使用权出让收入"
    r"(\d+)"
    r"亿元"
    r"[，,]"
    r"(?:比上年|同比)"
    r"(增长|下降)"
    r"(\d+\.?\d*)"
    r"%"
)

# タイトルから対象期間を抽出
# "2025年财政收支情况"             → (2025, 12)  年間
# "2025年1-11月财政收支情况"       → (2025, 11)
# "2025年1-2月财政收支情况"        → (2025, 2)
# "2025年一季度财政收支情况"       → (2025, 3)
# "2025年上半年财政收支情况"       → (2025, 6)
# "2025年前三季度财政收支情况"     → (2025, 9)
RE_TITLE_RANGE = re.compile(r"(\d{4})年(1-(\d{1,2})月|一季度|上半年|前三季度|)财政收支情况")


def _parse_title_period(title: str) -> Optional[Tuple[int, int]]:
    """タイトルから (year, end_month) を抽出"""
    m = RE_TITLE_RANGE.search(title)
    if not m:
        return None
    year = int(m.group(1))
    period_str = m.group(2)
    if not period_str:
        # "2025年财政收支情况" → 年間レポート
        return (year, 12)
    if period_str == "一季度":
        return (year, 3)
    if period_str == "上半年":
        return (year, 6)
    if period_str == "前三季度":
        return (year, 9)
    # "1-N月"
    end_month_str = m.group(3)
    if end_month_str:
        return (year, int(end_month_str))
    return None


def _fetch_with_retry(url: str) -> Optional[str]:
    """HTTPリクエスト（リトライ付き＋源泉ダウン時のサーキットブレーカー）"""
    global _source_down_until
    # 源泉ダウン中は即諦める（同一スクレイプ内の残りURLや、クールダウン中の再実行を無駄打ちしない）
    if _source_down_until and datetime.now(JST) < _source_down_until:
        return None
    for attempt in range(MAX_RETRY):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 502:
                wait = min(RETRY_BACKOFF * (attempt + 1), MAX_BACKOFF)
                logger.warning(f"[LandSales] 502 on {url}, retry {attempt + 1}/{MAX_RETRY} in {wait}s")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        except requests.exceptions.RequestException as e:
            wait = min(RETRY_BACKOFF * (attempt + 1), MAX_BACKOFF)
            logger.warning(f"[LandSales] Error on {url}: {e}, retry {attempt + 1}/{MAX_RETRY} in {wait}s")
            time.sleep(wait)
    # リトライを使い切った = 源泉ダウンとみなしクールダウンを設定（残りURLの無駄打ちを止める）
    _source_down_until = datetime.now(JST) + timedelta(seconds=SOURCE_DOWN_COOLDOWN_SEC)
    logger.error(
        f"[LandSales] Failed after {MAX_RETRY} retries: {url} "
        f"— 源泉ダウンとみなし {SOURCE_DOWN_COOLDOWN_SEC}s スクレイプ停止"
    )
    return None


class CnLandSalesIncomeService:
    """中国土地売却収入サービス"""

    DATA_CACHE_KEY = "china:cn_land_sales_income:data"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """土地売却収入データを取得"""
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
        """CSVデータ + MOFスクレイピングでデータ構築

        force_refresh=False: CSVデータのみ（高速、ダッシュボード用）
        force_refresh=True: CSV + MOFスクレイピング（更新チェック用）
        """
        # 1. CSV読み込み
        csv_records = self._load_csv()
        logger.info(f"[LandSales] CSV: {len(csv_records)} records")

        # 2. MOFスクレイピングはforce_refresh時のみ実行
        scraped_records: List[Dict[str, Any]] = []
        if force_refresh:
            scraped_records = self._scrape_mof()
            logger.info(f"[LandSales] Scraped: {len(scraped_records)} records")

        # 3. マージ（スクレイピングが優先）
        merged: Dict[str, Dict[str, Any]] = {}
        for rec in csv_records:
            key = rec["date"]
            merged[key] = rec
        for rec in scraped_records:
            key = rec["date"]
            merged[key] = rec

        # 4. CSVに書き戻し（新データがあれば）
        if scraped_records:
            self._update_csv(merged)

        # 5. ソートして整形
        all_records = sorted(merged.values(), key=lambda x: x["date"])

        # 6. 前月比（累計差分）を計算
        data_with_mom = self._calc_mom(all_records)

        if not data_with_mom:
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

        latest = data_with_mom[-1]

        return {
            "data": data_with_mom,
            "latest": latest,
            "metadata": {
                "source": "中国財政部",
                "indicator": "国有土地使用権出譲収入",
                "unit": "亿元（累計）",
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
            with open(CSV_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if len(lines) < 2:
                return records
            # ヘッダー: 公表日,国有土地使用权出让收入,同比
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(",")
                if len(parts) < 3:
                    continue
                date_raw = parts[0].strip()
                value_raw = parts[1].strip()
                yoy_raw = parts[2].strip()

                # 日付変換: "2023/3" → "2023-03-01"
                date_str = self._parse_csv_date(date_raw)
                if not date_str:
                    continue

                # 値解析: "8728亿元" → 8728.0
                value = self._parse_value(value_raw)
                if value is None:
                    continue

                # YoY解析: "-27％" → -27.0
                yoy = self._parse_yoy(yoy_raw)

                records.append({
                    "date": date_str,
                    "value": value,
                    "yoy": yoy,
                })
        except Exception as e:
            logger.error(f"[LandSales] CSV load error: {e}")
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

    def _parse_value(self, raw: str) -> Optional[float]:
        """値解析: '8728亿元' → 8728.0"""
        if not raw:
            return None
        m = re.search(r"(\d+\.?\d*)", raw)
        if m:
            return float(m.group(1))
        return None

    def _parse_yoy(self, raw: str) -> Optional[float]:
        """YoY解析: '-27％' → -27.0, '0%' → 0.0"""
        if not raw:
            return None
        # "0%" → 0.0
        raw = raw.replace("％", "%")
        m = re.search(r"([+-]?\d+\.?\d*)%", raw)
        if m:
            return float(m.group(1))
        return None

    def _scrape_mof(self) -> List[Dict[str, Any]]:
        """MOF統計データページからスクレイピング"""
        records = []
        # 源泉ダウン中（前回502でブレーカー作動）はスクレイプを丸ごとスキップし、CSV履歴で代替
        if _source_down_until and datetime.now(JST) < _source_down_until:
            logger.info(
                f"[LandSales] 源泉ダウン中 (〜{_source_down_until.strftime('%H:%M')}) のためスクレイプをスキップ（CSVキャッシュを使用）"
            )
            return records
        try:
            # インデックスページ（最大4ページ）からレポートリンクを収集
            report_links = self._collect_report_links()
            logger.info(f"[LandSales] Found {len(report_links)} fiscal report links")

            for url, title, pub_date in report_links:
                period = _parse_title_period(title)
                if not period:
                    continue
                year, end_month = period

                # 既にCSVにあるデータはスキップ
                date_str = f"{year}-{end_month:02d}-01"
                # 常に最新数件はスクレイピングする（更新がある場合があるため）
                # ただしスクレイピング数を制限（直近12件まで）
                if len(records) >= 12:
                    break

                # レポートページを取得
                time.sleep(SLEEP_BETWEEN_REQUESTS)
                html = _fetch_with_retry(url)
                if not html:
                    continue

                result = self._parse_report(html)
                if result:
                    value, yoy = result
                    records.append({
                        "date": date_str,
                        "value": value,
                        "yoy": yoy,
                    })
                    logger.info(f"[LandSales] Parsed {title}: {value}亿元, YoY={yoy}%")

        except Exception as e:
            logger.error(f"[LandSales] Scraping error: {e}")
            import traceback
            traceback.print_exc()
        return records

    def _collect_report_links(self) -> List[Tuple[str, str, str]]:
        """インデックスページからレポートリンクを収集
        Returns: [(url, title, pub_date), ...]
        """
        links = []
        for page_idx in range(4):
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

                # 財政収支情况レポートのみ対象
                if "财政收支情况" not in title:
                    continue

                # 相対URL→絶対URL
                if href.startswith("./"):
                    full_url = MOF_INDEX_BASE + href[2:]
                elif href.startswith("http"):
                    full_url = href
                else:
                    full_url = MOF_INDEX_BASE + href

                # 公表日
                span = li.find("span")
                pub_date = span.get_text(strip=True) if span else ""

                links.append((full_url, title, pub_date))

        return links

    def _parse_report(self, html: str) -> Optional[Tuple[float, float]]:
        """レポートHTMLから土地売却収入データを抽出
        Returns: (value_亿元, yoy_%)
        """
        soup = BeautifulSoup(html, "html.parser")
        # コンテンツ領域を取得
        content = (
            soup.find("div", class_="my_doccontent")
            or soup.find("div", class_="TRS_Editor")
            or soup
        )
        full_text = content.get_text("", strip=False)

        # 国有土地使用権出譲収入（収入側、支出側ではない）を抽出
        # 支出側は「出让收入相关支出」なので除外
        # 収入側パターン: "国有土地使用权出让收入XXXXX亿元，比上年下降/增长XX.X%"
        # ただし「相关支出」が後に続かないもの
        matches = list(RE_LAND_INCOME.finditer(full_text))
        if not matches:
            logger.warning("[LandSales] No land income pattern found in report")
            return None

        # 最初のマッチが収入側（2番目は支出側「相关支出」）
        m = matches[0]
        value = float(m.group(1))
        direction = m.group(2)
        pct = float(m.group(3))
        yoy = pct if direction == "增长" else -pct

        return (value, yoy)

    def _calc_mom(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """累計データから前月比（累計差分）を計算

        累計データなので「前月からの増分」= 当月累計 - 前月累計
        ただし年初（2月データ＝1-2月累計）は前月がないため増分=累計そのまま
        前月比 = (当月増分 - 前年同月増分) / 前年同月増分 × 100
        → ここでは単純に月次増分（当月累計-前月累計）を計算する
        """
        result = []
        prev_value: Optional[float] = None
        prev_year: Optional[int] = None

        for rec in records:
            date_str = rec["date"]
            year = int(date_str[:4])
            month = int(date_str[5:7])
            value = rec["value"]
            yoy = rec.get("yoy")

            # 月次増分の計算
            monthly_increment = None
            if month == 2 or month == 1:
                # 1-2月累計 → 増分 = 累計そのまま
                monthly_increment = value
                prev_value = None  # 年初リセット
            elif prev_value is not None and prev_year == year:
                monthly_increment = round(value - prev_value, 1)

            # 前月比は月次増分の前月比較で計算するが、
            # 累計の性質上、単純な前月比は意味が薄いため、
            # ここでは月次増分を記録し、前月比は前月増分との差分割合
            mom = None
            if len(result) >= 1 and monthly_increment is not None:
                prev_rec = result[-1]
                prev_increment = prev_rec.get("monthly_increment")
                if prev_increment is not None and prev_increment != 0:
                    mom = round((monthly_increment - prev_increment) / abs(prev_increment) * 100, 1)

            entry = {
                "date": date_str,
                "value": value,
                "yoy": yoy,
                "mom": mom,
                "monthly_increment": monthly_increment,
            }
            result.append(entry)

            prev_value = value
            prev_year = year

        return result

    def _update_csv(self, merged: Dict[str, Dict[str, Any]]) -> None:
        """マージ済みデータをCSVに書き戻す"""
        try:
            sorted_records = sorted(merged.values(), key=lambda x: x["date"])
            lines = ["公表日,国有土地使用权出让收入,同比"]
            for rec in sorted_records:
                date_str = rec["date"]
                # YYYY-MM-01 → YYYY/M
                year = int(date_str[:4])
                month = int(date_str[5:7])
                csv_date = f"{year}/{month}"

                value = rec.get("value")
                yoy = rec.get("yoy")

                value_str = f"{int(value)}亿元" if value is not None else ""
                yoy_str = f"{yoy}%" if yoy is not None else ""

                lines.append(f"{csv_date},{value_str},{yoy_str}")
            CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
            CSV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
            logger.info(f"[LandSales] Updated CSV with {len(sorted_records)} records")
        except Exception as e:
            logger.warning(f"[LandSales] CSV update failed: {e}")

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュ更新判定 - 1日1回(JST 12:00以降)"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)
            now = datetime.now(JST)

            # 同日のJST12:00以降にすでに更新済みなら更新不要
            today_noon = now.replace(hour=12, minute=0, second=0, microsecond=0)
            if last_updated >= today_noon:
                return False
            # JST12:00を過ぎていて、最終更新が今日の12:00より前なら更新
            if now >= today_noon:
                return True
            # 12:00前なら更新不要（前日の更新が有効）
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
            logger.error(f"[LandSales] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[LandSales] Failed to save file cache: {e}")

    def invalidate_cache(self) -> Dict[str, Any]:
        redis_client.delete(self.DATA_CACHE_KEY)
        if DATA_CACHE_FILE.exists():
            DATA_CACHE_FILE.unlink()
        return {"success": True, "message": "Land sales income cache invalidated"}

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        return {
            "indicator": "CN Land Sales Income",
            "source": "中国財政部",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトン
cn_land_sales_income_service = CnLandSalesIncomeService()
