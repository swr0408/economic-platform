"""
SHFE Copper Stock サービス

データソース:
  - DB: shfe_copper_stock テーブル（日次、SHFE Warehouse）
  - 最新値自動更新（プライマリ）: Eastmoney 期货库存 API
    (datacenter-web.eastmoney.com RPT_FUTU_STOCKDATA, SECURITY_CODE=CU)
    ※ 約3ヶ月分のローリングウィンドウを毎回返すため、スケジューラが
      数週間止まっても自動でバックフィルされる。
    ※ 旧プライマリ commoditieschart.net は 2026-04-03 で更新停止
      （凍結確認 2026-06-12）→ フォールバックに降格。
      Eastmoney 値は旧ソースと完全一致を確認済み（2026-03-03〜04-03 の24日分）。
  - 手動更新: CSVインポート (scripts/import_shfe_copper_stock.py)

更新スケジュール: 日次（JP_CLOSE: JST 16:30 / 20:30）
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
DATA_CACHE_FILE = CACHE_DIR / "shfe_copper_stock_cache.json"

DATA_CACHE_KEY = "market:shfe_copper_stock:data"

SCRAPE_URL = "https://commoditieschart.net/metals/copper/shfe-copper-stocks"

# Eastmoney 期货库存データセンター (https://data.eastmoney.com/ifdata/kcsj.html)
EASTMONEY_API_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
EASTMONEY_COPPER_CODE = "CU"  # 沪铜 (SHFE copper)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
}


class ShfeCopperStockService:
    """SHFE銅在庫サービス"""

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
        """SHFE銅在庫データを取得"""
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
            logger.error(f"[ShfeCopperStock] Build error: {e}")
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
            "metadata": {"source": "SHFE (Eastmoney)"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _fetch_eastmoney(self) -> List[tuple]:
        """Eastmoney 期货库存 API から SHFE銅在庫（日次）を取得

        約3ヶ月分のローリングウィンドウが返るため、取りこぼした週も
        毎回の取得で自動的にバックフィルされる。

        Returns:
            [(date_str, stock_tonnes_int), ...]（取得失敗時は空リスト）
        """
        import requests

        headers = dict(BROWSER_HEADERS)
        headers["Referer"] = "https://data.eastmoney.com/ifdata/kcsj.html"

        def _query_stock(security_code: str) -> List[tuple]:
            params = {
                "reportName": "RPT_FUTU_STOCKDATA",
                "columns": "SECURITY_CODE,TRADE_DATE,ON_WARRANT_NUM,ADDCHANGE",
                "filter": f'(SECURITY_CODE="{security_code}")',
                "pageNumber": "1",
                "pageSize": "5000",
                "sortTypes": "-1",
                "sortColumns": "TRADE_DATE",
                "source": "WEB",
                "client": "WEB",
            }
            resp = requests.get(
                EASTMONEY_API_URL, params=params, headers=headers, timeout=30
            )
            if resp.status_code != 200:
                logger.warning(
                    f"[ShfeCopperStock] Eastmoney HTTP {resp.status_code}"
                )
                return []
            j = resp.json()
            rows = (j.get("result") or {}).get("data") or []
            records: List[tuple] = []
            for row in rows:
                trade_date = row.get("TRADE_DATE")
                stock = row.get("ON_WARRANT_NUM")
                if not trade_date or stock is None:
                    continue
                records.append((str(trade_date)[:10], int(stock)))
            records.sort(key=lambda x: x[0])
            return records

        try:
            records = _query_stock(EASTMONEY_COPPER_CODE)
            if records:
                return records

            # コードドリフト対策: 銘柄コード一覧から「沪铜」を動的解決して再試行
            logger.warning(
                "[ShfeCopperStock] Eastmoney empty for code "
                f"'{EASTMONEY_COPPER_CODE}', resolving code dynamically..."
            )
            resp = requests.get(
                EASTMONEY_API_URL,
                params={
                    "reportName": "RPT_FUTU_POSITIONCODE",
                    "columns": "TRADE_MARKET_CODE,TRADE_CODE,TRADE_TYPE",
                    "filter": '(IS_MAINCODE="1")',
                    "pageNumber": "1",
                    "pageSize": "500",
                    "source": "WEB",
                    "client": "WEB",
                },
                headers=headers,
                timeout=30,
            )
            rows = (resp.json().get("result") or {}).get("data") or []
            code = next(
                (r["TRADE_CODE"] for r in rows if r.get("TRADE_TYPE") == "沪铜"),
                None,
            )
            if code and code != EASTMONEY_COPPER_CODE:
                logger.info(f"[ShfeCopperStock] Resolved 沪铜 code: {code}")
                return _query_stock(code)
        except Exception as e:
            logger.warning(f"[ShfeCopperStock] Eastmoney fetch error: {e}")
        return []

    def _fetch_commoditieschart(self) -> List[tuple]:
        """commoditieschart.net からスクレイピング（フォールバック）

        注意: 2026-04-03 でサイト自体の更新が停止（2026-06-12確認）。
        Eastmoney 失敗時の保険としてのみ残している。

        Returns:
            [(date_str, stock_tonnes_int), ...]（取得失敗時は空リスト）
        """
        import requests

        try:
            resp = requests.get(SCRAPE_URL, headers=BROWSER_HEADERS, timeout=30)
            if resp.status_code != 200:
                logger.warning(
                    f"[ShfeCopperStock] Scrape failed: HTTP {resp.status_code}"
                )
                return []
        except Exception as e:
            logger.warning(f"[ShfeCopperStock] Scrape error: {e}")
            return []

        html = resp.text

        # Pattern 1: 2026 以降サイトは非エスケープ・引用符なしキー形式に変更:
        #   {d:"YYYY-MM-DD",v:12345,date:"YYYY-MM-DD",value:12345}
        # 旧エスケープ形式 ({\"d\":\"...\",\"v\":...}) も後方互換で許容する。
        pattern1 = r'\{(?:\\")?d(?:\\")?:(?:\\")?(\d{4}-\d{2}-\d{2})(?:\\")?,(?:\\")?v(?:\\")?:(\d+)'
        matches1 = re.findall(pattern1, html)

        # Pattern 2: ["MMM DD,YYYY",value] / [\"MMM DD,YYYY\",value]
        #   groupedData の ["Oct 06,2008",7526] 形式（エスケープ有無どちらも）
        pattern2 = r'\[(?:\\")?([A-Z][a-z]{2} \d{2},\d{4})(?:\\")?,(\d+)\]'
        matches2 = re.findall(pattern2, html)

        seen: set[str] = set()
        records: list[tuple[str, int]] = []

        for date_str, value in matches1:
            if date_str not in seen:
                seen.add(date_str)
                records.append((date_str, int(value)))

        for date_raw, value in matches2:
            try:
                dt = datetime.strptime(date_raw, "%b %d,%Y")
                date_str = dt.strftime("%Y-%m-%d")
                if date_str not in seen:
                    seen.add(date_str)
                    records.append((date_str, int(value)))
            except ValueError:
                continue

        if not records:
            logger.warning("[ShfeCopperStock] No data extracted from page")
        records.sort(key=lambda x: x[0])
        return records

    def _scrape_latest(self) -> int:
        """最新データを取得しDBにUPSERT

        プライマリ: Eastmoney API（約3ヶ月分 → 取りこぼし自動バックフィル）
        フォールバック: commoditieschart.net スクレイピング

        Returns:
            挿入/更新された行数
        """
        from core.database import SessionLocal
        from sqlalchemy import text

        records = self._fetch_eastmoney()
        source_name = "eastmoney"
        if not records:
            logger.warning(
                "[ShfeCopperStock] Eastmoney returned no data, "
                "falling back to commoditieschart.net"
            )
            records = self._fetch_commoditieschart()
            source_name = "commoditieschart"

        if not records:
            logger.warning("[ShfeCopperStock] No data from any source")
            return 0

        # DB内の最新日付を取得して、新しいデータのみUPSERT
        upserted = 0
        try:
            with SessionLocal() as session:
                last_date_row = session.execute(
                    text("SELECT MAX(date) FROM shfe_copper_stock")
                ).scalar()
                last_date_str = (
                    last_date_row.strftime("%Y-%m-%d") if last_date_row else "1900-01-01"
                )

                new_records = [
                    (d, v) for d, v in records if d > last_date_str
                ]

                if not new_records:
                    logger.info(
                        f"[ShfeCopperStock] Scraped {len(records)} records, "
                        f"no new data after {last_date_str}"
                    )
                    return 0

                for date_str, stock in new_records:
                    session.execute(
                        text("""
                        INSERT INTO shfe_copper_stock (date, stock_tonnes, source)
                        VALUES (:date, :stock, :source)
                        ON CONFLICT (date) DO UPDATE SET
                            stock_tonnes = EXCLUDED.stock_tonnes,
                            updated_at = NOW()
                    """),
                        {"date": date_str, "stock": stock, "source": source_name},
                    )
                    upserted += 1

                session.commit()
        except Exception as e:
            logger.error(f"[ShfeCopperStock] DB upsert error: {e}")
            return 0

        logger.info(
            f"[ShfeCopperStock] Fetched {len(records)} records from "
            f"{source_name} ({records[0][0]} ~ {records[-1][0]}), "
            f"upserted {upserted} new rows"
        )
        return upserted

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """最新データ取得→DB UPSERT→DB全件読取"""
        from core.database import SessionLocal
        from sqlalchemy import text

        logger.info("[ShfeCopperStock] Building data...")

        # 0. commoditieschart.netから最新データをスクレイピングしDBに反映
        try:
            self._scrape_latest()
        except Exception as e:
            logger.warning(
                f"[ShfeCopperStock] Scrape failed (non-fatal): {e}"
            )

        # 1. DBから全データ取得
        try:
            with SessionLocal() as session:
                rows = session.execute(text("""
                    SELECT date, stock_tonnes
                    FROM shfe_copper_stock
                    ORDER BY date ASC
                """)).fetchall()
        except Exception as e:
            logger.error(f"[ShfeCopperStock] DB error: {e}")
            return None

        if not rows:
            logger.error("[ShfeCopperStock] No data in DB")
            return None

        # 2. データ構築
        result_data: List[Dict[str, Any]] = []
        for row in rows:
            date_str = row[0].strftime("%Y-%m-%d")
            stock = round(float(row[1]), 3) if row[1] is not None else None

            result_data.append({
                "date": date_str,
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
            f"[ShfeCopperStock] Built {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest stock={latest.get('stock_tonnes'):,.0f} tonnes"
        )

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "SHFE (Eastmoney)",
                "indicator": "SHFE Copper Warehouse Stock",
                "unit": "tonnes",
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
            logger.error(f"[ShfeCopperStock] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[ShfeCopperStock] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(DATA_CACHE_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[ShfeCopperStock] Redis load error: {e}")
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
            logger.error(f"[ShfeCopperStock] File load error: {e}")
        return None


# シングルトン
shfe_copper_stock_service = ShfeCopperStockService()
