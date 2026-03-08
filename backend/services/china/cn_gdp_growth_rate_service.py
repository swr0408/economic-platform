"""
中国 GDP成長率サービス

2系列:
- YoY%: 国内生产总值指数(上年同期=100) 当季値 → (value - 100) で%変換
- QoQ%: 国内生产总值环比增长速度(%) → 直接%値

データソース:
- DB蓄積: nbs_monthly_data テーブル（CSVインポート + NBS API蓄積）
  indicator: cn_gdp_yoy, cn_gdp_qoq
  ※ 四半期データだが nbs_monthly_data テーブルを共用（date は四半期末月の1日）
- 最新値: NBS統計データAPI（四半期DB: hgjd）から取得 → DB UPSERT
  A010301: 国内生产总值指数(上年同期=100)_当季値 → YoY
  A010401: 国内生产总值环比增长速度 → QoQ
- FMP: 次回発表日の取得のみ

四半期時間コード: 2025A=Q1, 2025B=Q2, 2025C=Q3, 2025D=Q4
DB日付: Q1→YYYY-03-01, Q2→YYYY-06-01, Q3→YYYY-09-01, Q4→YYYY-12-01
"""
import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from zoneinfo import ZoneInfo

import requests

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# パス定義
_BASE_DIR = Path(__file__).parent.parent.parent
_FILE_CACHE_DIR = _BASE_DIR / "data" / "cache" / "china" / "economy"
FILE_CACHE_PATH = str(_FILE_CACHE_DIR / "cn_gdp_growth_rate_cache.json")

REDIS_KEY = "china:cn_gdp_growth_rate:data"
REDIS_TTL = 86400  # 24h

ECONALPHA_ID = "cn_gdp_growth_rate"

# DB指標ID
DB_INDICATORS = {
    "yoy": "cn_gdp_yoy",
    "qoq": "cn_gdp_qoq",
}

# ---------------------------------------------------------------------------
# NBS 統計データ API 設定（四半期DB: hgjd）
# ---------------------------------------------------------------------------
NBS_API_URL = "https://data.stats.gov.cn/easyquery.htm"
NBS_INDICATORS = {
    "yoy": "A010301",  # 国内生产总值指数(上年同期=100)_当季値 (base=100)
    "qoq": "A010401",  # 国内生产总值环比增长速度 (%)
}

# 四半期コード → 日付変換
QUARTER_TO_MONTH = {"A": "03", "B": "06", "C": "09", "D": "12"}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def _fetch_nbs_quarterly(indicator_code: str, periods: int = 20, is_index: bool = False) -> Dict[str, float]:
    """NBS四半期DBからデータを取得

    Args:
        indicator_code: A010301 等
        periods: 取得四半期数
        is_index: True=指数(base=100)→%変換、False=直接%値

    Returns:
        {date_str: percent_value, ...}
    """
    try:
        params = {
            "m": "QueryData",
            "dbcode": "hgjd",
            "rowcode": "zb",
            "colcode": "sj",
            "wds": "[]",
            "dfwds": json.dumps([
                {"wdcode": "zb", "valuecode": indicator_code},
                {"wdcode": "sj", "valuecode": f"LAST{periods}"},
            ]),
            "k1": str(int(datetime.now().timestamp() * 1000)),
            "h": "1",
        }
        resp = requests.get(NBS_API_URL, params=params, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            return {}

        data = resp.json()
        if data.get("returncode") != 200:
            return {}

        result = {}
        for node in data.get("returndata", {}).get("datanodes", []):
            node_data = node.get("data", {})
            if not node_data.get("hasdata"):
                continue

            value = node_data.get("data")
            if value is None:
                continue

            wds = node.get("wds", [])
            time_code = None
            for wd in wds:
                if wd.get("wdcode") == "sj":
                    time_code = wd.get("valuecode")
                    break

            if not time_code or len(time_code) != 5:
                continue

            year = time_code[:4]
            quarter_letter = time_code[4]
            month = QUARTER_TO_MONTH.get(quarter_letter)
            if not month:
                continue

            date_str = f"{year}-{month}-01"

            if is_index:
                result[date_str] = round(value - 100, 1)
            else:
                result[date_str] = round(value, 1)

        return result

    except Exception as e:
        logger.warning(f"[NBS-GDP] API fetch failed for {indicator_code}: {e}")
        return {}


def _fetch_and_upsert_nbs() -> None:
    """NBS APIから最新データを取得し、DBにUPSERT"""
    from services.china.nbs_db_utils import upsert_nbs_data

    # YoY: 指数(base=100) → %変換
    yoy_data = _fetch_nbs_quarterly(NBS_INDICATORS["yoy"], periods=20, is_index=True)
    if yoy_data:
        count = upsert_nbs_data(DB_INDICATORS["yoy"], yoy_data, source="api")
        logger.info(f"[NBS-GDP] YoY: {len(yoy_data)} records, DB upserted {count}")

    # QoQ: 直接%値
    qoq_data = _fetch_nbs_quarterly(NBS_INDICATORS["qoq"], periods=20, is_index=False)
    if qoq_data:
        count = upsert_nbs_data(DB_INDICATORS["qoq"], qoq_data, source="api")
        logger.info(f"[NBS-GDP] QoQ: {len(qoq_data)} records, DB upserted {count}")


def _build_data() -> List[Dict[str, Any]]:
    """DBからデータを読み込み + NBS APIで最新取得→DB蓄積"""
    from services.china.nbs_db_utils import load_nbs_multi

    # --- NBS API → DB蓄積 ---
    try:
        _fetch_and_upsert_nbs()
    except Exception as e:
        logger.warning(f"[GDP] NBS API fetch/upsert failed: {e}")

    # --- DBから全データ読み込み ---
    db_data = load_nbs_multi([DB_INDICATORS["yoy"], DB_INDICATORS["qoq"]])
    yoy_data = db_data.get(DB_INDICATORS["yoy"], {})
    qoq_data = db_data.get(DB_INDICATORS["qoq"], {})

    logger.info(f"[GDP] DB YoY: {len(yoy_data)} records, QoQ: {len(qoq_data)} records")

    all_dates = set(yoy_data.keys()) | set(qoq_data.keys())

    result = []
    for date_str in sorted(all_dates):
        yoy = yoy_data.get(date_str)
        if yoy is None:
            continue
        result.append({
            "date": date_str,
            "yoy": yoy,
            "qoq": qoq_data.get(date_str),
        })

    logger.info(f"[GDP] Total: {len(result)} records")
    return result


def _get_next_release() -> Optional[Dict[str, Any]]:
    """FMPから次回発表日を取得"""
    try:
        from services.usa.fmp_next_release_utils import get_next_release_from_fmp
        return get_next_release_from_fmp(ECONALPHA_ID, country="CN")
    except Exception as e:
        logger.warning(f"[GDP] Failed to get next release: {e}")
        return None


class CnGdpGrowthRateService:
    """中国GDP成長率サービス"""

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
            logger.warning(f"[GDP] File cache write error: {e}")

    def _build_payload(self) -> Dict[str, Any]:
        data = _build_data()
        latest = data[-1] if data else None
        next_release = _get_next_release()

        return {
            "data": data,
            "latest": latest,
            "metadata": {
                "indicator": "Gross Domestic Product Growth Rate",
                "source": "National Bureau of Statistics (NBS)",
                "series": {
                    "yoy": "GDP 前年比 (%)",
                    "qoq": "GDP 前期比 (%)",
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
        return {"success": True, "message": "GDP Growth Rate cache invalidated"}

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
cn_gdp_growth_rate_service = CnGdpGrowthRateService()
