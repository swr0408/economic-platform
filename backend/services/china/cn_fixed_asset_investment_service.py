"""
中国 固定資産投資（Fixed Asset Investment）サービス

1系列:
- YTD累計増長率(%): 固定资产投资额_累計増長(%)

データソース:
- DB蓄積: nbs_monthly_data テーブル（CSVインポート + プレスリリース Excel 蓄積）
  indicator: cn_fixed_asset_investment_ytd
- 最新値: www.stats.gov.cn/sj/zxfb/ プレスリリース添付 Excel → DB UPSERT
  「固定资产投资」記事の Excel R4 行（累計YoY%）
- FMP: 次回発表日の取得のみ

DB蓄積で永続化。CSVは初期インポート済み。
※ 1月は発表なし（1-2月合算発表）
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
FILE_CACHE_PATH = str(_FILE_CACHE_DIR / "cn_fixed_asset_investment_cache.json")

REDIS_KEY = "china:cn_fixed_asset_investment:data"
REDIS_TTL = 86400  # 24h

ECONALPHA_ID = "cn_fixed_asset_investment"

# DB指標ID
DB_INDICATOR = "cn_fixed_asset_investment_ytd"


def _extract_fai_from_excel(excel_data: bytes, period) -> Dict[str, Dict[str, float]]:
    """固定資産投資プレスリリース Excel から累計YoY を抽出

    Excel「表」シート構造:
    - R2: 指標 | 同比増長(%)
    - R4: 固定资产投资（不含农户） | YoY%(累計)
    """
    from services.china.nbs_press_release_utils import parse_excel, _safe_float

    rows = parse_excel(excel_data)
    result = {}

    for row in rows:
        label = str(row[0]).strip() if row[0] else ""
        if "固定资产投资" not in label:
            continue
        # タイトル行・ヘッダー行を除外（年月やデータ区分を含むもの）
        if "主要数据" in label or "月份" in label:
            continue
        # "其中" を含むサブ行を除外
        if "其中" in label:
            continue

        # col1 = YoY%(累計)
        ytd_val = _safe_float(row[1]) if len(row) > 1 else None
        if period and ytd_val is not None:
            year, month = period
            date_str = f"{year}-{month:02d}-01"
            result[date_str] = round(ytd_val, 1)
            logger.info(f"[NBS-FAI] Excel: {date_str} ytd={ytd_val}")
            break

    return {DB_INDICATOR: result}


def _fetch_and_upsert_from_press_release() -> None:
    """NBS プレスリリース Excel から最新データを取得し、DB に UPSERT"""
    from services.china.nbs_press_release_utils import fetch_and_upsert_from_press_release

    results = fetch_and_upsert_from_press_release(
        category="fixed_asset",
        extractor_fn=_extract_fai_from_excel,
        primary_indicator=DB_INDICATOR,
    )
    if results:
        logger.info(f"[NBS-FAI] Press release upsert: {results}")


def _build_data() -> List[Dict[str, Any]]:
    """DBからデータを読み込み + プレスリリース Excel で最新取得→DB蓄積"""
    from services.china.nbs_db_utils import load_nbs_data

    # --- プレスリリース Excel → DB蓄積 ---
    try:
        _fetch_and_upsert_from_press_release()
    except Exception as e:
        logger.warning(f"[FAI] Press release fetch/upsert failed: {e}")

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
