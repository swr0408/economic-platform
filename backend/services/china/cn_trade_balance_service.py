"""
中国 貿易収支（Trade Balance）サービス

5系列:
- 貿易収支: 億USD
- 輸出額: 億USD
- 輸入額: 億USD
- 輸出 前年比 (%)
- 輸入 前年比 (%)
+ 前月増減幅（貿易収支のlevelから計算）

データソース:
- DB蓄積: nbs_monthly_data テーブル（CSVインポート + NBS API蓄積）
  indicators: cn_trade_balance, cn_exports, cn_imports, cn_exports_yoy, cn_imports_yoy
- 最新値: NBS統計データAPIから取得 → DB UPSERT
- FMP: 次回発表日の取得のみ

NBS APIは直近24ヶ月のみ返すため、DB蓄積で永続化する。
CSVは初期インポート済み（csv_import → nbs_monthly_data テーブル）。
レベル指標は1000 USD → 億USDに変換済み（CSVインポート時）。
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
FILE_CACHE_PATH = str(_FILE_CACHE_DIR / "cn_trade_balance_cache.json")

REDIS_KEY = "china:cn_trade_balance:data"
REDIS_TTL = 86400  # 24h

ECONALPHA_ID = "cn_trade_balance"

# DB指標ID
DB_INDICATORS = {
    "balance": "cn_trade_balance",
    "exports": "cn_exports",
    "imports": "cn_imports",
    "exports_yoy": "cn_exports_yoy",
    "imports_yoy": "cn_imports_yoy",
}

# ---------------------------------------------------------------------------
# NBS 統計データ API 設定
# ---------------------------------------------------------------------------
NBS_API_URL = "https://data.stats.gov.cn/easyquery.htm"

# NBS APIコード
# A0801配下: 進出口関連指標（当月値・累計・YoY等）
#   A080101: 進出口総額(当月)    A080102: 進出口総額(当月YoY%)
#   A080103: 進出口総額(累計)    A080104: 進出口総額(累計YoY%)
#   A080105: 輸出(当月)          A080106: 輸出(当月YoY%)
#   A080107: 輸出(累計)          A080108: 輸出(累計YoY%)
#   A080109: 輸入(当月)          A08010A: 輸入(当月YoY%)
#   A08010B: 輸入(累計)          A08010C: 輸入(累計YoY%)
#   A08010D: 貿易収支(当月)      A08010E: 貿易収支(累計)
NBS_API_CODES = {
    # Level: 当月値 (1000 USD)
    "balance_level": ["A08010D"],    # 進出口差額（当月）
    "exports_level": ["A080105"],    # 輸出（当月）
    "imports_level": ["A080109"],    # 輸入（当月）
    # YoY: 前年同期比 (%)
    "exports_yoy": ["A080106"],      # 輸出 当月YoY%
    "imports_yoy": ["A08010A"],      # 輸入 当月YoY%
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def _fetch_nbs_single(indicator_code: str, periods: int = 24) -> Dict[str, float]:
    """NBS統計データAPIから単一指標データを取得"""
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
            result[date_str] = value

        return result

    except Exception as e:
        logger.warning(f"[NBS-Trade] API fetch failed for {indicator_code}: {e}")
        return {}


def _fetch_and_upsert_nbs() -> None:
    """NBS APIから最新データを取得し、DBにUPSERT"""
    from services.china.nbs_db_utils import upsert_nbs_data

    # レベル指標（1000 USD → 億USD変換が必要）
    for key in ["balance_level", "exports_level", "imports_level"]:
        db_key = key.replace("_level", "")
        db_indicator = DB_INDICATORS.get(db_key)
        if not db_indicator:
            continue

        for code in NBS_API_CODES.get(key, []):
            raw = _fetch_nbs_single(code, periods=24)
            if raw:
                # 1000 USD → 億USD
                converted = {k: round(v / 100_000, 2) for k, v in raw.items()}
                count = upsert_nbs_data(db_indicator, converted, source="api")
                logger.info(f"[NBS-Trade] {db_indicator} ({code}): {len(raw)} fetched, {count} upserted")

    # YoY指標（%値をそのまま使用）
    for key in ["exports_yoy", "imports_yoy"]:
        db_indicator = DB_INDICATORS.get(key)
        if not db_indicator:
            continue

        for code in NBS_API_CODES.get(key, []):
            raw = _fetch_nbs_single(code, periods=24)
            if raw:
                rounded = {k: round(v, 1) for k, v in raw.items()}
                count = upsert_nbs_data(db_indicator, rounded, source="api")
                logger.info(f"[NBS-Trade] {db_indicator} ({code}): {len(raw)} fetched, {count} upserted")


def _build_data() -> Dict[str, Any]:
    """DBからデータを読み込み + NBS APIで最新取得→DB蓄積"""
    from services.china.nbs_db_utils import load_nbs_multi

    # --- NBS API → DB蓄積 ---
    try:
        _fetch_and_upsert_nbs()
    except Exception as e:
        logger.warning(f"[Trade] NBS API fetch/upsert failed: {e}")

    # --- DBから全データ読み込み ---
    all_indicators = list(DB_INDICATORS.values())
    db_data = load_nbs_multi(all_indicators)

    balance_data = db_data.get(DB_INDICATORS["balance"], {})
    exports_data = db_data.get(DB_INDICATORS["exports"], {})
    imports_data = db_data.get(DB_INDICATORS["imports"], {})
    exports_yoy_data = db_data.get(DB_INDICATORS["exports_yoy"], {})
    imports_yoy_data = db_data.get(DB_INDICATORS["imports_yoy"], {})

    logger.info(
        f"[Trade] DB records: balance={len(balance_data)}, "
        f"exports={len(exports_data)}, imports={len(imports_data)}, "
        f"exports_yoy={len(exports_yoy_data)}, imports_yoy={len(imports_yoy_data)}"
    )

    # 貿易収支水準データ
    balance_list = [{"date": d, "value": round(v, 2)} for d, v in sorted(balance_data.items())]
    exports_list = [{"date": d, "value": round(v, 2)} for d, v in sorted(exports_data.items())]
    imports_list = [{"date": d, "value": round(v, 2)} for d, v in sorted(imports_data.items())]

    # 前年比
    exports_yoy_list = [{"date": d, "value": round(v, 1)} for d, v in sorted(exports_yoy_data.items())]
    imports_yoy_list = [{"date": d, "value": round(v, 1)} for d, v in sorted(imports_yoy_data.items())]

    # 貿易収支 前年比（レベルから計算）
    balance_yoy_list = _calc_yoy_from_level(balance_data)

    # 前月増減幅（貿易収支レベルから計算）
    balance_mom_diff = _calc_mom_diff(balance_data)
    exports_mom_diff = _calc_mom_diff(exports_data)
    imports_mom_diff = _calc_mom_diff(imports_data)

    return {
        "balance": balance_list,
        "exports": exports_list,
        "imports": imports_list,
        "balance_yoy": balance_yoy_list,
        "exports_yoy": exports_yoy_list,
        "imports_yoy": imports_yoy_list,
        "balance_mom_diff": balance_mom_diff,
        "exports_mom_diff": exports_mom_diff,
        "imports_mom_diff": imports_mom_diff,
        "latest_balance": balance_list[-1] if balance_list else None,
        "latest_exports": exports_list[-1] if exports_list else None,
        "latest_imports": imports_list[-1] if imports_list else None,
    }


def _calc_mom_diff(data: Dict[str, float]) -> List[Dict[str, Any]]:
    """前月増減幅を計算"""
    sorted_dates = sorted(data.keys())
    result = []
    for i in range(1, len(sorted_dates)):
        curr_date = sorted_dates[i]
        prev_date = sorted_dates[i - 1]
        diff = data[curr_date] - data[prev_date]
        result.append({"date": curr_date, "value": round(diff, 2)})
    return result


def _calc_yoy_from_level(data: Dict[str, float]) -> List[Dict[str, Any]]:
    """レベルデータから前年比(%)を計算"""
    from datetime import datetime as dt
    result = []
    for date_str, current_val in sorted(data.items()):
        d = dt.strptime(date_str, "%Y-%m-%d")
        prev_year_date = f"{d.year - 1}-{d.month:02d}-01"
        if prev_year_date in data:
            prev_val = data[prev_year_date]
            if prev_val != 0:
                yoy = ((current_val - prev_val) / abs(prev_val)) * 100
                result.append({"date": date_str, "value": round(yoy, 1)})
    return result


def _get_next_release() -> Optional[Dict[str, Any]]:
    """FMPから次回発表日を取得"""
    try:
        from services.usa.fmp_next_release_utils import get_next_release_from_fmp
        return get_next_release_from_fmp(ECONALPHA_ID, country="CN")
    except Exception as e:
        logger.warning(f"[Trade] Failed to get next release: {e}")
        return None


class CnTradeBalanceService:
    """中国貿易収支サービス"""

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
            logger.warning(f"[Trade] File cache write error: {e}")

    def _build_payload(self) -> Dict[str, Any]:
        data = _build_data()
        next_release = _get_next_release()

        return {
            **data,
            "metadata": {
                "indicator": "Trade Balance",
                "source": "General Administration of Customs / NBS",
                "unit": "100 million USD",
                "series": {
                    "balance": "貿易収支 (億USD)",
                    "exports": "輸出額 (億USD)",
                    "imports": "輸入額 (億USD)",
                    "exports_yoy": "輸出 前年比 (%)",
                    "imports_yoy": "輸入 前年比 (%)",
                },
                "total_records": len(data.get("balance", [])),
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
        return {"success": True, "message": "Trade Balance cache invalidated"}

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
cn_trade_balance_service = CnTradeBalanceService()
