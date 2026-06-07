"""
中国 鉱工業生産（Industrial Production）サービス

1系列:
- YoY%: 规上工业增加值_同比增長(%) → 直接%値

データソース:
- DB蓄積: nbs_monthly_data テーブル（CSVインポート + プレスリリース Excel 蓄積）
  indicator: cn_industrial_production_yoy
- 最新値: www.stats.gov.cn/sj/zxfb/ プレスリリース添付 Excel → DB UPSERT
  「规模以上工业增加值」記事の Excel R4 行
- FMP: 次回発表日の取得のみ

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
FILE_CACHE_PATH = str(_FILE_CACHE_DIR / "cn_industrial_production_cache.json")

REDIS_KEY = "china:cn_industrial_production:data"
REDIS_TTL = 86400  # 24h

ECONALPHA_ID = "cn_industrial_production"

# DB指標ID
DB_INDICATOR = "cn_industrial_production_yoy"


def _extract_ip_from_excel(excel_data: bytes, period) -> Dict[str, Dict[str, float]]:
    """工業生産プレスリリース Excel から鉱工業生産 YoY を抽出

    Excel R4: 规模以上工业增加值 | … | 当期YoY% | … | 累計YoY%
    """
    from services.china.nbs_press_release_utils import parse_excel, _safe_float

    rows = parse_excel(excel_data)
    result = {}

    for row in rows:
        # col0は空、col1がラベル、col3=当期YoY%
        label = str(row[1]).strip() if len(row) > 1 and row[1] else ""
        if "规模以上工业增加值" not in label:
            continue
        # 分三大门类 等のサブ行を除外
        if "其中" in label or "采矿" in label or "制造" in label or "电力" in label:
            continue

        yoy_val = _safe_float(row[3]) if len(row) > 3 else None
        if period and yoy_val is not None:
            year, month = period
            date_str = f"{year}-{month:02d}-01"
            result[date_str] = round(yoy_val, 1)
            logger.info(f"[NBS-IP] Excel: {date_str} yoy={yoy_val}")
        break

    return {DB_INDICATOR: result}


def _fetch_and_upsert_from_press_release() -> None:
    """NBS プレスリリース Excel から最新データを取得し、DB に UPSERT"""
    from services.china.nbs_press_release_utils import fetch_and_upsert_from_press_release

    results = fetch_and_upsert_from_press_release(
        category="industrial_production",
        extractor_fn=_extract_ip_from_excel,
        primary_indicator=DB_INDICATOR,
    )
    if results:
        logger.info(f"[NBS-IP] Press release upsert: {results}")


def _build_data() -> List[Dict[str, Any]]:
    """DBからデータを読み込み + NBS APIで最新取得→DB蓄積"""
    from services.china.nbs_db_utils import load_nbs_data

    # --- プレスリリース Excel → DB蓄積 ---
    try:
        _fetch_and_upsert_from_press_release()
    except Exception as e:
        logger.warning(f"[IP] Press release fetch/upsert failed: {e}")

    # --- DBから全データ読み込み ---
    yoy_data = load_nbs_data(DB_INDICATOR)

    logger.info(f"[IP] DB YoY: {len(yoy_data)} records")

    result = []
    for date_str in sorted(yoy_data.keys()):
        result.append({
            "date": date_str,
            "yoy": yoy_data[date_str],
        })

    logger.info(f"[IP] Total: {len(result)} records")
    return result


def _get_next_release() -> Optional[Dict[str, Any]]:
    """FMPから次回発表日を取得"""
    try:
        from services.usa.fmp_next_release_utils import get_next_release_from_fmp
        return get_next_release_from_fmp(ECONALPHA_ID, country="CN")
    except Exception as e:
        logger.warning(f"[IP] Failed to get next release: {e}")
        return None


class CnIndustrialProductionService:
    """中国鉱工業生産サービス"""

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
            logger.warning(f"[IP] File cache write error: {e}")

    def _build_payload(self) -> Dict[str, Any]:
        data = _build_data()
        latest = data[-1] if data else None
        next_release = _get_next_release()

        return {
            "data": data,
            "latest": latest,
            "metadata": {
                "indicator": "Industrial Production",
                "source": "National Bureau of Statistics (NBS)",
                "series": {
                    "yoy": "鉱工業生産 前年比 (%)",
                },
                "total_records": len(data),
                "last_fetched": datetime.now(JST).isoformat(),
            },
            "next_release": next_release,
        }

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """データ取得（キャッシュ優先）

        空キャッシュ（data=[]）は外部API/DB取得失敗時に保存された破損キャッシュの
        可能性が高いため、採用せず再取得する。鉱工業生産は過去データが必ずDBにあるため。
        """
        if not force_refresh:
            cached = self._from_redis()
            if cached and cached.get("data"):
                return cached
            cached = self._from_file()
            if cached and cached.get("data"):
                self._to_redis(cached)
                return cached

        payload = self._build_payload()
        # 空ペイロードはキャッシュに保存しない（破損キャッシュ防止）
        if payload.get("data"):
            self._to_redis(payload)
            self._to_file(payload)
        else:
            logger.warning("[IP] Empty payload; skipping cache write to prevent stale empty cache")
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
        return {"success": True, "message": "Industrial Production cache invalidated"}

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
cn_industrial_production_service = CnIndustrialProductionService()
