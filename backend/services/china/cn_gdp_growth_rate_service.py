"""
中国 GDP成長率サービス

2系列:
- YoY%: 国内生产总值 前年同期比 (%)
- QoQ%: 国内生产总值 前期比 (%)（Excelに含まれる場合のみ）

データソース:
- DB蓄積: nbs_monthly_data テーブル（CSVインポート + プレスリリース Excel 蓄積）
  indicator: cn_gdp_yoy, cn_gdp_qoq
  ※ 四半期データだが nbs_monthly_data テーブルを共用（date は四半期末月の1日）
- 最新値: www.stats.gov.cn/sj/zxfb/ プレスリリース添付 Excel → DB UPSERT
  「国内生产总值」記事の Excel 表1（GDP YoY）
- FMP: 次回発表日の取得のみ

四半期末月: Q1→03, Q2→06, Q3→09, Q4→12
DB日付: Q1→YYYY-03-01, Q2→YYYY-06-01, Q3→YYYY-09-01, Q4→YYYY-12-01
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
FILE_CACHE_PATH = str(_FILE_CACHE_DIR / "cn_gdp_growth_rate_cache.json")

REDIS_KEY = "china:cn_gdp_growth_rate:data"
REDIS_TTL = 86400  # 24h

ECONALPHA_ID = "cn_gdp_growth_rate"

# DB指標ID
DB_INDICATORS = {
    "yoy": "cn_gdp_yoy",
    "qoq": "cn_gdp_qoq",
}

# 四半期コード → 日付変換
QUARTER_TO_MONTH = {"A": "03", "B": "06", "C": "09", "D": "12"}

# end_month → 四半期ラベル（ログ用）
MONTH_TO_QUARTER = {3: "Q1", 6: "Q2", 9: "Q3", 12: "Q4"}


def _extract_gdp_from_excel(excel_data: bytes, period) -> Dict[str, Dict[str, float]]:
    """GDPプレスリリース Excel からYoY（およびQoQがあれば）を抽出

    Excel 表1（GDP初步核算）構造:
    - R3: GDP | 絶対額 | YoY%
    表1から「国内生产总值」行を探し、YoY% を取得。
    QoQ は表1に含まれている場合のみ取得（列数で判定）。

    period は (year, end_month)。end_month を四半期末月として日付を構成。
    """
    from services.china.nbs_press_release_utils import parse_excel, _safe_float

    if not period:
        logger.warning("[NBS-GDP] No period info from release title")
        return {}

    year, end_month = period
    date_str = f"{year}-{end_month:02d}-01"
    q_label = MONTH_TO_QUARTER.get(end_month, f"M{end_month}")

    # 表1 をパース（sheet_index=0）
    rows = parse_excel(excel_data, sheet_index=0)

    yoy_result = {}
    qoq_result = {}

    for row in rows:
        label = str(row[0]).strip() if row[0] else ""
        # 「GDP」または「国内生产总值」行にマッチ
        if label != "GDP" and "国内生产总值" not in label:
            continue
        # サブ行を除外
        if "其中" in label or "第一产业" in label or "第二产业" in label or "第三产业" in label:
            continue

        # YoY%: col2（絶対額の次）
        yoy_val = _safe_float(row[2]) if len(row) > 2 else None
        if yoy_val is not None:
            yoy_result[date_str] = round(yoy_val, 1)
            logger.info(f"[NBS-GDP] Excel: {date_str} ({q_label}) yoy={yoy_val}")

        # QoQ%: col3 があればそちらを試行
        if len(row) > 3:
            qoq_val = _safe_float(row[3])
            if qoq_val is not None:
                qoq_result[date_str] = round(qoq_val, 1)
                logger.info(f"[NBS-GDP] Excel: {date_str} ({q_label}) qoq={qoq_val}")

        break

    result = {}
    if yoy_result:
        result[DB_INDICATORS["yoy"]] = yoy_result
    if qoq_result:
        result[DB_INDICATORS["qoq"]] = qoq_result

    return result


def _fetch_and_upsert_from_press_release() -> None:
    """NBS プレスリリース Excel から最新データを取得し、DB に UPSERT"""
    from services.china.nbs_press_release_utils import fetch_and_upsert_from_press_release

    results = fetch_and_upsert_from_press_release(
        category="gdp",
        extractor_fn=_extract_gdp_from_excel,
        primary_indicator=DB_INDICATORS["yoy"],
    )
    if results:
        logger.info(f"[NBS-GDP] Press release upsert: {results}")


def _build_data() -> List[Dict[str, Any]]:
    """DBからデータを読み込み + プレスリリース Excel で最新取得→DB蓄積"""
    from services.china.nbs_db_utils import load_nbs_multi

    # --- プレスリリース Excel → DB蓄積 ---
    try:
        _fetch_and_upsert_from_press_release()
    except Exception as e:
        logger.warning(f"[GDP] Press release fetch/upsert failed: {e}")

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
        """データ取得（キャッシュ優先）

        空キャッシュ（data=[]）は外部API/DB取得失敗時に保存された破損キャッシュの
        可能性が高いため、採用せず再取得する。GDPは過去データが必ずDBにあるため。
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
            logger.warning("[GDP] Empty payload; skipping cache write to prevent stale empty cache")
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
