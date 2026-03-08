"""
中国 商業住宅販売（Commercial Residential Sales）サービス

3系列の前年比累積値を表示:
- 新規着工床面積 (Floor space of buildings newly started) YoY%
- 新築商業ビル販売額 (Sales of newly built commercial buildings) YoY%
- 新築商業用ビル売却床面積 (Floor space of newly built commercial buildings sold) YoY%

データソース:
- DB蓄積: nbs_monthly_data テーブル（CSVインポート + NBS API蓄積）
  indicator: cn_re_floor_started_yoy, cn_re_sales_yoy, cn_re_floor_sold_yoy
- 最新値: NBS統計データAPIから取得 → DB UPSERT
  https://data.stats.gov.cn/easyquery.htm
  A060504: 住宅房屋新开工面积_累计增长(%) — 新規着工床面積（住宅）累積YoY
  A060902: 商品房销售额_累计增长(%) — 商業ビル販売額 累積YoY
  A060802: 商品房销售面积_累计增长(%) — 商業ビル売却床面積 累積YoY
- 発表スケジュール: FMPベース（cn_commercial_residential_sales）

NBS APIは直近24ヶ月のみ返すため、DB蓄積で永続化する。
CSVは初期インポート済み（csv_import → nbs_monthly_data テーブル）。
"""
import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from zoneinfo import ZoneInfo

import requests
from services.usa.fmp_next_release_utils import get_next_release_from_fmp

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
CST = ZoneInfo("Asia/Shanghai")

# パス定義
_BASE_DIR = Path(__file__).parent.parent.parent
_FILE_CACHE_DIR = _BASE_DIR / "data" / "cache" / "china" / "housing"
FILE_CACHE_PATH = str(_FILE_CACHE_DIR / "cn_commercial_residential_sales_cache.json")

REDIS_KEY = "china:cn_commercial_residential_sales:data"
REDIS_TTL = 86400  # 24h

# FMP指標ID
ECONALPHA_ID = "cn_commercial_residential_sales"

# DB指標ID
DB_INDICATORS = {
    "floor_started_yoy": "cn_re_floor_started_yoy",
    "sales_yoy": "cn_re_sales_yoy",
    "floor_sold_yoy": "cn_re_floor_sold_yoy",
}

# ---------------------------------------------------------------------------
# NBS 統計データ API 設定
# ---------------------------------------------------------------------------
NBS_API_URL = "https://data.stats.gov.cn/easyquery.htm"
NBS_INDICATORS = {
    "floor_started_yoy": "A060504",  # 住宅房屋新开工面积_累计增长(%)
    "sales_yoy": "A060902",          # 商品房销售额_累计增长(%)
    "floor_sold_yoy": "A060802",     # 商品房销售面积_累计增长(%)
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

    Args:
        indicator_code: A060504 等の指標コード
        periods: 取得期間数（月数）

    Returns:
        {date_str: value, ...} e.g. {"2026-01-01": -12.6, ...}
        値はそのまま%（累積前年比）
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
            logger.warning(f"[NBS-RealEstate] API HTTP {resp.status_code}")
            return {}

        data = resp.json()
        if data.get("returncode") != 200:
            logger.warning(f"[NBS-RealEstate] API returncode: {data.get('returncode')}")
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
            # 値はそのまま（累積前年比%）
            result[date_str] = round(value, 1)

        return result

    except Exception as e:
        logger.warning(f"[NBS-RealEstate] API fetch failed: {e}")
        return {}


def _fetch_and_upsert_nbs() -> Dict[str, Dict[str, float]]:
    """NBS APIから全指標の最新データを取得し、DBにUPSERT

    Returns:
        {"floor_started_yoy": {date_str: value}, "sales_yoy": {...}, "floor_sold_yoy": {...}}
    """
    from services.china.nbs_db_utils import upsert_nbs_data

    result = {}
    for key, code in NBS_INDICATORS.items():
        data = _fetch_nbs_api(code, periods=24)
        if data:
            result[key] = data
            count = upsert_nbs_data(DB_INDICATORS[key], data, source="api")
            logger.info(f"[NBS-RealEstate] API {key}: {len(data)} records, DB upserted {count}")
        else:
            result[key] = {}
    return result


def _build_data() -> List[Dict[str, Any]]:
    """DBからデータを読み込み + NBS APIで最新取得→DB蓄積

    手順:
    1. NBS APIから最新データ取得 → DB UPSERT
    2. DBから全データを読み込み
    3. 日付をキーにマージして時系列構築
    """
    from services.china.nbs_db_utils import load_nbs_multi

    # --- NBS API → DB蓄積 ---
    try:
        _fetch_and_upsert_nbs()
    except Exception as e:
        logger.warning(f"[CommercialSales] NBS API fetch/upsert failed: {e}")

    # --- DBから全データ読み込み ---
    db_indicators = list(DB_INDICATORS.values())
    db_data = load_nbs_multi(db_indicators)

    floor_started = db_data.get(DB_INDICATORS["floor_started_yoy"], {})
    sales = db_data.get(DB_INDICATORS["sales_yoy"], {})
    floor_sold = db_data.get(DB_INDICATORS["floor_sold_yoy"], {})

    logger.info(
        f"[CommercialSales] DB floor_started: {len(floor_started)}, "
        f"sales: {len(sales)}, floor_sold: {len(floor_sold)} records"
    )

    # 日付 → {key_yoy: value} のマップを構築
    all_dates = set(floor_started.keys()) | set(sales.keys()) | set(floor_sold.keys())

    result = []
    for date_str in sorted(all_dates):
        item: Dict[str, Any] = {"date": date_str}
        has_data = False
        fs = floor_started.get(date_str)
        if fs is not None:
            item["floor_started_yoy"] = fs
            has_data = True
        sl = sales.get(date_str)
        if sl is not None:
            item["sales_yoy"] = sl
            has_data = True
        fsd = floor_sold.get(date_str)
        if fsd is not None:
            item["floor_sold_yoy"] = fsd
            has_data = True
        if has_data:
            result.append(item)

    logger.info(f"[CommercialSales] Total: {len(result)} records")
    return result


def _get_next_release() -> Optional[Dict[str, Any]]:
    """FMPから次回発表日を取得"""
    try:
        return get_next_release_from_fmp(ECONALPHA_ID, country="CN")
    except Exception as e:
        logger.warning(f"[CommercialSales] Failed to get next release from FMP: {e}")
        return None


class CnCommercialResidentialSalesService:
    """中国商業住宅販売サービス"""

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
            logger.warning(f"[CommercialSales] File cache write error: {e}")

    def _build_payload(self) -> Dict[str, Any]:
        data = _build_data()
        latest = data[-1] if data else None

        next_release = _get_next_release()

        return {
            "data": data,
            "latest": latest,
            "metadata": {
                "indicator": "Commercial Residential Sales",
                "source": "National Bureau of Statistics (NBS)",
                "unit_floor_started": "%（累積前年比）",
                "unit_sales": "%（累積前年比）",
                "unit_floor_sold": "%（累積前年比）",
                "series": {
                    "floor_started_yoy": "新規着工床面積（住宅）累積YoY",
                    "sales_yoy": "新築商業ビル販売額 累積YoY",
                    "floor_sold_yoy": "新築商業用ビル売却床面積 累積YoY",
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
        return {"success": True, "message": "Commercial Residential Sales cache invalidated"}

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
cn_commercial_residential_sales_service = CnCommercialResidentialSalesService()
