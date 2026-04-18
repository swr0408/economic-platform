"""
RONI (Revised Oceanic Niño Index) サービス

データソース:
  - NOAA CPC HTML: https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/
  - テーブルID: roni-v5-table2
  - 月次更新（毎月5日まで）
  - 3ヶ月移動平均の海面水温偏差 (°C)

更新: 6時間TTL (Redis + ファイル)
"""
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "roni_cache.json"

REDIS_KEY = "market:roni:data"

RONI_URL = (
    "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/"
)

# 季節コード → 中央月（date文字列用）
# DJF = Dec-Jan-Feb → 中央月 = 1月
SEASON_MONTH_MAP = {
    "DJF": "01", "JFM": "02", "FMA": "03", "MAM": "04",
    "AMJ": "05", "MJJ": "06", "JJA": "07", "JAS": "08",
    "ASO": "09", "SON": "10", "OND": "11", "NDJ": "12",
}

SEASONS = ["DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ",
           "JJA", "JAS", "ASO", "SON", "OND", "NDJ"]


class RoniService:
    """NOAA CPC RONI サービス"""

    def _should_refresh(self) -> bool:
        try:
            cached = redis_client.get(REDIS_KEY)
            if not cached:
                return True
            last_updated_str = cached.get("last_updated")
            if not last_updated_str:
                return True
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)
            return (now - last_updated).total_seconds() >= 6 * 3600
        except Exception:
            return True

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        if not force_refresh and not self._should_refresh():
            cached = self._load_from_redis()
            if cached and cached.get("data"):
                return cached

        try:
            data = self._build_data()
            if data and data.get("data"):
                self._save_to_cache(data)
                return data
        except Exception as e:
            logger.error(f"[RONI] Build error: {e}")
            import traceback
            traceback.print_exc()

        cached = self._load_from_redis()
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "NOAA CPC"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """HTMLからRONIテーブルをスクレイピング"""
        logger.info("[RONI] Fetching from NOAA CPC...")

        try:
            resp = requests.get(
                RONI_URL,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=30,
            )
            if resp.status_code != 200:
                logger.error(f"[RONI] HTTP {resp.status_code}")
                return None
        except Exception as e:
            logger.error(f"[RONI] Fetch error: {e}")
            return None

        result_data = self._parse_html(resp.text)
        if not result_data:
            logger.error("[RONI] No data parsed from HTML")
            return None

        result_data.sort(key=lambda x: x["date"])

        latest = result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[RONI] {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest value={latest.get('value')}"
        )

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "NOAA CPC",
                "dataset": "RONI (Revised Oceanic Niño Index)",
                "frequency": "monthly",
                "unit": "°C",
                "base_period": "1991-2020",
                "data_count": len(result_data),
                "start_date": result_data[0]["date"],
                "end_date": result_data[-1]["date"],
            },
            "cached": False,
            "source": "model",
            "last_updated": now_str,
        }

    def _parse_html(self, html: str) -> Optional[List[Dict[str, Any]]]:
        """HTMLテーブルからRONIデータを抽出（BeautifulSoup不使用）"""
        # テーブルを抽出
        table_match = re.search(
            r'<table[^>]*id=["\']roni-v5-table2["\'][^>]*>(.*?)</table>',
            html, re.DOTALL | re.IGNORECASE)
        if not table_match:
            # フォールバック: 任意のテーブルを探す
            table_match = re.search(
                r'<table[^>]*>(.*?)</table>',
                html, re.DOTALL | re.IGNORECASE)
            if not table_match:
                logger.error("[RONI] No table found in HTML")
                return None

        table_html = table_match.group(1)

        # 行を抽出 (NOAAのHTMLは最終行の</tr>が省略されることがあるため
        # </tr> / </tbody> / </table> / 次の<tr で区切る)
        rows = re.findall(
            r'<tr[^>]*>(.*?)(?=</tr>|</tbody>|</table>|<tr[^>]*>)',
            table_html, re.DOTALL | re.IGNORECASE,
        )

        result_data: List[Dict[str, Any]] = []

        for row_html in rows:
            # 年を取得（<th>内の数値）
            year_match = re.search(
                r'<th[^>]*>\s*(?:<p>)?\s*(\d{4})\s*(?:</p>)?\s*</th>',
                row_html, re.IGNORECASE)
            if not year_match:
                continue
            year = int(year_match.group(1))

            # セルからRONI値を取得
            cells = re.findall(
                r'<td[^>]*>\s*(?:<span[^>]*>)?\s*([^<]*?)\s*(?:</span>)?\s*</td>',
                row_html, re.IGNORECASE)

            for i, cell_text in enumerate(cells):
                if i >= len(SEASONS):
                    break
                val_str = cell_text.strip()
                if not val_str:
                    continue
                try:
                    value = round(float(val_str), 2)
                except (ValueError, TypeError):
                    continue

                season = SEASONS[i]
                month = SEASON_MONTH_MAP[season]
                date_str = f"{year}-{month}-01"

                result_data.append({
                    "date": date_str,
                    "value": value,
                    "season": season,
                })

        return result_data if result_data else None

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(REDIS_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[RONI] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[RONI] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(REDIS_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[RONI] Redis load error: {e}")
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
            logger.error(f"[RONI] File load error: {e}")
        return None


roni_service = RoniService()
