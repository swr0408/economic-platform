"""
中国 商業住宅販売（Commercial Residential Sales）サービス

3系列の前年比累積値を表示:
- 新規着工床面積 (Floor space of buildings newly started) YoY%
- 新築商業ビル販売額 (Sales of newly built commercial buildings) YoY%
- 新築商業用ビル売却床面積 (Floor space of newly built commercial buildings sold) YoY%

データソース:
- DB蓄積: nbs_monthly_data テーブル（CSVインポート + プレスリリース蓄積）
  indicator: cn_re_floor_started_yoy, cn_re_sales_yoy, cn_re_floor_sold_yoy
- 最新値: www.stats.gov.cn/sj/zxfb/ プレスリリース添付 Excel → DB UPSERT
  「房地产市场基本情况」記事添付 Excel「表1」シート
- 発表スケジュール: FMPベース（cn_commercial_residential_sales）

CSVは初期インポート済み（csv_import → nbs_monthly_data テーブル）。
"""
import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from zoneinfo import ZoneInfo

from services.usa.fmp_next_release_utils import get_next_release_from_fmp
from services.china.nbs_press_release_utils import fetch_and_upsert_from_press_release, parse_excel, parse_xls, _safe_float

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
# Excel ラベル → DB indicator マッピング
# ---------------------------------------------------------------------------
# 「房地产市场基本情况」記事添付 Excel「表1」シート
# R2: 指標 | 绝对量 | 同比增长（%）
RE_EXCEL_LABELS = {
    "房屋新开工面积": "cn_re_floor_started_yoy",
    "商品房销售额": "cn_re_sales_yoy",
    "商品房销售面积": "cn_re_floor_sold_yoy",
}


def _extract_re_from_excel(
    excel_data: bytes, period: Optional[tuple],
) -> Dict[str, Dict[str, float]]:
    """不動産プレスリリース添付 Excel からデータを抽出

    Excel「表1」シート構造:
    - R2: 指標 | 绝对量 | 同比增长（%）
    - R3以降: 各指標行

    不動産データは累計データ（1-N月）。period は (year, end_month)。

    Returns:
        {db_indicator: {date_str: value}, ...}
    """
    if not period:
        logger.warning("[NBS-RealEstate] No period info, cannot determine date")
        return {}

    year, month = period
    date_str = f"{year}-{month:02d}-01"

    rows = parse_excel(excel_data, sheet_name="表1", sheet_index=0)
    if len(rows) < 3:
        logger.warning("[NBS-RealEstate] Excel has too few rows")
        return {}

    result: Dict[str, Dict[str, float]] = {}

    # ヘッダー行（index 1）から YoY% の列位置を特定
    header = rows[1] if len(rows) > 1 else []
    yoy_col = None
    for col_idx, cell in enumerate(header):
        if cell is not None and "同比" in str(cell):
            yoy_col = col_idx
            break

    # デフォルト: col2 (index 2) が YoY%
    if yoy_col is None:
        yoy_col = 2

    # データ行をスキャン
    for row in rows[2:]:
        if not row or row[0] is None:
            continue
        label = str(row[0]).strip()
        for excel_label, db_indicator in RE_EXCEL_LABELS.items():
            if excel_label in label:
                if yoy_col < len(row):
                    val = _safe_float(row[yoy_col])
                    if val is not None:
                        result[db_indicator] = {date_str: round(val, 1)}
                break

    return result


def _build_data() -> List[Dict[str, Any]]:
    """DBからデータを読み込み + プレスリリースExcelで最新取得→DB蓄積

    手順:
    1. プレスリリース Excel から最新データ取得 → DB UPSERT
    2. DBから全データを読み込み
    3. 日付をキーにマージして時系列構築
    """
    from services.china.nbs_db_utils import load_nbs_multi

    # --- プレスリリース Excel → DB蓄積 ---
    try:
        fetch_and_upsert_from_press_release("real_estate", _extract_re_from_excel)
    except Exception as e:
        logger.warning(f"[CommercialSales] Press release fetch/upsert failed: {e}")

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
