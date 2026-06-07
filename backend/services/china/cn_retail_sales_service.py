"""
中国 小売売上高（Retail Sales）サービス

1系列:
- YoY%: 社会消费品零售总额 同比増長 (%)

データソース:
- DB蓄積: nbs_monthly_data テーブル（CSVインポート + プレスリリース Excel 蓄積）
  indicator: cn_retail_sales_yoy
- 最新値: www.stats.gov.cn/sj/zxfb/ プレスリリース添付 Excel → DB UPSERT
  「社会消费品零售」記事の Excel R5 行（当期YoY%）
- FMP: 次回発表日の取得のみ

DB蓄積で永続化。CSVは初期インポート済み。
"""
import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# パス定義
_BASE_DIR = Path(__file__).parent.parent.parent
_FILE_CACHE_DIR = _BASE_DIR / "data" / "cache" / "china" / "consumer"
FILE_CACHE_PATH = str(_FILE_CACHE_DIR / "cn_retail_sales_cache.json")

REDIS_KEY = "china:cn_retail_sales:data"
REDIS_TTL = 86400  # 24h

ECONALPHA_ID = "cn_retail_sales"

# DB指標ID
DB_INDICATOR = "cn_retail_sales_yoy"


def _extract_retail_from_excel(excel_data: bytes, period) -> Dict[str, Dict[str, float]]:
    """小売売上プレスリリース Excel から YoY を抽出

    Excel「表」シート構造:
    - R2-R4: ヘッダー（指標/当期/累計の区分）
    - R5: 社会消费品零售总额 | 絶対量(億元) | 当期YoY% | 累計絶対量 | 累計YoY%
    """
    from services.china.nbs_press_release_utils import parse_excel, _safe_float

    rows = parse_excel(excel_data)
    result = {}

    for row in rows:
        label = str(row[0]).strip() if row[0] else ""
        if "社会消费品零售总额" not in label:
            continue
        # タイトル行を除外
        if "主要数据" in label or "月份" in label:
            continue
        # サブ行を除外（"其中" を含む行など）
        if "其中" in label:
            continue

        # col2 = 当期YoY%
        yoy_val = _safe_float(row[2]) if len(row) > 2 else None
        if period and yoy_val is not None:
            year, month = period
            date_str = f"{year}-{month:02d}-01"
            result[date_str] = round(yoy_val, 1)
            logger.info(f"[NBS-RetailSales] Excel: {date_str} yoy={yoy_val}")
            break

    return {DB_INDICATOR: result}


def _fetch_and_upsert_from_press_release() -> None:
    """NBS プレスリリース Excel から最新データを取得し、DB に UPSERT"""
    from services.china.nbs_press_release_utils import fetch_and_upsert_from_press_release

    results = fetch_and_upsert_from_press_release(
        category="retail",
        extractor_fn=_extract_retail_from_excel,
        primary_indicator=DB_INDICATOR,
    )
    if results:
        logger.info(f"[NBS-RetailSales] Press release upsert: {results}")


def _build_data() -> List[Dict[str, Any]]:
    """DBからデータを読み込み + プレスリリース Excel で最新取得→DB蓄積"""
    from services.china.nbs_db_utils import load_nbs_data

    # --- プレスリリース Excel → DB蓄積 ---
    try:
        _fetch_and_upsert_from_press_release()
    except Exception as e:
        logger.warning(f"[RetailSales] Press release fetch/upsert failed: {e}")

    # --- DBから全データ読み込み ---
    yoy_data = load_nbs_data(DB_INDICATOR)

    logger.info(f"[RetailSales] DB YoY: {len(yoy_data)} records")

    result = []
    for date_str in sorted(yoy_data.keys()):
        yoy = yoy_data[date_str]
        result.append({
            "date": date_str,
            "yoy": yoy,
        })

    logger.info(f"[RetailSales] Total: {len(result)} records")
    return result


def _get_next_release() -> Optional[Dict[str, Any]]:
    """FMPから次回発表日を取得"""
    try:
        from services.usa.fmp_next_release_utils import get_next_release_from_fmp
        return get_next_release_from_fmp(ECONALPHA_ID, country="CN")
    except Exception as e:
        logger.warning(f"[RetailSales] Failed to get next release: {e}")
        return None


class CnRetailSalesService:
    """中国小売売上高サービス"""

    def __init__(self):
        self._redis = None

    def _get_redis(self):
        if self._redis is None:
            try:
                import redis
                self._redis = redis.Redis(host="localhost", port=6379, db=0, socket_timeout=2)
                self._redis.ping()
            except Exception:
                self._redis = None
        return self._redis

    def _from_redis(self) -> Optional[Dict[str, Any]]:
        r = self._get_redis()
        if not r:
            return None
        try:
            raw = r.get(REDIS_KEY)
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return None

    def _to_redis(self, payload: Dict[str, Any]) -> None:
        r = self._get_redis()
        if not r:
            return
        try:
            r.setex(REDIS_KEY, REDIS_TTL, json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass

    def _from_file(self) -> Optional[Dict[str, Any]]:
        if not os.path.exists(FILE_CACHE_PATH):
            return None
        try:
            with open(FILE_CACHE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _to_file(self, payload: Dict[str, Any]) -> None:
        os.makedirs(_FILE_CACHE_DIR, exist_ok=True)
        try:
            with open(FILE_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[RetailSales] File cache write error: {e}")

    def _build_payload(self) -> Dict[str, Any]:
        data = _build_data()
        latest = data[-1] if data else None
        next_release = _get_next_release()

        return {
            "data": data,
            "latest": latest,
            "metadata": {
                "indicator": "Total Retail Sales of Consumer Goods",
                "source": "National Bureau of Statistics (NBS)",
                "series": {
                    "yoy": "小売売上高 前年比 (%)",
                },
                "total_records": len(data),
                "last_fetched": datetime.now(JST).isoformat(),
            },
            "next_release": next_release,
        }

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """データ取得（キャッシュ優先）"""
        if not force_refresh:
            cached = self._from_redis()
            if cached:
                return cached
            cached = self._from_file()
            if cached:
                self._to_redis(cached)
                return cached

        payload = self._build_payload()
        self._to_redis(payload)
        self._to_file(payload)
        return payload

    def invalidate_cache(self) -> Dict[str, Any]:
        r = self._get_redis()
        if r:
            try:
                r.delete(REDIS_KEY)
            except Exception:
                pass
        if os.path.exists(FILE_CACHE_PATH):
            os.remove(FILE_CACHE_PATH)
        return {"success": True, "message": "Retail Sales cache invalidated"}

    def get_cache_status(self) -> Dict[str, Any]:
        r = self._get_redis()
        redis_exists = False
        redis_ttl = None
        if r:
            try:
                redis_exists = bool(r.exists(REDIS_KEY))
                redis_ttl = r.ttl(REDIS_KEY)
            except Exception:
                pass
        file_exists = os.path.exists(FILE_CACHE_PATH)
        file_mtime = None
        if file_exists:
            file_mtime = datetime.fromtimestamp(
                os.path.getmtime(FILE_CACHE_PATH), tz=JST
            ).isoformat()
        return {
            "redis": {"exists": redis_exists, "ttl_seconds": redis_ttl},
            "file": {"exists": file_exists, "last_modified": file_mtime},
        }


# シングルトン
cn_retail_sales_service = CnRetailSalesService()
