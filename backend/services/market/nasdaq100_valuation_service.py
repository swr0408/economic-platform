"""
Nasdaq 100 Valuation サービス

データソース:
  - 予想PER: backend/data/manual_update/daily/stock_pe/nasdaq100_pe.csv (MacroMicro由来, 月次)
    参照: https://en.macromicro.me/series/23955/nasdaq-100-pe
  - Nasdaq100価格: yfinance (^NDX)
  - 米国10年債利回り（名目）: yfinance (^TNX)
  - 米国10年実質利回り（TIPS）: FRED DFII10

算出系列:
  - 予想EPS = 指数値 ÷ 予想PER
  - 予想株式益利回り = 1 ÷ 予想PER
  - 予想イールドスプレッド（名目） = 予想株式益利回り − 名目10年国債利回り
  - 予想イールドスプレッド（実質） = 予想株式益利回り − 実質10年国債利回り

更新: CSVファイルのタイムスタンプ変更を検出して自動リフレッシュ
"""
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

from core.redis_client import redis_client
from services.market.valuation_utils import assert_expected_ticker, assert_value_range
from services.usa.fred_utils import fetch_fred_series

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CSV_DIR = Path(__file__).parent.parent.parent / "data" / "manual_update" / "daily" / "stock_pe"
CSV_FILE = CSV_DIR / "nasdaq100_pe.csv"
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "nasdaq100_valuation_cache.json"

REDIS_KEY = "market:nasdaq100_valuation:data"


class Nasdaq100ValuationService:
    """Nasdaq 100 Valuation サービス"""

    def _get_file_mtime(self) -> Optional[float]:
        """CSVファイルの更新日時を取得"""
        try:
            if CSV_FILE.exists():
                return os.path.getmtime(CSV_FILE)
        except Exception:
            pass
        return None

    def _should_refresh(self) -> bool:
        try:
            cached = redis_client.get(REDIS_KEY)
            if not cached:
                return True
            cached_mtime = cached.get("metadata", {}).get("file_mtime")
            if cached_mtime is None:
                return True
            current_mtime = self._get_file_mtime()
            if current_mtime is None:
                return False
            if abs(current_mtime - cached_mtime) > 0.01:
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
            logger.error(f"[NDX-VAL] Build error: {e}")
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
            "metadata": {"source": "Nasdaq 100 Valuation"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """CSVから予想PER（月次）を読み込み、yfinanceで価格・金利を取得し、各系列を算出"""
        if not CSV_FILE.exists():
            logger.error(f"[NDX-VAL] CSV file not found: {CSV_FILE}")
            return None

        logger.info(f"[NDX-VAL] Reading CSV: {CSV_FILE}")

        # 1. CSV読み込み（予想PER - 月次）
        try:
            df_pe = pd.read_csv(CSV_FILE)
            df_pe["date"] = pd.to_datetime(df_pe["date"])
            df_pe = df_pe[["date", "value"]].rename(columns={"value": "forward_pe"})
            df_pe = df_pe.dropna(subset=["forward_pe"])
            df_pe = df_pe.sort_values("date").reset_index(drop=True)
        except Exception as e:
            logger.error(f"[NDX-VAL] CSV parse error: {e}")
            return None

        if df_pe.empty:
            logger.error("[NDX-VAL] No data in CSV")
            return None

        start_date = df_pe["date"].min().strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        # 2. yfinanceからNasdaq100価格を取得（日次）
        logger.info(f"[NDX-VAL] Fetching ^NDX from {start_date} to {end_date}")
        try:
            ndx = yf.download("^NDX", start=start_date, end=end_date, progress=False)
        except Exception as e:
            logger.error(f"[NDX-VAL] yfinance ^NDX error: {e}")
            return None
        if ndx.empty:
            logger.error("[NDX-VAL] No NDX price data from yfinance")
            return None
        assert_expected_ticker(ndx, "^NDX")
        ndx = ndx[["Close"]].reset_index()
        ndx.columns = ["date", "close"]
        ndx["date"] = pd.to_datetime(ndx["date"]).dt.tz_localize(None)
        # 健全性チェック: 指数値が異常に小さい場合は誤ティッカー(例:^VIX)/破損とみなし中断
        assert_value_range(ndx["close"], "^NDX close", 1000.0, 1000000.0)

        # 3. yfinanceから10年債利回りを取得（日次）
        logger.info(f"[NDX-VAL] Fetching ^TNX from {start_date} to {end_date}")
        try:
            tnx = yf.download("^TNX", start=start_date, end=end_date, progress=False)
        except Exception as e:
            logger.error(f"[NDX-VAL] yfinance ^TNX error: {e}")
            return None
        if tnx.empty:
            logger.error("[NDX-VAL] No TNX data from yfinance")
            return None
        assert_expected_ticker(tnx, "^TNX")
        tnx = tnx[["Close"]].reset_index()
        tnx.columns = ["date", "yield_10y"]
        tnx["date"] = pd.to_datetime(tnx["date"]).dt.tz_localize(None)
        tnx["yield_10y"] = tnx["yield_10y"] / 100  # % → decimal
        # 健全性チェック: 10年債利回り(小数)が0〜30%の範囲外なら破損とみなし中断
        assert_value_range(tnx["yield_10y"], "^TNX yield(decimal)", 0.0, 0.30)

        # 4. FRED DFII10（実質10年債利回り）を取得
        logger.info("[NDX-VAL] Fetching DFII10 from FRED")
        real_yield_df = pd.DataFrame()
        try:
            dfii10_data = fetch_fred_series("DFII10", start_date=start_date)
            if dfii10_data:
                real_yield_df = pd.DataFrame(dfii10_data)
                real_yield_df["date"] = pd.to_datetime(real_yield_df["date"])
                real_yield_df = real_yield_df.rename(columns={"value": "real_yield_10y"})
                real_yield_df["real_yield_10y"] = real_yield_df["real_yield_10y"] / 100  # % → decimal
                real_yield_df = real_yield_df.sort_values("date").reset_index(drop=True)
        except Exception as e:
            logger.warning(f"[NDX-VAL] DFII10 fetch failed (non-fatal): {e}")

        # 5. 月次PERと日次価格のマッチング
        # 各PER日付に最も近い取引日（同日以降）の価格・金利を割り当て
        ndx_sorted = ndx.sort_values("date").reset_index(drop=True)
        tnx_sorted = tnx.sort_values("date").reset_index(drop=True)

        data_list: List[Dict[str, Any]] = []
        for _, pe_row in df_pe.iterrows():
            pe_date = pe_row["date"]
            pe_val = pe_row["forward_pe"]

            # 最も近い取引日を検索（同日以降、3日以内）
            ndx_match = ndx_sorted[ndx_sorted["date"] >= pe_date]
            if ndx_match.empty:
                continue
            closest_ndx = ndx_match.iloc[0]
            if (closest_ndx["date"] - pe_date).days > 5:
                continue

            tnx_match = tnx_sorted[tnx_sorted["date"] >= pe_date]
            yield_10y = tnx_match.iloc[0]["yield_10y"] if not tnx_match.empty else None

            # 実質利回りのマッチング
            real_yield_10y = None
            if not real_yield_df.empty:
                ry_match = real_yield_df[real_yield_df["date"] >= pe_date]
                if not ry_match.empty:
                    real_yield_10y = float(ry_match.iloc[0]["real_yield_10y"])

            close_val = float(closest_ndx["close"])
            forward_eps = close_val / pe_val
            earnings_yield = 1 / pe_val
            yield_spread = (earnings_yield - yield_10y) if yield_10y is not None else None
            real_yield_spread = (earnings_yield - real_yield_10y) if real_yield_10y is not None else None

            data_list.append({
                "date": closest_ndx["date"].strftime("%Y-%m-%d"),
                "close": round(close_val, 2),
                "forward_pe": round(float(pe_val), 4),
                "forward_eps": round(forward_eps, 2),
                "earnings_yield": round(earnings_yield, 6),
                "yield_10y": round(float(yield_10y), 6) if yield_10y is not None else None,
                "yield_spread": round(float(yield_spread), 6) if yield_spread is not None else None,
                "real_yield_10y": round(real_yield_10y, 6) if real_yield_10y is not None else None,
                "real_yield_spread": round(float(real_yield_spread), 6) if real_yield_spread is not None else None,
            })

        if not data_list:
            logger.error("[NDX-VAL] No matched data points")
            return None

        # 5. 前年比（12ヶ月前との比較）
        for i, item in enumerate(data_list):
            for col in ["forward_pe", "forward_eps", "earnings_yield"]:
                if i >= 12:
                    cur = item[col]
                    prev = data_list[i - 12][col]
                    if prev and prev != 0:
                        item[f"{col}_yoy"] = round(((cur - prev) / prev) * 100, 2)
                    else:
                        item[f"{col}_yoy"] = None
                else:
                    item[f"{col}_yoy"] = None

        # 6. 前月比（月次テーブル用）
        monthly_table: List[Dict[str, Any]] = []
        for i, item in enumerate(data_list):
            d = datetime.strptime(item["date"], "%Y-%m-%d")
            ym = f"{d.year}-{d.month:02d}"
            mom_pe = None
            mom_eps = None
            mom_ey = None
            if i > 0:
                prev = data_list[i - 1]
                if prev["forward_pe"] and prev["forward_pe"] != 0:
                    mom_pe = round(((item["forward_pe"] - prev["forward_pe"]) / prev["forward_pe"]) * 100, 2)
                if prev["forward_eps"] and prev["forward_eps"] != 0:
                    mom_eps = round(((item["forward_eps"] - prev["forward_eps"]) / prev["forward_eps"]) * 100, 2)
                if prev["earnings_yield"] and prev["earnings_yield"] != 0:
                    mom_ey = round(((item["earnings_yield"] - prev["earnings_yield"]) / prev["earnings_yield"]) * 100, 2)

            mt_item = {
                "date": ym,
                "forward_pe": round(item["forward_pe"], 2),
                "forward_eps": round(item["forward_eps"], 2),
                "earnings_yield": round(item["earnings_yield"] * 100, 2),
                "close": round(item["close"], 2),
                "yield_10y": round(item["yield_10y"] * 100, 2) if item["yield_10y"] is not None else None,
                "forward_pe_mom": mom_pe,
                "forward_eps_mom": mom_eps,
                "earnings_yield_mom": mom_ey,
            }
            if item.get("real_yield_10y") is not None:
                mt_item["real_yield_10y"] = round(item["real_yield_10y"] * 100, 2)
            monthly_table.append(mt_item)

        latest = data_list[-1] if data_list else None
        file_mtime = self._get_file_mtime()
        now_str = datetime.now(JST).isoformat()

        logger.info(f"[NDX-VAL] Built {len(data_list)} data points, "
                     f"monthly table: {len(monthly_table)} rows")

        return {
            "data": data_list,
            "monthly_table": monthly_table,
            "latest": latest,
            "metadata": {
                "source": "Nasdaq 100 Valuation",
                "source_url": "https://en.macromicro.me/series/23955/nasdaq-100-pe",
                "pe_source_url": "https://en.macromicro.me/series/23955/nasdaq-100-pe",
                "pe_source": "MacroMicro",
                "file_name": CSV_FILE.name,
                "file_mtime": file_mtime,
                "data_count": len(data_list),
                "date_range": {
                    "start": data_list[0]["date"] if data_list else None,
                    "end": data_list[-1]["date"] if data_list else None,
                },
                "series": [
                    "forward_pe (予想PER)",
                    "forward_eps (予想EPS = 指数値÷予想PER)",
                    "earnings_yield (予想株式益利回り = 1÷予想PER)",
                    "yield_10y (米国10年名目債利回り)",
                    "yield_spread (予想イールドスプレッド = 益利回り−名目10年債)",
                    "real_yield_10y (米国10年実質利回り = FRED DFII10)",
                    "real_yield_spread (実質イールドスプレッド = 益利回り−実質10年債)",
                ],
            },
            "cached": False,
            "source": "csv+yfinance",
            "last_updated": now_str,
        }

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(REDIS_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[NDX-VAL] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[NDX-VAL] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(REDIS_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[NDX-VAL] Redis load error: {e}")
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
            logger.error(f"[NDX-VAL] File load error: {e}")
        return None


nasdaq100_valuation_service = Nasdaq100ValuationService()
