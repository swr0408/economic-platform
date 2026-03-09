"""
CBOE Total Put/Call Ratio サービス

データソース:
  - CBOE CDN API: https://cdn.cboe.com/data/us/options/market_statistics/daily/{date}_daily_options
  - DB: cboe_put_call_ratio テーブル（CSV過去データ + 日次積み上げ）
  - S&P 500: yfinance (^GSPC) 日足

更新スケジュール: 日次（JST 8:00）
"""
import json
import logging
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
EST = ZoneInfo("America/New_York")

# キャッシュ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "cboe_pcr_cache.json"

# Redis
DATA_CACHE_KEY = "market:cboe_pcr:data"

# CBOE CDN API
CBOE_CDN_URL = "https://cdn.cboe.com/data/us/options/market_statistics/daily/{date}_daily_options"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


class CboePcrService:
    """CBOE Total Put/Call Ratio サービス"""

    def _should_refresh(self) -> bool:
        """キャッシュの更新が必要かどうか判定"""
        try:
            cached = redis_client.get(DATA_CACHE_KEY)
            if not cached:
                return True

            last_updated_str = cached.get("last_updated")
            if not last_updated_str:
                return True

            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)

            # 6時間以内に更新されていればスキップ
            if (now - last_updated).total_seconds() < 6 * 3600:
                return False

            return True
        except Exception:
            return True

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """PCRデータを取得"""
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
            logger.error(f"[CboePCR] Build error: {e}")
            import traceback
            traceback.print_exc()

        # フォールバック
        cached = self._load_from_redis()
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "CBOE Put/Call Ratio"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _fetch_latest_from_cboe(self) -> Optional[Dict[str, Any]]:
        """CBOE CDN APIから最新のPCRデータを取得し、DBに保存"""
        import requests
        from core.database import SessionLocal
        from sqlalchemy import text

        inserted_count = 0

        # 直近5営業日分を試行（週末スキップ）
        now_est = datetime.now(EST)
        for days_back in range(7):
            target_date = (now_est - timedelta(days=days_back)).date()

            # 週末スキップ
            if target_date.weekday() >= 5:
                continue

            date_str = target_date.strftime("%Y-%m-%d")
            url = CBOE_CDN_URL.format(date=date_str)

            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                ratios = data.get("ratios", [])
                total_pcr = None
                for r in ratios:
                    if r.get("name") == "TOTAL PUT/CALL RATIO":
                        total_pcr = float(r["value"])
                        break

                if total_pcr is None:
                    continue

                # DBに保存
                with SessionLocal() as session:
                    session.execute(text("""
                        INSERT INTO cboe_put_call_ratio (date, total_pcr, source)
                        VALUES (:date, :pcr, 'CBOE_API')
                        ON CONFLICT (date) DO UPDATE SET
                            total_pcr = EXCLUDED.total_pcr,
                            source = 'CBOE_API',
                            updated_at = NOW()
                    """), {"date": date_str, "pcr": total_pcr})
                    session.commit()
                    inserted_count += 1

                logger.info(f"[CboePCR] Fetched {date_str}: PCR={total_pcr}")

            except Exception as e:
                logger.warning(f"[CboePCR] Failed to fetch {date_str}: {e}")
                continue

        if inserted_count > 0:
            logger.info(f"[CboePCR] Inserted/updated {inserted_count} days from CBOE API")

        return None

    def _load_from_db(self) -> List[Dict[str, Any]]:
        """DBからPCRデータを取得"""
        from core.database import SessionLocal
        from sqlalchemy import text

        try:
            with SessionLocal() as session:
                rows = session.execute(text("""
                    SELECT date, total_pcr
                    FROM cboe_put_call_ratio
                    WHERE total_pcr IS NOT NULL
                    ORDER BY date ASC
                """)).fetchall()

                result = []
                for row in rows:
                    result.append({
                        "date": row[0].strftime("%Y-%m-%d"),
                        "pcr": float(row[1]),
                    })

                logger.info(f"[CboePCR] Loaded {len(result)} rows from DB")
                return result

        except Exception as e:
            logger.error(f"[CboePCR] DB load error: {e}")
            return []

    def _get_sp500_daily(self) -> Dict[str, float]:
        """yfinanceからS&P 500日足終値を取得"""
        import yfinance as yf

        try:
            ticker = yf.Ticker("^GSPC")
            end_dt = datetime.now(JST) + timedelta(days=2)
            hist = ticker.history(
                start="2006-10-01",
                end=end_dt.strftime("%Y-%m-%d"),
                interval="1d",
            )

            if hist.empty:
                logger.warning("[CboePCR] No yfinance data for ^GSPC")
                return {}

            result: Dict[str, float] = {}
            for idx, row in hist.iterrows():
                date_str = idx.strftime("%Y-%m-%d")
                result[date_str] = round(float(row["Close"]), 2)

            logger.info(f"[CboePCR] S&P 500 daily: {len(result)} days")
            return result

        except Exception as e:
            logger.error(f"[CboePCR] yfinance error: {e}")
            return {}

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """データを構築"""
        logger.info("[CboePCR] Building data...")

        # 1. CBOE APIから最新データを取得してDBに保存
        self._fetch_latest_from_cboe()

        # 2. DBから全データ取得
        db_data = self._load_from_db()
        if not db_data:
            return None

        # 3. 10日移動平均を計算
        pcr_values = [d["pcr"] for d in db_data]
        pcr_10ma: List[Optional[float]] = []
        for i in range(len(pcr_values)):
            if i < 9:
                pcr_10ma.append(None)
            else:
                window = pcr_values[i - 9 : i + 1]
                pcr_10ma.append(round(sum(window) / 10.0, 4))

        # 4. S&P 500日足データ
        sp500 = self._get_sp500_daily()

        # 5. 全データをマージ
        result_data: List[Dict[str, Any]] = []
        for i, d in enumerate(db_data):
            item: Dict[str, Any] = {
                "date": d["date"],
                "pcr": d["pcr"],
                "pcr_10ma": pcr_10ma[i],
                "sp500": sp500.get(d["date"]),
            }
            result_data.append(item)

        # S&P500のみの日があれば追加（PCRデータがない営業日）
        pcr_dates = {d["date"] for d in db_data}
        for sp_date in sorted(sp500.keys()):
            if sp_date not in pcr_dates and sp_date >= db_data[0]["date"]:
                result_data.append({
                    "date": sp_date,
                    "pcr": None,
                    "pcr_10ma": None,
                    "sp500": sp500[sp_date],
                })

        result_data.sort(key=lambda x: x["date"])

        if not result_data:
            return None

        # latestはPCRデータがある最新日
        latest_with_pcr = [d for d in result_data if d.get("pcr") is not None]
        latest = latest_with_pcr[-1].copy() if latest_with_pcr else result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "CBOE / yfinance",
                "data_count": len(result_data),
                "pcr_count": len(latest_with_pcr),
                "start_date": result_data[0]["date"],
                "end_date": result_data[-1]["date"],
                "pcr_latest": latest_with_pcr[-1]["date"] if latest_with_pcr else None,
            },
            "cached": False,
            "source": "model",
            "last_updated": now_str,
        }

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(DATA_CACHE_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[CboePCR] Redis save error: {e}")

        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[CboePCR] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(DATA_CACHE_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[CboePCR] Redis load error: {e}")
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
            logger.error(f"[CboePCR] File load error: {e}")
        return None


# シングルトン
cboe_pcr_service = CboePcrService()
