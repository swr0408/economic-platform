"""
Treasury Quarterly Refunding サービス

米財務省四半期リファンディング関連文書を自動取得・DB蓄積・提供する。

文書タイプ:
- policy_statement:    Policy Statement（入札サイズ・資金調達額等）
- financing_estimates: Marketable Borrowing Estimates（借入見込み）
- tbac_report:         TBAC Report to Secretary
- tbac_minutes:        TBAC Minutes

取得フロー:
1. Index page (most-recent-quarterly-refunding-documents) からリンク発見
2. Press release ページからテキスト抽出 + メトリクス正規表現パース
3. XML (Auction Schedule / Buyback Schedule) を構造化保存
4. DB蓄積 → Redis/ファイルキャッシュ

更新スケジュール:
- 2月/5月/8月/11月 第1週にFinancing Estimates + Policy Statement等公開
"""
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

JST = ZoneInfo("Asia/Tokyo")
ET_TZ = ZoneInfo("America/New_York")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "quarterly_refunding_cache.json"

INDEX_URL = (
    "https://home.treasury.gov/policy-issues/financing-the-government"
    "/quarterly-refunding/most-recent-quarterly-refunding-documents"
)
BASE_URL = "https://home.treasury.gov"

# quarter_label 正規化マップ
QUARTER_MAP = {
    "1st": "Q1", "2nd": "Q2", "3rd": "Q3", "4th": "Q4",
}

# document_type 判定キーワード
DOC_TYPE_KEYWORDS = {
    "policy_statement": ["Policy Statement"],
    "financing_estimates": ["Financing Estimates", "Marketable Borrowing"],
    "tbac_report": ["TBAC Report", "Report to the Secretary"],
    "tbac_minutes": ["TBAC Minutes", "Minutes of the Meeting"],
}

# Auction size テーブルの年限キー
TENORS = ["2y", "3y", "5y", "7y", "10y", "20y", "30y", "frn"]


class QuarterlyRefundingService:
    """Treasury Quarterly Refunding サービス"""

    DATA_CACHE_KEY = "usa:quarterly_refunding:data"

    # ==================================================================
    # メイン取得メソッド
    # ==================================================================

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """四半期リファンディングデータを取得"""
        # Redisキャッシュ
        if not force_refresh:
            cached = redis_client.get(self.DATA_CACHE_KEY)
            if cached:
                cached["cached"] = True
                cached["source"] = "redis"
                return cached

        # ファイルキャッシュ
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                file_cache["cached"] = True
                file_cache["source"] = "file"
                return file_cache

        # force_refresh: index page scrape → DB保存
        if force_refresh:
            try:
                self._scrape_and_store()
            except Exception as e:
                print(f"[QR] Scrape error: {e}")

        # DBから読み出し
        result = self._load_from_db()
        if result and result.get("events"):
            redis_client.set(self.DATA_CACHE_KEY, result, expire=0)
            self._save_file_cache(result)
            result["cached"] = False
            result["source"] = "database"
            return result

        return {
            "quarter_label": None,
            "next_release": None,
            "events": {},
            "auction_schedule": [],
            "buyback_schedule": [],
            "metadata": self._metadata(),
            "cached": False,
            "source": "empty",
            "last_updated": datetime.now(JST).isoformat(),
        }

    # ==================================================================
    # Index page スクレイピング
    # ==================================================================

    def _scrape_and_store(self) -> None:
        """Index page をスクレイプし、新規文書をDB保存"""
        import requests
        from bs4 import BeautifulSoup

        print(f"[QR] Scraping index page: {INDEX_URL}")
        resp = requests.get(INDEX_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0 (EconAlpha)"})
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # quarter_label 抽出: "2026 - 1st Quarter"
        quarter_label = self._extract_quarter_label(soup)
        if not quarter_label:
            print("[QR] Could not extract quarter_label")
            return
        print(f"[QR] Quarter: {quarter_label}")

        # next_release 抽出
        next_release = self._extract_next_release(soup)
        if next_release:
            print(f"[QR] Next release: {next_release}")

        # 既存のis_currentをFALSEに
        self._clear_current_flags()

        # Press release リンク収集
        press_links = self._extract_press_release_links(soup)
        for doc_type, url, title in press_links:
            self._process_press_release(quarter_label, doc_type, url, title)

        # XML リンク収集・処理
        xml_links = self._extract_xml_links(soup)
        for xml_type, url in xml_links:
            if xml_type == "auction":
                self._process_auction_xml(quarter_label, url)
            elif xml_type == "buyback":
                self._process_buyback_xml(quarter_label, url)

    def _extract_quarter_label(self, soup) -> Optional[str]:
        """ページからquarter_labelを抽出: '2026 - 1st Quarter' → '2026-Q1'"""
        text = soup.get_text()
        m = re.search(r"(\d{4})\s*[-–]\s*(1st|2nd|3rd|4th)\s*Quarter", text)
        if m:
            year = m.group(1)
            q = QUARTER_MAP.get(m.group(2), m.group(2))
            return f"{year}-{q}"
        return None

    def _extract_next_release(self, soup) -> Optional[str]:
        """'The next release is scheduled for ...' から日付を抽出"""
        text = soup.get_text()
        m = re.search(
            r"next\s+release\s+is\s+scheduled\s+for\s+(\w+\s+\d{1,2},?\s+\d{4})",
            text, re.IGNORECASE,
        )
        if m:
            try:
                dt = datetime.strptime(m.group(1).replace(",", ""), "%B %d %Y")
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
        return None

    def _extract_press_release_links(self, soup) -> List[Tuple[str, str, str]]:
        """Press release リンクを(doc_type, url, title)のリストで返す"""
        results = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/news/press-releases/" not in href:
                continue
            link_text = a.get_text(strip=True)
            if not link_text:
                continue

            url = href if href.startswith("http") else BASE_URL + href
            doc_type = self._classify_document(link_text)
            if doc_type:
                results.append((doc_type, url, link_text))

        return results

    def _extract_xml_links(self, soup) -> List[Tuple[str, str]]:
        """XML リンクを(type, url)のリストで返す"""
        results = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href.endswith(".xml"):
                continue
            url = href if href.startswith("http") else BASE_URL + href
            lower = href.lower()
            if "auction" in lower:
                results.append(("auction", url))
            elif "buyback" in lower:
                results.append(("buyback", url))
        return results

    def _classify_document(self, link_text: str) -> Optional[str]:
        """リンクテキストからdocument_typeを判定"""
        for doc_type, keywords in DOC_TYPE_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in link_text.lower():
                    return doc_type
        return None

    # ==================================================================
    # Press release 処理
    # ==================================================================

    def _process_press_release(
        self, quarter_label: str, doc_type: str, url: str, title: str
    ) -> None:
        """Press releaseを取得・パース・DB保存"""
        import requests
        from bs4 import BeautifulSoup

        try:
            print(f"[QR] Fetching {doc_type}: {url}")
            resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (EconAlpha)"})
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            # メインコンテンツ抽出
            content = soup.find("div", class_="field--type-text-long")
            if not content:
                content = soup.find("article") or soup.find("main")
            raw_text = content.get_text("\n", strip=True) if content else ""

            # published_at 抽出
            published_at = self._extract_published_at(soup)

            # イベントDB保存
            event_id = self._upsert_event({
                "quarter_label": quarter_label,
                "published_at": published_at,
                "document_type": doc_type,
                "title": title,
                "source_url": url,
                "raw_text": raw_text,
                "is_current": True,
            })

            if event_id is None:
                return

            # メトリクス抽出・保存
            metrics = []
            if doc_type == "policy_statement":
                metrics = self._parse_policy_statement_metrics(raw_text)
            elif doc_type == "financing_estimates":
                metrics = self._parse_financing_estimates_metrics(raw_text)

            if metrics:
                self._upsert_metrics(event_id, metrics)
                print(f"[QR] Stored {len(metrics)} metrics for {doc_type}")

        except Exception as e:
            print(f"[QR] Error processing {doc_type} {url}: {e}")

    def _extract_published_at(self, soup) -> Optional[str]:
        """Press releaseの発表日時を抽出"""
        # <time> タグから
        time_el = soup.find("time")
        if time_el and time_el.get("datetime"):
            return time_el["datetime"]
        # テキストから日付抽出
        date_el = soup.find("div", class_="field--name-field-press-release-date")
        if date_el:
            text = date_el.get_text(strip=True)
            try:
                dt = datetime.strptime(text, "%B %d, %Y")
                return dt.strftime("%Y-%m-%dT00:00:00-05:00")
            except ValueError:
                pass
        return None

    # ==================================================================
    # Policy Statement メトリクスパース
    # ==================================================================

    def _parse_policy_statement_metrics(self, text: str) -> List[Dict]:
        """Policy Statementからメトリクスを抽出"""
        metrics = []

        # Total offering: "$125 billion in Treasury securities"
        m = re.search(r"\$(\d+(?:\.\d+)?)\s*billion\s+(?:of|in)\s+Treasury\s+securities", text, re.IGNORECASE)
        if m:
            metrics.append({"key": "refunding_total", "value": float(m.group(1)), "unit": "billion_usd", "label": "Total Offering"})

        # New cash raised: "approximately $34.8 billion"
        m = re.search(r"(?:new\s+cash|raise)\D{0,40}?\$(\d+(?:\.\d+)?)\s*billion", text, re.IGNORECASE)
        if m:
            metrics.append({"key": "new_cash_raised", "value": float(m.group(1)), "unit": "billion_usd", "label": "New Cash Raised"})

        # Maturing securities
        m = re.search(r"(?:matur\w+)\D{0,40}?\$(\d+(?:\.\d+)?)\s*billion", text, re.IGNORECASE)
        if m:
            metrics.append({"key": "maturing_securities", "value": float(m.group(1)), "unit": "billion_usd", "label": "Maturing Securities"})

        # Refunding sizes: "3-year note ... $58 billion"
        for tenor_years, key in [(3, "refunding_3y"), (10, "refunding_10y")]:
            m = re.search(rf"{tenor_years}-year\s+note\D{{0,30}}?\$(\d+(?:\.\d+)?)\s*billion", text, re.IGNORECASE)
            if m:
                metrics.append({"key": key, "value": float(m.group(1)), "unit": "billion_usd", "label": f"{tenor_years}-Year Note"})

        # 30-year bond
        m = re.search(r"30-year\s+bond\D{0,30}?\$(\d+(?:\.\d+)?)\s*billion", text, re.IGNORECASE)
        if m:
            metrics.append({"key": "refunding_30y", "value": float(m.group(1)), "unit": "billion_usd", "label": "30-Year Bond"})

        # Buyback liquidity support: "up to $38 billion"
        m = re.search(r"(?:off-the-run|liquidity\s+support)\D{0,60}?\$(\d+(?:\.\d+)?)\s*billion", text, re.IGNORECASE)
        if m:
            metrics.append({"key": "buyback_liquidity_max", "value": float(m.group(1)), "unit": "billion_usd", "label": "Buyback Liquidity Support Max"})

        # Buyback cash management: "up to $75 billion"
        m = re.search(r"(?:cash\s+management)\D{0,60}?\$(\d+(?:\.\d+)?)\s*billion", text, re.IGNORECASE)
        if m:
            metrics.append({"key": "buyback_cash_mgmt_max", "value": float(m.group(1)), "unit": "billion_usd", "label": "Buyback Cash Management Max"})

        # End-of-month cash balance: "$850 billion"
        m = re.search(r"(?:end[- ]of[- ]\w+\s+(?:cash\s+)?balance|assumed\D{0,20}balance)\D{0,30}?\$(\d+(?:,\d+)*(?:\.\d+)?)\s*billion", text, re.IGNORECASE)
        if m:
            val = float(m.group(1).replace(",", ""))
            metrics.append({"key": "cash_balance_eom", "value": val, "unit": "billion_usd", "label": "Assumed End-of-Quarter Cash Balance"})

        # Auction size table 抽出
        metrics.extend(self._parse_auction_size_table(text))

        return metrics

    def _parse_auction_size_table(self, text: str) -> List[Dict]:
        """Policy Statement内のAuction Sizeテーブルを抽出"""
        metrics = []
        # テーブル行パターン: "Nov-25  69  58  70  44  42  16  25  28"
        # または: "Feb-26  69  58  70  44  42  16  25  28"
        month_map = {
            "jan": "01", "feb": "02", "mar": "03", "apr": "04",
            "may": "05", "jun": "06", "jul": "07", "aug": "08",
            "sep": "09", "oct": "10", "nov": "11", "dec": "12",
        }

        # 各行を検索: "Mon-YY" + 8個の数値
        pattern = re.compile(
            r"(\w{3})-(\d{2})\s+"
            r"(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)",
        )

        for m in pattern.finditer(text):
            mon_str = m.group(1).lower()
            yr_str = m.group(2)
            if mon_str not in month_map:
                continue

            month = month_map[mon_str]
            year = f"20{yr_str}"
            yyyymm = f"{year}{month}"

            values = [int(m.group(i)) for i in range(3, 11)]
            for i, tenor in enumerate(TENORS):
                key = f"auction_size_{tenor}_{yyyymm}"
                label_month = f"{m.group(1).capitalize()}-{yr_str}"
                metrics.append({
                    "key": key,
                    "value": float(values[i]),
                    "unit": "billion_usd",
                    "label": f"{tenor.upper()} {label_month}",
                })

        return metrics

    # ==================================================================
    # Financing Estimates メトリクスパース
    # ==================================================================

    def _parse_financing_estimates_metrics(self, text: str) -> List[Dict]:
        """Financing Estimatesからメトリクスを抽出"""
        metrics = []

        # パターン: "$574 billion in ... net marketable debt ... $850 billion"
        # Current quarter
        m = re.search(
            r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"[-–]\w+\s+\d{4}\s+quarter\D{0,20}?\$(\d+(?:,?\d+)*)\s*billion\D{0,80}?"
            r"(?:end[- ]of[- ]\w+\s+)?(?:cash\s+)?balance\s+of\s+\$(\d+(?:,?\d+)*)\s*billion",
            text, re.IGNORECASE | re.DOTALL,
        )
        if m:
            borrow = float(m.group(1).replace(",", ""))
            cash = float(m.group(2).replace(",", ""))
            metrics.append({"key": "borrowing_estimate_current_qtr", "value": borrow, "unit": "billion_usd", "label": "Current Quarter Borrowing Estimate"})
            metrics.append({"key": "assumed_end_cash_balance_current_qtr", "value": cash, "unit": "billion_usd", "label": "Current Quarter End Cash Balance"})

        # Next quarter - 次の段落
        lines = text.split("\n")
        for i, line in enumerate(lines):
            # "$109 billion ... April-June" パターン
            m2 = re.search(
                r"(?:April|May|June|July|August|September|October|November|December|January|February|March)"
                r"[-–]\w+\s+\d{4}\D{0,20}?\$(\d+(?:,?\d+)*)\s*billion\D{0,80}?"
                r"(?:end[- ]of[- ]\w+\s+)?(?:cash\s+)?balance\s+of\s+\$(\d+(?:,?\d+)*)\s*billion",
                line, re.IGNORECASE,
            )
            if m2 and "borrowing_estimate_next_qtr" not in [m.get("key") for m in metrics]:
                borrow = float(m2.group(1).replace(",", ""))
                cash = float(m2.group(2).replace(",", ""))
                metrics.append({"key": "borrowing_estimate_next_qtr", "value": borrow, "unit": "billion_usd", "label": "Next Quarter Borrowing Estimate"})
                metrics.append({"key": "assumed_end_cash_balance_next_qtr", "value": cash, "unit": "billion_usd", "label": "Next Quarter End Cash Balance"})

        # Previous quarter actual
        m = re.search(
            r"(?:actual\s+)?(?:net\s+)?(?:privately[- ]held\s+)?(?:net\s+)?marketable\s+(?:debt\s+)?borrowing\s+(?:was|of)\s+\$(\d+(?:,?\d+)*)\s*billion",
            text, re.IGNORECASE,
        )
        if m:
            metrics.append({"key": "actual_borrowing_prev_qtr", "value": float(m.group(1).replace(",", "")), "unit": "billion_usd", "label": "Previous Quarter Actual Borrowing"})

        # Previous estimate
        m = re.search(
            r"(?:lower|higher)\s+than\s+(?:the\s+)?(?:\$)?(\d+(?:,?\d+)*)\s*billion\s+(?:announced|estimated)",
            text, re.IGNORECASE,
        )
        if m:
            metrics.append({"key": "prev_estimate_current_qtr", "value": float(m.group(1).replace(",", "")), "unit": "billion_usd", "label": "Previous Estimate"})

        return metrics

    # ==================================================================
    # XML 処理
    # ==================================================================

    def _process_auction_xml(self, quarter_label: str, url: str) -> None:
        """Auction Schedule XMLを取得・パース・DB保存"""
        import requests

        try:
            print(f"[QR] Fetching auction XML: {url}")
            resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (EconAlpha)"})
            resp.raise_for_status()

            root = ET.fromstring(resp.content)
            records = []

            for entry in root.findall(".//AuctionCalendarDate"):
                # ホリデーエントリをスキップ
                if entry.find("HolidayName") is not None:
                    continue

                security_term = self._xml_text(entry, "SecurityTermWeekYear")
                security_type = self._xml_text(entry, "SecurityType")
                if not security_term or not security_type:
                    continue

                records.append({
                    "quarter_label": quarter_label,
                    "security_term": security_term,
                    "security_type": security_type,
                    "reopening": self._xml_text(entry, "ReOpeningIndicator") == "Y",
                    "is_tips": self._xml_text(entry, "TIPS") == "Y",
                    "is_frn": self._xml_text(entry, "FloatingRate") == "Y",
                    "announcement_date": self._xml_date(entry, "AnnouncementDate"),
                    "auction_date": self._xml_date(entry, "AuctionDate"),
                    "settlement_date": self._xml_date(entry, "SettlementDate"),
                    "source_url": url,
                })

            if records:
                self._upsert_auction_schedule(quarter_label, records)
                print(f"[QR] Stored {len(records)} auction entries")

        except Exception as e:
            print(f"[QR] Error processing auction XML: {e}")

    def _process_buyback_xml(self, quarter_label: str, url: str) -> None:
        """Buyback Schedule XMLを取得・パース・DB保存"""
        import requests

        try:
            print(f"[QR] Fetching buyback XML: {url}")
            resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (EconAlpha)"})
            resp.raise_for_status()

            root = ET.fromstring(resp.content)
            records = []

            for entry in root.findall(".//BuybackCalendarDate"):
                purchase_bucket = self._xml_text(entry, "PurchaseBucketName")
                if not purchase_bucket:
                    continue

                min_amt = self._xml_text(entry, "MinimumPurchaseAmountDollars")
                max_amt = self._xml_text(entry, "MaximumPurchaseAmountDollars")

                records.append({
                    "quarter_label": quarter_label,
                    "purchase_bucket": purchase_bucket,
                    "security_type": self._xml_text(entry, "SecurityType"),
                    "operation_type": self._xml_text(entry, "OperationType"),
                    "min_amount": float(min_amt.replace(",", "")) if min_amt else None,
                    "max_amount": float(max_amt.replace(",", "")) if max_amt else None,
                    "maturity_range_start": self._xml_date(entry, "MaturityDateRangeStart"),
                    "maturity_range_end": self._xml_date(entry, "MaturityDateRangeEnd"),
                    "announcement_date": self._xml_date(entry, "AnnouncementDate"),
                    "operation_date": self._xml_date(entry, "OperationDate"),
                    "settlement_date": self._xml_date(entry, "SettlementDate"),
                    "source_url": url,
                })

            if records:
                self._upsert_buyback_schedule(quarter_label, records)
                print(f"[QR] Stored {len(records)} buyback entries")

        except Exception as e:
            print(f"[QR] Error processing buyback XML: {e}")

    def _xml_text(self, el, tag: str) -> Optional[str]:
        """XML要素からテキスト取得"""
        child = el.find(tag)
        return child.text.strip() if child is not None and child.text else None

    def _xml_date(self, el, tag: str) -> Optional[str]:
        """XML要素から日付文字列取得 (YYYY-MM-DD)"""
        text = self._xml_text(el, tag)
        if text:
            # "2026-02-10" or "02/10/2026" 等
            for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
                try:
                    return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue
        return None

    # ==================================================================
    # DB操作
    # ==================================================================

    def _upsert_event(self, record: Dict) -> Optional[int]:
        """イベントをupsertしてIDを返す"""
        try:
            from core.database import get_db_connection

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO treasury_quarterly_refunding_events
                            (quarter_label, published_at, document_type, title, source_url, raw_text, is_current)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (quarter_label, document_type) DO UPDATE SET
                            published_at = COALESCE(EXCLUDED.published_at, treasury_quarterly_refunding_events.published_at),
                            title = COALESCE(EXCLUDED.title, treasury_quarterly_refunding_events.title),
                            source_url = EXCLUDED.source_url,
                            raw_text = COALESCE(EXCLUDED.raw_text, treasury_quarterly_refunding_events.raw_text),
                            is_current = EXCLUDED.is_current,
                            updated_at = NOW()
                        RETURNING id
                        """,
                        (
                            record["quarter_label"],
                            record.get("published_at"),
                            record["document_type"],
                            record.get("title"),
                            record["source_url"],
                            record.get("raw_text"),
                            record.get("is_current", True),
                        ),
                    )
                    result = cur.fetchone()
                conn.commit()
                return result[0] if result else None
        except Exception as e:
            print(f"[QR] DB upsert event error: {e}")
            return None

    def _upsert_metrics(self, event_id: int, metrics: List[Dict]) -> None:
        """メトリクスをupsert"""
        try:
            from core.database import get_db_connection

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    for m in metrics:
                        cur.execute(
                            """
                            INSERT INTO treasury_quarterly_refunding_metrics
                                (event_id, metric_key, metric_value, metric_unit, metric_label)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (event_id, metric_key) DO UPDATE SET
                                metric_value = EXCLUDED.metric_value,
                                metric_unit = EXCLUDED.metric_unit,
                                metric_label = EXCLUDED.metric_label
                            """,
                            (event_id, m["key"], m["value"], m.get("unit"), m.get("label")),
                        )
                conn.commit()
        except Exception as e:
            print(f"[QR] DB upsert metrics error: {e}")

    def _upsert_auction_schedule(self, quarter_label: str, records: List[Dict]) -> None:
        """Auction scheduleをupsert"""
        try:
            from core.database import get_db_connection

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # 既存データ削除（quarter単位で入れ替え）
                    cur.execute(
                        "DELETE FROM treasury_auction_schedule WHERE quarter_label = %s",
                        (quarter_label,),
                    )
                    for r in records:
                        cur.execute(
                            """
                            INSERT INTO treasury_auction_schedule
                                (quarter_label, security_term, security_type, reopening, is_tips, is_frn,
                                 announcement_date, auction_date, settlement_date, source_url)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                r["quarter_label"], r["security_term"], r["security_type"],
                                r["reopening"], r["is_tips"], r["is_frn"],
                                r["announcement_date"], r["auction_date"], r["settlement_date"],
                                r["source_url"],
                            ),
                        )
                conn.commit()
        except Exception as e:
            print(f"[QR] DB upsert auction schedule error: {e}")

    def _upsert_buyback_schedule(self, quarter_label: str, records: List[Dict]) -> None:
        """Buyback scheduleをupsert"""
        try:
            from core.database import get_db_connection

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM treasury_buyback_schedule WHERE quarter_label = %s",
                        (quarter_label,),
                    )
                    for r in records:
                        cur.execute(
                            """
                            INSERT INTO treasury_buyback_schedule
                                (quarter_label, purchase_bucket, security_type, operation_type,
                                 min_amount, max_amount, maturity_range_start, maturity_range_end,
                                 announcement_date, operation_date, settlement_date, source_url)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                r["quarter_label"], r["purchase_bucket"], r["security_type"],
                                r["operation_type"], r.get("min_amount"), r.get("max_amount"),
                                r.get("maturity_range_start"), r.get("maturity_range_end"),
                                r["announcement_date"], r["operation_date"], r.get("settlement_date"),
                                r["source_url"],
                            ),
                        )
                conn.commit()
        except Exception as e:
            print(f"[QR] DB upsert buyback schedule error: {e}")

    def _clear_current_flags(self) -> None:
        """全既存データのis_currentをFALSEに"""
        try:
            from core.database import get_db_connection

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE treasury_quarterly_refunding_events SET is_current = FALSE WHERE is_current = TRUE"
                    )
                conn.commit()
        except Exception as e:
            print(f"[QR] DB clear current flags error: {e}")

    # ==================================================================
    # DB読み出し
    # ==================================================================

    def _load_from_db(self) -> Dict[str, Any]:
        """DBから最新四半期のデータを読み出し"""
        try:
            from core.database import get_db_connection

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # 最新のquarter_label取得
                    cur.execute(
                        """
                        SELECT DISTINCT quarter_label FROM treasury_quarterly_refunding_events
                        WHERE is_current = TRUE
                        ORDER BY quarter_label DESC LIMIT 1
                        """
                    )
                    row = cur.fetchone()
                    if not row:
                        return {}
                    quarter_label = row[0]

                    # イベント + メトリクス取得
                    events = self._load_events_with_metrics(cur, quarter_label)

                    # Auction schedule
                    cur.execute(
                        """
                        SELECT security_term, security_type, reopening, is_tips, is_frn,
                               announcement_date, auction_date, settlement_date, source_url
                        FROM treasury_auction_schedule
                        WHERE quarter_label = %s
                        ORDER BY auction_date, security_type
                        """,
                        (quarter_label,),
                    )
                    auction_rows = cur.fetchall()

                    # Buyback schedule
                    cur.execute(
                        """
                        SELECT purchase_bucket, security_type, operation_type,
                               min_amount, max_amount, maturity_range_start, maturity_range_end,
                               announcement_date, operation_date, settlement_date, source_url
                        FROM treasury_buyback_schedule
                        WHERE quarter_label = %s
                        ORDER BY operation_date
                        """,
                        (quarter_label,),
                    )
                    buyback_rows = cur.fetchall()

            # レスポンス構築
            auction_schedule = [
                {
                    "security_term": r[0],
                    "security_type": r[1],
                    "reopening": r[2],
                    "is_tips": r[3],
                    "is_frn": r[4],
                    "announcement_date": r[5].isoformat() if r[5] else None,
                    "auction_date": r[6].isoformat() if r[6] else None,
                    "settlement_date": r[7].isoformat() if r[7] else None,
                    "source_url": r[8],
                }
                for r in auction_rows
            ]

            buyback_schedule = [
                {
                    "purchase_bucket": r[0],
                    "security_type": r[1],
                    "operation_type": r[2],
                    "min_amount": float(r[3]) if r[3] else None,
                    "max_amount": float(r[4]) if r[4] else None,
                    "maturity_range_start": r[5].isoformat() if r[5] else None,
                    "maturity_range_end": r[6].isoformat() if r[6] else None,
                    "announcement_date": r[7].isoformat() if r[7] else None,
                    "operation_date": r[8].isoformat() if r[8] else None,
                    "settlement_date": r[9].isoformat() if r[9] else None,
                    "source_url": r[10],
                }
                for r in buyback_rows
            ]

            return {
                "quarter_label": quarter_label,
                "next_release": None,  # refreshで更新
                "events": events,
                "auction_schedule": auction_schedule,
                "buyback_schedule": buyback_schedule,
                "metadata": self._metadata(),
                "last_updated": datetime.now(JST).isoformat(),
            }

        except Exception as e:
            print(f"[QR] DB read error: {e}")
            return {}

    def _load_events_with_metrics(self, cur, quarter_label: str) -> Dict[str, Any]:
        """イベント + メトリクスをdoc_type別辞書で返す"""
        cur.execute(
            """
            SELECT e.id, e.document_type, e.published_at, e.title, e.source_url, e.raw_text,
                   m.metric_key, m.metric_value, m.metric_unit, m.metric_label
            FROM treasury_quarterly_refunding_events e
            LEFT JOIN treasury_quarterly_refunding_metrics m ON m.event_id = e.id
            WHERE e.quarter_label = %s AND e.is_current = TRUE
            ORDER BY e.document_type, m.metric_key
            """,
            (quarter_label,),
        )
        rows = cur.fetchall()

        events = {}
        for row in rows:
            _, doc_type, published_at, title, source_url, raw_text, mk, mv, mu, ml = row
            if doc_type not in events:
                events[doc_type] = {
                    "published_at": published_at.isoformat() if published_at else None,
                    "title": title,
                    "source_url": source_url,
                    "metrics": {},
                }
                # raw_textはPolicy Statement / TBAC のみ含める（サイズ制限のため）
                if doc_type in ("tbac_report", "tbac_minutes"):
                    events[doc_type]["raw_text"] = raw_text

            if mk:
                events[doc_type]["metrics"][mk] = {
                    "value": float(mv) if mv is not None else None,
                    "unit": mu,
                    "label": ml,
                }

        # Policy Statement: auction_size_table構造化
        ps = events.get("policy_statement")
        if ps:
            ps["auction_size_table"] = self._build_auction_size_table(ps["metrics"])
            # bill/tips/buyback guidance をraw_textから抽出
            raw = self._get_raw_text_for_event(quarter_label, "policy_statement")
            if raw:
                ps["bill_guidance"] = self._extract_guidance(raw, "bill")
                ps["tips_guidance"] = self._extract_guidance(raw, "TIPS")
                ps["buyback_guidance"] = self._extract_guidance(raw, "buyback")

        return events

    def _get_raw_text_for_event(self, quarter_label: str, doc_type: str) -> Optional[str]:
        """特定イベントのraw_textを取得"""
        try:
            from core.database import get_db_connection

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT raw_text FROM treasury_quarterly_refunding_events WHERE quarter_label = %s AND document_type = %s",
                        (quarter_label, doc_type),
                    )
                    row = cur.fetchone()
                    return row[0] if row else None
        except Exception:
            return None

    def _build_auction_size_table(self, metrics: Dict) -> List[Dict]:
        """metrics辞書からauction_size_tableを構築"""
        # auction_size_{tenor}_{yyyymm} → 月別テーブル
        months = {}
        for key, m in metrics.items():
            if not key.startswith("auction_size_"):
                continue
            parts = key.split("_")  # auction_size_2y_202602
            if len(parts) != 4:
                continue
            tenor = parts[2]
            yyyymm = parts[3]
            if yyyymm not in months:
                months[yyyymm] = {"month": f"{yyyymm[:4]}-{yyyymm[4:]}"}
            months[yyyymm][tenor] = m["value"]

        return sorted(months.values(), key=lambda x: x["month"])

    def _extract_guidance(self, text: str, keyword: str) -> Optional[str]:
        """テキストからキーワードを含む段落を抽出"""
        paragraphs = text.split("\n")
        results = []
        for p in paragraphs:
            p = p.strip()
            if keyword.lower() in p.lower() and len(p) > 30:
                results.append(p)
        return "\n".join(results[:3]) if results else None

    # ==================================================================
    # メタデータ・キャッシュ
    # ==================================================================

    def _metadata(self) -> Dict[str, Any]:
        return {
            "source": "U.S. Department of the Treasury",
            "source_url": INDEX_URL,
            "frequency": "quarterly",
            "description": "Treasury Quarterly Refunding Documents",
            "documents": {
                "policy_statement": "Policy Statement（入札サイズ・新規資金調達額）",
                "financing_estimates": "Marketable Borrowing Estimates（借入見込み）",
                "tbac_report": "TBAC Report to Secretary",
                "tbac_minutes": "TBAC Minutes",
                "auction_schedule": "Tentative Auction Schedule (XML)",
                "buyback_schedule": "Tentative Buyback Schedule (XML)",
            },
        }

    def _load_file_cache(self) -> Optional[Dict]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _save_file_cache(self, data: Dict) -> None:
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"[QR] Error saving file cache: {e}")

    def invalidate_cache(self) -> bool:
        try:
            redis_client.delete(self.DATA_CACHE_KEY)
            if DATA_CACHE_FILE.exists():
                DATA_CACHE_FILE.unlink()
            return True
        except Exception:
            return False

    def get_cache_status(self) -> Dict[str, Any]:
        cached = redis_client.get(self.DATA_CACHE_KEY)
        return {
            "redis_cache_exists": cached is not None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
            "quarter_label": cached.get("quarter_label") if cached else None,
            "last_updated": cached.get("last_updated") if cached else None,
        }


# シングルトン
quarterly_refunding_service = QuarterlyRefundingService()
