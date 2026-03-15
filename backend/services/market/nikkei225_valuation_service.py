"""
日経平均 Valuation サービス

データソース:
  - 予想PER: backend/data/csv_import/nikkei225_per.csv (Nikkei Indexes由来)
    参照: https://indexes.nikkei.co.jp/en/nkave/archives/data?list=per
  - 日経平均価格: yfinance (^N225)
  - 日本10年国債利回り: FRED (IRLTLT01JPM156N) ※月次→日次前方充填

算出系列:
  - 予想EPS = 指数値 ÷ 予想PER
  - 予想株式益利回り = 1 ÷ 予想PER
  - 予想イールドスプレッド = 予想株式益利回り − 日本10年国債利回り
  - 予想イールドレシオ = 予想株式益利回り ÷ 日本10年国債利回り

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
import requests
import yfinance as yf

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CSV_DIR = Path(__file__).parent.parent.parent / "data" / "csv_import"
CSV_FILE = CSV_DIR / "nikkei225_per.csv"
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "nikkei225_valuation_cache.json"

REDIS_KEY = "market:nikkei225_valuation:data"

# FRED series for Japan 10Y government bond yield (monthly)
FRED_JGB_SERIES = "IRLTLT01JPM156N"


class Nikkei225ValuationService:
    """日経平均 Valuation サービス"""

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
            logger.error(f"[NIKKEI-VAL] Build error: {e}")
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
            "metadata": {"source": "Nikkei 225 Valuation"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _fetch_jgb_yield(self, start_date: str) -> Optional[pd.DataFrame]:
        """FREDから日本10年国債利回り(月次)を取得"""
        try:
            fred_api_key = os.environ.get("FRED_API_KEY", "")
            if not fred_api_key:
                logger.warning("[NIKKEI-VAL] FRED_API_KEY not set")
                return None

            url = (
                f"https://api.stlouisfed.org/fred/series/observations"
                f"?series_id={FRED_JGB_SERIES}"
                f"&observation_start={start_date}"
                f"&api_key={fred_api_key}"
                f"&file_type=json"
            )
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            obs = resp.json().get("observations", [])

            if not obs:
                logger.warning("[NIKKEI-VAL] No JGB yield data from FRED")
                return None

            rows = []
            for o in obs:
                if o["value"] != ".":
                    rows.append({
                        "date": pd.Timestamp(o["date"]),
                        "yield_10y": float(o["value"]) / 100,  # % → decimal
                    })

            if not rows:
                return None

            df = pd.DataFrame(rows)
            logger.info(f"[NIKKEI-VAL] FRED JGB yield: {len(df)} monthly observations")
            return df

        except Exception as e:
            logger.error(f"[NIKKEI-VAL] FRED JGB fetch error: {e}")
            return None

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """CSVから予想PERを読み込み、yfinanceで価格、FREDで金利を取得し、各系列を算出"""
        if not CSV_FILE.exists():
            logger.error(f"[NIKKEI-VAL] CSV file not found: {CSV_FILE}")
            return None

        logger.info(f"[NIKKEI-VAL] Reading CSV: {CSV_FILE}")

        # 1. CSV読み込み（予想PER - index_weight_basis列を使用）
        try:
            df_pe = pd.read_csv(CSV_FILE, encoding="utf-8-sig")
            df_pe["date"] = pd.to_datetime(df_pe["date"])
            # index_weight_basis を予想PERとして使用
            df_pe = df_pe[["date", "index_weight_basis"]].rename(
                columns={"index_weight_basis": "forward_pe"}
            )
            df_pe = df_pe.dropna(subset=["forward_pe"])
            df_pe = df_pe.sort_values("date").reset_index(drop=True)
        except Exception as e:
            logger.error(f"[NIKKEI-VAL] CSV parse error: {e}")
            return None

        if df_pe.empty:
            logger.error("[NIKKEI-VAL] No data in CSV")
            return None

        start_date = df_pe["date"].min().strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        # 2. yfinanceから日経平均価格を取得
        logger.info(f"[NIKKEI-VAL] Fetching ^N225 from {start_date} to {end_date}")
        try:
            nikkei = yf.download("^N225", start=start_date, end=end_date, progress=False)
            if nikkei.empty:
                logger.error("[NIKKEI-VAL] No Nikkei price data from yfinance")
                return None
            nikkei = nikkei[["Close"]].reset_index()
            nikkei.columns = ["date", "close"]
            nikkei["date"] = pd.to_datetime(nikkei["date"]).dt.tz_localize(None)
        except Exception as e:
            logger.error(f"[NIKKEI-VAL] yfinance ^N225 error: {e}")
            return None

        # 3. FREDから日本10年国債利回りを取得（月次）
        df_jgb = self._fetch_jgb_yield(start_date)

        # 4. マージ（PER日次 + 日経平均価格）
        merged = df_pe.merge(nikkei, on="date", how="inner")

        # JGB利回りをマージ（月次→日次に前方充填）
        if df_jgb is not None and not df_jgb.empty:
            merged = merged.merge(df_jgb, on="date", how="left")
            merged["yield_10y"] = merged["yield_10y"].ffill()
        else:
            merged["yield_10y"] = None

        # 5. 各系列を算出
        merged["forward_eps"] = merged["close"] / merged["forward_pe"]
        merged["earnings_yield"] = 1 / merged["forward_pe"]

        has_yield = merged["yield_10y"].notna().any()
        if has_yield:
            merged["yield_spread"] = merged["earnings_yield"] - merged["yield_10y"]
            # yield_10yが0の場合はratioをNoneに
            merged["yield_ratio"] = merged.apply(
                lambda r: r["earnings_yield"] / r["yield_10y"]
                if pd.notna(r["yield_10y"]) and r["yield_10y"] != 0
                else None,
                axis=1,
            )
        else:
            merged["yield_spread"] = None
            merged["yield_ratio"] = None

        # 6. 前年比・前月比を算出
        merged["date_str"] = merged["date"].dt.strftime("%Y-%m-%d")

        # 月平均を計算（テーブル用）
        merged["year_month"] = merged["date"].dt.to_period("M")
        monthly = merged.groupby("year_month").agg(
            forward_pe=("forward_pe", "mean"),
            forward_eps=("forward_eps", "mean"),
            earnings_yield=("earnings_yield", "mean"),
            close=("close", "mean"),
            yield_10y=("yield_10y", "mean"),
        ).reset_index()
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

        # 7. JSONシリアライズ用にデータを構築
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
                "yield_ratio": round(float(row["yield_ratio"]), 4) if pd.notna(row["yield_ratio"]) else None,
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
            monthly_table.append({
                "date": ym,
                "forward_pe": round(float(row["forward_pe"]), 2),
                "forward_eps": round(float(row["forward_eps"]), 2),
                "earnings_yield": round(float(row["earnings_yield"]) * 100, 2),
                "close": round(float(row["close"]), 2),
                "yield_10y": round(float(row["yield_10y"]) * 100, 2) if pd.notna(row["yield_10y"]) else None,
                "forward_pe_mom": mom.get("forward_pe"),
                "forward_eps_mom": mom.get("forward_eps"),
                "earnings_yield_mom": mom.get("earnings_yield"),
            })

        latest = data_list[-1] if data_list else None
        file_mtime = self._get_file_mtime()
        now_str = datetime.now(JST).isoformat()

        logger.info(f"[NIKKEI-VAL] Built {len(data_list)} data points, "
                     f"monthly table: {len(monthly_table)} rows")

        return {
            "data": data_list,
            "monthly_table": monthly_table,
            "latest": latest,
            "metadata": {
                "source": "Nikkei 225 Valuation",
                "source_url": "https://indexes.nikkei.co.jp/en/nkave/archives/data?list=per",
                "pe_source_url": "https://indexes.nikkei.co.jp/en/nkave/archives/data?list=per",
                "pe_source": "Nikkei Indexes",
                "yield_source": "FRED (IRLTLT01JPM156N)",
                "file_name": CSV_FILE.name,
                "file_mtime": file_mtime,
                "data_count": len(data_list),
                "date_range": {
                    "start": data_list[0]["date"] if data_list else None,
                    "end": data_list[-1]["date"] if data_list else None,
                },
                "series": [
                    "forward_pe (予想PER: 指数ウェイトベース)",
                    "forward_eps (予想EPS = 指数値÷予想PER)",
                    "earnings_yield (予想株式益利回り = 1÷予想PER)",
                    "yield_10y (日本10年国債利回り: FRED月次→日次充填)",
                    "yield_spread (予想イールドスプレッド = 益利回り−10年債)",
                    "yield_ratio (予想イールドレシオ = 益利回り÷10年債)",
                ],
            },
            "cached": False,
            "source": "csv+yfinance+fred",
            "last_updated": now_str,
        }

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(REDIS_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[NIKKEI-VAL] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[NIKKEI-VAL] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(REDIS_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[NIKKEI-VAL] Redis load error: {e}")
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
            logger.error(f"[NIKKEI-VAL] File load error: {e}")
        return None


nikkei225_valuation_service = Nikkei225ValuationService()
