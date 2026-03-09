"""
GEX / DIX サービス（SqueezeMetrics）

データ項目:
- price: S&P 500 終値
- dix: Dark Index (0〜1の割合、ダークプール取引の買い比率)
- gex: Gamma Exposure (ガンマエクスポージャー、ドル建て)

データソース:
- SqueezeMetrics CSV: https://squeezemetrics.com/monitor/static/DIX.csv

更新スケジュール: 毎営業日（JST 7:00頃）
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# キャッシュ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "gex_dix_cache.json"

# Redis
DATA_CACHE_KEY = "market:gex_dix:data"

# SqueezeMetrics
CSV_URL = "https://squeezemetrics.com/monitor/static/DIX.csv"

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/csv,text/plain,*/*",
}


class GexDixService:
    """GEX / DIX データ取得サービス"""

    def _should_refresh(self) -> bool:
        """キャッシュの更新が必要かどうか判定"""
        try:
            cached = redis_client.get(DATA_CACHE_KEY)
            if not cached:
                return True

            last_updated_str = cached.get("last_updated")
            if not last_updated_str:
                return True

            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)

            # 6時間以内に更新されていればスキップ
            if (now - last_updated).total_seconds() < 6 * 3600:
                return False

            return True
        except Exception:
            return True

    def get_gex_dix_data(
        self, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """GEX / DIX データを取得"""
        # キャッシュ確認
        if not force_refresh and not self._should_refresh():
            cached = self._load_from_redis()
            if cached and cached.get("data"):
                return cached

        # CSVからデータ取得
        try:
            data = self._fetch_from_csv()
            if data and data.get("data"):
                self._save_to_cache(data)
                return data
        except Exception as e:
            logger.error(f"[GexDix] CSV fetch error: {e}")

        # フォールバック: Redis → ファイル
        cached = self._load_from_redis()
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "SqueezeMetrics"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _fetch_from_csv(self) -> Optional[Dict[str, Any]]:
        """SqueezeMetrics CSVからGEX/DIXデータを取得"""
        logger.info(f"[GexDix] Fetching CSV from: {CSV_URL}")

        resp = requests.get(CSV_URL, headers=HTTP_HEADERS, timeout=30)
        resp.raise_for_status()

        text = resp.text
        lines = text.strip().split("\n")

        if len(lines) < 2:
            logger.warning("[GexDix] CSV has insufficient rows")
            return None

        # ヘッダー解析
        header = lines[0].strip().split(",")
        header = [h.strip().strip('"') for h in header]

        # 列インデックス
        try:
            date_idx = header.index("date")
            price_idx = header.index("price")
            dix_idx = header.index("dix")
            gex_idx = header.index("gex")
        except ValueError as e:
            logger.error(f"[GexDix] CSV column not found: {e}. Header: {header}")
            return None

        result_data: List[Dict[str, Any]] = []
        for line in lines[1:]:
            parts = line.strip().split(",")
            if len(parts) <= max(date_idx, price_idx, dix_idx, gex_idx):
                continue

            try:
                date_str = parts[date_idx].strip().strip('"')
                price_val = float(parts[price_idx].strip().strip('"'))
                dix_val = float(parts[dix_idx].strip().strip('"'))
                gex_val = float(parts[gex_idx].strip().strip('"'))

                # DIXを%表記に変換（0.38 → 38.0%）
                dix_pct = round(dix_val * 100, 2)

                # GEXを十億単位に変換（見やすくする）
                gex_bn = round(gex_val / 1_000_000_000, 2)

                result_data.append({
                    "date": date_str,
                    "price": round(price_val, 2),
                    "dix": dix_pct,
                    "gex": gex_bn,
                })
            except (ValueError, IndexError):
                continue

        # 日付でソート
        result_data.sort(key=lambda x: x["date"])

        if not result_data:
            logger.warning("[GexDix] No data parsed from CSV")
            return None

        latest = result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "SqueezeMetrics",
                "data_count": len(result_data),
                "start_date": result_data[0]["date"],
                "end_date": result_data[-1]["date"],
                "units": {
                    "price": "S&P 500 (USD)",
                    "dix": "Dark Index (%)",
                    "gex": "Gamma Exposure (Bn USD)",
                },
            },
            "cached": False,
            "source": "api",
            "last_updated": now_str,
        }

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        """Redis + ファイルキャッシュに保存"""
        try:
            redis_client.set(DATA_CACHE_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[GexDix] Redis save error: {e}")

        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[GexDix] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        """Redisキャッシュから読み込み"""
        try:
            data = redis_client.get(DATA_CACHE_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[GexDix] Redis load error: {e}")
        return None

    def _load_from_file(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュから読み込み"""
        try:
            if DATA_CACHE_FILE.exists():
                with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["cached"] = True
                data["source"] = "file"
                return data
        except Exception as e:
            logger.error(f"[GexDix] File load error: {e}")
        return None


# シングルトン
gex_dix_service = GexDixService()
