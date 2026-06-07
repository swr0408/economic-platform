"""
VIX先物カーブ (VIX Futures Curve) サービス

CBOE Futures Exchange (CFE) の VIX 先物 (VX) 月次限月の決済値から、
第1〜第3限月 (M1/M2/M3) を日次で取得し、以下の指標を算出する:

  - Front Spread        = M1 - M2
  - Double Spread (Curvature) = M1 - 2*M2 + M3
  - M1-M3 Slope         = M1 - M3
  - M1 DTE (残存日数)

データソース:
  - 個別限月CSV: https://cdn.cboe.com/data/us/futures/market_statistics/historical_data/VX/VX_{YYYY-MM-DD}.csv
  - 当日セトル: https://www-api.cboe.com/us/futures/market_statistics/settlement/csv?dt=YYYY-MM-DD
  - S&P 500 オーバーレイ: yfinance ^GSPC

バックフィル開始: 2013-01-16 (新URLパターンが安定して利用可能な範囲)
"""
from __future__ import annotations

import csv
import io
import json
import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import requests
import yfinance as yf

from core.redis_client import redis_client
from services.market.vix_expiration_calendar import list_vx_expiries

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CONTRACTS_DIR = CACHE_DIR / "vx_contracts"
CONTRACTS_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "vix_futures_curve_cache.json"

REDIS_KEY = "market:vix_futures_curve:data"

CONTRACT_CSV_URL = (
    "https://cdn.cboe.com/data/us/futures/market_statistics/historical_data/VX/VX_{date}.csv"
)
DAILY_SETTLEMENT_URL = (
    "https://www-api.cboe.com/us/futures/market_statistics/settlement/csv?dt={date}"
)

BACKFILL_START = date(2013, 1, 1)

# 当日近辺のCSVは存在しない (まだ取引中) ことがあるので何日まで遡るかの上限
MAX_LOOKBACK_DAYS = 7


class VixFuturesCurveService:
    """VIX先物カーブサービス"""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        if not force_refresh and not self._should_refresh():
            cached = self._load_from_redis() or self._load_from_file()
            if cached and cached.get("data"):
                return cached

        try:
            data = self._build_full_dataset()
            if data and data.get("data"):
                self._save_to_cache(data)
                return data
        except Exception as e:
            logger.error(f"VIX先物カーブ取得エラー: {e}", exc_info=True)

        cached = self._load_from_redis() or self._load_from_file()
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "cboe", "description": "VIX Futures Curve"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    # ------------------------------------------------------------------
    # Refresh logic
    # ------------------------------------------------------------------
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
            today_refresh = now.replace(hour=8, minute=0, second=0, microsecond=0)
            if now >= today_refresh and last_updated < today_refresh:
                return True
            return False
        except Exception:
            return True

    # ------------------------------------------------------------------
    # CSV download / caching
    # ------------------------------------------------------------------
    @staticmethod
    def _contract_cache_path(expiry: date) -> Path:
        return CONTRACTS_DIR / f"VX_{expiry.isoformat()}.csv"

    def _download_contract(self, expiry: date, refresh: bool = False) -> Optional[str]:
        """単一限月のCSVテキストを取得（キャッシュ優先）"""
        path = self._contract_cache_path(expiry)
        today = datetime.now(JST).date()
        # 既存ファイルあり、且つ「満期済みかつrefresh不要」なら再ダウンロード不要
        if path.exists() and not refresh and expiry < today:
            try:
                return path.read_text(encoding="utf-8")
            except Exception:
                pass

        url = CONTRACT_CSV_URL.format(date=expiry.isoformat())
        try:
            resp = requests.get(url, timeout=15)
        except Exception as e:
            logger.warning(f"VX契約取得失敗 {expiry}: {e}")
            if path.exists():
                return path.read_text(encoding="utf-8")
            return None
        if resp.status_code != 200:
            if path.exists():
                return path.read_text(encoding="utf-8")
            logger.warning(f"VX契約 {expiry} 取得HTTP {resp.status_code}")
            return None
        text = resp.text
        try:
            path.write_text(text, encoding="utf-8")
        except Exception as e:
            logger.warning(f"VX契約キャッシュ書込失敗 {expiry}: {e}")
        return text

    @staticmethod
    def _parse_contract_csv(text: str) -> Dict[date, float]:
        """CSV → {trade_date: settle} のdictへ"""
        out: Dict[date, float] = {}
        if not text:
            return out
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            try:
                date_str = (row.get("Trade Date") or "").strip()
                if not date_str:
                    continue
                # 新パターン: "YYYY-MM-DD" / 旧archive: "MM/DD/YYYY"
                if "/" in date_str:
                    td = datetime.strptime(date_str, "%m/%d/%Y").date()
                else:
                    td = datetime.fromisoformat(date_str).date()
                settle_str = (row.get("Settle") or "").strip()
                if not settle_str:
                    continue
                settle = float(settle_str)
                # 期限到来日の0埋め行（Open/High/Low/Volumeが0かつSettleのみ値あり）も settle としては有効
                if settle <= 0:
                    continue
                out[td] = settle
            except Exception:
                continue
        return out

    # ------------------------------------------------------------------
    # Build full dataset
    # ------------------------------------------------------------------
    def _build_full_dataset(self) -> Dict[str, Any]:
        start_date = BACKFILL_START
        # 最低でも今日から3限月先までは取得
        today = datetime.now(JST).date()
        end_horizon = today + timedelta(days=200)

        expiries = list_vx_expiries(start_date, end_horizon)
        logger.info(f"VX限月数: {len(expiries)} ({expiries[0] if expiries else '-'} 〜 {expiries[-1] if expiries else '-'})")

        # 各限月の settle 辞書を蓄積
        contract_settles: List[Tuple[date, Dict[date, float]]] = []
        for exp in expiries:
            # 直近〜未来の限月は再ダウンロード
            refresh = exp >= today - timedelta(days=7)
            text = self._download_contract(exp, refresh=refresh)
            if not text:
                continue
            settles = self._parse_contract_csv(text)
            if settles:
                contract_settles.append((exp, settles))

        if not contract_settles:
            return {"data": [], "latest": None, "metadata": {}, "cached": False, "source": "error", "last_updated": None}

        # 全 trade_date 集合
        all_trade_dates: set = set()
        for _, settles in contract_settles:
            all_trade_dates.update(settles.keys())
        sorted_trade_dates = sorted(all_trade_dates)

        # S&P 500 オーバーレイ
        sp500_map = self._fetch_sp500_map(sorted_trade_dates[0], sorted_trade_dates[-1])

        # 各営業日について M1, M2, M3 を解決
        rows: List[Dict[str, Any]] = []
        for td in sorted_trade_dates:
            if td < start_date:
                continue
            m_settles: List[Tuple[date, float]] = []
            for exp, settles in contract_settles:
                if exp < td:
                    continue
                s = settles.get(td)
                if s is None:
                    continue
                m_settles.append((exp, s))
                if len(m_settles) >= 4:
                    break
            if len(m_settles) < 3:
                continue
            m1_exp, m1 = m_settles[0]
            m2_exp, m2 = m_settles[1]
            m3_exp, m3 = m_settles[2]

            front_spread = round(m1 - m2, 4)
            double_spread = round(m1 - 2 * m2 + m3, 4)
            m1_m3_slope = round(m1 - m3, 4)
            m1_dte = (m1_exp - td).days

            row: Dict[str, Any] = {
                "date": td.isoformat(),
                "m1_settle": round(m1, 4),
                "m2_settle": round(m2, 4),
                "m3_settle": round(m3, 4),
                "front_spread": front_spread,
                "double_spread": double_spread,
                "m1_m3_slope": m1_m3_slope,
                "m1_dte": m1_dte,
                "m1_expiry": m1_exp.isoformat(),
            }
            sp = sp500_map.get(td.isoformat())
            if sp is not None:
                row["sp500"] = sp
            rows.append(row)

        latest = rows[-1] if rows else None

        logger.info(f"VIX先物カーブ: {len(rows)}件 ({rows[0]['date'] if rows else '-'} 〜 {rows[-1]['date'] if rows else '-'})")

        return {
            "data": rows,
            "latest": latest,
            "metadata": {
                "source": "cboe_cfe",
                "description": "VIX Futures Curve (VX1 / VX2 / VX3 Settlement)",
                "data_points": len(rows),
                "contracts_loaded": len(contract_settles),
                "backfill_start": BACKFILL_START.isoformat(),
            },
            "cached": False,
            "source": "api",
            "last_updated": datetime.now(JST).isoformat(),
        }

    # ------------------------------------------------------------------
    # S&P 500 overlay (yfinance)
    # ------------------------------------------------------------------
    @staticmethod
    def _fetch_sp500_map(start_d: date, end_d: date) -> Dict[str, float]:
        try:
            df = yf.download(
                "^GSPC",
                start=start_d.isoformat(),
                end=(end_d + timedelta(days=1)).isoformat(),
                progress=False,
                auto_adjust=False,
            )
            if df.empty:
                return {}
            import pandas as pd  # local import
            if isinstance(df.columns, pd.MultiIndex):
                close = df[("Close", "^GSPC")]
            else:
                close = df["Close"]
            out: Dict[str, float] = {}
            for idx, val in close.items():
                if pd.isna(val):
                    continue
                out[idx.strftime("%Y-%m-%d")] = round(float(val), 2)
            return out
        except Exception as e:
            logger.warning(f"S&P500オーバーレイ取得失敗: {e}")
            return {}

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------
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


vix_futures_curve_service = VixFuturesCurveService()
