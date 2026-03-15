"""
投資部門別売買状況 サービス

データソース:
  - DB: jpx_investor_trading テーブル（週次ネット売買金額、千円単位）
  - 日経平均日足: yfinance (^N225)

更新スケジュール: 毎週第4営業日（通常木曜）JST 15:30
更新: 6時間TTL (Redis + ファイル)
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# キャッシュ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "jpx_investor_trading_cache.json"

# Redis
DATA_CACHE_KEY = "market:jpx_investor_trading:data"

# 千円 → 億円 変換 (1億 = 100,000千円)
OKU_DIVISOR = 100_000


class JpxInvestorTradingService:
    """投資部門別売買状況サービス"""

    def _should_refresh(self) -> bool:
        try:
            cached = redis_client.get(DATA_CACHE_KEY)
            if not cached:
                return True
            last_updated_str = cached.get("last_updated")
            if not last_updated_str:
                return True
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)
            if (now - last_updated).total_seconds() < 6 * 3600:
                return False
            return True
        except Exception:
            return True

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """投資部門別売買状況データを取得"""
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
            logger.error(f"[JpxInvTrading] Build error: {e}")
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
            "metadata": {"source": "JPX + yfinance"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """DBから取得し日経平均日足をマージ"""
        import yfinance as yf
        import pandas as pd
        from core.database import SessionLocal
        from sqlalchemy import text

        logger.info("[JpxInvTrading] Building data...")

        # 1. DBから全データ取得
        try:
            with SessionLocal() as session:
                rows = session.execute(text("""
                    SELECT date, individuals, foreigners, trust_banks,
                           investment_trusts, business_corps, proprietary
                    FROM jpx_investor_trading
                    ORDER BY date ASC
                """)).fetchall()
        except Exception as e:
            logger.error(f"[JpxInvTrading] DB error: {e}")
            return None

        if not rows:
            logger.error("[JpxInvTrading] No data in DB")
            return None

        # 2. 日経平均週足を取得
        first_date = rows[0][0].strftime("%Y-%m-%d")
        nikkei_map: Dict[str, float] = {}  # 週の開始日 → 終値
        nikkei_latest: Optional[Dict[str, Any]] = None  # 最新日足
        try:
            ticker = yf.Ticker("^N225")
            end_dt = datetime.now(JST) + timedelta(days=7)
            # 週足
            hist_w = ticker.history(
                start=first_date,
                end=end_dt.strftime("%Y-%m-%d"),
                interval="1wk",
            )
            if not hist_w.empty:
                nikkei_df = hist_w[["Close"]].copy()
                nikkei_df.index = pd.to_datetime(nikkei_df.index).tz_localize(None)
                nikkei_df = nikkei_df.sort_index()
                for idx, row_data in nikkei_df.iterrows():
                    nikkei_map[idx.strftime("%Y-%m-%d")] = round(float(row_data["Close"]), 2)
                logger.info(f"[JpxInvTrading] Nikkei weekly: {len(nikkei_map)} weeks")
            # 日足で最新値を取得（最新値ボックス用）
            hist_d = ticker.history(period="5d", interval="1d")
            if not hist_d.empty:
                hist_d.index = pd.to_datetime(hist_d.index).tz_localize(None)
                hist_d = hist_d.sort_index()
                last_idx = hist_d.index[-1]
                nikkei_latest = {
                    "date": last_idx.strftime("%Y-%m-%d"),
                    "close": round(float(hist_d.iloc[-1]["Close"]), 2),
                }
        except Exception as e:
            logger.warning(f"[JpxInvTrading] yfinance error: {e}")

        # 3. マージ
        result_data: List[Dict[str, Any]] = []
        for row in rows:
            date_str = row[0].strftime("%Y-%m-%d")

            def _to_oku(val) -> Optional[float]:
                if val is None:
                    return None
                return round(val / OKU_DIVISOR, 1)

            # 日経平均: 週の開始日に最も近い終値を探す
            nikkei_close = None
            dt = pd.Timestamp(date_str)
            # 当日 → 1日ずつ前に遡って最大7日
            for delta in range(8):
                check = (dt + timedelta(days=delta)).strftime("%Y-%m-%d")
                if check in nikkei_map:
                    nikkei_close = nikkei_map[check]
                    break
            if nikkei_close is None:
                # 前方も探す
                for delta in range(1, 8):
                    check = (dt - timedelta(days=delta)).strftime("%Y-%m-%d")
                    if check in nikkei_map:
                        nikkei_close = nikkei_map[check]
                        break

            result_data.append({
                "date": date_str,
                "individuals": _to_oku(row[1]),
                "foreigners": _to_oku(row[2]),
                "trust_banks": _to_oku(row[3]),
                "investment_trusts": _to_oku(row[4]),
                "business_corps": _to_oku(row[5]),
                "proprietary": _to_oku(row[6]),
                "nikkei_close": nikkei_close,
            })

        if not result_data:
            return None

        latest = result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        # 4. 売買データ最終日以降の日経週足を追加（チャートを最新週まで延長）
        last_trading_date = result_data[-1]["date"]
        trailing_weeks = sorted([d for d in nikkei_map.keys() if d > last_trading_date])
        for wdate in trailing_weeks:
            result_data.append({
                "date": wdate,
                "individuals": None,
                "foreigners": None,
                "trust_banks": None,
                "investment_trusts": None,
                "business_corps": None,
                "proprietary": None,
                "nikkei_close": nikkei_map[wdate],
            })

        # latest_nikkei: 日足の最新値（最新値ボックス用）
        latest_nikkei = nikkei_latest

        logger.info(
            f"[JpxInvTrading] Built {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest: individuals={latest.get('individuals')}, "
            f"foreigners={latest.get('foreigners')}, "
            f"latest_nikkei={latest_nikkei}"
        )

        return {
            "data": result_data,
            "latest": latest,
            "latest_nikkei": latest_nikkei,
            "metadata": {
                "source": "JPX + yfinance (^N225)",
                "indicator": "Investor Type Weekly Trading (Net)",
                "unit": "億円",
                "frequency": "weekly",
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
            redis_client.set(DATA_CACHE_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[JpxInvTrading] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[JpxInvTrading] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(DATA_CACHE_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[JpxInvTrading] Redis load error: {e}")
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
            logger.error(f"[JpxInvTrading] File load error: {e}")
        return None


# シングルトン
jpx_investor_trading_service = JpxInvestorTradingService()
