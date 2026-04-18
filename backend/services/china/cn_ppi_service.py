"""
中国 PPI（Producer Price Index）サービス

2系列を表示:
- PPI YoY%: 生産者物価指数（前年比）
- PPI MoM%: 生産者物価指数（前月比）

データソース:
- DB蓄積: nbs_monthly_data テーブル（CSVインポート + プレスリリース蓄積）
  indicator: cn_ppi_yoy, cn_ppi_mom
- 最新値: www.stats.gov.cn/sj/zxfb/ プレスリリース添付 Excel → DB UPSERT
  Excel「Sheet1」シート: R4=工业生产者出厂价格 MoM/YoY
- FMP: 次回発表日の取得のみ

CSVは初期インポート済み（csv_import → nbs_monthly_data テーブル）。
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
_FILE_CACHE_DIR = _BASE_DIR / "data" / "cache" / "china" / "inflation"
FILE_CACHE_PATH = str(_FILE_CACHE_DIR / "cn_ppi_cache.json")

REDIS_KEY = "china:cn_ppi:data"
REDIS_TTL = 86400  # 24h

ECONALPHA_ID = "cn_ppi"

# DB指標ID
DB_INDICATORS = {
    "yoy": "cn_ppi_yoy",
    "mom": "cn_ppi_mom",
}

def _extract_ppi_from_excel(
    excel_data: bytes, period: Optional[tuple],
) -> Dict[str, Dict[str, float]]:
    """PPI プレスリリース添付 Excel からデータを抽出

    Excel「Sheet1」シート構造:
      R4: 一、工业生产者出厂价格 | MoM% (col1) | YoY% (col2) | 累計YoY% (col3)

    Returns:
        {db_indicator: {date_str: value}, ...}
    """
    from services.china.nbs_press_release_utils import parse_excel, _safe_float

    if not period:
        logger.warning("[PPI] No period info from release title")
        return {}

    year, month = period
    date_str = f"{year}-{month:02d}-01"

    rows = parse_excel(excel_data, sheet_name="Sheet1")

    result: Dict[str, Dict[str, float]] = {}

    # R4 (idx=3): 工业生产者出厂价格
    if len(rows) > 3 and len(rows[3]) > 2:
        mom = _safe_float(rows[3][1])
        yoy = _safe_float(rows[3][2])
        if mom is not None:
            result[DB_INDICATORS["mom"]] = {date_str: mom}
        if yoy is not None:
            result[DB_INDICATORS["yoy"]] = {date_str: yoy}

    logger.info(f"[PPI] Extracted {len(result)} indicators from Excel for {date_str}")
    return result


def _build_data() -> List[Dict[str, Any]]:
    """DBからデータを読み込み + プレスリリース Excel で最新取得→DB蓄積

    手順:
    1. プレスリリース Excel から最新データ取得 → DB UPSERT
    2. DBから全データを読み込み
    3. 日付をキーにマージして時系列構築
    """
    from services.china.nbs_db_utils import load_nbs_multi

    # --- プレスリリース Excel → DB蓄積 ---
    try:
        from services.china.nbs_press_release_utils import fetch_and_upsert_from_press_release
        fetch_and_upsert_from_press_release("ppi", _extract_ppi_from_excel)
    except Exception as e:
        logger.warning(f"[PPI] Press release fetch/upsert failed: {e}")

    # --- DBから全データ読み込み ---
    db_data = load_nbs_multi([DB_INDICATORS["yoy"], DB_INDICATORS["mom"]])
    yoy_data = db_data.get(DB_INDICATORS["yoy"], {})
    mom_data = db_data.get(DB_INDICATORS["mom"], {})

    logger.info(f"[PPI] DB YoY: {len(yoy_data)} records, MoM: {len(mom_data)} records")

    # 日付 → {yoy, mom} のマップを構築
    all_dates = set(yoy_data.keys()) | set(mom_data.keys())

    # ソートして構築（yoyがNoneのレコードは除外）
    result = []
    for date_str in sorted(all_dates):
        yoy = yoy_data.get(date_str)
        if yoy is not None:
            result.append({
                "date": date_str,
                "yoy": yoy,
                "mom": mom_data.get(date_str),
            })

    logger.info(f"[PPI] Total: {len(result)} records")
    return result


def _get_next_release() -> Optional[Dict[str, Any]]:
    """FMPから次回発表日を取得"""
    try:
        from services.usa.fmp_next_release_utils import get_next_release_from_fmp
        return get_next_release_from_fmp(ECONALPHA_ID, country="CN")
    except Exception as e:
        logger.warning(f"[PPI] Failed to get next release: {e}")
        return None


class CnPpiService:
    """中国PPIサービス"""

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
            logger.warning(f"[PPI] File cache write error: {e}")

    def _build_payload(self) -> Dict[str, Any]:
        data = _build_data()
        latest = data[-1] if data else None
        next_release = _get_next_release()

        return {
            "data": data,
            "latest": latest,
            "metadata": {
                "indicator": "Producer Price Index",
                "source": "National Bureau of Statistics (NBS)",
                "series": {
                    "yoy": "PPI 前年比 (%)",
                    "mom": "PPI 前月比 (%)",
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
        return {"success": True, "message": "PPI cache invalidated"}

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
cn_ppi_service = CnPpiService()
