"""
ヒストリカルボラティリティ (Historical Volatility / Realized Volatility) サービス

S&P500の終値から日次対数リターンを計算し、
HV20（20日）・HV30（30日）のローリング標準偏差 × √252 × 100 で年率換算ボラティリティを算出。

追加系列:
  - VIX - HV20, VIX - HV30: ボラティリティ・リスクプレミアム
  - VIX / HV20, VIX / HV30: ボラティリティ・レシオ

データソース: yfinance (^GSPC, ^VIX)
更新スケジュール: 日次（JST 7:00）
"""
import json
import logging
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import yfinance as yf

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "historical_volatility_cache.json"

REDIS_KEY = "market:historical_volatility:data"

DATA_YEARS = 15


class HistoricalVolatilityService:
    """ヒストリカルボラティリティサービス"""

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
            logger.error(f"ヒストリカルボラティリティ取得エラー: {e}")

        cached = self._load_from_redis()
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "yfinance", "description": "Historical Volatility (HV20/HV30)"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _fetch_data(self) -> Dict[str, Any]:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=DATA_YEARS * 365 + 60)  # +60 for rolling window
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # S&P500 終値を取得
        sp500_map: Dict[str, float] = {}
        try:
            df_sp = yf.download("^GSPC", start=start_str, end=end_str, progress=False, auto_adjust=True)
            if not df_sp.empty:
                for idx, row in df_sp.iterrows():
                    date_str = idx.strftime("%Y-%m-%d")
                    close_val = float(row["Close"].iloc[0]) if hasattr(row["Close"], "iloc") else float(row["Close"])
                    sp500_map[date_str] = round(close_val, 2)
        except Exception as e:
            logger.error(f"S&P500データ取得エラー: {e}")

        # VIX を取得
        vix_map: Dict[str, float] = {}
        try:
            df_vix = yf.download("^VIX", start=start_str, end=end_str, progress=False, auto_adjust=True)
            if not df_vix.empty:
                for idx, row in df_vix.iterrows():
                    date_str = idx.strftime("%Y-%m-%d")
                    close_val = float(row["Close"].iloc[0]) if hasattr(row["Close"], "iloc") else float(row["Close"])
                    vix_map[date_str] = round(close_val, 2)
        except Exception as e:
            logger.error(f"VIXデータ取得エラー: {e}")

        if not sp500_map:
            raise ValueError("S&P500データが取得できませんでした")

        # 日付順にソートして対数リターンを計算
        sorted_dates = sorted(sp500_map.keys())
        log_returns: Dict[str, float] = {}
        for i in range(1, len(sorted_dates)):
            prev_date = sorted_dates[i - 1]
            curr_date = sorted_dates[i]
            prev_close = sp500_map[prev_date]
            curr_close = sp500_map[curr_date]
            if prev_close > 0:
                log_returns[curr_date] = math.log(curr_close / prev_close)

        # HV20, HV30 をローリングで計算
        return_dates = sorted(log_returns.keys())
        sqrt_252 = math.sqrt(252)

        data: List[Dict[str, Any]] = []
        # DATA_YEARS分のカットオフ
        cutoff_date = (end_date - timedelta(days=DATA_YEARS * 365)).strftime("%Y-%m-%d")

        for i in range(29, len(return_dates)):  # HV30には最低30日分必要
            date = return_dates[i]
            if date < cutoff_date:
                continue

            # HV20: 直近20日のリターンの標準偏差 × √252 × 100
            returns_20 = [log_returns[return_dates[j]] for j in range(i - 19, i + 1)]
            mean_20 = sum(returns_20) / 20
            var_20 = sum((r - mean_20) ** 2 for r in returns_20) / 19  # sample variance (N-1)
            hv20 = math.sqrt(var_20) * sqrt_252 * 100

            # HV30: 直近30日のリターンの標準偏差 × √252 × 100
            returns_30 = [log_returns[return_dates[j]] for j in range(i - 29, i + 1)]
            mean_30 = sum(returns_30) / 30
            var_30 = sum((r - mean_30) ** 2 for r in returns_30) / 29  # sample variance (N-1)
            hv30 = math.sqrt(var_30) * sqrt_252 * 100

            item: Dict[str, Any] = {
                "date": date,
                "hv20": round(hv20, 2),
                "hv30": round(hv30, 2),
            }

            # S&P500
            sp_val = sp500_map.get(date)
            if sp_val is not None:
                item["sp500"] = sp_val

            # VIX
            vix_val = vix_map.get(date)
            if vix_val is not None:
                item["vix"] = vix_val
                # VIX - HV (ボラティリティ・リスクプレミアム)
                item["vix_minus_hv20"] = round(vix_val - hv20, 2)
                item["vix_minus_hv30"] = round(vix_val - hv30, 2)
                # VIX / HV (ボラティリティ・レシオ)
                if hv20 > 0:
                    item["vix_div_hv20"] = round(vix_val / hv20, 4)
                if hv30 > 0:
                    item["vix_div_hv30"] = round(vix_val / hv30, 4)

            data.append(item)

        latest = data[-1] if data else None

        logger.info(
            f"ヒストリカルボラティリティ: {len(data)}件算出 "
            f"(S&P500: {len(sp500_map)}, VIX: {len(vix_map)})"
        )

        return {
            "data": data,
            "latest": latest,
            "metadata": {
                "source": "yfinance",
                "tickers": {"sp500": "^GSPC", "vix": "^VIX"},
                "description": "Historical Volatility (HV20/HV30) with VIX comparison",
                "formula": "HV = stdev(log_returns, N) * sqrt(252) * 100",
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


historical_volatility_service = HistoricalVolatilityService()
