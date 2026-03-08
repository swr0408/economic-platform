"""
中国 集積回路生産（Integrated Circuit Manufacturing）サービス

3系列:
- raw_value: 当期生産量（億個）
- yoy: 前年比成長率(%)
- mom: 前月比(%)（rawから自動計算）

データソース:
- DB蓄積: nbs_monthly_data テーブル（CSVインポート + NBS API蓄積）
  indicator: cn_ic_raw        → 当期生産量（億個）
  indicator: cn_ic_yoy        → 前年比成長率(%)
- 最新値: NBS統計データAPIから取得 → DB UPSERT
  工业主要产品产量 → 集成电路
- FMPマッピングなし

NBS APIは直近24ヶ月のみ返すため、DB蓄積で永続化する。
CSVは初期インポート済み（csv_import → nbs_monthly_data テーブル）。
※ 1-2月は合算発表のため、1月・2月にデータがない月がある
※ NBS APIはアンチボット保護により接続不可の場合があるため、
   DB蓄積データを主データソースとし、APIは補助的に使用する。
   新しいデータはCSVを更新して再インポートするか、APIが利用可能な時に自動取得。
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
FILE_CACHE_PATH = str(_FILE_CACHE_DIR / "cn_integrated_circuit_manufacturing_cache.json")

REDIS_KEY = "china:cn_integrated_circuit_manufacturing:data"
REDIS_TTL = 86400  # 24h

# DB指標ID
DB_INDICATOR_RAW = "cn_ic_raw"
DB_INDICATOR_YOY = "cn_ic_yoy"

# ---------------------------------------------------------------------------
# NBS 統計データ API 設定
# ---------------------------------------------------------------------------
NBS_API_URL = "https://data.stats.gov.cn/easyquery.htm"

# NBS API指標コード (hgyd DB = 月次)
# 工业主要产品产量 → 集成电路
# NBS_INDICATOR_RAW_CODE: 集成电路 当期产量
# NBS_INDICATOR_YOY_CODE: 集成电路 前年同期比
# ※ コードはNBS英語サイトのCSVと照合して特定
# ※ NBS APIがアンチボット保護で応答しない場合はスキップ
NBS_INDICATOR_RAW_CODE = "A020M01"  # 集成电路 当期（推定コード）
NBS_INDICATOR_YOY_CODE = "A020M06"  # 集成电路 同比（推定コード）

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def _fetch_nbs_api(indicator_code: str, periods: int = 24) -> Dict[str, float]:
    """NBS統計データAPIからデータを取得

    ※ NBS APIはアンチボット保護によりサーバーから接続不可の場合がある。
       失敗時は空dictを返し、DB蓄積データにフォールバック。

    Returns:
        {date_str: value, ...}
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
            result[date_str] = round(value, 2)

        return result

    except Exception:
        # NBS APIが応答しない場合はサイレントにスキップ
        return {}


def _fetch_and_upsert_nbs() -> None:
    """NBS APIから最新データを取得し、DBにUPSERT"""
    from services.china.nbs_db_utils import upsert_nbs_data

    # 当期値
    raw_data = _fetch_nbs_api(NBS_INDICATOR_RAW_CODE, periods=24)
    if raw_data:
        count = upsert_nbs_data(DB_INDICATOR_RAW, raw_data, source="api")
        logger.info(f"[NBS-IC] Raw API: {len(raw_data)} records, DB upserted {count}")

    # YoY成長率
    yoy_data = _fetch_nbs_api(NBS_INDICATOR_YOY_CODE, periods=24)
    if yoy_data:
        # NBS YoY は base=100 形式の可能性: 112.9 → 12.9%
        converted = {}
        for date_str, val in yoy_data.items():
            if val > 50:  # base=100 形式の場合
                converted[date_str] = round(val - 100, 1)
            else:
                converted[date_str] = round(val, 1)
        count = upsert_nbs_data(DB_INDICATOR_YOY, converted, source="api")
        logger.info(f"[NBS-IC] YoY API: {len(converted)} records, DB upserted {count}")


def _build_data() -> List[Dict[str, Any]]:
    """DBからデータを読み込み + NBS APIで最新取得→DB蓄積"""
    from services.china.nbs_db_utils import load_nbs_multi

    # --- NBS API → DB蓄積（ベストエフォート） ---
    try:
        _fetch_and_upsert_nbs()
    except Exception as e:
        logger.warning(f"[IC] NBS API fetch/upsert failed: {e}")

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
