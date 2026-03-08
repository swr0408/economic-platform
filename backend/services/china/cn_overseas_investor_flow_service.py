"""
中国 海外投資家フロー（Foreign Holdings）サービス

Bond Connect（chinabondconnect.com）から海外投資家の中国債券保有残高データを取得

系列:
- shch: Shanghai Clearing House (SHCH) 保有残高（RMB billion）
- ccdc: China Central Depository & Clearing (CCDC) 保有残高（RMB billion）
- total: 合計保有残高（RMB billion）

データソース: Bond Connect
https://www.chinabondconnect.com/en/Resource/Market-Data.html

発表スケジュール: 毎月1日 JST 9:00 頃更新
"""
import json
import logging
import re
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "china" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "cn_overseas_investor_flow_cache.json"

CSV_PATH = Path(__file__).parent.parent.parent / "data" / "csv_import" / "中国海外投資家フロー.csv"

# Bond Connect Market Data ページ
BOND_CONNECT_URL = "https://www.chinabondconnect.com/en/Resource/Market-Data.html"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRY = 5
RETRY_BACKOFF = 3

# 月名マッピング（CSVの日付パース用: "January 2026", "Dec 2024", etc.）
MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9,
    "oct": 10, "nov": 11, "dec": 12,
}


def _parse_english_date(text: str) -> Optional[str]:
    """英語月名+年 → 'YYYY-MM-01'

    Examples:
        'January 2026' → '2026-01-01'
        'Dec 2024'     → '2024-12-01'
        'Apr 2025'     → '2025-04-01'
    """
    text = text.strip()
    parts = text.split()
    if len(parts) != 2:
        return None
    month_str = parts[0].lower().rstrip(".")
    year_str = parts[1]
    month = MONTH_NAMES.get(month_str)
    if month is None:
        return None
    try:
        year = int(year_str)
    except ValueError:
        return None
    return f"{year}-{month:02d}-01"


def _parse_number(text: str) -> Optional[float]:
    """カンマ区切り数値をfloatに変換"""
    if not text:
        return None
    text = text.strip().replace(",", "").replace("\xa0", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _fetch_with_retry(url: str) -> Optional[str]:
    """HTTPリクエスト（リトライ付き）"""
    for attempt in range(MAX_RETRY):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 502:
                wait = RETRY_BACKOFF + attempt * 2
                logger.warning(f"[OverseasInvestorFlow] 502 on {url}, retry {attempt + 1}/{MAX_RETRY} in {wait}s")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return resp.text
        except requests.exceptions.RequestException as e:
            wait = RETRY_BACKOFF + attempt * 2
            logger.warning(f"[OverseasInvestorFlow] Error: {e}, retry {attempt + 1}/{MAX_RETRY} in {wait}s")
            time.sleep(wait)
    logger.error(f"[OverseasInvestorFlow] Failed after {MAX_RETRY} retries: {url}")
    return None


class CnOverseasInvestorFlowService:
    """中国海外投資家フローサービス"""

    DATA_CACHE_KEY = "china:cn_overseas_investor_flow:data"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """海外投資家フローデータを取得"""
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
            "metadata": {"source": "Bond Connect", "error": "No data available"},
            "next_release": None,
        }

    def _build_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """CSVデータ + Bond Connectスクレイピングでデータ構築"""
        # 1. CSV読み込み
        csv_records = self._load_csv()
        logger.info(f"[OverseasInvestorFlow] CSV: {len(csv_records)} records")

        # 2. スクレイピングはforce_refresh時のみ
        scraped_records: List[Dict[str, Any]] = []
        if force_refresh:
            scraped_records = self._scrape_bond_connect()
            logger.info(f"[OverseasInvestorFlow] Scraped: {len(scraped_records)} records")

        # 3. マージ（スクレイピングが優先）
        merged: Dict[str, Dict[str, Any]] = {}
        for rec in csv_records:
            merged[rec["date"]] = rec
        for rec in scraped_records:
            merged[rec["date"]] = rec

        # 4. CSVに書き戻し（新データがあれば）
        if scraped_records:
            self._update_csv(merged)

        # 5. ソート
        all_records = sorted(merged.values(), key=lambda x: x["date"])

        if not all_records:
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

        latest = all_records[-1]

        return {
            "data": all_records,
            "latest": latest,
            "metadata": {
                "source": "Bond Connect",
                "indicator": "Foreign Holdings (Month-end)",
                "unit": "RMB billion",
                "frequency": "monthly",
            },
            "next_release": None,
        }

    def _load_csv(self) -> List[Dict[str, Any]]:
        """CSVから履歴データ読み込み

        CSV形式:
        "Foreign Holdings*\n(Month-end)",Shanghai Clearing House (SHCH),...
        January 2026,620.4,2734.1,"3,354.50"
        """
        records = []
        try:
            if not CSV_PATH.exists():
                return records

            # CSVにはカンマ含む値が引用符で囲まれている → csv.readerで処理
            import csv
            with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader, None)  # ヘッダー行をスキップ
                if header is None:
                    return records

                for row in reader:
                    if len(row) < 4:
                        continue

                    date_str = _parse_english_date(row[0])
                    if not date_str:
                        continue

                    shch = _parse_number(row[1])
                    ccdc = _parse_number(row[2])
                    total = _parse_number(row[3])

                    records.append({
                        "date": date_str,
                        "shch": shch,
                        "ccdc": ccdc,
                        "total": total,
                    })
        except Exception as e:
            logger.error(f"[OverseasInvestorFlow] CSV load error: {e}")
        return records

    def _scrape_bond_connect(self) -> List[Dict[str, Any]]:
        """Bond Connect Market Dataページからスクレイピング"""
        records = []
        try:
            html = _fetch_with_retry(BOND_CONNECT_URL)
            if not html:
                return records

            soup = BeautifulSoup(html, "html.parser")

            # Foreign Holdings テーブルを探す（SHCHを含むテーブル）
            target_table = None
            for table in soup.find_all("table"):
                table_text = table.get_text()
                if "SHCH" in table_text or "Shanghai Clearing House" in table_text:
                    target_table = table
                    break

            if target_table is None:
                logger.warning("[OverseasInvestorFlow] Foreign Holdings table not found")
                return records

            # テーブル行をパース（ヘッダーをスキップ）
            rows = target_table.find_all("tr")
            for row in rows[1:]:  # ヘッダー行をスキップ
                cells = row.find_all(["td", "th"])
                if len(cells) < 4:
                    continue

                cell_texts = [c.get_text(strip=True) for c in cells]
                date_str = _parse_english_date(cell_texts[0])
                if not date_str:
                    continue

                shch = _parse_number(cell_texts[1])
                ccdc = _parse_number(cell_texts[2])
                total = _parse_number(cell_texts[3])

                records.append({
                    "date": date_str,
                    "shch": shch,
                    "ccdc": ccdc,
                    "total": total,
                })

            logger.info(f"[OverseasInvestorFlow] Scraped {len(records)} rows from Bond Connect")
        except Exception as e:
            logger.error(f"[OverseasInvestorFlow] Scraping error: {e}")
            import traceback
            traceback.print_exc()
        return records

    def _update_csv(self, merged: Dict[str, Dict[str, Any]]) -> None:
        """マージ済みデータをCSVに書き戻す"""
        try:
            import csv
            sorted_records = sorted(merged.values(), key=lambda x: x["date"], reverse=True)

            CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                # ヘッダー
                writer.writerow([
                    "Foreign Holdings*\n(Month-end)",
                    "Shanghai Clearing House (SHCH)",
                    "China Central Depository & Clearing (CCDC)",
                    "Total\n(RMB billion)",
                ])
                # データ行（新しい順）
                for rec in sorted_records:
                    date_str = rec["date"]
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    month_label = dt.strftime("%B %Y")  # "January 2026"

                    shch = rec.get("shch")
                    ccdc = rec.get("ccdc")
                    total = rec.get("total")

                    writer.writerow([
                        month_label,
                        f"{shch:,.1f}" if shch is not None else "",
                        f"{ccdc:,.1f}" if ccdc is not None else "",
                        f"{total:,.2f}" if total is not None else "",
                    ])

            logger.info(f"[OverseasInvestorFlow] Updated CSV with {len(sorted_records)} records")
        except Exception as e:
            logger.warning(f"[OverseasInvestorFlow] CSV update failed: {e}")

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュ更新判定 - 毎月1日 JST 9:00以降に更新"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)
            now = datetime.now(JST)

            # 日次チェック（JST 12:00以降）
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
            logger.error(f"[OverseasInvestorFlow] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[OverseasInvestorFlow] Failed to save file cache: {e}")

    def invalidate_cache(self) -> Dict[str, Any]:
        redis_client.delete(self.DATA_CACHE_KEY)
        if DATA_CACHE_FILE.exists():
            DATA_CACHE_FILE.unlink()
        return {"success": True, "message": "Overseas investor flow cache invalidated"}

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        return {
            "indicator": "CN Overseas Investor Flow",
            "source": "Bond Connect",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトン
cn_overseas_investor_flow_service = CnOverseasInvestorFlowService()
