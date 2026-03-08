"""
中国 固定資産投資（Fixed Asset Investment）サービス

1系列:
- YTD累計増長率(%): 固定资产投资额_累計増長(%)

データソース:
- DB蓄積: nbs_monthly_data テーブル（CSVインポート + NBS API蓄積）
  indicator: cn_fixed_asset_investment_ytd
- 最新値: NBS統計データAPIから取得 → DB UPSERT
  A040102: 固定资产投资额_累計増長
- FMP: 次回発表日の取得のみ

NBS APIは直近24ヶ月のみ返すため、DB蓄積で永続化する。
CSVは初期インポート済み（csv_import → nbs_monthly_data テーブル）。
※ 1月は発表なし（1-2月合算発表）
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
FILE_CACHE_PATH = str(_FILE_CACHE_DIR / "cn_fixed_asset_investment_cache.json")

REDIS_KEY = "china:cn_fixed_asset_investment:data"
REDIS_TTL = 86400  # 24h

ECONALPHA_ID = "cn_fixed_asset_investment"

# DB指標ID
DB_INDICATOR = "cn_fixed_asset_investment_ytd"

# ---------------------------------------------------------------------------
# NBS 統計データ API 設定
# ---------------------------------------------------------------------------
NBS_API_URL = "https://data.stats.gov.cn/easyquery.htm"
NBS_INDICATOR_CODE = "A040102"  # 固定资产投资额_累計増長(%)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def _fetch_nbs_api(periods: int = 24) -> Dict[str, float]:
    """NBS統計データAPIから固定資産投資YTD累計増長率を取得

    Returns:
        {date_str: percent_value, ...} 直接%値
    """
    try:
        params = {
            "m": "QueryData",
            "dbcode": "hgyd",
            "rowcode": "zb",
            "colcode": "sj",
            "wds": "[]",
            "dfwds": json.dumps([
                {"wdcode": "zb", "valuecode": NBS_INDICATOR_CODE},
                {"wdcode": "sj", "valuecode": f"LAST{periods}"},
            ]),
            "k1": str(int(datetime.now().timestamp() * 1000)),
            "h": "1",
        }
        resp = requests.get(NBS_API_URL, params=params, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            logger.warning(f"[NBS-FAI] API HTTP {resp.status_code}")
            return {}

        data = resp.json()
        if data.get("returncode") != 200:
            logger.warning(f"[NBS-FAI] API returncode: {data.get('returncode')}")
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
            result[date_str] = round(value, 1)

        return result

    except Exception as e:
        logger.warning(f"[NBS-FAI] API fetch failed: {e}")
        return {}


def _fetch_and_upsert_nbs() -> None:
    """NBS APIから最新データを取得し、DBにUPSERT"""
    from services.china.nbs_db_utils import upsert_nbs_data

    data = _fetch_nbs_api(periods=24)
    if data:
        count = upsert_nbs_data(DB_INDICATOR, data, source="api")
        logger.info(f"[NBS-FAI] API: {len(data)} records, DB upserted {count}")


def _build_data() -> List[Dict[str, Any]]:
    """DBからデータを読み込み + NBS APIで最新取得→DB蓄積"""
    from services.china.nbs_db_utils import load_nbs_data

    # --- NBS API → DB蓄積 ---
    try:
        _fetch_and_upsert_nbs()
    except Exception as e:
        logger.warning(f"[FAI] NBS API fetch/upsert failed: {e}")

    # --- DBから全データ読み込み ---
    ytd_data = load_nbs_data(DB_INDICATOR)

    logger.info(f"[FAI] DB YTD: {len(ytd_data)} records")

    result = []
    for date_str in sorted(ytd_data.keys()):
        result.append({
            "date": date_str,
            "ytd": ytd_data[date_str],
        })

    logger.info(f"[FAI] Total: {len(result)} records")
    return result


def _get_next_release() -> Optional[Dict[str, Any]]:
    """FMPから次回発表日を取得"""
    try:
        from services.usa.fmp_next_release_utils import get_next_release_from_fmp
        return get_next_release_from_fmp(ECONALPHA_ID, country="CN")
    except Exception as e:
        logger.warning(f"[FAI] Failed to get next release: {e}")
        return None


class CnFixedAssetInvestmentService:
    """中国固定資産投資サービス"""

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
            logger.warning(f"[FAI] File cache write error: {e}")

    def _build_payload(self) -> Dict[str, Any]:
        data = _build_data()
        latest = data[-1] if data else None
        next_release = _get_next_release()

        return {
            "data": data,
            "latest": latest,
            "metadata": {
                "indicator": "Fixed Asset Investment",
                "source": "National Bureau of Statistics (NBS)",
                "series": {
                    "ytd": "固定資産投資 累計前年比 (%)",
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
        return {"success": True, "message": "Fixed Asset Investment cache invalidated"}

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
cn_fixed_asset_investment_service = CnFixedAssetInvestmentService()
