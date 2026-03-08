"""
NZ インフレ期待サービス

指標:
- B1. 1 year out (SOE.Q.E210.na)
- B2. 2 years out (SOE.Q.E215.na)
- B3. 5 years out (SOE.Q.E220.na)
- B4. 10 years out (SOE.Q.E230.na)

データソース:
- RBNZ Survey of Expectations
- https://www.rbnz.govt.nz/statistics/series/economic-indicators/survey-of-expectations

取得方法:
- hm14.xlsx をダウンロード
- Data シートから系列IDで列を特定しデータ抽出

発表スケジュール:
- 四半期ごと

キャッシュ方式:
- Redis + ファイルキャッシュ
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd
import io

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "newzealand" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "nz_inflation_expectations_cache.json"

EXCEL_URL = "https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/m/m14/hm14.xlsx"

# 対象系列
SERIES = {
    "one_year": "SOE.Q.E210.na",
    "two_year": "SOE.Q.E215.na",
    "five_year": "SOE.Q.E220.na",
    "ten_year": "SOE.Q.E230.na",
}

_scraper = None

def _get_scraper():
    """cloudscraper インスタンスを遅延初期化"""
    global _scraper
    if _scraper is None:
        import cloudscraper
        _scraper = cloudscraper.create_scraper()
    return _scraper


class NzInflationExpectationsService:
    """NZ インフレ期待サービス"""

    DATA_CACHE_KEY = "newzealand:nz_inflation_expectations:data"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """NZ インフレ期待データを取得"""

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # RBNZからデータ取得
        result = self._load_from_rbnz()
        if result:
            latest = result[-1] if result else None
            next_release = self._get_next_release()

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "RBNZ",
                    "indicator": "Survey of Expectations - Inflation",
                    "description": "NZ インフレ期待",
                    "unit": "%",
                    "frequency": "quarterly",
                    "series": SERIES,
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "rbnz",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきか判定（1日1回）"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)
            return (now - last_updated).total_seconds() > 86400
        except Exception:
            return True

    def _load_from_rbnz(self) -> Optional[List[Dict[str, Any]]]:
        """RBNZ Excelからインフレ期待データを取得"""
        try:
            print(f"[NzInflExp] Downloading: {EXCEL_URL}")
            resp = _get_scraper().get(EXCEL_URL, timeout=60)
            if resp.status_code != 200 or len(resp.content) < 5000:
                print(f"[NzInflExp] Download failed: HTTP {resp.status_code}, {len(resp.content)} bytes")
                return None

            print(f"[NzInflExp] Downloaded: {len(resp.content)} bytes")

            df = pd.read_excel(io.BytesIO(resp.content), sheet_name="Data", header=None, engine="openpyxl")
            print(f"[NzInflExp] Data sheet shape: {df.shape}")

            # Row 4 から系列IDで列インデックスを特定
            series_row = df.iloc[4]
            col_map: Dict[str, int] = {}
            for key, series_id in SERIES.items():
                for col_idx in range(df.shape[1]):
                    val = str(series_row.iloc[col_idx]).strip() if pd.notna(series_row.iloc[col_idx]) else ""
                    if val == series_id:
                        col_map[key] = col_idx
                        print(f"[NzInflExp] {key} ({series_id}): Col {col_idx}")
                        break

            if not col_map:
                print("[NzInflExp] No series found in Excel")
                return None

            # Row 5以降からデータ抽出
            result = []
            for row_idx in range(5, df.shape[0]):
                date_val = df.iloc[row_idx, 0]
                if pd.isna(date_val):
                    continue

                # 日付を文字列に変換
                if isinstance(date_val, datetime):
                    # 四半期末日付（3/31, 6/30, 9/30, 12/31）→ 四半期開始月（1, 4, 7, 10）に変換
                    month = date_val.month
                    year = date_val.year
                    # 四半期開始月に合わせる
                    quarter_start_month = ((month - 1) // 3) * 3 + 1
                    date_str = f"{year}-{quarter_start_month:02d}-01"
                else:
                    try:
                        dt = pd.to_datetime(date_val)
                        month = dt.month
                        year = dt.year
                        quarter_start_month = ((month - 1) // 3) * 3 + 1
                        date_str = f"{year}-{quarter_start_month:02d}-01"
                    except Exception:
                        continue

                if date_str < "2000-01-01":
                    continue

                item: Dict[str, Any] = {"date": date_str}
                has_any = False

                for key, col_idx in col_map.items():
                    val = df.iloc[row_idx, col_idx]
                    if pd.notna(val):
                        try:
                            item[key] = round(float(val), 2)
                            has_any = True
                        except (ValueError, TypeError):
                            item[key] = None
                    else:
                        item[key] = None

                if has_any:
                    result.append(item)

            if result:
                print(f"[NzInflExp] Total {len(result)} records")
                print(f"[NzInflExp] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[NzInflExp] Latest: 1yr={latest.get('one_year')}%, 2yr={latest.get('two_year')}%, "
                      f"5yr={latest.get('five_year')}%, 10yr={latest.get('ten_year')}%")

            return result

        except Exception as e:
            print(f"[NzInflExp] Error loading from RBNZ: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """FMPから次回発表日を取得"""
        try:
            from services.newzealand.fmp_next_release_utils import get_next_release_by_pattern
            return get_next_release_by_pattern(
                "Inflation Expectations",
                country="NZ",
            )
        except Exception as e:
            print(f"[NzInflExp] Error getting next release: {e}")
            return None

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[NzInflExp] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[NzInflExp] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        return {
            "indicator": "NZ Inflation Expectations",
            "source": "RBNZ",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
nz_inflation_expectations_service = NzInflationExpectationsService()
