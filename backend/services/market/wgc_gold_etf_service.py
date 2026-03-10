"""
WGC (World Gold Council) 金ETFフロー/保有残高 サービス

データソース:
  - DB: wgc_gold_etf テーブル（月次、11カ国）
  - Excel初回インポート + scheduler週次API更新

更新: 6時間TTL (Redis + ファイル)
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

REDIS_KEY_PREFIX = "market:wgc_gold_etf"

VALID_DATA_TYPES = {"holdings_ton", "flows_usd"}
COUNTRIES = [
    "us", "uk", "germany", "switzerland", "japan",
    "china", "india", "australia", "canada",
    "south_africa", "hong_kong",
]


class WgcGoldEtfService:
    """WGC 金ETFフロー/保有残高サービス（国別）"""

    def _cache_key(self, data_type: str) -> str:
        return f"{REDIS_KEY_PREFIX}:{data_type}"

    def _cache_file(self, data_type: str) -> Path:
        return CACHE_DIR / f"wgc_gold_etf_{data_type}_cache.json"

    def _should_refresh(self, data_type: str) -> bool:
        try:
            cached = redis_client.get(self._cache_key(data_type))
            if not cached:
                return True
            last_updated_str = cached.get("last_updated")
            if not last_updated_str:
                return True
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)
            return (now - last_updated).total_seconds() >= 6 * 3600
        except Exception:
            return True

    def get_data(
        self, data_type: str = "holdings_ton", force_refresh: bool = False
    ) -> Dict[str, Any]:
        if data_type not in VALID_DATA_TYPES:
            data_type = "holdings_ton"

        if not force_refresh and not self._should_refresh(data_type):
            cached = self._load_from_redis(data_type)
            if cached and cached.get("data"):
                return cached

        try:
            data = self._build_data(data_type)
            if data and data.get("data"):
                self._save_to_cache(data_type, data)
                return data
        except Exception as e:
            logger.error(f"[WgcGoldEtf] Build error ({data_type}): {e}")
            import traceback
            traceback.print_exc()

        cached = self._load_from_redis(data_type)
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file(data_type)
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "data_type": data_type,
            "latest": None,
            "metadata": {"source": "World Gold Council"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _build_data(self, data_type: str) -> Optional[Dict[str, Any]]:
        """DBから月次+最新週次データを取得しフロントエンド用に整形。

        月次確定データの末尾に、まだ月次が出ていない期間の最新週次データを
        暫定値として付加する。月次が発表されれば週次は不要になる。
        """
        from core.database import SessionLocal
        from sqlalchemy import text

        value_column = data_type  # holdings_ton or flows_usd

        logger.info(f"[WgcGoldEtf] Building data ({data_type})...")

        try:
            with SessionLocal() as session:
                # 月次データ
                monthly_rows = session.execute(
                    text(f"""
                        SELECT date, country, {value_column}, gold_price_usd
                        FROM wgc_gold_etf
                        WHERE frequency = 'monthly'
                        ORDER BY date ASC, country ASC
                    """)
                ).fetchall()

                # 最新の月次日付を取得
                max_monthly = session.execute(
                    text("SELECT MAX(date) FROM wgc_gold_etf WHERE frequency = 'monthly'")
                ).fetchone()
                max_monthly_date = max_monthly[0] if max_monthly and max_monthly[0] else None

                # 月次より新しい週次データ（全週分取得）
                weekly_rows = []
                if max_monthly_date:
                    weekly_rows = session.execute(
                        text(f"""
                            SELECT date, country, {value_column}, gold_price_usd
                            FROM wgc_gold_etf
                            WHERE frequency = 'weekly'
                              AND date > :max_monthly
                            ORDER BY date ASC, country ASC
                        """),
                        {"max_monthly": max_monthly_date},
                    ).fetchall()

        except Exception as e:
            logger.error(f"[WgcGoldEtf] DB error: {e}")
            return None

        if not monthly_rows:
            logger.error("[WgcGoldEtf] No data in DB")
            return None

        # 日付ごとに11カ国のデータを1行にまとめる
        def _rows_to_date_map(rows) -> Dict[str, Dict[str, Any]]:
            date_map: Dict[str, Dict[str, Any]] = {}
            for row in rows:
                date_str = row[0].strftime("%Y-%m-%d")
                country = row[1]
                raw_val = float(row[2]) if row[2] is not None else None
                value = round(raw_val, 2) if raw_val is not None else None
                gold_price = round(float(row[3]), 2) if row[3] is not None else None

                if date_str not in date_map:
                    entry: Dict[str, Any] = {"date": date_str, "gold_price_usd": gold_price}
                    for c in COUNTRIES:
                        entry[c] = None
                    entry["total"] = None
                    date_map[date_str] = entry

                if country in COUNTRIES:
                    date_map[date_str][country] = value
                    if gold_price is not None:
                        date_map[date_str]["gold_price_usd"] = gold_price
            return date_map

        monthly_map = _rows_to_date_map(monthly_rows)
        weekly_map = _rows_to_date_map(weekly_rows)

        # totalを計算して結果リストを作成
        def _calc_total(date_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
            result: List[Dict[str, Any]] = []
            for date_str in sorted(date_map.keys()):
                item = date_map[date_str]
                vals = [item.get(c) for c in COUNTRIES if item.get(c) is not None]
                item["total"] = round(sum(vals), 2) if vals else None
                result.append(item)
            return result

        result_data = _calc_total(monthly_map)

        # 週次データを個別ポイントとして末尾に付加（合算しない）
        # 3/6, 3/13, 3/20... がそれぞれ独立した点としてチャートに表示される
        weekly_data = _calc_total(weekly_map)
        if weekly_data:
            result_data.extend(weekly_data)
            dates = [w["date"] for w in weekly_data]
            logger.info(
                f"[WgcGoldEtf] Appended {len(weekly_data)} weekly point(s): "
                f"{', '.join(dates)}"
            )

        if not result_data:
            return None

        latest = result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[WgcGoldEtf] Built {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest total={latest.get('total')}"
        )

        return {
            "data": result_data,
            "data_type": data_type,
            "latest": latest,
            "metadata": {
                "source": "World Gold Council",
                "countries": COUNTRIES,
                "frequency": "monthly",
                "data_count": len(result_data),
                "start_date": result_data[0]["date"],
                "end_date": result_data[-1]["date"],
            },
            "cached": False,
            "source": "model",
            "last_updated": now_str,
        }

    def _save_to_cache(self, data_type: str, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(self._cache_key(data_type), data, expire=86400)
        except Exception as e:
            logger.error(f"[WgcGoldEtf] Redis save error: {e}")
        try:
            with open(self._cache_file(data_type), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[WgcGoldEtf] File save error: {e}")

    def _load_from_redis(self, data_type: str) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(self._cache_key(data_type))
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[WgcGoldEtf] Redis load error: {e}")
        return None

    def _load_from_file(self, data_type: str) -> Optional[Dict[str, Any]]:
        try:
            cache_file = self._cache_file(data_type)
            if cache_file.exists():
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["cached"] = True
                data["source"] = "file"
                return data
        except Exception as e:
            logger.error(f"[WgcGoldEtf] File load error: {e}")
        return None


# シングルトン
wgc_gold_etf_service = WgcGoldEtfService()
