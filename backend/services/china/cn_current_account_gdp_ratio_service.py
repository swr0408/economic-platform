"""
中国 経常収支対GDP比サービス

SAFE経常収支(RMB) / NBS名目GDP(RMB) で比率を算出

指標:
- 経常収支対GDP比（Current Account to GDP Ratio）

データソース:
- SAFE quarterly(RMB) シート Row 5: Current Account (亿元 = 100 million RMB)
- NBS hgjd A010101: 名目GDP当季值 (亿元 = 100 million RMB)

計算:
- Ratio (%) = (Current Account 亿元 / Nominal GDP 亿元) × 100

発表スケジュール: 四半期（GDP発表時に更新）
"""
import io
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd
import requests

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "china" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "cn_current_account_gdp_ratio_cache.json"

# 名目GDP CSV（NBS A010101 の履歴データ）
GDP_CSV_PATH = Path(__file__).parent.parent.parent / "data" / "csv_import" / "中国名目GDP当季値.csv"

# SAFE Excel URL
SAFE_EXCEL_URL = (
    "https://www.safe.gov.cn/en/file/file/20251231/"
    "4fb0399bcbc74ad8a823cd1f72f0d57b.xlsx"
    "?n=The%20time-series%20data%20of%20Balance%20of%20Payments%20of%20China"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

# SAFE Excel構造 (RMB sheet)
SAFE_SHEET_NAME = "quarterly(RMB)"
SAFE_HEADER_ROW = 3
SAFE_CURRENT_ACCOUNT_ROW = 5

# NBS API
NBS_API_URL = "https://data.stats.gov.cn/easyquery.htm"
NBS_GDP_CODE = "A010101"  # 名目GDP当季値（亿元）

# FMPイベントパターン（GDP発表時に更新）
FMP_EVENT_PATTERN = "GDP Growth Rate YoY"
FMP_COUNTRY = "CN"


def _quarter_to_date(quarter_str: str) -> Optional[str]:
    """四半期文字列(e.g. '2024Q3')をYYYY-MM-01形式に変換"""
    match = re.match(r"(\d{4})Q([1-4])", str(quarter_str).strip())
    if not match:
        return None
    year = int(match.group(1))
    q = int(match.group(2))
    month = {1: 3, 2: 6, 3: 9, 4: 12}[q]
    return f"{year}-{month:02d}-01"


def _nbs_period_to_date(period: str) -> Optional[str]:
    """NBS期間コード(e.g. '2024D')をYYYY-MM-01形式に変換"""
    if len(period) != 5:
        return None
    year = period[:4]
    q_letter = period[4]
    q_map = {"A": 3, "B": 6, "C": 9, "D": 12}
    month = q_map.get(q_letter)
    if month is None:
        return None
    return f"{year}-{month:02d}-01"


class CnCurrentAccountGdpRatioService:
    """中国経常収支対GDP比サービス"""

    DATA_CACHE_KEY = "china:cn_current_account_gdp_ratio:data"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """経常収支対GDP比データを取得"""
        next_release = self._get_next_release()

        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                    }

        result = self._load_from_source()
        if result:
            latest = result[-1] if result else None
            from services.usa.fmp_next_release_utils import guarded_last_updated
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
            )

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "SAFE / NBS",
                    "indicator": "Current Account to GDP Ratio",
                    "unit": "%",
                    "frequency": "quarterly",
                    "ca_source": "SAFE quarterly(RMB) Current Account (亿元)",
                    "gdp_source": "NBS A010101 Nominal GDP (亿元)",
                },
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "SAFE / NBS", "error": "No data available"},
            "next_release": next_release,
        }

    def _load_from_source(self) -> List[Dict[str, Any]]:
        """SAFE経常収支(RMB) + NBS名目GDPから対GDP比を計算"""
        try:
            # 1. SAFE経常収支データ取得（亿元）
            logger.info("[CN CA/GDP] Fetching current account from SAFE (RMB)")
            ca_data = self._fetch_safe_ca_rmb()
            logger.info(f"[CN CA/GDP] Current account: {len(ca_data)} quarters")

            # 2. NBS名目GDPデータ取得（亿元）
            logger.info("[CN CA/GDP] Fetching nominal GDP from NBS")
            gdp_data = self._fetch_nbs_gdp()
            logger.info(f"[CN CA/GDP] Nominal GDP: {len(gdp_data)} quarters")

            # 3. 比率を計算
            result = []
            for date_str in sorted(ca_data.keys()):
                if date_str in gdp_data:
                    ca_value = ca_data[date_str]
                    gdp_value = gdp_data[date_str]
                    if gdp_value > 0:
                        ratio = (ca_value / gdp_value) * 100
                        result.append({
                            "date": date_str,
                            "value": round(ratio, 2),
                            "current_account": round(ca_value, 1),  # 亿元
                            "gdp": round(gdp_value, 1),             # 亿元
                        })

            logger.info(f"[CN CA/GDP] Calculated {len(result)} quarterly records")
            if result:
                latest = result[-1]
                logger.info(
                    f"[CN CA/GDP] Latest: {latest['date']} "
                    f"Ratio={latest['value']}% "
                    f"CA={latest['current_account']}亿元 "
                    f"GDP={latest['gdp']}亿元"
                )

            return result

        except Exception as e:
            logger.error(f"[CN CA/GDP] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_safe_ca_rmb(self) -> Dict[str, float]:
        """SAFE quarterly(RMB)シートから経常収支を取得

        Returns:
            Dict[date_str, value]: 日付→経常収支（亿元）
        """
        try:
            resp = requests.get(SAFE_EXCEL_URL, headers=HEADERS, timeout=60)
            if resp.status_code != 200:
                logger.error(f"SAFE Excel download returned HTTP {resp.status_code}")
                return {}

            df = pd.read_excel(
                io.BytesIO(resp.content),
                sheet_name=SAFE_SHEET_NAME,
                header=None,
            )

            headers_row = df.iloc[SAFE_HEADER_ROW]
            data_row = df.iloc[SAFE_CURRENT_ACCOUNT_ROW]

            data: Dict[str, float] = {}
            for col_idx in range(1, len(headers_row)):
                quarter_label = headers_row.iloc[col_idx]
                if pd.isna(quarter_label):
                    continue

                date_str = _quarter_to_date(str(quarter_label))
                if not date_str:
                    continue

                val = data_row.iloc[col_idx]
                if pd.isna(val):
                    continue

                try:
                    data[date_str] = float(val)
                except (ValueError, TypeError):
                    continue

            return data

        except Exception as e:
            logger.error(f"[CN CA/GDP] Error fetching SAFE CA (RMB): {e}")
            return {}

    def _fetch_nbs_gdp(self) -> Dict[str, float]:
        """名目GDP四半期データを取得（CSV + NBS API増分）

        1. CSVから履歴データを読み込み
        2. NBS APIから直近8四半期を取得して補完・更新
        3. 新しいデータがあればCSVに書き戻し

        Returns:
            Dict[date_str, value]: 日付→名目GDP（亿元）
        """
        data: Dict[str, float] = {}

        # 1. CSVから履歴データを読み込み
        try:
            if GDP_CSV_PATH.exists():
                df = pd.read_csv(GDP_CSV_PATH)
                for _, row in df.iterrows():
                    date_str = str(row["date"]).strip()
                    value = float(row["value"])
                    data[date_str] = value
                logger.info(f"[CN CA/GDP] Loaded {len(data)} quarters from GDP CSV")
        except Exception as e:
            logger.warning(f"[CN CA/GDP] Error reading GDP CSV: {e}")

        # 2. NBS APIはWAFでブロックされているため、CSVのみで運用
        # 新しいGDPデータはCSVを手動更新してください

        logger.info(f"[CN CA/GDP] Total GDP data: {len(data)} quarters")
        return data

    def _update_gdp_csv(self, data: Dict[str, float]) -> None:
        """GDP CSVを更新"""
        try:
            rows = sorted(data.items())
            lines = ["date,value"]
            for date_str, value in rows:
                lines.append(f"{date_str},{value}")
            GDP_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
            GDP_CSV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
            logger.info(f"[CN CA/GDP] Updated GDP CSV with {len(rows)} records")
        except Exception as e:
            logger.warning(f"[CN CA/GDP] Failed to update GDP CSV: {e}")

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得（GDP発表日ベース）"""
        try:
            from services.china.fmp_next_release_utils import get_next_release_by_pattern
            return get_next_release_by_pattern(FMP_EVENT_PATTERN, country=FMP_COUNTRY)
        except Exception as e:
            logger.warning(f"[CN CA/GDP] Error getting next release: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュ更新判定"""
        try:
            from services.china.fmp_next_release_utils import should_refresh_by_pattern
            return should_refresh_by_pattern(FMP_EVENT_PATTERN, last_updated_str, country=FMP_COUNTRY)
        except Exception:
            try:
                last_updated = datetime.fromisoformat(last_updated_str)
                if last_updated.tzinfo is None:
                    last_updated = last_updated.replace(tzinfo=JST)
                now = datetime.now(JST)
                age = now - last_updated
                return age.total_seconds() > 86400 * 7
            except Exception:
                return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[CN CA/GDP] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[CN CA/GDP] Failed to save file cache: {e}")

    def invalidate_cache(self) -> Dict[str, Any]:
        redis_client.delete(self.DATA_CACHE_KEY)
        if DATA_CACHE_FILE.exists():
            DATA_CACHE_FILE.unlink()
        return {"success": True, "message": "CA/GDP ratio cache invalidated"}

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        return {
            "indicator": "CN Current Account to GDP Ratio",
            "source": "SAFE / NBS",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
            "next_release": self._get_next_release(),
        }


# シングルトン
cn_current_account_gdp_ratio_service = CnCurrentAccountGdpRatioService()
