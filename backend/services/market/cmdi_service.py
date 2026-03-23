"""
企業債券市場ディストレス指数（CMDI）サービス

NY連銀が公開するCorporate Bond Market Distress Indexを取得する。
CMDIは企業債券市場の機能不全度を0-1のスケールで示す指数。

データソース:
  - NY Fed: Market CMDI.xlsx
    - "Index Data" シート
    - 列: eow_friday, Market CMDI, IG CMDI, HY CMDI

3系列:
  - Market CMDI: 全体（IG+HY集約）
  - IG CMDI: 投資適格債
  - HY CMDI: ハイイールド債

更新スケジュール: 月次（毎月最終水曜日 10:00 AM ET）、日次チェック（JST 7:00）
"""
import json
import logging
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "cmdi_cache.json"

REDIS_KEY = "market:cmdi:data"

EXCEL_URL = "https://www.newyorkfed.org/medialibrary/research/interactives/cmdi/downloads/Market%20CMDI.xlsx"


class CmdiService:
    """企業債券市場ディストレス指数（CMDI）サービス"""

    def _should_refresh(self) -> bool:
        try:
            cached = redis_client.get(REDIS_KEY)
            if not cached:
                return True
            last_updated_str = cached.get("last_updated")
            if not last_updated_str:
                return True
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)
            today_refresh = now.replace(hour=7, minute=0, second=0, microsecond=0)
            if now >= today_refresh and last_updated < today_refresh:
                return True
            return False
        except Exception:
            return True

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        if not force_refresh and not self._should_refresh():
            cached = self._load_from_redis()
            if cached and cached.get("data"):
                return cached

        try:
            data = self._fetch_data()
            if data and data.get("data"):
                self._save_to_cache(data)
                return data
        except Exception as e:
            logger.error(f"CMDIデータ取得エラー: {e}")

        cached = self._load_from_redis()
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "NY Fed", "description": "Corporate Bond Market Distress Index"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _fetch_data(self) -> Dict[str, Any]:
        resp = requests.get(EXCEL_URL, timeout=60)
        resp.raise_for_status()

        df = pd.read_excel(BytesIO(resp.content), sheet_name="Index Data", header=5)

        data: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            date_val = row.get("eow_friday")
            if pd.isna(date_val):
                continue

            if isinstance(date_val, datetime):
                date_str = date_val.strftime("%Y-%m-%d")
            elif isinstance(date_val, str):
                date_str = date_val[:10]
            else:
                date_str = str(date_val)[:10]

            market_val = row.get("Market CMDI")
            ig_val = row.get("IG CMDI")
            hy_val = row.get("HY CMDI")

            item: Dict[str, Any] = {"date": date_str}

            if pd.notna(market_val):
                item["market"] = round(float(market_val), 4)
            if pd.notna(ig_val):
                item["ig"] = round(float(ig_val), 4)
            if pd.notna(hy_val):
                item["hy"] = round(float(hy_val), 4)

            data.append(item)

        data.sort(key=lambda x: x["date"])
        latest = data[-1] if data else None

        logger.info(f"CMDI: {len(data)}件取得")

        return {
            "data": data,
            "latest": latest,
            "metadata": {
                "source": "NY Fed",
                "description": "Corporate Bond Market Distress Index (Market / IG / HY)",
                "data_points": len(data),
            },
            "cached": False,
            "source": "api",
            "last_updated": datetime.now(JST).isoformat(),
        }

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(REDIS_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"Redis保存エラー: {e}")

        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            logger.error(f"ファイルキャッシュ保存エラー: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            cached = redis_client.get(REDIS_KEY)
            if cached:
                cached["cached"] = True
                cached["source"] = "redis"
                return cached
        except Exception:
            pass
        return None

    def _load_from_file(self) -> Optional[Dict[str, Any]]:
        try:
            if DATA_CACHE_FILE.exists():
                with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["cached"] = True
                data["source"] = "file"
                return data
        except Exception:
            pass
        return None


cmdi_service = CmdiService()
