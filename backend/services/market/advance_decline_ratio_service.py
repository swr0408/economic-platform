"""
東証プライム 騰落レシオ (25日) サービス

nikkei225jp.com の daily2year.json から過去2年分の騰落レシオデータを取得。
yfinance で日経225・TOPIX ETF をオーバーレイ。

計算方法（ソース側で計算済み）:
  直近25営業日の上昇合計 / 下落合計 × 100 = 騰落レシオ

一般的な目安:
  120%以上 → 過熱警戒
  100%前後 → 中立
  70%以下  → 底値圏

更新スケジュール: 日次（東証引け後 JST 16:00頃）
更新: 6時間TTL (Redis + ファイル)

データソース: nikkei225jp.com / yfinance
"""

import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from core.redis_client import redis_client
from services.market._stooq_utils import fetch_stooq_daily

logger = logging.getLogger(__name__)

# --- 定数 ---
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "advance_decline_ratio_cache.json"
DATA_CACHE_KEY = "market:advance_decline_ratio:data"

NIKKEI225JP_URL = "https://nikkei225jp.com/_data/_nfsWEB/DAY/daily2year.json"
AD_WINDOW = 25

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://nikkei225jp.com/data/touraku.php",
}


def _fetch_nikkei225jp_data() -> List[Dict[str, Any]]:
    """nikkei225jp.com から2年分の騰落レシオデータを取得

    Returns:
        List of dicts with keys: date, ratio, advances, declines, nikkei225_src
    """
    resp = requests.get(NIKKEI225JP_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    text = resp.text.strip()
    # Format: var DAILY = [[...], ...]
    match = re.search(r"var\s+DAILY\s*=\s*(\[.+\])", text, re.DOTALL)
    if not match:
        raise ValueError("Could not parse nikkei225jp.com response")

    raw = json.loads(match.group(1))
    result: List[Dict[str, Any]] = []

    for row in raw:
        if not isinstance(row, list) or len(row) < 8:
            continue

        ts = row[0]
        nikkei225_price = row[1]
        advances = row[5]
        declines = row[6]
        ratio = row[7]

        # timestamp (ms) → date string
        try:
            dt = datetime.fromtimestamp(ts / 1000)
            date_str = dt.strftime("%Y-%m-%d")
        except (TypeError, ValueError, OSError):
            continue

        # Validate numeric fields
        try:
            adv = int(advances) if advances is not None else 0
            dec = int(declines) if declines is not None else 0
            r = float(ratio) if ratio is not None else None
            n225 = float(nikkei225_price) if nikkei225_price is not None else None
        except (TypeError, ValueError):
            continue

        result.append({
            "date": date_str,
            "ratio": round(r, 2) if r is not None else None,
            "advances": adv,
            "declines": dec,
            "unchanged": 0,  # not available from this source
            "advances_25d": 0,  # pre-calculated ratio is used directly
            "declines_25d": 0,
            "nikkei225_src": round(n225, 2) if n225 is not None else None,
        })

    result.sort(key=lambda x: x["date"])
    return result


class AdvanceDeclineRatioService:
    """東証プライム 騰落レシオ (25日) サービス"""

    def _should_refresh(self) -> bool:
        try:
            cached = redis_client.get(DATA_CACHE_KEY)
            if not cached:
                return True
            last_updated_str = cached.get("last_updated")
            if not last_updated_str:
                return True
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now()
            if (now - last_updated).total_seconds() < 6 * 3600:
                return False
            return True
        except Exception:
            return True

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """騰落レシオデータを取得"""
        if not force_refresh and not self._should_refresh():
            cached = self._load_from_redis()
            if cached and cached.get("data"):
                return cached

        try:
            data = self._build_data()
            if data and data.get("data"):
                self._save_to_cache(data)
                return data
        except Exception as e:
            logger.error(f"[AdvanceDeclineRatio] Build error: {e}")

        cached = self._load_from_redis()
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "nikkei225jp.com"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """nikkei225jp.com からデータ取得 → yfinance マージ"""
        logger.info("[AdvanceDeclineRatio] Fetching from nikkei225jp.com")
        raw_data = _fetch_nikkei225jp_data()

        if not raw_data:
            logger.warning("[AdvanceDeclineRatio] No data from nikkei225jp.com")
            return None

        logger.info(f"[AdvanceDeclineRatio] Got {len(raw_data)} rows: {raw_data[0]['date']} ~ {raw_data[-1]['date']}")

        # Build result with ratio data (already calculated by source)
        result_data: List[Dict[str, Any]] = []
        for item in raw_data:
            if item["ratio"] is None:
                continue
            result_data.append({
                "date": item["date"],
                "ratio": item["ratio"],
                "advances": item["advances"],
                "declines": item["declines"],
                "unchanged": item["unchanged"],
                "advances_25d": item["advances_25d"],
                "declines_25d": item["declines_25d"],
            })

        # Merge yfinance indices (Nikkei225 & TOPIX ETF)
        result_data = self._merge_indices(result_data)

        latest = result_data[-1].copy() if result_data else None
        now_str = datetime.now().isoformat()

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "nikkei225jp.com",
                "frequency": "daily",
                "data_count": len(result_data),
                "start_date": result_data[0]["date"] if result_data else None,
                "end_date": result_data[-1]["date"] if result_data else None,
                "window": AD_WINDOW,
            },
            "cached": False,
            "source": "api",
            "last_updated": now_str,
        }

    def _merge_indices(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """日経225(yfinance)・TOPIX(Stooq)を取得してマージ"""
        if not data:
            return data
        try:
            import yfinance as yf
            import pandas as pd

            start_date = data[0]["date"]
            end_dt = datetime.strptime(data[-1]["date"], "%Y-%m-%d") + timedelta(days=5)
            end_date = end_dt.strftime("%Y-%m-%d")

            # 日経平均: yfinance
            n225 = yf.Ticker("^N225")
            n225_hist = n225.history(start=start_date, end=end_date, interval="1d")
            n225_map: Dict[str, float] = {}
            for idx, row in n225_hist.iterrows():
                n225_map[idx.strftime("%Y-%m-%d")] = round(float(row["Close"]), 2)

            # TOPIX: Stooq（正規インデックス値）
            topix_map: Dict[str, float] = {}
            df_topix = fetch_stooq_daily("^tpx", start_date, end_date)
            if df_topix is not None and not df_topix.empty:
                for _, row in df_topix.iterrows():
                    topix_map[row["Date"].strftime("%Y-%m-%d")] = round(float(row["Close"]), 2)
                logger.info(f"[AdvanceDeclineRatio] TOPIX (Stooq): {len(topix_map)}件")

            for item in data:
                item["nikkei225"] = n225_map.get(item["date"])
                item["topix"] = topix_map.get(item["date"])

        except Exception as e:
            logger.error(f"[AdvanceDeclineRatio] Index merge error: {e}")

        return data

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(DATA_CACHE_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[AdvanceDeclineRatio] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[AdvanceDeclineRatio] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(DATA_CACHE_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[AdvanceDeclineRatio] Redis load error: {e}")
        return None

    def _load_from_file(self) -> Optional[Dict[str, Any]]:
        try:
            if DATA_CACHE_FILE.exists():
                with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["cached"] = True
                data["source"] = "file"
                return data
        except Exception as e:
            logger.error(f"[AdvanceDeclineRatio] File load error: {e}")
        return None


# シングルトン
advance_decline_ratio_service = AdvanceDeclineRatioService()
