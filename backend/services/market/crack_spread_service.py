"""
クラックスプレッド (Crack Spread) サービス

データソース: yfinance
  - CL=F: WTI原油 (USD/bbl)
  - BZ=F: ブレント原油 (USD/bbl)
  - RB=F: RBOBガソリン (USD/gal)
  - HO=F: ULSD / ヒーティングオイル (USD/gal)

計算:
  - RBOB Crack (WTI) = RBOB×42 - WTI
  - ULSD Crack (WTI) = ULSD×42 - WTI
  - 3:2:1 Crack (WTI) = (2×RBOB×42 + ULSD×42 - 3×WTI) / 3
  - RBOB Crack (Brent) = RBOB×42 - Brent
  - ULSD Crack (Brent) = ULSD×42 - Brent
  - 3:2:1 Crack (Brent) = (2×RBOB×42 + ULSD×42 - 3×Brent) / 3

更新スケジュール: 日次（JST 7:00、yfinance再試行と同タイミング）
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor

import yfinance as yf
import pandas as pd

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "crack_spread_cache.json"

REDIS_KEY = "market:crack_spread:data"

# yfinance ティッカー
TICKERS = {
    "wti": "CL=F",
    "brent": "BZ=F",
    "rbob": "RB=F",
    "ulsd": "HO=F",
}

# ガロン→バレル換算係数（1バレル = 42ガロン）
GAL_TO_BBL = 42

DATA_YEARS = 15


class CrackSpreadService:
    """クラックスプレッドサービス"""

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
            today_refresh = now.replace(hour=6, minute=0, second=0, microsecond=0)
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
            data = self._build_data()
            if data and data.get("data"):
                self._save_to_cache(data)
                return data
        except Exception as e:
            logger.error(f"[CrackSpread] Build error: {e}")
            import traceback
            traceback.print_exc()

        cached = self._load_from_redis()
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "yfinance"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """yfinance から4銘柄を取得し、クラックスプレッドを計算"""
        logger.info("[CrackSpread] Building data from yfinance...")

        end_date = datetime.now()
        start_date = end_date - timedelta(days=DATA_YEARS * 365)
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # 4銘柄を並列取得
        price_maps: Dict[str, Dict[str, float]] = {}

        def fetch_one(name: str, ticker: str):
            try:
                t = yf.Ticker(ticker)
                df = t.history(start=start_str, end=end_str, interval="1d")
                if df.empty:
                    logger.warning(f"[CrackSpread] No data for {ticker}")
                    return name, {}
                result = {}
                for idx, row in df.iterrows():
                    date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
                    close = row.get("Close")
                    if pd.notna(close):
                        result[date_str] = round(float(close), 4)
                logger.info(f"[CrackSpread] {ticker}: {len(result)} records")
                return name, result
            except Exception as e:
                logger.error(f"[CrackSpread] Error fetching {ticker}: {e}")
                return name, {}

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(fetch_one, name, ticker) for name, ticker in TICKERS.items()]
            for f in futures:
                try:
                    name, data = f.result(timeout=60)
                    price_maps[name] = data
                except Exception as e:
                    logger.error(f"[CrackSpread] Fetch error: {e}")

        wti_map = price_maps.get("wti", {})
        brent_map = price_maps.get("brent", {})
        rbob_map = price_maps.get("rbob", {})
        ulsd_map = price_maps.get("ulsd", {})

        if not wti_map or not rbob_map or not ulsd_map:
            logger.error("[CrackSpread] Missing essential price data")
            return None

        # 全4銘柄が揃う日付のみ（Brentは欠損許容）
        common_dates = sorted(
            set(wti_map.keys()) & set(rbob_map.keys()) & set(ulsd_map.keys())
        )

        if not common_dates:
            logger.error("[CrackSpread] No common dates")
            return None

        result_data: List[Dict[str, Any]] = []
        for d in common_dates:
            wti = wti_map[d]
            rbob = rbob_map[d]
            ulsd = ulsd_map[d]
            brent = brent_map.get(d)

            rbob_bbl = rbob * GAL_TO_BBL
            ulsd_bbl = ulsd * GAL_TO_BBL

            # WTIベース
            rbob_crack_wti = round(rbob_bbl - wti, 2)
            ulsd_crack_wti = round(ulsd_bbl - wti, 2)
            crack_321_wti = round((2 * rbob_bbl + ulsd_bbl - 3 * wti) / 3, 2)

            row: Dict[str, Any] = {
                "date": d,
                "wti": wti,
                "rbob_crack_wti": rbob_crack_wti,
                "ulsd_crack_wti": ulsd_crack_wti,
                "crack_321_wti": crack_321_wti,
            }

            # Brentベース（データがある場合のみ）
            if brent is not None:
                row["brent"] = brent
                row["rbob_crack_brent"] = round(rbob_bbl - brent, 2)
                row["ulsd_crack_brent"] = round(ulsd_bbl - brent, 2)
                row["crack_321_brent"] = round((2 * rbob_bbl + ulsd_bbl - 3 * brent) / 3, 2)
            else:
                row["brent"] = None
                row["rbob_crack_brent"] = None
                row["ulsd_crack_brent"] = None
                row["crack_321_brent"] = None

            result_data.append(row)

        if not result_data:
            return None

        latest = result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[CrackSpread] {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest 3:2:1 WTI={latest.get('crack_321_wti')}, "
            f"3:2:1 Brent={latest.get('crack_321_brent')}"
        )

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "yfinance",
                "frequency": "daily",
                "unit": "USD/bbl",
                "tickers": TICKERS,
                "formula": {
                    "rbob_crack_wti": "RBOB×42 - WTI",
                    "ulsd_crack_wti": "ULSD×42 - WTI",
                    "crack_321_wti": "(2×RBOB×42 + ULSD×42 - 3×WTI) / 3",
                    "rbob_crack_brent": "RBOB×42 - Brent",
                    "ulsd_crack_brent": "ULSD×42 - Brent",
                    "crack_321_brent": "(2×RBOB×42 + ULSD×42 - 3×Brent) / 3",
                },
                "data_count": len(result_data),
                "start_date": result_data[0]["date"],
                "end_date": result_data[-1]["date"],
            },
            "cached": False,
            "source": "model",
            "last_updated": now_str,
        }

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(REDIS_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[CrackSpread] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[CrackSpread] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(REDIS_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[CrackSpread] Redis load error: {e}")
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
            logger.error(f"[CrackSpread] File load error: {e}")
        return None


crack_spread_service = CrackSpreadService()
