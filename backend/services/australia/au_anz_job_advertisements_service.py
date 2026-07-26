"""
ANZ-Indeed Australian Job Advertisements サービス

データソース:
- ANZ公式サイトからxlsxをダウンロード
- シート「ANZ-Indeed Australian Job Ads」のSeasonal adjusted列を使用
- Index (2019=100), Monthly

発表スケジュール: 月次
"""
import json
import hashlib
import logging
import calendar
from datetime import datetime
from io import BytesIO
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, quote
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
from bs4 import BeautifulSoup
import openpyxl

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# キャッシュ設定
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "australia" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "au_anz_job_advertisements_cache.json"

# ANZ設定
ANZ_BASE = "https://www.anz.com.au"
ANZ_RELEASE_DATES_URL = "https://www.anz.com.au/newsroom/media/release-dates/"

FMP_EVENT_PATTERNS = ["ANZ Job Advertisements MoM"]


class AuAnzJobAdvertisementsService:
    """ANZ-Indeed Australian Job Advertisements Service"""

    DATA_CACHE_KEY = "australia:au_anz_job_advertisements:data"

    def __init__(self):
        pass

    def _probe_dynamic_url(self) -> Optional[str]:
        """公表URLをパターンから動的に解決する。

        リリースページのリンクは旧版(前月データ)に固着しがちで、新ファイルは
        別URL(翌月フォルダ)に置かれるため取りこぼす。ANZの規則:
          データ月M(年Y) → 翌月(M+1)の月名フォルダに
          `.../jobads/{公表年}/{公表月名(小文字)}/ANZ-Indeed Australian Job Ads data_{Mon}{YY}.xlsx`
        最新候補(データ月=今月)から遡り、最初に200で取得できたURLを返す。
        """
        base = f"{ANZ_BASE}/content/dam/anzcomau/mediacentre/pdfs/jobads/"
        now = datetime.now(JST)
        y, m = now.year, now.month
        sess = requests.Session()
        for back in range(0, 13):
            # データ月(dm)/データ年(dy)
            dm, dy = m - back, y
            while dm <= 0:
                dm += 12
                dy -= 1
            # 公表月(pm)/公表年(py) = データ月 + 1ヶ月
            pm, py = dm + 1, dy
            if pm > 12:
                pm, py = pm - 12, py + 1
            folder = calendar.month_name[pm].lower()   # 例: 'july'
            mon3 = calendar.month_abbr[dm]             # 例: 'Jun'
            fname = f"ANZ-Indeed Australian Job Ads data_{mon3}{dy % 100:02d}.xlsx"
            url = base + f"{py}/{folder}/" + quote(fname)
            try:
                # HEADはCDNが403を返すためGET(stream)で存在確認
                r = sess.get(url, timeout=30, stream=True)
                status = r.status_code
                r.close()
                if status == 200:
                    logger.info(f"ANZ dynamic URL resolved: {url}")
                    return url
            except Exception as e:
                logger.debug(f"ANZ probe failed for {url}: {e}")
        logger.info("ANZ dynamic URL probe found nothing; falling back to release page")
        return None

    def _find_xlsx_url(self) -> Optional[str]:
        """xlsxのURLを解決（動的パターン優先→リリースページscrapeへフォールバック）"""
        dynamic = self._probe_dynamic_url()
        if dynamic:
            return dynamic
        try:
            sess = requests.Session()
            html = sess.get(ANZ_RELEASE_DATES_URL, timeout=30).text
            soup = BeautifulSoup(html, "html.parser")

            for cand in soup.find_all("a", href=True):
                text = (cand.get_text() or "").strip().lower()
                href = cand["href"].lower()
                if ("download" in text or "data" in text) and "/content/dam/" in href and "jobads" in href and href.endswith(".xlsx"):
                    return urljoin(ANZ_BASE, cand["href"])

            # broader search
            for cand in soup.find_all("a", href=True):
                href = cand["href"].lower()
                if "jobads" in href and href.endswith(".xlsx"):
                    return urljoin(ANZ_BASE, cand["href"])

            logger.error("ANZ xlsx link not found on release page")
            return None
        except Exception as e:
            logger.error(f"Error finding ANZ xlsx URL: {e}")
            return None

    def _download_xlsx(self, url: str) -> Optional[bytes]:
        """xlsxファイルをダウンロード"""
        try:
            logger.info(f"Downloading ANZ xlsx from {url}")
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            logger.error(f"Error downloading xlsx: {e}")
            return None

    def _parse_xlsx(self, content: bytes) -> List[Dict[str, Any]]:
        """xlsxをパースしてデータポイントを構築（MoM%・YoY%を算出）"""
        raw_points = []
        try:
            wb = openpyxl.load_workbook(BytesIO(content), read_only=True, data_only=True)
            ws = wb["ANZ-Indeed Australian Job Ads"]

            for row in ws.iter_rows(min_row=4, values_only=True):
                date_val = row[0]
                sa_val = row[2]  # Seasonal adjusted
                if date_val is None or sa_val is None:
                    continue
                if isinstance(date_val, datetime):
                    date_str = date_val.strftime("%Y-%m-%d")
                else:
                    continue
                raw_points.append({
                    "date": date_str,
                    "value": round(float(sa_val), 2),
                })

            wb.close()
            raw_points.sort(key=lambda x: x["date"])
        except Exception as e:
            logger.error(f"Error parsing xlsx: {e}")
            return []

        # MoM% と YoY% を算出
        data_points = []
        for i, pt in enumerate(raw_points):
            mom = None
            yoy = None
            # MoM%: 前月比
            if i >= 1:
                prev = raw_points[i - 1]["value"]
                if prev and prev != 0:
                    mom = round((pt["value"] - prev) / prev * 100, 2)
            # YoY%: 前年比 (12ヶ月前)
            if i >= 12:
                prev12 = raw_points[i - 12]["value"]
                if prev12 and prev12 != 0:
                    yoy = round((pt["value"] - prev12) / prev12 * 100, 2)
            data_points.append({
                "date": pt["date"],
                "value": pt["value"],
                "mom": mom,
                "yoy": yoy,
            })

        logger.info(f"Parsed {len(data_points)} ANZ Job Ads data points (with MoM/YoY)")
        return data_points

    def get_au_anz_job_advertisements_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ANZ求人広告データを取得（キャッシュ付き）"""
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                    }

        xlsx_url = self._find_xlsx_url()
        if xlsx_url:
            content = self._download_xlsx(xlsx_url)
            if content:
                data_points = self._parse_xlsx(content)
                if data_points:
                    latest = data_points[-1]
                    next_release = self._get_next_release()
                    result = {
                        "data": data_points,
                        "latest": latest,
                        "metadata": {
                            "source": "ANZ-Indeed",
                            "indicator": "Australian Job Advertisements",
                            "frequency": "monthly",
                            "unit": "index (2019=100)",
                        },
                        "next_release": next_release,
                    }
                    cache_payload = {**result, "last_updated": datetime.now(JST).isoformat()}
                    redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
                    self._save_file_cache(cache_payload)
                    return {**result, "cached": False, "source": "anz_xlsx"}

        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
            }

        return {
            "data": [], "latest": None,
            "metadata": {"source": "ANZ-Indeed", "error": "No data available"},
            "next_release": None, "cached": False, "source": "none",
        }

    def _get_next_release(self) -> Optional[Dict[str, str]]:
        try:
            from services.australia.fmp_next_release_utils import get_next_release_by_pattern
            return get_next_release_by_pattern("ANZ Job Advertisements", country="AU")
        except Exception as e:
            logger.warning(f"Failed to get next release: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)
            now = datetime.now(JST)
            if (now - last_updated).total_seconds() >= 7 * 24 * 3600:
                return True
            return False
        except Exception as e:
            logger.error(f"Error in should_refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        return {
            "indicator": "AU ANZ Job Advertisements", "source": "ANZ-Indeed",
            "cache_key": self.DATA_CACHE_KEY, "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


au_anz_job_advertisements_service = AuAnzJobAdvertisementsService()
