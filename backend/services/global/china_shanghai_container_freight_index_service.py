"""
中国・上海コンテナ運賃指数（SCFI / CCFI）サービス

2系列:
- scfi: Shanghai Containerized Freight Index（上海輸出コンテナ運賃指数）
- ccfi: China Containerized Freight Index（中国輸出コンテナ運賃指数）

データソース:
- 過去時系列: CSV → DB蓄積（nbs_monthly_data テーブル、indicator = scfi / ccfi）
- 最新値: Shanghai Shipping Exchange (SSE) ウェブサイトスクレイピング → DB蓄積
  - SCFI: https://en.sse.net.cn/indices/scfinew.jsp → /currentIndex?indexName=scfi
  - CCFI: https://en.sse.net.cn/indices/ccfinew.jsp → /currentIndex?indexName=ccfi

FMPマッピング: なし

発表スケジュール: 週次（通常毎週金曜 北京時間15:00 / JST 16:00）
"""
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
CST = ZoneInfo("Asia/Shanghai")

# キャッシュ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "global" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "china_shanghai_container_freight_index_cache.json"

# CSV
CSV_DIR = Path(__file__).parent.parent.parent / "data" / "csv_import"
CSV_FILE = CSV_DIR / "コンテナ運賃指数.csv"

# DB indicator IDs（nbs_monthly_data テーブルを再利用）
DB_INDICATOR_SCFI = "scfi"
DB_INDICATOR_CCFI = "ccfi"

# Redis
DATA_CACHE_KEY = "global:china_shanghai_container_freight_index:data"

# SSE API
SSE_BASE_URL = "https://en.sse.net.cn"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://en.sse.net.cn/indices/scfinew.jsp",
}


# ---------------------------------------------------------------------------
# CSV読み込み → DB蓄積
# ---------------------------------------------------------------------------

def _parse_csv_date(date_str: str) -> Optional[str]:
    """日本語日付文字列をISO形式に変換

    '2021年01月08日' → '2021-01-08'
    """
    m = re.match(r"(\d{4})年(\d{2})月(\d{2})日", date_str.strip())
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"


def _parse_value(val_str: str) -> Optional[float]:
    """カンマ付き数値文字列をfloatに変換

    '"2,870.34"' → 2870.34
    '995.16' → 995.16
    """
    cleaned = val_str.strip().strip('"').replace(",", "")
    if not cleaned:
        return None
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def import_csv_to_db() -> int:
    """CSVファイルからSCFI/CCFIデータをDBにインポート"""
    from services.china.nbs_db_utils import upsert_nbs_data

    if not CSV_FILE.exists():
        logger.warning(f"[ContainerFreight] CSV not found: {CSV_FILE}")
        return 0

    scfi_data: Dict[str, float] = {}
    ccfi_data: Dict[str, float] = {}

    with open(CSV_FILE, "r", encoding="utf-8") as f:
        import csv
        reader = csv.DictReader(f)
        for row in reader:
            date_str = _parse_csv_date(row.get("公表日", ""))
            if not date_str:
                continue

            scfi_val = _parse_value(row.get("上海輸出コンテナ運賃指数 SCFI", ""))
            ccfi_val = _parse_value(row.get("中国輸出コンテナ運賃指数 CCFI", ""))

            if scfi_val is not None:
                scfi_data[date_str] = scfi_val
            if ccfi_val is not None:
                ccfi_data[date_str] = ccfi_val

    total = 0
    if scfi_data:
        count = upsert_nbs_data(DB_INDICATOR_SCFI, scfi_data, source="csv")
        logger.info(f"[ContainerFreight] SCFI CSV: {len(scfi_data)} records, DB upserted {count}")
        total += count

    if ccfi_data:
        count = upsert_nbs_data(DB_INDICATOR_CCFI, ccfi_data, source="csv")
        logger.info(f"[ContainerFreight] CCFI CSV: {len(ccfi_data)} records, DB upserted {count}")
        total += count

    return total


# ---------------------------------------------------------------------------
# SSE ウェブスクレイピング → DB蓄積
# ---------------------------------------------------------------------------

def _fetch_sse_current(index_name: str) -> Optional[Dict[str, Any]]:
    """SSEのcurrentIndex APIから最新データを取得

    Args:
        index_name: 'scfi' or 'ccfi'

    Returns:
        {'date': '2026-03-06', 'value': 1489.19} or None
    """
    try:
        url = f"{SSE_BASE_URL}/currentIndex"
        params = {"indexName": index_name}
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)

        if resp.status_code != 200:
            logger.warning(f"[ContainerFreight] SSE {index_name} HTTP {resp.status_code}")
            return None

        resp_json = resp.json()
        if not resp_json:
            return None

        # APIレスポンスは {"data": {...}, "msg": "...", "status": ...} 形式
        data = resp_json.get("data", resp_json)
        if not data:
            return None

        # lineDataList配列から総合指数を取得
        line_list = data.get("lineDataList", [])
        if not line_list:
            return None

        # 最初のエントリが「Comprehensive Index」(SCFI) or「COMPOSITE INDEX」(CCFI)
        composite = line_list[0]
        current_content = composite.get("currentContent")
        current_date = data.get("currentDate")

        if current_content is None or current_date is None:
            return None

        # 日付変換: "2026-03-06" → そのまま
        date_str = str(current_date).strip()
        value = round(float(current_content), 2)

        return {"date": date_str, "value": value}

    except Exception as e:
        logger.warning(f"[ContainerFreight] SSE {index_name} fetch error: {e}")
        return None


def _fetch_and_upsert_latest() -> None:
    """SSEから最新のSCFI/CCFIを取得しDBに蓄積"""
    from services.china.nbs_db_utils import upsert_nbs_data

    # SCFI
    scfi = _fetch_sse_current("scfi")
    if scfi:
        count = upsert_nbs_data(DB_INDICATOR_SCFI, {scfi["date"]: scfi["value"]}, source="api")
        logger.info(f"[ContainerFreight] SCFI latest: {scfi['date']} = {scfi['value']} (upserted {count})")

    # CCFI
    ccfi = _fetch_sse_current("ccfi")
    if ccfi:
        count = upsert_nbs_data(DB_INDICATOR_CCFI, {ccfi["date"]: ccfi["value"]}, source="api")
        logger.info(f"[ContainerFreight] CCFI latest: {ccfi['date']} = {ccfi['value']} (upserted {count})")


# ---------------------------------------------------------------------------
# データ構築
# ---------------------------------------------------------------------------

def _build_data() -> List[Dict[str, Any]]:
    """DBからSCFI/CCFIデータを読み込み、マージして返す"""
    from services.china.nbs_db_utils import load_nbs_multi

    # DBにデータが少ない場合はCSVインポートを実行
    existing = load_nbs_multi([DB_INDICATOR_SCFI, DB_INDICATOR_CCFI])
    if len(existing.get(DB_INDICATOR_SCFI, {})) < 50 or len(existing.get(DB_INDICATOR_CCFI, {})) < 50:
        logger.info("[ContainerFreight] DB has few records, importing CSV...")
        try:
            import_csv_to_db()
        except Exception as e:
            logger.warning(f"[ContainerFreight] CSV import failed: {e}")

    # SSEから最新値を取得→DB蓄積（ベストエフォート）
    try:
        _fetch_and_upsert_latest()
    except Exception as e:
        logger.warning(f"[ContainerFreight] SSE fetch/upsert failed: {e}")

    # DBから全データ読み込み
    all_data = load_nbs_multi([DB_INDICATOR_SCFI, DB_INDICATOR_CCFI])
    scfi_data = all_data.get(DB_INDICATOR_SCFI, {})
    ccfi_data = all_data.get(DB_INDICATOR_CCFI, {})

    logger.info(f"[ContainerFreight] DB SCFI: {len(scfi_data)} records, CCFI: {len(ccfi_data)} records")

    # 全日付を統合（週次なので日付が一致しない場合もある）
    all_dates = sorted(set(scfi_data.keys()) | set(ccfi_data.keys()))

    result = []
    for date_str in all_dates:
        scfi = scfi_data.get(date_str)
        ccfi = ccfi_data.get(date_str)
        result.append({
            "date": date_str,
            "scfi": scfi,
            "ccfi": ccfi,
        })

    logger.info(f"[ContainerFreight] Total: {len(result)} records")
    return result


# ---------------------------------------------------------------------------
# サービスクラス
# ---------------------------------------------------------------------------

class ChinaShanghaiContainerFreightIndexService:
    """中国・上海コンテナ運賃指数サービス"""

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """データ取得（キャッシュ優先）"""

        if not force_refresh:
            cached = redis_client.get(DATA_CACHE_KEY)
            if cached:
                last_updated_str = cached.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached.get("data", []),
                        "latest": cached.get("latest"),
                        "metadata": cached.get("metadata", {}),
                        "next_release": None,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # データ構築
        data = _build_data()
        latest = data[-1] if data else None

        if latest:
            scfi_str = f"{latest['scfi']:.2f}" if latest.get('scfi') is not None else 'N/A'
            ccfi_str = f"{latest['ccfi']:.2f}" if latest.get('ccfi') is not None else 'N/A'
            logger.info(f"[ContainerFreight] Latest: {latest['date']} SCFI={scfi_str} CCFI={ccfi_str}")

        metadata = {
            "source": "Shanghai Shipping Exchange (SSE)",
            "indicator": "Container Freight Index (SCFI / CCFI)",
            "description": "上海輸出コンテナ運賃指数(SCFI)・中国輸出コンテナ運賃指数(CCFI)",
            "unit": "index",
            "frequency": "weekly",
            "series": {
                "scfi": "Shanghai Containerized Freight Index (SCFI)",
                "ccfi": "China Containerized Freight Index (CCFI)",
            },
        }

        cache_payload = {
            "data": data,
            "latest": latest,
            "metadata": metadata,
            "last_updated": datetime.now(JST).isoformat(),
            "csv_mtime": self._get_csv_mtime(),
        }
        redis_client.set(DATA_CACHE_KEY, cache_payload, expire=0)
        self._save_file_cache(cache_payload)

        return {
            "data": data,
            "latest": latest,
            "metadata": metadata,
            "next_release": None,
            "cached": False,
            "source": "db+sse",
            "last_updated": datetime.now(JST).isoformat(),
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきか判定

        週次データ: CSVタイムスタンプ変更 or 6時間以上経過 でリフレッシュ
        """
        try:
            cached = redis_client.get(DATA_CACHE_KEY)
            if not cached:
                return True

            # CSVファイル変更チェック
            cached_csv_mtime = cached.get("csv_mtime")
            current_csv_mtime = self._get_csv_mtime()
            if cached_csv_mtime != current_csv_mtime:
                return True

            # 6時間以上経過でリフレッシュ（週次なので頻繁な更新は不要）
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)
            if (now - last_updated).total_seconds() > 6 * 3600:
                return True

            return False
        except Exception:
            return True

    def _get_csv_mtime(self) -> Optional[str]:
        """CSVファイルの最終更新時刻"""
        try:
            if CSV_FILE.exists():
                mtime = os.path.getmtime(CSV_FILE)
                return datetime.fromtimestamp(mtime, tz=JST).isoformat()
        except Exception:
            pass
        return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュ保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[ContainerFreight] File cache write error: {e}")

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュ読み込み"""
        try:
            if DATA_CACHE_FILE.exists():
                with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def invalidate_cache(self) -> bool:
        """キャッシュ無効化"""
        return redis_client.delete(DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態"""
        data_exists = redis_client.exists(DATA_CACHE_KEY)
        cached_data = redis_client.get(DATA_CACHE_KEY) if data_exists else None
        data_count = len(cached_data.get("data", [])) if cached_data else 0

        return {
            "indicator": "Container Freight Index (SCFI / CCFI)",
            "source": "Shanghai Shipping Exchange (SSE)",
            "cache_key": DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": data_count,
            "csv_file_exists": CSV_FILE.exists(),
            "csv_mtime": self._get_csv_mtime(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトン
china_shanghai_container_freight_index_service = ChinaShanghaiContainerFreightIndexService()
