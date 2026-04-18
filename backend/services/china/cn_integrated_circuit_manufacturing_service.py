"""
中国 集積回路生産（Integrated Circuit Manufacturing）サービス

3系列:
- raw_value: 当期生産量（億個）
- yoy: 前年比成長率(%)
- mom: 前月比(%)（rawから自動計算）

データソース:
- DB蓄積: nbs_monthly_data テーブル（CSVインポート + プレスリリース Excel 蓄積）
  indicator: cn_ic_raw        → 当期生産量（億個）
  indicator: cn_ic_yoy        → 前年比成長率(%)
- 最新値: www.stats.gov.cn/sj/zxfb/ のプレスリリース添付 Excel から取得 → DB UPSERT
  「规模以上工业增加值」記事の Excel 内「集成电路」行
- FMPマッピングなし

DB蓄積で永続化。CSVは初期インポート済み。
※ 1-2月は合算発表のため、1月・2月にデータがない月がある
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
_FILE_CACHE_DIR = _BASE_DIR / "data" / "cache" / "china" / "economy"
FILE_CACHE_PATH = str(_FILE_CACHE_DIR / "cn_integrated_circuit_manufacturing_cache.json")

REDIS_KEY = "china:cn_integrated_circuit_manufacturing:data"
REDIS_TTL = 86400  # 24h

# DB指標ID
DB_INDICATOR_RAW = "cn_ic_raw"
DB_INDICATOR_YOY = "cn_ic_yoy"


def _extract_ic_from_excel(excel_data: bytes, period) -> Dict[str, Dict[str, float]]:
    """工業生産プレスリリース Excel から集積回路データを抽出

    Excel 構造（「规模以上工业增加值」記事添付）:
      R61: 集成电路（亿块） | 当期絶対量 | 当期YoY% | 累計絶対量 | 累計YoY%
    """
    from services.china.nbs_press_release_utils import parse_excel, _safe_float

    rows = parse_excel(excel_data)

    raw_data = {}
    yoy_data = {}

    for row in rows:
        # col0は空、col1がラベル、col2=当期絶対量、col3=当期YoY%
        label = str(row[1]).strip() if len(row) > 1 and row[1] else ""
        if "集成电路" not in label:
            continue

        raw_val = _safe_float(row[2]) if len(row) > 2 else None
        yoy_val = _safe_float(row[3]) if len(row) > 3 else None

        if period and raw_val is not None:
            year, month = period
            date_str = f"{year}-{month:02d}-01"
            raw_data[date_str] = round(raw_val, 2)
            if yoy_val is not None:
                yoy_data[date_str] = round(yoy_val, 1)
            logger.info(f"[NBS-IC] Excel: {date_str} raw={raw_val}, yoy={yoy_val}")
        break

    return {
        DB_INDICATOR_RAW: raw_data,
        DB_INDICATOR_YOY: yoy_data,
    }


def _fetch_and_upsert_from_press_release() -> None:
    """NBS プレスリリース Excel から最新データを取得し、DB に UPSERT"""
    from services.china.nbs_press_release_utils import fetch_and_upsert_from_press_release

    results = fetch_and_upsert_from_press_release(
        category="industrial_production",
        extractor_fn=_extract_ic_from_excel,
    )
    if results:
        logger.info(f"[NBS-IC] Press release upsert: {results}")
    else:
        logger.warning("[NBS-IC] Press release: no data extracted")


def _build_data() -> List[Dict[str, Any]]:
    """DBからデータを読み込み + NBS APIで最新取得→DB蓄積"""
    from services.china.nbs_db_utils import load_nbs_multi

    # --- プレスリリース Excel → DB蓄積（ベストエフォート） ---
    try:
        _fetch_and_upsert_from_press_release()
    except Exception as e:
        logger.warning(f"[IC] Press release fetch/upsert failed: {e}")

    # --- DBから全データ読み込み ---
    all_data = load_nbs_multi([DB_INDICATOR_RAW, DB_INDICATOR_YOY])
    raw_data = all_data.get(DB_INDICATOR_RAW, {})
    yoy_data = all_data.get(DB_INDICATOR_YOY, {})

    logger.info(f"[IC] DB Raw: {len(raw_data)} records, YoY: {len(yoy_data)} records")

    # 全日付を統合
    all_dates = sorted(set(raw_data.keys()) | set(yoy_data.keys()))

    # MoM計算用に日付順のrawデータリストを作成
    sorted_raw_dates = sorted(raw_data.keys())

    result = []
    for date_str in all_dates:
        raw = raw_data.get(date_str)
        yoy = yoy_data.get(date_str)

        # MoM計算
        mom = None
        if raw is not None:
            idx = sorted_raw_dates.index(date_str) if date_str in sorted_raw_dates else -1
            if idx > 0:
                prev_date = sorted_raw_dates[idx - 1]
                prev_raw = raw_data.get(prev_date)
                if prev_raw and prev_raw > 0:
                    mom = round((raw - prev_raw) / prev_raw * 100, 1)

        result.append({
            "date": date_str,
            "raw_value": raw,
            "yoy": yoy,
            "mom": mom,
        })

    logger.info(f"[IC] Total: {len(result)} records")
    return result


class CnIntegratedCircuitManufacturingService:
    """中国集積回路生産サービス"""

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
            logger.warning(f"[IC] File cache write error: {e}")

    def _build_payload(self) -> Dict[str, Any]:
        data = _build_data()
        latest = data[-1] if data else None

        return {
            "data": data,
            "latest": latest,
            "metadata": {
                "indicator": "Integrated Circuit Manufacturing",
                "source": "National Bureau of Statistics (NBS)",
                "series": {
                    "raw_value": "集積回路生産量（億個）",
                    "yoy": "前年比 (%)",
                    "mom": "前月比 (%)",
                },
                "unit": "億個 (100 million units)",
                "total_records": len(data),
                "last_fetched": datetime.now(JST).isoformat(),
            },
            "next_release": None,
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
        return {"success": True, "message": "IC Manufacturing cache invalidated"}

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
cn_integrated_circuit_manufacturing_service = CnIntegratedCircuitManufacturingService()
