"""
中国 NBS PMI（購買担当者景況指数）サービス

3チャート分のデータを一括提供:
1. ヘッドライン PMI: 総合PMI + 製造業PMI + 非製造業PMI
2. 製造業PMIサブインデックス: 生産、新規受注、新規輸出受注、手持ち受注、雇用、原材料購入価格、出荷価格、サプライヤー納期
3. 非製造業PMIサブインデックス: サービス業、建設業、新規受注、輸出新規受注、手持ち受注、販売価格、投入価格、サプライヤー納期、雇用

データソース:
- DB蓄積: nbs_monthly_data テーブル（CSVインポート + NBS API蓄積）
- 最新値: NBS統計データAPIから取得 → DB UPSERT
  https://data.stats.gov.cn/easyquery.htm
- FMP: 次回発表日の取得のみ

NBS APIは直近24ヶ月のみ返すため、DB蓄積で永続化する。
CSVは初期インポート済み（import_nbs_pmi_csv.py → nbs_monthly_data テーブル）。
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
FILE_CACHE_PATH = str(_FILE_CACHE_DIR / "cn_pmi_cache.json")

REDIS_KEY = "china:cn_pmi:data"
REDIS_TTL = 86400  # 24h

ECONALPHA_ID = "cn_national_bureau_of_Statistics_pmi"

# ---------------------------------------------------------------------------
# DB 指標IDマッピング
# ---------------------------------------------------------------------------
# ヘッドライン
DB_HEADLINE = {
    "composite":      "cn_pmi_composite",
    "manufacturing":  "cn_pmi_manufacturing",
    "non_manufacturing": "cn_pmi_non_manufacturing",
}

# 製造業サブインデックス
DB_MFG_SUB = {
    "production":         "cn_pmi_mfg_production",
    "new_orders":         "cn_pmi_mfg_new_orders",
    "new_export_orders":  "cn_pmi_mfg_new_export_orders",
    "in_hand_orders":     "cn_pmi_mfg_in_hand_orders",
    "employment":         "cn_pmi_mfg_employment",
    "raw_material_price": "cn_pmi_mfg_raw_material_price",
    "producer_prices":    "cn_pmi_mfg_producer_prices",
    "supplier_delivery":  "cn_pmi_mfg_supplier_delivery",
}

# 非製造業サブインデックス
DB_NMF_SUB = {
    "services":           "cn_pmi_nmf_services",
    "construction":       "cn_pmi_nmf_construction",
    "new_orders":         "cn_pmi_nmf_new_orders",
    "export_new_orders":  "cn_pmi_nmf_export_new_orders",
    "in_hand_orders":     "cn_pmi_nmf_in_hand_orders",
    "sale_price":         "cn_pmi_nmf_sale_price",
    "input_price":        "cn_pmi_nmf_input_price",
    "supplier_delivery":  "cn_pmi_nmf_supplier_delivery",
    "employment":         "cn_pmi_nmf_employment",
}

# ---------------------------------------------------------------------------
# NBS 統計データ API 設定
# ---------------------------------------------------------------------------
NBS_API_URL = "https://data.stats.gov.cn/easyquery.htm"

# NBS API 指標コード → DB指標ID のマッピング
NBS_API_CODES = {
    # ヘッドライン
    "A0B0301": "cn_pmi_composite",
    "A0B0101": "cn_pmi_manufacturing",
    "A0B0201": "cn_pmi_non_manufacturing",
    # 製造業サブ
    "A0B0102": "cn_pmi_mfg_production",
    "A0B0103": "cn_pmi_mfg_new_orders",
    "A0B0104": "cn_pmi_mfg_new_export_orders",
    "A0B0105": "cn_pmi_mfg_in_hand_orders",
    "A0B010C": "cn_pmi_mfg_employment",
    "A0B010A": "cn_pmi_mfg_raw_material_price",
    "A0B0109": "cn_pmi_mfg_producer_prices",
    "A0B010D": "cn_pmi_mfg_supplier_delivery",
    # 非製造業サブ
    "A0B020C": "cn_pmi_nmf_services",
    "A0B020B": "cn_pmi_nmf_construction",
    "A0B0202": "cn_pmi_nmf_new_orders",
    "A0B0203": "cn_pmi_nmf_export_new_orders",
    "A0B0204": "cn_pmi_nmf_in_hand_orders",
    "A0B0207": "cn_pmi_nmf_sale_price",
    "A0B0206": "cn_pmi_nmf_input_price",
    "A0B0209": "cn_pmi_nmf_supplier_delivery",
    "A0B0208": "cn_pmi_nmf_employment",
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

    PMIは指数値そのままなので変換不要（PPIと異なりbase=100変換しない）

    Returns:
        {date_str: value, ...} e.g. {"2026-01-01": 49.3}
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
            logger.warning(f"[NBS-PMI] API HTTP {resp.status_code} for {indicator_code}")
            return {}

        data = resp.json()
        if data.get("returncode") != 200:
            logger.warning(f"[NBS-PMI] API returncode: {data.get('returncode')} for {indicator_code}")
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
            # PMIはそのまま（50基準の拡散指数）
            result[date_str] = round(value, 1)

        return result

    except Exception as e:
        logger.warning(f"[NBS-PMI] API fetch failed for {indicator_code}: {e}")
        return {}


def _fetch_and_upsert_nbs() -> None:
    """NBS APIから全PMI指標の最新データを取得し、DBにUPSERT"""
    from services.china.nbs_db_utils import upsert_nbs_data

    for api_code, db_indicator in NBS_API_CODES.items():
        try:
            data = _fetch_nbs_api(api_code, periods=24)
            if data:
                count = upsert_nbs_data(db_indicator, data, source="api")
                logger.info(f"[NBS-PMI] API {api_code} → {db_indicator}: {len(data)} records, DB upserted {count}")
        except Exception as e:
            logger.warning(f"[NBS-PMI] API {api_code} fetch/upsert failed: {e}")


def _build_headline_data() -> List[Dict[str, Any]]:
    """ヘッドラインPMIデータ構築: 総合 + 製造業 + 非製造業"""
    from services.china.nbs_db_utils import load_nbs_multi

    indicators = list(DB_HEADLINE.values())
    db_data = load_nbs_multi(indicators)

    composite_data = db_data.get(DB_HEADLINE["composite"], {})
    mfg_data = db_data.get(DB_HEADLINE["manufacturing"], {})
    nmf_data = db_data.get(DB_HEADLINE["non_manufacturing"], {})

    all_dates = set(composite_data.keys()) | set(mfg_data.keys()) | set(nmf_data.keys())

    result = []
    for date_str in sorted(all_dates):
        item = {"date": date_str}
        mfg = mfg_data.get(date_str)
        nmf = nmf_data.get(date_str)
        comp = composite_data.get(date_str)
        # 少なくとも製造業PMIがある場合のみ追加
        if mfg is not None:
            item["manufacturing"] = mfg
            item["non_manufacturing"] = nmf
            item["composite"] = comp
            result.append(item)

    return result


def _build_mfg_sub_data() -> List[Dict[str, Any]]:
    """製造業PMIサブインデックスデータ構築"""
    from services.china.nbs_db_utils import load_nbs_multi

    indicators = list(DB_MFG_SUB.values())
    db_data = load_nbs_multi(indicators)

    # 全日付を収集
    all_dates: set = set()
    for ind_data in db_data.values():
        all_dates.update(ind_data.keys())

    result = []
    for date_str in sorted(all_dates):
        item: Dict[str, Any] = {"date": date_str}
        has_any = False
        for key, db_id in DB_MFG_SUB.items():
            val = db_data.get(db_id, {}).get(date_str)
            item[key] = val
            if val is not None:
                has_any = True
        if has_any:
            result.append(item)

    return result


def _build_nmf_sub_data() -> List[Dict[str, Any]]:
    """非製造業PMIサブインデックスデータ構築"""
    from services.china.nbs_db_utils import load_nbs_multi

    indicators = list(DB_NMF_SUB.values())
    db_data = load_nbs_multi(indicators)

    all_dates: set = set()
    for ind_data in db_data.values():
        all_dates.update(ind_data.keys())

    result = []
    for date_str in sorted(all_dates):
        item: Dict[str, Any] = {"date": date_str}
        has_any = False
        for key, db_id in DB_NMF_SUB.items():
            val = db_data.get(db_id, {}).get(date_str)
            item[key] = val
            if val is not None:
                has_any = True
        if has_any:
            result.append(item)

    return result


def _get_next_release() -> Optional[Dict[str, Any]]:
    """FMPから次回発表日を取得"""
    try:
        from services.usa.fmp_next_release_utils import get_next_release_from_fmp
        return get_next_release_from_fmp(ECONALPHA_ID, country="CN")
    except Exception as e:
        logger.warning(f"[PMI] Failed to get next release: {e}")
        return None


class CnPmiService:
    """中国 NBS PMI サービス"""

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
            logger.warning(f"[PMI] File cache write error: {e}")

    def _build_payload(self) -> Dict[str, Any]:
        # NBS APIから最新取得→DB蓄積
        try:
            _fetch_and_upsert_nbs()
        except Exception as e:
            logger.warning(f"[PMI] NBS API fetch/upsert failed: {e}")

        headline_data = _build_headline_data()
        mfg_sub_data = _build_mfg_sub_data()
        nmf_sub_data = _build_nmf_sub_data()

        headline_latest = headline_data[-1] if headline_data else None
        mfg_sub_latest = mfg_sub_data[-1] if mfg_sub_data else None
        nmf_sub_latest = nmf_sub_data[-1] if nmf_sub_data else None

        next_release = _get_next_release()

        return {
            "headline": {
                "data": headline_data,
                "latest": headline_latest,
            },
            "manufacturing_sub": {
                "data": mfg_sub_data,
                "latest": mfg_sub_latest,
            },
            "non_manufacturing_sub": {
                "data": nmf_sub_data,
                "latest": nmf_sub_latest,
            },
            "metadata": {
                "indicator": "NBS Purchasing Managers Index",
                "source": "National Bureau of Statistics (NBS)",
                "headline_records": len(headline_data),
                "mfg_sub_records": len(mfg_sub_data),
                "nmf_sub_records": len(nmf_sub_data),
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
        return {"success": True, "message": "PMI cache invalidated"}

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
cn_pmi_service = CnPmiService()
