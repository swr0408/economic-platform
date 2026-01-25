"""
日本 所定内給与サービス（共通事業所版）
毎月勤労統計調査データを取得

指標:
- 所定内給与 (Scheduled Wage): 所定内給与 前年同月比 (%)
- 一般 (General): 一般労働者 前年同月比 (%)
- パート (Part-time): パートタイム労働者 前年同月比 (%)

データソース:
- e-Stat: 毎月勤労統計調査 共通事業所
  https://www.e-stat.go.jp/stat-search/file-download?statInfId=000031771318&fileKind=1

発表スケジュール:
- 1日〜10日: 速報値(p) 8:30 JST
- 17日〜月末: 確報値(r) 8:30 JST

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import requests
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path
from io import StringIO
import logging

from core.redis_client import redis_client
from services.japan.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "scheduled_wage_common_cache.json"


class ScheduledWageCommonService:
    """日本 所定内給与サービス（共通事業所版）"""

    DATA_CACHE_KEY = "japan:employment:scheduled_wage_common:data"

    # FMP event mapping
    ECONALPHA_ID = "jp_average_cash_earnings_yoy"

    # e-Stat CSV download URL (共通事業所版)
    ESTAT_CSV_URL = "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000031771318&fileKind=1"

    def __init__(self):
        pass

    def get_scheduled_wage_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        所定内給与データを取得（共通事業所版CSV）

        Returns:
            {
                "scheduled_wage": {"data": [...], "latest": {...}},
                "general": {"data": [...], "latest": {...}},
                "part_time": {"data": [...], "latest": {...}},
                "next_release": {...},
                "cached": bool,
                "source": str
            }
        """
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "scheduled_wage": cached_data.get("scheduled_wage"),
                        "general": cached_data.get("general"),
                        "part_time": cached_data.get("part_time"),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # e-Stat CSVからデータを取得
        estat_data = self._load_from_estat()

        if estat_data:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            cache_payload = {
                "scheduled_wage": estat_data.get("scheduled_wage"),
                "general": estat_data.get("general"),
                "part_time": estat_data.get("part_time"),
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                **cache_payload,
                "cached": False,
                "source": "e-Stat CSV",
            }

        # ファイルキャッシュからフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "scheduled_wage": file_cache.get("scheduled_wage"),
                "general": file_cache.get("general"),
                "part_time": file_cache.get("part_time"),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "scheduled_wage": None,
            "general": None,
            "part_time": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _load_from_estat(self) -> Optional[Dict[str, Any]]:
        """e-Stat CSVから所定内給与データを取得（共通事業所版）"""
        try:
            logger.info(f"Downloading scheduled wage data from e-Stat: {self.ESTAT_CSV_URL}")

            response = requests.get(self.ESTAT_CSV_URL, timeout=60)
            if response.status_code != 200:
                logger.error(f"Failed to download from e-Stat: {response.status_code}")
                return None

            # Shift-JIS encoding
            content = response.content.decode('shift_jis', errors='replace')
            df = pd.read_csv(StringIO(content))

            return self._process_csv(df)

        except Exception as e:
            logger.error(f"Error fetching scheduled wage data from e-Stat: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _process_csv(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        共通事業所版CSVデータを処理

        CSV構造（カラムインデックス）:
        - 0: 種別 (共通事業所)
        - 1: 年月 (YYYYMM)
        - 2: 産業分類 (TL 調査産業計)
        - 3: 規模 (５人ー)
        - 4: 就業形態 (計, 一般, パート)
        - 5: ー (separator)
        - 6: 現金給与総額 前年比(%)
        - 7: きまって支給する給与 前年比(%)
        - 8: 所定内給与 前年比(%)
        """
        try:
            logger.info(f"Processing e-Stat CSV with shape: {df.shape}")

            scheduled_wage_data = []  # 所定内給与 - 計
            general_data = []  # 所定内給与 - 一般
            part_time_data = []  # 所定内給与 - パート

            # Filter for TL (調査産業計) only - Column 2
            df_tl = df[df.iloc[:, 2].str.contains('TL', na=False)]
            logger.info(f"Filtered to TL (調査産業計): {len(df_tl)} rows from {len(df)} total")

            # Get unique employment types in column 4
            employment_types = df_tl.iloc[:, 4].unique()
            logger.info(f"Employment types found: {employment_types}")

            # Process each row
            for _, row in df_tl.iterrows():
                try:
                    year_month = str(row.iloc[1])  # Column 1: 年月
                    if len(year_month) != 6:
                        continue

                    year = int(year_month[:4])
                    month = int(year_month[4:])
                    date_str = f"{year}-{month:02d}-01"

                    # Skip data before 2000
                    if year < 2000:
                        continue

                    employment_type = str(row.iloc[4])  # Column 4: 就業形態
                    value = row.iloc[8]  # Column 8: 所定内給与

                    if pd.isna(value) or value == '' or value == '-':
                        continue

                    data_point = {
                        "date": date_str,
                        "value": round(float(value), 1)
                    }

                    # Categorize by employment type (handling different encodings)
                    if '計' in employment_type:
                        scheduled_wage_data.append(data_point)
                    elif '一般' in employment_type or '般' in employment_type:
                        general_data.append(data_point)
                    elif 'パート' in employment_type or 'パ' in employment_type:
                        part_time_data.append(data_point)

                except Exception as e:
                    logger.debug(f"Error processing row: {e}")
                    continue

            # Sort by date
            scheduled_wage_data.sort(key=lambda x: x["date"])
            general_data.sort(key=lambda x: x["date"])
            part_time_data.sort(key=lambda x: x["date"])

            logger.info(f"Processed: {len(scheduled_wage_data)} scheduled, {len(general_data)} general, {len(part_time_data)} part-time")

            if scheduled_wage_data:
                logger.info(f"Scheduled wage date range: {scheduled_wage_data[0]['date']} to {scheduled_wage_data[-1]['date']}")
                logger.info(f"Latest scheduled wage: {scheduled_wage_data[-1]}")

            return {
                "scheduled_wage": {
                    "data": scheduled_wage_data,
                    "latest": scheduled_wage_data[-1] if scheduled_wage_data else None,
                },
                "general": {
                    "data": general_data,
                    "latest": general_data[-1] if general_data else None,
                },
                "part_time": {
                    "data": part_time_data,
                    "latest": part_time_data[-1] if part_time_data else None,
                },
            }

        except Exception as e:
            logger.error(f"Error processing CSV: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_fmp_schedule(
            self.ECONALPHA_ID,
            last_updated_str
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            logger.error(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        scheduled_wage_count = 0
        general_count = 0
        part_time_count = 0

        if cached_data:
            sw = cached_data.get("scheduled_wage")
            gen = cached_data.get("general")
            pt = cached_data.get("part_time")
            scheduled_wage_count = len(sw.get("data", [])) if sw else 0
            general_count = len(gen.get("data", [])) if gen else 0
            part_time_count = len(pt.get("data", [])) if pt else 0

        return {
            "indicator": "JP Scheduled Wage (所定内給与 - 共通事業所版)",
            "source": "e-Stat (厚生労働省)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": {
                "scheduled_wage": scheduled_wage_count,
                "general": general_count,
                "part_time": part_time_count,
            },
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
scheduled_wage_common_service = ScheduledWageCommonService()
