"""
IEA Oil Market Report サービス

データソース:
  - 手動配置CSV: backend/data/manual_update/monthly/iea/IEA Oil Market Report.csv
  - ヘッダー行: 項目, {月号1}, {月号2}, ... , {差分列}, 備考
  - 項目数は月号によって増減する（可変対応）

更新: ファイルのタイムスタンプ変更を検出して自動リフレッシュ
"""
import csv
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CSV_DIR = Path(__file__).parent.parent.parent / "data" / "manual_update" / "monthly" / "iea"
CSV_FILE = CSV_DIR / "IEA Oil Market Report.csv"
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "iea_oil_market_report_cache.json"

REDIS_KEY = "market:iea_oil_market_report:data"


class IeaOilMarketReportService:
    """IEA Oil Market Report サービス"""

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """FMPから次回IEA Oil Market Report発表日を取得
        週1回（土曜 7:00 JST）にFMPを確認し、結果をRedisにキャッシュ。
        取得できない場合は空欄（None）を返す。"""
        redis_key = "market:iea_oil_market_report:next_release"
        try:
            # Redisキャッシュを確認（7日間有効）
            cached = redis_client.get(redis_key)
            if cached is not None:
                # cached == {} は「取得できなかった」を意味
                return cached if cached else None

            # キャッシュがない場合、土曜7:00 JSTかどうかに関わらず初回は取得を試みる
            return self._fetch_and_cache_next_release(redis_key)
        except Exception as e:
            logger.error(f"[IEA-OMR] Next release error: {e}")
            return None

    def _fetch_and_cache_next_release(self, redis_key: str) -> Optional[Dict[str, Any]]:
        """FMPから次回発表日を取得してRedisにキャッシュ（TTL=7日）"""
        try:
            try:
                from backend.services.usa.fmp_next_release_utils import get_next_release_from_fmp
            except ImportError:
                from services.usa.fmp_next_release_utils import get_next_release_from_fmp

            result = get_next_release_from_fmp(
                "iea_oil_market_report",
                patterns=["%IEA Oil Market Report%"],
                country="FR",
            )

            # 結果をキャッシュ（取得できなくても空dictをキャッシュして再問い合わせを防止）
            # TTL = 7日（604800秒）— 次の土曜チェックで更新される
            redis_client.set(redis_key, result if result else {}, expire=604800)
            return result
        except Exception as e:
            logger.error(f"[IEA-OMR] FMP fetch error: {e}")
            return None

    def _get_file_mtime(self) -> Optional[float]:
        """CSVファイルの更新日時を取得"""
        try:
            if CSV_FILE.exists():
                return os.path.getmtime(CSV_FILE)
        except Exception:
            pass
        return None

    def _should_refresh(self) -> bool:
        try:
            cached = redis_client.get(REDIS_KEY)
            if not cached:
                return True
            cached_mtime = cached.get("metadata", {}).get("file_mtime")
            if cached_mtime is None:
                return True
            current_mtime = self._get_file_mtime()
            if current_mtime is None:
                return False  # ファイルがなければキャッシュを使用
            # ファイルのタイムスタンプが変わったらリフレッシュ
            if abs(current_mtime - cached_mtime) > 0.01:
                return True
            return False
        except Exception:
            return True

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        if not force_refresh and not self._should_refresh():
            cached = self._load_from_redis()
            if cached and cached.get("headers"):
                cached["next_release"] = self._get_next_release()
                return cached

        try:
            data = self._build_data()
            if data and data.get("headers"):
                self._save_to_cache(data)
                data["next_release"] = self._get_next_release()
                return data
        except Exception as e:
            logger.error(f"[IEA-OMR] Build error: {e}")
            import traceback
            traceback.print_exc()

        cached = self._load_from_redis()
        if cached and cached.get("headers"):
            cached["next_release"] = self._get_next_release()
            return cached

        cached = self._load_from_file()
        if cached and cached.get("headers"):
            cached["next_release"] = self._get_next_release()
            return cached

        return {
            "headers": [],
            "rows": [],
            "next_release": self._get_next_release(),
            "metadata": {"source": "IEA Oil Market Report"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """CSVを読み込んでデータを構築"""
        if not CSV_FILE.exists():
            logger.error(f"[IEA-OMR] CSV file not found: {CSV_FILE}")
            return None

        logger.info(f"[IEA-OMR] Reading CSV: {CSV_FILE}")

        rows_data: List[Dict[str, str]] = []
        headers: List[str] = []

        try:
            with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                raw_headers = next(reader, None)
                if not raw_headers:
                    logger.error("[IEA-OMR] CSV has no header row")
                    return None

                # ヘッダーをクリーンアップ（空列を除去）
                headers = [h.strip() for h in raw_headers if h.strip()]

                for row in reader:
                    if not row or not row[0].strip():
                        continue
                    # 可変列数対応: ヘッダー数に合わせて行データをマッピング
                    row_dict: Dict[str, str] = {}
                    for i, header in enumerate(headers):
                        if i < len(row):
                            row_dict[header] = row[i].strip()
                        else:
                            row_dict[header] = ""
                    rows_data.append(row_dict)
        except Exception as e:
            logger.error(f"[IEA-OMR] CSV read error: {e}")
            return None

        if not rows_data:
            logger.error("[IEA-OMR] No data rows in CSV")
            return None

        file_mtime = self._get_file_mtime()
        now_str = datetime.now(JST).isoformat()

        logger.info(f"[IEA-OMR] Parsed {len(rows_data)} rows, {len(headers)} columns")

        return {
            "headers": headers,
            "rows": rows_data,
            "metadata": {
                "source": "IEA Oil Market Report",
                "file_name": CSV_FILE.name,
                "file_mtime": file_mtime,
                "row_count": len(rows_data),
                "column_count": len(headers),
            },
            "cached": False,
            "source": "csv",
            "last_updated": now_str,
        }

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(REDIS_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[IEA-OMR] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[IEA-OMR] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(REDIS_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[IEA-OMR] Redis load error: {e}")
        return None

    def _load_from_file(self) -> Optional[Dict[str, Any]]:
        try:
            if DATA_CACHE_FILE.exists():
                with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["cached"] = True
                data["source"] = "file"
                return data
        except Exception as e:
            logger.error(f"[IEA-OMR] File load error: {e}")
        return None


iea_oil_market_report_service = IeaOilMarketReportService()
