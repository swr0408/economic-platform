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
- DB蓄積: nbs_monthly_data テーブル（CSVインポート + NBS API蓄積）
- 最新値: NBS統計データAPIから取得 → DB UPSERT
  https://data.stats.gov.cn/easyquery.htm
  NBS APIは時代別にコードが分かれている（2016-2020, 2021-2025, 2026+）
  各時代の最新コードのみ24ヶ月分取得してDB蓄積
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

import requests

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

# ---------------------------------------------------------------------------
# NBS 統計データ API 設定
# NBS APIは時代別にコードが分かれている
# 各系列の「最新時代のコード」のみ使用（LAST24で十分）
# 過去データはCSV初期インポートでDB蓄積済み
# ---------------------------------------------------------------------------
NBS_API_URL = "https://data.stats.gov.cn/easyquery.htm"

# 各系列の時代別APIコード（値は指数 base=100）
# 最新の時代コードのみAPIで定期取得し、DB蓄積する
NBS_API_CODES: Dict[str, List[str]] = {
    # CPI Total YoY: 2016-2020 + 2021-2025 + 2026+
    "cpi_yoy": ["A01010101", "A01010G01", "A01010J01"],
    # CPI Total MoM: 2016-2020 + 2021-2025 + 2026+
    "cpi_mom": ["A01030101", "A01030G01", "A01030J01"],
    # Food CPI YoY: cross-period (single code covers all eras)
    "food_yoy": ["A01010301"],
    # Food CPI MoM: cross-period
    "food_mom": ["A01030301"],
    # Non-Food CPI YoY: 2016-2020 + 2021-2025 + 2026+
    "nonfood_yoy": ["A01010109", "A01010G0A", "A01010J0A"],
    # Non-Food CPI MoM: 2016-2020 + 2021-2025 + 2026+
    "nonfood_mom": ["A01030109", "A01030G0A", "A01030J0A"],
    # Core CPI (Excl Food & Energy) YoY: 2021-2025 + 2026+ (no 2016-2020 code)
    "core_yoy": ["A01010G0D", "A01010J0D"],
    # Core CPI (Excl Food & Energy) MoM: 2021-2025 + 2026+
    "core_mom": ["A01030G0D", "A01030J0D"],
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def _fetch_nbs_api(indicator_code: str, periods: int = 24) -> Dict[str, float]:
    """NBS統計データAPIから指標データを取得

    Returns:
        {date_str: percent_value, ...}
        指数(base=100)から%に変換済み
    """
    try:
        params = {
            "m": "QueryData",
            "dbcode": "hgyd",
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
            if not time_code or len(time_code) != 6:
                continue

            year = int(time_code[:4])
            month = int(time_code[4:6])
            date_str = f"{year}-{month:02d}-01"
            # 指数(base=100) → %変換
            result[date_str] = round(value - 100, 2)

        return result
    except Exception as e:
        logger.warning(f"[NBS-CPI] API fetch failed for {indicator_code}: {e}")
        return {}


def _fetch_and_upsert_nbs() -> None:
    """NBS APIから全6系列の最新データを取得し、DBにUPSERT

    各系列の全時代コードからデータを取得しマージする。
    同一日付は後のコード（より新しい時代）が優先。
    """
    from services.china.nbs_db_utils import upsert_nbs_data

    for series_key, api_codes in NBS_API_CODES.items():
        merged: Dict[str, float] = {}
        for code in api_codes:
            data = _fetch_nbs_api(code, periods=24)
            if data:
                merged.update(data)  # 後の時代コードが優先

        if merged:
            db_key = DB_INDICATORS[series_key]
            count = upsert_nbs_data(db_key, merged, source="api")
            logger.info(f"[NBS-CPI] {series_key}: {len(merged)} records from API, DB upserted {count}")


def _build_data() -> List[Dict[str, Any]]:
    """DBから全データを読み込み、時系列データを構築

    手順:
    1. NBS APIから最新データ取得 → DB UPSERT
    2. DBから全6系列を読み込み
    3. 日付をキーにマージして出力
    """
    from services.china.nbs_db_utils import load_nbs_multi

    # --- NBS API → DB蓄積 ---
    try:
        _fetch_and_upsert_nbs()
    except Exception as e:
        logger.warning(f"[CPI] NBS API fetch/upsert failed: {e}")

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
