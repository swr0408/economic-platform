"""
中国 輸出物価指数（Chinese Export Prices）サービス

データソース:
- 中國海關總署（General Administration of Customs of China）
  http://gdfs.customs.gov.cn/customs/syx/index.html
- 手動更新: backend/data/manual_update/monthly/china/中国輸出物価.csv を更新後、
  `python backend/scripts/import_cn_export_prices_csv.py` を実行して DB へ反映

DB指標ID:
  cn_export_prices_index: 輸出物価指数（前年同月=100）
  cn_export_prices_yoy:   前年比 (%) = index - 100

更新スケジュール: 月次（手動更新）
"""
import os
import csv
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

_BASE_DIR = Path(__file__).parent.parent.parent
_FILE_CACHE_DIR = _BASE_DIR / "data" / "cache" / "china" / "inflation"
FILE_CACHE_PATH = str(_FILE_CACHE_DIR / "cn_export_prices_cache.json")

REDIS_KEY = "china:cn_export_prices:data"
REDIS_TTL = 86400  # 24h

DB_INDICATORS = {
    "index": "cn_export_prices_index",
    "yoy": "cn_export_prices_yoy",
}

# 手動更新CSV（公表日 YYYY/M, 結果=指数 前年同月=100）。
# DB（過去データ）より優先し、CSV更新だけで自動反映させる。
_MANUAL_CSV = _BASE_DIR / "data" / "manual_update" / "monthly" / "china" / "中国輸出物価.csv"


def _parse_csv() -> Dict[str, float]:
    """中国輸出物価.csv を解析し {date_str: index_val} を返す。

    import_cn_export_prices_csv.py と同じ解析ロジック（日付 YYYY/M、値=指数）。
    """
    result: Dict[str, float] = {}
    try:
        if not _MANUAL_CSV.exists():
            return result
        with open(_MANUAL_CSV, encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # ヘッダー（公表日,結果）
            for row in reader:
                if len(row) < 2:
                    continue
                date_raw = row[0].strip()
                value_raw = row[1].strip()
                if not date_raw or not value_raw:
                    continue
                parts = date_raw.split("/")
                if len(parts) != 2:
                    continue
                try:
                    year = int(parts[0])
                    month = int(parts[1])
                    index_val = float(value_raw)
                except ValueError:
                    continue
                result[f"{year}-{month:02d}-01"] = round(index_val, 2)
    except Exception as e:
        logger.warning(f"[CnExportPrices] CSV parse error: {e}")
    return result


def _get_csv_mtime() -> Optional[float]:
    """手動更新CSVの更新時刻（mtime）。CSV更新の自動検知に使用。"""
    try:
        if _MANUAL_CSV.exists():
            return os.path.getmtime(_MANUAL_CSV)
    except OSError:
        pass
    return None


def _build_data() -> List[Dict[str, Any]]:
    """DB（過去データ）+ 手動更新CSV（優先）から index/yoy を読み込み、mom は index 差分から算出"""
    from services.china.nbs_db_utils import load_nbs_multi

    db_keys = list(DB_INDICATORS.values())
    db_data = load_nbs_multi(db_keys)

    index_map = dict(db_data.get(DB_INDICATORS["index"], {}))
    yoy_map = dict(db_data.get(DB_INDICATORS["yoy"], {}))

    # 手動更新CSVで上書き・補完（CSV優先）。yoy = index - 100。
    for date_str, idx_val in _parse_csv().items():
        index_map[date_str] = idx_val
        yoy_map[date_str] = round(idx_val - 100, 2)

    sorted_dates = sorted(index_map.keys())
    result: List[Dict[str, Any]] = []
    prev_index: Optional[float] = None

    for date_str in sorted_dates:
        idx_val = index_map.get(date_str)
        if idx_val is None:
            continue

        mom_val: Optional[float] = None
        if prev_index is not None:
            mom_val = round(idx_val - prev_index, 2)

        result.append({
            "date": date_str,
            "index": idx_val,
            "yoy": yoy_map.get(date_str),
            "mom": mom_val,
        })
        prev_index = idx_val

    logger.info(f"[CnExportPrices] Total: {len(result)} records")
    return result


class CnExportPricesService:
    """中国 輸出物価指数サービス（手動CSV更新）"""

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
            logger.warning(f"[CnExportPrices] File cache write error: {e}")

    def _build_payload(self) -> Dict[str, Any]:
        data = _build_data()
        latest = data[-1] if data else None

        return {
            "data": data,
            "latest": latest,
            "metadata": {
                "indicator": "Chinese Export Prices",
                "source": "General Administration of Customs of China (GACC)",
                "source_url": "http://gdfs.customs.gov.cn/customs/syx/index.html",
                "series": {
                    "index": "輸出物価指数（前年同月=100）",
                    "yoy": "前年比 (%)",
                    "mom": "前月比（index差分）",
                },
                "total_records": len(data),
                "last_fetched": datetime.now(JST).isoformat(),
            },
            "next_release": None,
            # CSV更新の自動検知用。読み込み時に現在のmtimeと比較する。
            "csv_mtime": _get_csv_mtime(),
        }

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        if not force_refresh:
            current_mtime = _get_csv_mtime()
            cached = self._from_redis()
            # CSVが更新されている（mtime不一致）場合はキャッシュを使わず再ビルド
            if cached and cached.get("csv_mtime") == current_mtime:
                return cached
            cached = self._from_file()
            if cached and cached.get("csv_mtime") == current_mtime:
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
        return {"success": True, "message": "Chinese Export Prices cache invalidated"}

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


cn_export_prices_service = CnExportPricesService()
