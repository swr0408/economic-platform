"""
LME Copper Stock サービス

データソース:
  - DB: lme_copper_stock テーブル（日次、LME Warehouse）
  - 最新値自動更新: westmetall.com スクレイピング（約3ヶ月分）
  - 銅先物価格: yfinance (HG=F)

更新スケジュール: 日次（JST 8:30）
更新: 6時間TTL (Redis + ファイル)
"""
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
DATA_CACHE_FILE = CACHE_DIR / "lme_copper_stock_cache.json"

DATA_CACHE_KEY = "market:lme_copper_stock:data"


class LmeCopperStockService:
    """LME銅在庫サービス"""

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
        """LME銅在庫データを取得"""
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
            logger.error(f"[LmeCopperStock] Build error: {e}")
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
            "latest_copper": None,
            "metadata": {"source": "LME + yfinance (HG=F)"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _scrape_westmetall(self) -> int:
        """westmetall.comからLME銅データをスクレイピングしDBにUPSERT

        Returns:
            挿入/更新された行数
        """
        import requests
        from bs4 import BeautifulSoup
        from core.database import SessionLocal
        from sqlalchemy import text

        url = "https://www.westmetall.com/en/markdaten.php?action=table&field=LME_Cu_cash"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }

        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"[LmeCopperStock] Westmetall fetch error: {e}")
            return 0

        soup = BeautifulSoup(resp.text, "html.parser")

        # LME Copper テーブルを検索
        target_table = None
        for tbl in soup.find_all("table"):
            thead = tbl.find("thead")
            if thead and "LME Copper" in thead.get_text():
                target_table = tbl
                break

        if not target_table:
            logger.warning("[LmeCopperStock] Westmetall: LME Copper table not found")
            return 0

        tbody = target_table.find("tbody")
        if not tbody:
            return 0

        # 月名マッピング
        MONTH_MAP = {
            "January": 1, "February": 2, "March": 3, "April": 4,
            "May": 5, "June": 6, "July": 7, "August": 8,
            "September": 9, "October": 10, "November": 11, "December": 12,
        }

        records = []
        for tr in tbody.find_all("tr"):
            cells = [td.get_text().strip() for td in tr.find_all("td")]
            if len(cells) < 4:
                continue

            # 日付パース: "13. March 2026"
            date_str = cells[0]
            m = re.match(r"(\d{1,2})\.\s+(\w+)\s+(\d{4})", date_str)
            if not m:
                continue
            day, month_name, year = int(m.group(1)), m.group(2), int(m.group(3))
            month = MONTH_MAP.get(month_name)
            if not month:
                continue

            try:
                dt = datetime(year, month, day).date()
            except ValueError:
                continue

            # 数値パース（カンマ区切り）
            def parse_num(s: str) -> Optional[float]:
                s = s.replace(",", "").strip()
                if not s or s == "-":
                    return None
                try:
                    return float(s)
                except ValueError:
                    return None

            cash = parse_num(cells[1])
            three_m = parse_num(cells[2])
            stock_str = cells[3].replace(",", "").strip()
            stock = int(float(stock_str)) if stock_str and stock_str != "-" else None

            records.append((dt, cash, three_m, stock))

        if not records:
            logger.warning("[LmeCopperStock] Westmetall: no records parsed")
            return 0

        # DB UPSERT
        upserted = 0
        try:
            with SessionLocal() as session:
                for dt, cash, three_m, stock in records:
                    session.execute(text("""
                        INSERT INTO lme_copper_stock (date, cash_usd, three_month_usd, stock_tonnes, source)
                        VALUES (:date, :cash, :three_m, :stock, 'westmetall')
                        ON CONFLICT (date) DO UPDATE SET
                            cash_usd = COALESCE(EXCLUDED.cash_usd, lme_copper_stock.cash_usd),
                            three_month_usd = COALESCE(EXCLUDED.three_month_usd, lme_copper_stock.three_month_usd),
                            stock_tonnes = COALESCE(EXCLUDED.stock_tonnes, lme_copper_stock.stock_tonnes),
                            updated_at = NOW()
                    """), {"date": dt, "cash": cash, "three_m": three_m, "stock": stock})
                    upserted += 1
                session.commit()
        except Exception as e:
            logger.error(f"[LmeCopperStock] Westmetall DB upsert error: {e}")
            return 0

        logger.info(f"[LmeCopperStock] Westmetall: upserted {upserted} records")
        return upserted

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """westmetallから最新データを取得→DBにUPSERT→DB全件読取→銅先物価格を補完"""
        import yfinance as yf
        import pandas as pd
        from core.database import SessionLocal
        from sqlalchemy import text

        logger.info("[LmeCopperStock] Building data...")

        # 0. westmetall.comから最新データをスクレイピングしDBに反映
        try:
            self._scrape_westmetall()
        except Exception as e:
            logger.warning(f"[LmeCopperStock] Westmetall scrape failed (non-fatal): {e}")

        # 1. DBから全データ取得
        try:
            with SessionLocal() as session:
                rows = session.execute(text("""
                    SELECT date, cash_usd, three_month_usd, stock_tonnes
                    FROM lme_copper_stock
                    ORDER BY date ASC
                """)).fetchall()
        except Exception as e:
            logger.error(f"[LmeCopperStock] DB error: {e}")
            return None

        if not rows:
            logger.error("[LmeCopperStock] No data in DB")
            return None

        # 2. yfinance HG=F で最新銅先物価格を取得
        copper_latest: Optional[Dict[str, Any]] = None
        try:
            ticker = yf.Ticker("HG=F")
            hist_d = ticker.history(period="5d", interval="1d")
            if not hist_d.empty:
                hist_d.index = pd.to_datetime(hist_d.index).tz_localize(None)
                hist_d = hist_d.sort_index()
                last_idx = hist_d.index[-1]
                copper_latest = {
                    "date": last_idx.strftime("%Y-%m-%d"),
                    "close": round(float(hist_d.iloc[-1]["Close"]), 4),
                }
        except Exception as e:
            logger.warning(f"[LmeCopperStock] yfinance error: {e}")

        # 3. データ構築
        result_data: List[Dict[str, Any]] = []
        for row in rows:
            date_str = row[0].strftime("%Y-%m-%d")
            cash = round(float(row[1]), 2) if row[1] is not None else None
            three_m = round(float(row[2]), 2) if row[2] is not None else None
            stock = int(row[3]) if row[3] is not None else None

            result_data.append({
                "date": date_str,
                "cash_usd": cash,
                "three_month_usd": three_m,
                "stock_tonnes": stock,
            })

        if not result_data:
            return None

        latest = None
        for item in reversed(result_data):
            if item.get("stock_tonnes") is not None:
                latest = item.copy()
                break
        if latest is None:
            latest = result_data[-1].copy()

        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[LmeCopperStock] Built {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest stock={latest.get('stock_tonnes')} tonnes, "
            f"copper_futures={copper_latest}"
        )

        return {
            "data": result_data,
            "latest": latest,
            "latest_copper": copper_latest,
            "metadata": {
                "source": "LME + yfinance (HG=F)",
                "indicator": "LME Copper Warehouse Stock",
                "unit_price": "USD/tonne",
                "unit_stock": "tonnes",
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
            logger.error(f"[LmeCopperStock] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[LmeCopperStock] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(DATA_CACHE_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[LmeCopperStock] Redis load error: {e}")
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
            logger.error(f"[LmeCopperStock] File load error: {e}")
        return None


# シングルトン
lme_copper_stock_service = LmeCopperStockService()
