"""
S&P 500 Valuation サービス

データソース:
  - 予想PER: backend/data/manual_update/daily/stock_pe/sp500_pe.csv (MacroMicro由来)
    参照: https://en.macromicro.me/series/20052/sp500-forward-pe-ratio
  - S&P500価格: yfinance (^GSPC)
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
CSV_FILE = CSV_DIR / "sp500_pe.csv"
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "sp500_valuation_cache.json"

REDIS_KEY = "market:sp500_valuation:data"


class Sp500ValuationService:
    """S&P 500 Valuation サービス"""

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
            logger.error(f"[SP500-VAL] Build error: {e}")
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
            "metadata": {"source": "S&P 500 Valuation"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """CSVから予想PERを読み込み、yfinanceで価格・金利を取得し、各系列を算出"""
        if not CSV_FILE.exists():
            logger.error(f"[SP500-VAL] CSV file not found: {CSV_FILE}")
            return None

        logger.info(f"[SP500-VAL] Reading CSV: {CSV_FILE}")

        # 1. CSV読み込み（予想PER）
        try:
            df_pe = pd.read_csv(CSV_FILE)
            df_pe["date"] = pd.to_datetime(df_pe["date"])
            df_pe = df_pe[["date", "value"]].rename(columns={"value": "forward_pe"})
            df_pe = df_pe.dropna(subset=["forward_pe"])
            df_pe = df_pe.sort_values("date").reset_index(drop=True)
        except Exception as e:
            logger.error(f"[SP500-VAL] CSV parse error: {e}")
            return None

        if df_pe.empty:
            logger.error("[SP500-VAL] No data in CSV")
            return None

        start_date = df_pe["date"].min().strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        # 2. yfinanceからS&P500価格を取得
        logger.info(f"[SP500-VAL] Fetching ^GSPC from {start_date} to {end_date}")
        try:
            sp500 = yf.download("^GSPC", start=start_date, end=end_date, progress=False)
        except Exception as e:
            logger.error(f"[SP500-VAL] yfinance ^GSPC error: {e}")
            return None
        if sp500.empty:
            logger.error("[SP500-VAL] No S&P500 price data from yfinance")
            return None
        assert_expected_ticker(sp500, "^GSPC")
        sp500 = sp500[["Close"]].reset_index()
        sp500.columns = ["date", "close"]
        sp500["date"] = pd.to_datetime(sp500["date"]).dt.tz_localize(None)
        # 健全性チェック: 指数値が異常に小さい場合は誤ティッカー(例:^VIX)/破損とみなし中断
        assert_value_range(sp500["close"], "^GSPC close", 100.0, 100000.0)

        # 3. yfinanceから10年債利回りを取得
        logger.info(f"[SP500-VAL] Fetching ^TNX from {start_date} to {end_date}")
        try:
            tnx = yf.download("^TNX", start=start_date, end=end_date, progress=False)
        except Exception as e:
            logger.error(f"[SP500-VAL] yfinance ^TNX error: {e}")
            return None
        if tnx.empty:
            logger.error("[SP500-VAL] No TNX data from yfinance")
            return None
        assert_expected_ticker(tnx, "^TNX")
        tnx = tnx[["Close"]].reset_index()
        tnx.columns = ["date", "yield_10y"]
        tnx["date"] = pd.to_datetime(tnx["date"]).dt.tz_localize(None)
        tnx["yield_10y"] = tnx["yield_10y"] / 100  # % → decimal
        # 健全性チェック: 10年債利回り(小数)が0〜30%の範囲外なら破損とみなし中断
        assert_value_range(tnx["yield_10y"], "^TNX yield(decimal)", 0.0, 0.30)

        # 4. FRED DFII10（実質10年債利回り）を取得
        logger.info("[SP500-VAL] Fetching DFII10 from FRED")
        real_yield_df = pd.DataFrame()
        try:
            dfii10_data = fetch_fred_series("DFII10", start_date=start_date)
            if dfii10_data:
                real_yield_df = pd.DataFrame(dfii10_data)
                real_yield_df["date"] = pd.to_datetime(real_yield_df["date"])
                real_yield_df = real_yield_df.rename(columns={"value": "real_yield_10y"})
                real_yield_df["real_yield_10y"] = real_yield_df["real_yield_10y"] / 100  # % → decimal
        except Exception as e:
            logger.warning(f"[SP500-VAL] DFII10 fetch failed (non-fatal): {e}")

        # 5. マージ（PER日次 + S&P500価格 + 10年債利回り + 実質利回り）
        merged = df_pe.merge(sp500, on="date", how="inner")
        merged = merged.merge(tnx, on="date", how="left")
        merged["yield_10y"] = merged["yield_10y"].ffill()
        if not real_yield_df.empty:
            merged = merged.merge(real_yield_df[["date", "real_yield_10y"]], on="date", how="left")
            merged["real_yield_10y"] = merged["real_yield_10y"].ffill()
        else:
            merged["real_yield_10y"] = None

        # 6. 各系列を算出
        merged["forward_eps"] = merged["close"] / merged["forward_pe"]
        merged["earnings_yield"] = 1 / merged["forward_pe"]
        merged["yield_spread"] = merged["earnings_yield"] - merged["yield_10y"]
        merged["real_yield_spread"] = merged["earnings_yield"] - merged["real_yield_10y"]

        # 7. 前年比・前月比を算出
        merged["date_str"] = merged["date"].dt.strftime("%Y-%m-%d")

        # 月平均を計算（テーブル用）
        merged["year_month"] = merged["date"].dt.to_period("M")
        agg_dict = {
            "forward_pe": ("forward_pe", "mean"),
            "forward_eps": ("forward_eps", "mean"),
            "earnings_yield": ("earnings_yield", "mean"),
            "close": ("close", "mean"),
            "yield_10y": ("yield_10y", "mean"),
        }
        if "real_yield_10y" in merged.columns and merged["real_yield_10y"].notna().any():
            agg_dict["real_yield_10y"] = ("real_yield_10y", "mean")
        monthly = merged.groupby("year_month").agg(**agg_dict).reset_index()
        monthly["year_month_str"] = monthly["year_month"].astype(str)

        # 前年比（日次データから、252営業日前との比較）
        merged = merged.sort_values("date").reset_index(drop=True)
        for col in ["forward_pe", "forward_eps", "earnings_yield"]:
            shifted = merged[col].shift(252)
            merged[f"{col}_yoy"] = ((merged[col] - shifted) / shifted * 100).round(2)

        # 前月比（月次平均ベース）
        monthly_mom: Dict[str, Dict[str, Optional[float]]] = {}
        monthly_sorted = monthly.sort_values("year_month").reset_index(drop=True)
        for i in range(len(monthly_sorted)):
            ym = monthly_sorted.iloc[i]["year_month_str"]
            monthly_mom[ym] = {}
            for col in ["forward_pe", "forward_eps", "earnings_yield"]:
                if i > 0:
                    cur = monthly_sorted.iloc[i][col]
                    prev = monthly_sorted.iloc[i - 1][col]
                    if prev and prev != 0:
                        monthly_mom[ym][col] = round(((cur - prev) / prev) * 100, 2)
                    else:
                        monthly_mom[ym][col] = None
                else:
                    monthly_mom[ym][col] = None

        # 8. JSONシリアライズ用にデータを構築
        data_list: List[Dict[str, Any]] = []
        for _, row in merged.iterrows():
            item: Dict[str, Any] = {
                "date": row["date_str"],
                "close": round(float(row["close"]), 2),
                "forward_pe": round(float(row["forward_pe"]), 4),
                "forward_eps": round(float(row["forward_eps"]), 2),
                "earnings_yield": round(float(row["earnings_yield"]), 6),
                "yield_10y": round(float(row["yield_10y"]), 6) if pd.notna(row["yield_10y"]) else None,
                "yield_spread": round(float(row["yield_spread"]), 6) if pd.notna(row["yield_spread"]) else None,
                "real_yield_10y": round(float(row["real_yield_10y"]), 6) if pd.notna(row.get("real_yield_10y")) else None,
                "real_yield_spread": round(float(row["real_yield_spread"]), 6) if pd.notna(row.get("real_yield_spread")) else None,
            }
            for col in ["forward_pe", "forward_eps", "earnings_yield"]:
                yoy_val = row.get(f"{col}_yoy")
                item[f"{col}_yoy"] = round(float(yoy_val), 2) if pd.notna(yoy_val) else None
            data_list.append(item)

        # 月次平均テーブル
        monthly_table: List[Dict[str, Any]] = []
        for _, row in monthly_sorted.iterrows():
            ym = row["year_month_str"]
            mom = monthly_mom.get(ym, {})
            mt_item = {
                "date": ym,
                "forward_pe": round(float(row["forward_pe"]), 2) if pd.notna(row.get("forward_pe")) else None,
                "forward_eps": round(float(row["forward_eps"]), 2) if pd.notna(row.get("forward_eps")) else None,
                "earnings_yield": round(float(row["earnings_yield"]) * 100, 2) if pd.notna(row.get("earnings_yield")) else None,
                "close": round(float(row["close"]), 2) if pd.notna(row.get("close")) else None,
                "yield_10y": round(float(row["yield_10y"]) * 100, 2) if pd.notna(row.get("yield_10y")) else None,
                "forward_pe_mom": mom.get("forward_pe"),
                "forward_eps_mom": mom.get("forward_eps"),
                "earnings_yield_mom": mom.get("earnings_yield"),
            }
            if "real_yield_10y" in monthly_sorted.columns and pd.notna(row.get("real_yield_10y")):
                mt_item["real_yield_10y"] = round(float(row["real_yield_10y"]) * 100, 2)
            monthly_table.append(mt_item)

        latest = data_list[-1] if data_list else None
        file_mtime = self._get_file_mtime()
        now_str = datetime.now(JST).isoformat()

        logger.info(f"[SP500-VAL] Built {len(data_list)} data points, "
                     f"monthly table: {len(monthly_table)} rows")

        return {
            "data": data_list,
            "monthly_table": monthly_table,
            "latest": latest,
            "metadata": {
                "source": "S&P 500 Valuation",
                "source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                "pe_source_url": "https://en.macromicro.me/series/20052/sp500-forward-pe-ratio",
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
            logger.error(f"[SP500-VAL] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[SP500-VAL] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(REDIS_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[SP500-VAL] Redis load error: {e}")
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
            logger.error(f"[SP500-VAL] File load error: {e}")
        return None


sp500_valuation_service = Sp500ValuationService()
