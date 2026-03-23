"""
NT倍率サービス

日経平均 / TOPIX の比率を算出し、大型値がさ株 vs 市場全体の相対強弱を把握する。
日経平均とTOPIXも重ねて表示。

データソース:
  - 日経平均: yfinance (^N225)
  - TOPIX: Stooq (^TPX) ※yfinanceの^TPXはデータが不完全なため

更新スケジュール: 日次（JST 7:00）
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "nt_magnification_cache.json"

REDIS_KEY = "market:nt_magnification:data"

DATA_YEARS = 15


class NtMagnificationService:
    """NT倍率サービス"""

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
            data = self._fetch_data()
            if data and data.get("data"):
                self._save_to_cache(data)
                return data
        except Exception as e:
            logger.error(f"NT倍率データ取得エラー: {e}")

        cached = self._load_from_redis()
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "yfinance + stooq", "description": "NT Magnification (Nikkei 225 / TOPIX)"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _fetch_nikkei225(self, start_str: str, end_str: str) -> Dict[str, float]:
        """yfinanceから日経平均を取得"""
        try:
            df = yf.download("^N225", start=start_str, end=end_str, progress=False, auto_adjust=True)
            if df.empty:
                return {}
            result: Dict[str, float] = {}
            for idx, row in df.iterrows():
                date_str = idx.strftime("%Y-%m-%d")
                close_val = float(row["Close"].iloc[0]) if hasattr(row["Close"], "iloc") else float(row["Close"])
                result[date_str] = round(close_val, 4)
            logger.info(f"  nikkei225 (^N225): {len(result)}件")
            return result
        except Exception as e:
            logger.error(f"yfinance ^N225 ダウンロードエラー: {e}")
            return {}

    def _fetch_topix(self, start_str: str, end_str: str) -> Dict[str, float]:
        """StooqからTOPIXインデックスを取得（正規のインデックス値）"""
        try:
            d1 = start_str.replace("-", "")
            d2 = end_str.replace("-", "")
            stooq_url = f"https://stooq.com/q/d/l/?s=^tpx&d1={d1}&d2={d2}&i=d"
            df = pd.read_csv(stooq_url)
            if df.empty:
                logger.error("Stooq TOPIX: データなし")
                return {}
            result: Dict[str, float] = {}
            for _, row in df.iterrows():
                date_str = str(row["Date"])
                close_val = float(row["Close"])
                result[date_str] = round(close_val, 4)
            logger.info(f"  topix (Stooq ^tpx): {len(result)}件")
            return result
        except Exception as e:
            logger.error(f"Stooq TOPIX ダウンロードエラー: {e}")
            return {}

    def _fetch_data(self) -> Dict[str, Any]:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=DATA_YEARS * 365)
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        n225_map = self._fetch_nikkei225(start_str, end_str)
        topix_map = self._fetch_topix(start_str, end_str)

        if not n225_map or not topix_map:
            logger.error("NT倍率: 日経平均またはTOPIXのデータ取得失敗")
            return {"data": [], "latest": None}

        # 両方にデータがある日付のみ使用
        all_dates = sorted(set(n225_map.keys()) & set(topix_map.keys()))

        data: List[Dict[str, Any]] = []
        for date_str in all_dates:
            n225_val = n225_map.get(date_str)
            topix_val = topix_map.get(date_str)
            if n225_val is None or topix_val is None or topix_val <= 0:
                continue

            ratio = round(n225_val / topix_val, 2)
            data.append({
                "date": date_str,
                "nikkei225": round(n225_val, 2),
                "topix": round(topix_val, 2),
                "ratio": ratio,
            })

        latest = data[-1] if data else None

        logger.info(
            f"NT倍率: {len(data)}件取得 "
            f"(N225: {len(n225_map)}件, TOPIX: {len(topix_map)}件)"
        )

        return {
            "data": data,
            "latest": latest,
            "metadata": {
                "source": "yfinance + stooq",
                "nikkei225_source": "yfinance (^N225)",
                "topix_source": "Stooq (^TPX)",
                "description": "NT Magnification (Nikkei 225 / TOPIX) with overlays",
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


nt_magnification_service = NtMagnificationService()
