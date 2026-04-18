"""
中国 CPI（Consumer Price Index）サービス

4系列 × 2ビュー = 8指標:
- CPI YoY%: 消費者物価指数（前年比）
- CPI MoM%: 消費者物価指数（前月比）
- Non-Food CPI YoY%: 非食品CPI（前年比）
- Non-Food CPI MoM%: 非食品CPI（前月比）
- Food CPI YoY%: 食品CPI（前年比）
- Food CPI MoM%: 食品CPI（前月比）
- Core CPI YoY%: コアCPI（食品・エネルギー除く、前年比）
- Core CPI MoM%: コアCPI（食品・エネルギー除く、前月比）

データソース:
- DB蓄積: nbs_monthly_data テーブル（CSVインポート + プレスリリース蓄積）
- 最新値: www.stats.gov.cn/sj/zxfb/ プレスリリース添付 Excel → DB UPSERT
  Excel「CPI」シート: R4=CPI総合, R7=食品, R8=非食品, R11=コア
- FMP: 次回発表日の取得のみ

DB指標ID:
  cn_cpi_yoy, cn_cpi_mom,
  cn_cpi_food_yoy, cn_cpi_food_mom,
  cn_cpi_nonfood_yoy, cn_cpi_nonfood_mom,
  cn_cpi_core_yoy, cn_cpi_core_mom
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
FILE_CACHE_PATH = str(_FILE_CACHE_DIR / "cn_cpi_cache.json")

REDIS_KEY = "china:cn_cpi:data"
REDIS_TTL = 86400  # 24h

ECONALPHA_ID = "cn_cpi"

# DB指標ID
DB_INDICATORS = {
    "cpi_yoy": "cn_cpi_yoy",
    "cpi_mom": "cn_cpi_mom",
    "food_yoy": "cn_cpi_food_yoy",
    "food_mom": "cn_cpi_food_mom",
    "nonfood_yoy": "cn_cpi_nonfood_yoy",
    "nonfood_mom": "cn_cpi_nonfood_mom",
    "core_yoy": "cn_cpi_core_yoy",
    "core_mom": "cn_cpi_core_mom",
}

def _extract_cpi_from_excel(
    excel_data: bytes, period: Optional[tuple],
) -> Dict[str, Dict[str, float]]:
    """CPI プレスリリース添付 Excel からデータを抽出

    Excel「CPI」シート構造:
      R4: 居民消费价格 | MoM% | YoY% | 累計YoY%
      R7: 食品           | MoM  | YoY  | 累計YoY
      R8: 非食品         | MoM  | YoY  | 累計YoY
      R11: 不包括食品和能源 (Core) | MoM | YoY | 累計YoY

    Returns:
        {db_indicator: {date_str: value}, ...}
    """
    from services.china.nbs_press_release_utils import parse_excel, _safe_float

    if not period:
        logger.warning("[CPI] No period info from release title")
        return {}

    year, month = period
    date_str = f"{year}-{month:02d}-01"

    rows = parse_excel(excel_data, sheet_name="CPI")

    # 行インデックス (0-based): R4→idx3, R7→idx6, R8→idx7, R11→idx10
    # 列: col1=MoM%, col2=YoY%, col3=累計YoY%
    result: Dict[str, Dict[str, float]] = {}

    def _set(db_key: str, row_idx: int, col_idx: int):
        if row_idx < len(rows) and col_idx < len(rows[row_idx]):
            v = _safe_float(rows[row_idx][col_idx])
            if v is not None:
                result[db_key] = {date_str: v}

    # CPI総合: R4 (idx=3)
    _set(DB_INDICATORS["cpi_mom"], 3, 1)    # MoM
    _set(DB_INDICATORS["cpi_yoy"], 3, 2)    # YoY
    # 食品: R7 (idx=6)
    _set(DB_INDICATORS["food_mom"], 6, 1)
    _set(DB_INDICATORS["food_yoy"], 6, 2)
    # 非食品: R8 (idx=7)
    _set(DB_INDICATORS["nonfood_mom"], 7, 1)
    _set(DB_INDICATORS["nonfood_yoy"], 7, 2)
    # コア: R11 (idx=10)
    _set(DB_INDICATORS["core_mom"], 10, 1)
    _set(DB_INDICATORS["core_yoy"], 10, 2)

    logger.info(f"[CPI] Extracted {len(result)} indicators from Excel for {date_str}")
    return result


def _build_data() -> List[Dict[str, Any]]:
    """DBから全データを読み込み、時系列データを構築

    手順:
    1. プレスリリース Excel から最新データ取得 → DB UPSERT
    2. DBから全8系列を読み込み
    3. 日付をキーにマージして出力
    """
    from services.china.nbs_db_utils import load_nbs_multi

    # --- プレスリリース Excel → DB蓄積 ---
    try:
        from services.china.nbs_press_release_utils import fetch_and_upsert_from_press_release
        fetch_and_upsert_from_press_release("cpi", _extract_cpi_from_excel)
    except Exception as e:
        logger.warning(f"[CPI] Press release fetch/upsert failed: {e}")

    # --- DBから全データ読み込み ---
    db_keys = list(DB_INDICATORS.values())
    db_data = load_nbs_multi(db_keys)

    cpi_yoy = db_data.get(DB_INDICATORS["cpi_yoy"], {})
    cpi_mom = db_data.get(DB_INDICATORS["cpi_mom"], {})
    food_yoy = db_data.get(DB_INDICATORS["food_yoy"], {})
    food_mom = db_data.get(DB_INDICATORS["food_mom"], {})
    nonfood_yoy = db_data.get(DB_INDICATORS["nonfood_yoy"], {})
    nonfood_mom = db_data.get(DB_INDICATORS["nonfood_mom"], {})
    core_yoy = db_data.get(DB_INDICATORS["core_yoy"], {})
    core_mom = db_data.get(DB_INDICATORS["core_mom"], {})

    logger.info(
        f"[CPI] DB records - yoy:{len(cpi_yoy)}, mom:{len(cpi_mom)}, "
        f"food_yoy:{len(food_yoy)}, food_mom:{len(food_mom)}, "
        f"nonfood_yoy:{len(nonfood_yoy)}, nonfood_mom:{len(nonfood_mom)}, "
        f"core_yoy:{len(core_yoy)}, core_mom:{len(core_mom)}"
    )

    # 全日付を集約
    all_dates = set()
    for d in [cpi_yoy, cpi_mom, food_yoy, food_mom, nonfood_yoy, nonfood_mom, core_yoy, core_mom]:
        all_dates.update(d.keys())

    # ソートして構築（cpi_yoyがNoneのレコードは除外）
    result = []
    for date_str in sorted(all_dates):
        yoy = cpi_yoy.get(date_str)
        if yoy is None:
            continue
        result.append({
            "date": date_str,
            "yoy": yoy,
            "mom": cpi_mom.get(date_str),
            "food_yoy": food_yoy.get(date_str),
            "food_mom": food_mom.get(date_str),
            "nonfood_yoy": nonfood_yoy.get(date_str),
            "nonfood_mom": nonfood_mom.get(date_str),
            "core_yoy": core_yoy.get(date_str),
            "core_mom": core_mom.get(date_str),
        })

    logger.info(f"[CPI] Total: {len(result)} records")
    return result


def _get_next_release() -> Optional[Dict[str, Any]]:
    """FMPから次回発表日を取得"""
    try:
        from services.usa.fmp_next_release_utils import get_next_release_from_fmp
        return get_next_release_from_fmp(ECONALPHA_ID, country="CN")
    except Exception as e:
        logger.warning(f"[CPI] Failed to get next release: {e}")
        return None


class CnCpiService:
    """中国CPIサービス"""

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
            logger.warning(f"[CPI] File cache write error: {e}")

    def _build_payload(self) -> Dict[str, Any]:
        data = _build_data()
        latest = data[-1] if data else None
        next_release = _get_next_release()

        return {
            "data": data,
            "latest": latest,
            "metadata": {
                "indicator": "Consumer Price Index",
                "source": "National Bureau of Statistics (NBS)",
                "series": {
                    "yoy": "CPI 前年比 (%)",
                    "mom": "CPI 前月比 (%)",
                    "food_yoy": "食品CPI 前年比 (%)",
                    "food_mom": "食品CPI 前月比 (%)",
                    "nonfood_yoy": "非食品CPI 前年比 (%)",
                    "nonfood_mom": "非食品CPI 前月比 (%)",
                    "core_yoy": "コアCPI（食品・エネルギー除く）前年比 (%)",
                    "core_mom": "コアCPI（食品・エネルギー除く）前月比 (%)",
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
        return {"success": True, "message": "CPI cache invalidated"}

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
cn_cpi_service = CnCpiService()
