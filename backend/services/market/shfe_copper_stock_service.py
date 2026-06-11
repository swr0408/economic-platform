"""
SHFE Copper Stock サービス

データソース:
  - DB: shfe_copper_stock テーブル（日次、SHFE Warehouse）
  - 最新値自動更新: commoditieschart.net (HTMLに埋め込まれたJSON)
  - 手動更新: CSVインポート (scripts/import_shfe_copper_stock.py)

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
DATA_CACHE_FILE = CACHE_DIR / "shfe_copper_stock_cache.json"

DATA_CACHE_KEY = "market:shfe_copper_stock:data"

SCRAPE_URL = "https://commoditieschart.net/metals/copper/shfe-copper-stocks"


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
            "metadata": {"source": "SHFE (commoditieschart.net)"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _scrape_latest(self) -> int:
        """commoditieschart.net から最新データをスクレイピングしDBにUPSERT

        Returns:
            挿入/更新された行数
        """
        import requests
        from core.database import SessionLocal
        from sqlalchemy import text

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }

        try:
            resp = requests.get(SCRAPE_URL, headers=headers, timeout=30)
            if resp.status_code != 200:
                logger.warning(
                    f"[ShfeCopperStock] Scrape failed: HTTP {resp.status_code}"
                )
                return 0
        except Exception as e:
            logger.warning(f"[ShfeCopperStock] Scrape error: {e}")
            return 0

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
                        VALUES (:date, :stock, 'commoditieschart')
                        ON CONFLICT (date) DO UPDATE SET
                            stock_tonnes = EXCLUDED.stock_tonnes,
                            updated_at = NOW()
                    """),
                        {"date": date_str, "stock": stock},
                    )
                    upserted += 1

                session.commit()
        except Exception as e:
            logger.error(f"[ShfeCopperStock] DB upsert error: {e}")
            return 0

        logger.info(
            f"[ShfeCopperStock] Scraped {len(records)} records total, "
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
                "source": "SHFE (commoditieschart.net)",
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
