"""
NAAIM Exposure Index サービス

データ項目:
- naaim_number: NAAIM Exposure Index (平均値, 0-200 range)
- sp500: S&P 500 終値

データソース:
- NAAIM (National Association of Active Investment Managers)
  https://naaim.org/programs/naaim-exposure-index/
- Excelファイル: 動的URL（ページからスクレイピングで取得）

更新スケジュール: 毎週木曜日（米国時間） → JST 毎週金曜 AM 8:00
"""
import io
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from bs4 import BeautifulSoup

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# キャッシュ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "naaim_exposure_cache.json"

# Redis
DATA_CACHE_KEY = "market:naaim_exposure:data"

# NAAIM
NAAIM_PAGE_URL = "https://naaim.org/programs/naaim-exposure-index/"

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


class NaaimService:
    """NAAIM Exposure Index データ取得サービス"""

    def _should_refresh(self) -> bool:
        """キャッシュの更新が必要かどうか判定
        週次データなので、毎週金曜JST 8:00以降に更新"""
        try:
            cached = redis_client.get(DATA_CACHE_KEY)
            if not cached:
                return True

            last_updated_str = cached.get("last_updated")
            if not last_updated_str:
                return True

            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)

            # 12時間以内に更新されていればスキップ
            if (now - last_updated).total_seconds() < 12 * 3600:
                return False

            # 金曜8時以降で、最終更新が金曜8時より前なら更新
            friday_8am = now.replace(hour=8, minute=0, second=0, microsecond=0)
            weekday = now.weekday()  # 0=Mon, 4=Fri
            if weekday == 4 and now >= friday_8am and last_updated < friday_8am:
                return True

            return False
        except Exception:
            return True

    def get_naaim_data(
        self, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """NAAIM Exposure Index データを取得"""
        if not force_refresh and not self._should_refresh():
            cached = self._load_from_redis()
            if cached and cached.get("data"):
                return cached

        # ExcelからNAAIMデータ取得
        try:
            data = self._fetch_from_excel()
            if data and data.get("data"):
                self._save_to_cache(data)
                return data
        except Exception as e:
            logger.error(f"[NAAIM] Excel fetch error: {e}")

        # フォールバック
        cached = self._load_from_redis()
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "NAAIM"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _find_excel_url(self) -> Optional[str]:
        """NAAIMページから動的ExcelファイルURLを取得"""
        try:
            resp = requests.get(NAAIM_PAGE_URL, headers=HTTP_HEADERS, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            for a in soup.find_all("a", href=True):
                if ".xlsx" in a["href"]:
                    return a["href"]

            logger.warning("[NAAIM] No .xlsx link found on page")
            return None
        except Exception as e:
            logger.error(f"[NAAIM] Page scrape error: {e}")
            return None

    def _fetch_from_excel(self) -> Optional[Dict[str, Any]]:
        """ExcelファイルからNAAIMデータを取得"""
        excel_url = self._find_excel_url()
        if not excel_url:
            return None

        logger.info(f"[NAAIM] Fetching Excel: {excel_url}")
        resp = requests.get(excel_url, headers=HTTP_HEADERS, timeout=60)
        resp.raise_for_status()

        df = pd.read_excel(io.BytesIO(resp.content))

        # 必要な列を確認
        required_cols = {"Date", "NAAIM Number", "S&P 500"}
        if not required_cols.issubset(set(df.columns)):
            logger.error(f"[NAAIM] Missing columns. Found: {df.columns.tolist()}")
            return None

        # データ変換
        result_data: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            date_val = row["Date"]
            naaim_val = row["NAAIM Number"]
            sp500_val = row["S&P 500"]

            if pd.isna(date_val) or pd.isna(naaim_val):
                continue

            # 日付変換
            if isinstance(date_val, pd.Timestamp):
                date_str = date_val.strftime("%Y-%m-%d")
            elif isinstance(date_val, datetime):
                date_str = date_val.strftime("%Y-%m-%d")
            else:
                try:
                    date_str = pd.to_datetime(date_val).strftime("%Y-%m-%d")
                except Exception:
                    continue

            item: Dict[str, Any] = {
                "date": date_str,
                "naaim_number": round(float(naaim_val), 2),
            }

            if not pd.isna(sp500_val):
                item["sp500"] = round(float(sp500_val), 2)
            else:
                item["sp500"] = None

            result_data.append(item)

        # 日付昇順でソートし重複除去
        result_data.sort(key=lambda x: x["date"])
        seen: Dict[str, int] = {}
        for i, item in enumerate(result_data):
            seen[item["date"]] = i
        result_data = [result_data[i] for i in sorted(seen.values())]

        latest = result_data[-1].copy() if result_data else None

        now_str = datetime.now(JST).isoformat()

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "NAAIM",
                "excel_url": excel_url,
                "data_count": len(result_data),
                "start_date": result_data[0]["date"] if result_data else None,
                "end_date": result_data[-1]["date"] if result_data else None,
            },
            "cached": False,
            "source": "api",
            "last_updated": now_str,
        }

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        """Redis + ファイルキャッシュに保存"""
        try:
            redis_client.set(DATA_CACHE_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[NAAIM] Redis save error: {e}")

        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[NAAIM] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        """Redisキャッシュから読み込み"""
        try:
            data = redis_client.get(DATA_CACHE_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[NAAIM] Redis load error: {e}")
        return None

    def _load_from_file(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュから読み込み"""
        try:
            if DATA_CACHE_FILE.exists():
                with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["cached"] = True
                data["source"] = "file"
                return data
        except Exception as e:
            logger.error(f"[NAAIM] File load error: {e}")
        return None


# シングルトン
naaim_service = NaaimService()
