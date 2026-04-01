"""
中国 電気機器在庫（Electrical Machinery Inventory）サービス

1系列:
- YoY%: 电气机械和器材制造业存货_累計増減(%) → 直接%値

データソース:
- DB蓄積: nbs_monthly_data テーブル（CSVインポート済み）
  indicator: cn_electronics_stock_yoy
- SOX指数: yfinance ^SOX 月足から前年比を算出し、8ヶ月先行させて重ねて表示

NBS APIでの自動取得は当該指標コードが不明のため未対応。
CSVファイルを手動更新してインポートスクリプトで蓄積する。
"""
import os
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

_BASE_DIR = Path(__file__).parent.parent.parent
_FILE_CACHE_DIR = _BASE_DIR / "data" / "cache" / "china" / "economy"
FILE_CACHE_PATH = str(_FILE_CACHE_DIR / "cn_electronics_stock_cache.json")

REDIS_KEY = "china:cn_electronics_stock:data"
REDIS_TTL = 86400  # 24h

DB_INDICATOR = "cn_electronics_stock_yoy"


def _build_data() -> List[Dict[str, Any]]:
    """DBからデータを読み込み"""
    from services.china.nbs_db_utils import load_nbs_data

    yoy_data = load_nbs_data(DB_INDICATOR)
    logger.info(f"[ElecStock] DB YoY: {len(yoy_data)} records")

    result = []
    for date_str in sorted(yoy_data.keys()):
        result.append({
            "date": date_str,
            "yoy": yoy_data[date_str],
        })

    return result


def _fetch_sox_yoy() -> List[Dict[str, Any]]:
    """yfinanceからSOX指数の月足を取得し、前年比を計算して8ヶ月先行させる"""
    try:
        import yfinance as yf
        import pandas as pd

        ticker = yf.Ticker("^SOX")
        hist = ticker.history(period="max", interval="1mo")

        if hist.empty:
            logger.warning("[ElecStock] SOX: No data from yfinance")
            return []

        monthly_close = hist["Close"]
        # 前年比を計算（12ヶ月前との変化率）
        sox_yoy = monthly_close.pct_change(periods=12) * 100

        # 8ヶ月先行: インデックスを8ヶ月進める
        sox_yoy_shifted = sox_yoy.copy()
        sox_yoy_shifted.index = sox_yoy_shifted.index + pd.DateOffset(months=8)

        result = []
        for dt, val in sox_yoy_shifted.items():
            if pd.notna(val):
                # タイムゾーン付きdatetimeを処理
                if hasattr(dt, 'tz') and dt.tz is not None:
                    dt = dt.tz_localize(None)
                date_str = f"{dt.year}-{dt.month:02d}-01"
                result.append({
                    "date": date_str,
                    "sox_yoy": round(float(val), 2),
                })

        logger.info(f"[ElecStock] SOX YoY (8m lead): {len(result)} records")
        return result

    except Exception as e:
        logger.warning(f"[ElecStock] SOX fetch failed: {e}")
        return []


class CnElectronicsStockService:
    """中国電気機器在庫サービス"""

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
            logger.warning(f"[ElecStock] File cache write error: {e}")

    def _build_payload(self) -> Dict[str, Any]:
        data = _build_data()
        sox_data = _fetch_sox_yoy()
        latest = data[-1] if data else None

        return {
            "data": data,
            "sox_data": sox_data,
            "latest": latest,
            "metadata": {
                "indicator": "Electrical Machinery Inventory",
                "source": "National Bureau of Statistics (NBS)",
                "series": {
                    "yoy": "电气机械和器材制造业 存货増減 (%)",
                },
                "sox_note": "SOX YoY (8-month lead)",
                "total_records": len(data),
                "sox_records": len(sox_data),
                "last_fetched": datetime.now(JST).isoformat(),
            },
            "next_release": None,
        }

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
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
        return {"success": True, "message": "Electronics Stock cache invalidated"}

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
cn_electronics_stock_service = CnElectronicsStockService()
