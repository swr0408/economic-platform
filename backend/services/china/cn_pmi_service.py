"""
中国 NBS PMI（購買担当者景況指数）サービス

3チャート分のデータを一括提供:
1. ヘッドライン PMI: 総合PMI + 製造業PMI + 非製造業PMI
2. 製造業PMIサブインデックス: 生産、新規受注、新規輸出受注、手持ち受注、雇用、原材料購入価格、出荷価格、サプライヤー納期
3. 非製造業PMIサブインデックス: サービス業、建設業、新規受注、輸出新規受注、手持ち受注、販売価格、投入価格、サプライヤー納期、雇用

データソース:
- DB蓄積: nbs_monthly_data テーブル（CSVインポート + プレスリリース蓄積）
- 最新値: www.stats.gov.cn/sj/zxfb/ プレスリリース添付 Excel → DB UPSERT
- FMP: 次回発表日の取得のみ

CSVは初期インポート済み（import_nbs_pmi_csv.py → nbs_monthly_data テーブル）。
"""
import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from zoneinfo import ZoneInfo

from services.china.nbs_press_release_utils import fetch_and_upsert_from_press_release, parse_excel, parse_xls, _safe_float

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
# Excel 列名 → DB indicator マッピング
# ---------------------------------------------------------------------------
# 製造業シート（シート1「制造业」）
MFG_EXCEL_COLUMNS = {
    "PMI": "cn_pmi_manufacturing",
    "生产": "cn_pmi_mfg_production",
    "新订单": "cn_pmi_mfg_new_orders",
    "从业人员": "cn_pmi_mfg_employment",
    "供应商配送时间": "cn_pmi_mfg_supplier_delivery",
    "新出口订单": "cn_pmi_mfg_new_export_orders",
    "在手订单": "cn_pmi_mfg_in_hand_orders",
    "出厂价格": "cn_pmi_mfg_producer_prices",
    "原材料购进价格": "cn_pmi_mfg_raw_material_price",
}

# 非製造業シート（シート2「非制造业」）
NMF_EXCEL_COLUMNS = {
    "商务活动": "cn_pmi_non_manufacturing",
    "新订单": "cn_pmi_nmf_new_orders",
    "投入品价格": "cn_pmi_nmf_input_price",
    "销售价格": "cn_pmi_nmf_sale_price",
    "从业人员": "cn_pmi_nmf_employment",
    "新出口订单": "cn_pmi_nmf_export_new_orders",
    "在手订单": "cn_pmi_nmf_in_hand_orders",
    "供应商配送时间": "cn_pmi_nmf_supplier_delivery",
}


def _excel_serial_to_date(serial) -> Optional[str]:
    """Excelシリアル値を 'YYYY-MM-01' 文字列に変換"""
    from datetime import timedelta
    try:
        serial_int = int(float(serial))
        dt = datetime(1899, 12, 30) + timedelta(days=serial_int)
        return f"{dt.year}-{dt.month:02d}-01"
    except (ValueError, TypeError, OverflowError):
        return None


def _parse_sheet(rows: List[List], column_map: Dict[str, str]) -> Dict[str, Dict[str, float]]:
    """PMI Excelシートをパースして {db_indicator: {date_str: value}} を返す

    R3 (index 2) がヘッダー行、R4以降がデータ行。
    """
    if len(rows) < 4:
        return {}

    # ヘッダー行（index 2）からマッピングを構築
    header_row = rows[2]
    col_indices: Dict[str, int] = {}
    for col_idx, cell in enumerate(header_row):
        if cell is None:
            continue
        cell_str = str(cell).strip()
        if cell_str in column_map:
            col_indices[cell_str] = col_idx

    if not col_indices:
        logger.warning(f"[NBS-PMI] No matching columns found in header: {header_row}")
        return {}

    # データ行をパース（index 3以降）
    result: Dict[str, Dict[str, float]] = {db_id: {} for db_id in column_map.values()}

    for row in rows[3:]:
        if not row or row[0] is None:
            continue

        date_str = _excel_serial_to_date(row[0])
        if not date_str:
            continue

        for col_name, col_idx in col_indices.items():
            if col_idx >= len(row):
                continue
            val = _safe_float(row[col_idx])
            if val is not None:
                db_indicator = column_map[col_name]
                result[db_indicator][date_str] = round(val, 1)

    return result


def _extract_pmi_from_excel(
    excel_data: bytes, period: Optional[tuple],
) -> Dict[str, Dict[str, float]]:
    """PMI プレスリリース添付 Excel からデータを抽出

    Excel構造:
    - シート1「制造业」: 製造業PMI時系列
    - シート2「非制造业」: 非製造業PMI時系列

    Returns:
        {db_indicator: {date_str: value}, ...}
    """
    result: Dict[str, Dict[str, float]] = {}

    # 製造業シート
    try:
        mfg_rows = parse_excel(excel_data, sheet_name="制造业", sheet_index=0)
        mfg_data = _parse_sheet(mfg_rows, MFG_EXCEL_COLUMNS)
        result.update(mfg_data)
        logger.info(f"[NBS-PMI] Manufacturing sheet: parsed {sum(len(v) for v in mfg_data.values())} values")
    except Exception as e:
        logger.warning(f"[NBS-PMI] Failed to parse manufacturing sheet: {e}")

    # 非製造業シート
    try:
        nmf_rows = parse_excel(excel_data, sheet_name="非制造业", sheet_index=1)
        nmf_data = _parse_sheet(nmf_rows, NMF_EXCEL_COLUMNS)
        result.update(nmf_data)
        logger.info(f"[NBS-PMI] Non-manufacturing sheet: parsed {sum(len(v) for v in nmf_data.values())} values")
    except Exception as e:
        logger.warning(f"[NBS-PMI] Failed to parse non-manufacturing sheet: {e}")

    return result


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
        # プレスリリース Excel → DB蓄積
        try:
            fetch_and_upsert_from_press_release("pmi", _extract_pmi_from_excel)
        except Exception as e:
            logger.warning(f"[PMI] Press release fetch/upsert failed: {e}")

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
