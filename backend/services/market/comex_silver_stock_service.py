"""
COMEX Silver Stock サービス

データソース:
  - DB: comex_silver_stock テーブル（日次、COMEX Warehouse）
  - 最新値自動更新: CME Silver_stocks.xls（日次レポート）
  - 銀先物価格: yfinance (SI=F)

更新スケジュール: 日次（JST 8:30）
更新: 6時間TTL (Redis + ファイル)
"""
import io
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "comex_silver_stock_cache.json"

DATA_CACHE_KEY = "market:comex_silver_stock:data"

CME_XLS_URL = "https://www.cmegroup.com/delivery_reports/Silver_stocks.xls"


class ComexSilverStockService:
    """COMEX銀在庫サービス"""

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
        """COMEX銀在庫データを取得"""
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
            logger.error(f"[ComexSilverStock] Build error: {e}")
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
            "latest_silver": None,
            "metadata": {"source": "CME COMEX + yfinance (SI=F)"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _scrape_cme_xls(self) -> int:
        """CME Silver_stocks.xls から最新データをスクレイピングしDBにUPSERT

        Returns:
            挿入/更新された行数
        """
        import requests
        import xlrd
        from core.database import SessionLocal
        from sqlalchemy import text

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }

        try:
            resp = requests.get(CME_XLS_URL, headers=headers, timeout=30)
            if resp.status_code != 200:
                logger.warning(
                    f"[ComexSilverStock] CME XLS fetch failed: HTTP {resp.status_code}"
                )
                return 0
        except Exception as e:
            logger.warning(f"[ComexSilverStock] CME XLS fetch error: {e}")
            return 0

        try:
            wb = xlrd.open_workbook(file_contents=resp.content)
            ws = wb.sheet_by_index(0)
        except Exception as e:
            logger.warning(f"[ComexSilverStock] XLS parse error: {e}")
            return 0

        # Report Date パース (Row 7, Col 6): "Report Date: M/DD/YYYY"
        report_date = None
        try:
            date_cell = str(ws.cell_value(7, 6)).strip()
            m = re.search(r"Report Date:\s*(\d{1,2}/\d{1,2}/\d{4})", date_cell)
            if m:
                report_date = datetime.strptime(m.group(1), "%m/%d/%Y").date()
        except Exception as e:
            logger.warning(f"[ComexSilverStock] Date parse error: {e}")

        if not report_date:
            logger.warning("[ComexSilverStock] Could not parse Report Date from XLS")
            return 0

        # TOTAL REGISTERED, TOTAL ELIGIBLE, COMBINED TOTAL を探す
        registered = None
        eligible = None
        combined = None

        for r in range(ws.nrows):
            cell_val = str(ws.cell_value(r, 0)).strip().upper()
            if "TOTAL REGISTERED" in cell_val:
                val = ws.cell_value(r, 7)  # TOTAL TODAY column
                if isinstance(val, (int, float)) and val > 0:
                    registered = val
            elif "TOTAL ELIGIBLE" in cell_val:
                val = ws.cell_value(r, 7)
                if isinstance(val, (int, float)) and val > 0:
                    eligible = val
            elif "COMBINED TOTAL" in cell_val:
                val = ws.cell_value(r, 7)
                if isinstance(val, (int, float)) and val > 0:
                    combined = val

        if combined is None:
            logger.warning("[ComexSilverStock] COMBINED TOTAL not found in XLS")
            return 0

        # DB UPSERT
        try:
            with SessionLocal() as session:
                session.execute(text("""
                    INSERT INTO comex_silver_stock
                        (date, registered_oz, eligible_oz, total_oz, source)
                    VALUES (:date, :registered, :eligible, :total, 'CME')
                    ON CONFLICT (date) DO UPDATE SET
                        registered_oz = COALESCE(EXCLUDED.registered_oz, comex_silver_stock.registered_oz),
                        eligible_oz = COALESCE(EXCLUDED.eligible_oz, comex_silver_stock.eligible_oz),
                        total_oz = COALESCE(EXCLUDED.total_oz, comex_silver_stock.total_oz),
                        updated_at = NOW()
                """), {
                    "date": report_date,
                    "registered": registered,
                    "eligible": eligible,
                    "total": combined,
                })
                session.commit()
        except Exception as e:
            logger.error(f"[ComexSilverStock] DB upsert error: {e}")
            return 0

        reg_str = f"{registered:,.0f}" if registered else "N/A"
        elig_str = f"{eligible:,.0f}" if eligible else "N/A"
        logger.info(
            f"[ComexSilverStock] CME XLS: date={report_date}, "
            f"total={combined:,.0f}, registered={reg_str}, eligible={elig_str}"
        )
        return 1

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """CME XLSから最新データ取得→DB UPSERT→DB全件読取→銀先物価格を補完"""
        import yfinance as yf
        import pandas as pd
        from core.database import SessionLocal
        from sqlalchemy import text

        logger.info("[ComexSilverStock] Building data...")

        # 0. CME XLSから最新データをスクレイピングしDBに反映
        try:
            self._scrape_cme_xls()
        except Exception as e:
            logger.warning(f"[ComexSilverStock] CME XLS scrape failed (non-fatal): {e}")

        # 1. DBから全データ取得
        try:
            with SessionLocal() as session:
                rows = session.execute(text("""
                    SELECT date, registered_oz, eligible_oz, total_oz
                    FROM comex_silver_stock
                    ORDER BY date ASC
                """)).fetchall()
        except Exception as e:
            logger.error(f"[ComexSilverStock] DB error: {e}")
            return None

        if not rows:
            logger.error("[ComexSilverStock] No data in DB")
            return None

        # 2. yfinance SI=F で最新銀先物価格を取得
        silver_latest: Optional[Dict[str, Any]] = None
        try:
            ticker = yf.Ticker("SI=F")
            hist_d = ticker.history(period="5d", interval="1d")
            if not hist_d.empty:
                hist_d.index = pd.to_datetime(hist_d.index).tz_localize(None)
                hist_d = hist_d.sort_index()
                last_idx = hist_d.index[-1]
                silver_latest = {
                    "date": last_idx.strftime("%Y-%m-%d"),
                    "close": round(float(hist_d.iloc[-1]["Close"]), 4),
                }
        except Exception as e:
            logger.warning(f"[ComexSilverStock] yfinance error: {e}")

        # 3. データ構築
        result_data: List[Dict[str, Any]] = []
        for row in rows:
            date_str = row[0].strftime("%Y-%m-%d")
            registered = round(float(row[1]), 3) if row[1] is not None else None
            eligible = round(float(row[2]), 3) if row[2] is not None else None
            total = round(float(row[3]), 3) if row[3] is not None else None

            result_data.append({
                "date": date_str,
                "registered_oz": registered,
                "eligible_oz": eligible,
                "total_oz": total,
            })

        if not result_data:
            return None

        latest = None
        for item in reversed(result_data):
            if item.get("total_oz") is not None:
                latest = item.copy()
                break
        if latest is None:
            latest = result_data[-1].copy()

        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[ComexSilverStock] Built {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest total={latest.get('total_oz'):,.0f} oz, "
            f"silver_futures={silver_latest}"
        )

        return {
            "data": result_data,
            "latest": latest,
            "latest_silver": silver_latest,
            "metadata": {
                "source": "CME COMEX + yfinance (SI=F)",
                "indicator": "COMEX Silver Warehouse Stock",
                "unit": "troy oz",
                "frequency": "daily",
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
            logger.error(f"[ComexSilverStock] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[ComexSilverStock] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(DATA_CACHE_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[ComexSilverStock] Redis load error: {e}")
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
            logger.error(f"[ComexSilverStock] File load error: {e}")
        return None


# シングルトン
comex_silver_stock_service = ComexSilverStockService()
