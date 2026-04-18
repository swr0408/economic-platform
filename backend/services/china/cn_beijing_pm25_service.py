"""
北京PM2.5濃度サービス

データソース: 手動更新CSV (beijing-air-quality.csv)
カラム: date, pm25, pm10, o3, no2, so2, co

CSVファイルのタイムスタンプが前回読み込みより新しければ再読み込みする。

レスポンス:
- daily: 日次データ（date, pm25）
- monthly: 月平均データ（date, pm25_avg）
- ma30: 30日移動平均データ（date, pm25_ma30）
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
CSV_PATH = str(_BASE_DIR / "data" / "manual_update" / "daily" / "beijing_pm25" / "beijing-air-quality.csv")
_FILE_CACHE_DIR = _BASE_DIR / "data" / "cache" / "china" / "economy"
FILE_CACHE_PATH = str(_FILE_CACHE_DIR / "cn_beijing_pm25_cache.json")

REDIS_KEY = "china:cn_beijing_pm25:data"
REDIS_TTL = 86400  # 24h


def _parse_csv() -> List[Dict[str, Any]]:
    """CSVファイルを読み込んで日次データを返す"""
    import pandas as pd

    if not os.path.exists(CSV_PATH):
        logger.warning(f"[BeijingPM25] CSV not found: {CSV_PATH}")
        return []

    df = pd.read_csv(CSV_PATH)

    # カラム名のスペースを除去
    df.columns = df.columns.str.strip()

    # date を datetime に変換
    df['date'] = pd.to_datetime(df['date'], format='mixed', dayfirst=False)

    # pm25 を数値に変換
    df['pm25'] = pd.to_numeric(df['pm25'], errors='coerce')

    # pm25 が NaN の行を除外
    df = df.dropna(subset=['pm25'])

    # 日付順にソート
    df = df.sort_values('date').reset_index(drop=True)

    result = []
    for _, row in df.iterrows():
        result.append({
            "date": row['date'].strftime('%Y-%m-%d'),
            "pm25": round(float(row['pm25']), 1),
        })

    logger.info(f"[BeijingPM25] Parsed {len(result)} daily records from CSV")
    return result


def _compute_monthly(daily: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """日次データから月平均を計算"""
    import pandas as pd

    if not daily:
        return []

    df = pd.DataFrame(daily)
    df['date'] = pd.to_datetime(df['date'])
    df['pm25'] = pd.to_numeric(df['pm25'], errors='coerce')

    monthly = df.groupby(df['date'].dt.to_period('M')).agg(
        pm25_avg=('pm25', 'mean'),
        count=('pm25', 'count'),
    ).reset_index()

    monthly['date'] = monthly['date'].dt.to_timestamp()

    result = []
    for _, row in monthly.iterrows():
        result.append({
            "date": row['date'].strftime('%Y-%m-%d'),
            "pm25_avg": round(float(row['pm25_avg']), 1),
        })

    return result


def _compute_ma30(daily: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """日次データから30日移動平均を計算"""
    import pandas as pd

    if not daily:
        return []

    df = pd.DataFrame(daily)
    df['date'] = pd.to_datetime(df['date'])
    df['pm25'] = pd.to_numeric(df['pm25'], errors='coerce')

    # 全日付範囲を生成して欠損日を補間
    all_dates = pd.date_range(start=df['date'].min(), end=df['date'].max(), freq='D')
    df = df.set_index('date').reindex(all_dates).rename_axis('date').reset_index()

    # 30日移動平均
    df['pm25_ma30'] = df['pm25'].rolling(window=30, min_periods=15).mean()

    # NaN を除外
    df = df.dropna(subset=['pm25_ma30'])

    result = []
    for _, row in df.iterrows():
        result.append({
            "date": row['date'].strftime('%Y-%m-%d'),
            "pm25_ma30": round(float(row['pm25_ma30']), 1),
        })

    return result


class CnBeijingPm25Service:
    """北京PM2.5濃度サービス"""

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

    def _csv_mtime(self) -> Optional[float]:
        """CSVファイルの最終更新時刻を取得"""
        if os.path.exists(CSV_PATH):
            return os.path.getmtime(CSV_PATH)
        return None

    def _csv_changed(self, cached_payload: Optional[Dict[str, Any]]) -> bool:
        """キャッシュに記録された mtime と現在の CSV mtime を比較"""
        current_mtime = self._csv_mtime()
        if current_mtime is None:
            return False
        if not cached_payload:
            return True
        cached_mtime = (cached_payload.get("metadata") or {}).get("csv_mtime")
        if cached_mtime is None:
            return True
        try:
            return abs(current_mtime - float(cached_mtime)) > 0.01
        except (TypeError, ValueError):
            return True

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
                json.dump(payload, f, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"[BeijingPM25] File cache write error: {e}")

    def _build_payload(self) -> Dict[str, Any]:
        daily = _parse_csv()
        monthly = _compute_monthly(daily)
        ma30 = _compute_ma30(daily)

        latest_daily = daily[-1] if daily else None
        latest_monthly = monthly[-1] if monthly else None

        csv_mtime = self._csv_mtime()

        return {
            "daily": daily,
            "monthly": monthly,
            "ma30": ma30,
            "latest": latest_daily,
            "latest_monthly": latest_monthly,
            "metadata": {
                "indicator": "Beijing PM2.5 Concentration",
                "source": "Beijing Air Quality (Manual CSV)",
                "total_daily": len(daily),
                "total_monthly": len(monthly),
                "total_ma30": len(ma30),
                "csv_mtime": csv_mtime,
                "csv_last_modified": datetime.fromtimestamp(
                    csv_mtime, tz=JST
                ).isoformat() if csv_mtime else None,
                "last_fetched": datetime.now(JST).isoformat(),
            },
        }

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """データ取得（キャッシュ優先、CSVファイル更新時は自動再読み込み）"""
        cached = self._from_redis()
        if cached is None:
            cached = self._from_file()
            if cached is not None:
                self._to_redis(cached)

        if not force_refresh and cached and not self._csv_changed(cached):
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
        return {"success": True, "message": "Beijing PM2.5 cache invalidated"}

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
        csv_mtime = None
        if os.path.exists(CSV_PATH):
            csv_mtime = datetime.fromtimestamp(
                os.path.getmtime(CSV_PATH), tz=JST
            ).isoformat()
        return {
            "redis": {"exists": redis_exists, "ttl_seconds": redis_ttl},
            "file": {"exists": file_exists, "last_modified": file_mtime},
            "csv": {"exists": os.path.exists(CSV_PATH), "last_modified": csv_mtime},
        }


# シングルトン
cn_beijing_pm25_service = CnBeijingPm25Service()
