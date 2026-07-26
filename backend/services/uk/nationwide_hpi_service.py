"""
ネーションワイド住宅価格指数サービス
Nationwide公式Excelファイルからデータを取得

指標:
- ネーションワイド住宅価格指数（前月比・前年比）

データソース:
- Excel: https://www.nationwide.co.uk/media/hpi/download/monthly
- DB: economic_calendar_events（FMP蓄積データ・フォールバック）

発表スケジュール:
- 月次（毎月27日～翌月4日頃）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import logging
import requests
import pandas as pd
from io import BytesIO
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "housing"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "nationwide_hpi_cache.json"

# Nationwide HPI Excel URL
NATIONWIDE_HPI_URL = "https://www.nationwide.co.uk/media/hpi/download/monthly"


class NationwideHPIService:
    """ネーションワイド住宅価格指数サービス"""

    DATA_CACHE_KEY = "uk:nationwide_hpi:data"
    ECONALPHA_ID = "nationwide_hpi"

    def __init__(self):
        pass

    def get_nationwide_hpi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ネーションワイド住宅価格指数データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "mom": cached_data.get("mom", []),
                        "yoy": cached_data.get("yoy", []),
                        "latest_mom": cached_data.get("latest_mom"),
                        "latest_yoy": cached_data.get("latest_yoy"),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # Excelから取得
        excel_data = self._fetch_from_excel()

        if excel_data:
            mom_data = excel_data.get("mom", [])
            yoy_data = excel_data.get("yoy", [])
        else:
            # Excelから取得できない場合はDBからフォールバック
            logger.warning("[Nationwide HPI] Excel fetch failed, falling back to DB")
            mom_data = self._load_mom_from_db()
            yoy_data = self._load_yoy_from_db()

        if mom_data or yoy_data:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
            latest_mom = mom_data[-1] if mom_data else None
            latest_yoy = yoy_data[-1] if yoy_data else None

            from services.usa.fmp_next_release_utils import guarded_last_updated_keys, _max_date_of
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated_keys(
                self.DATA_CACHE_KEY, ("mom", "yoy"),
                _max_date_of(mom_data, yoy_data), now_str
            )
            cache_payload = {
                "mom": mom_data,
                "yoy": yoy_data,
                "latest_mom": latest_mom,
                "latest_yoy": latest_yoy,
                "next_release": next_release,
                "last_updated": last_updated
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "mom": mom_data,
                "yoy": yoy_data,
                "latest_mom": latest_mom,
                "latest_yoy": latest_yoy,
                "next_release": next_release,
                "cached": False,
                "source": "excel" if excel_data else "database",
                "last_updated": last_updated
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "mom": file_cache.get("mom", []),
                "yoy": file_cache.get("yoy", []),
                "latest_mom": file_cache.get("latest_mom"),
                "latest_yoy": file_cache.get("latest_yoy"),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "mom": [],
            "yoy": [],
            "latest_mom": None,
            "latest_yoy": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_excel(self) -> Optional[Dict[str, Any]]:
        """
        Nationwide公式Excelファイルからデータを取得

        Returns:
            {"mom": [...], "yoy": [...]} or None
        """
        try:
            logger.info(f"[Nationwide HPI] Fetching data from {NATIONWIDE_HPI_URL}")

            # Excelファイルをダウンロード
            response = requests.get(NATIONWIDE_HPI_URL, timeout=30)
            response.raise_for_status()

            # Excelを解析
            excel_data = BytesIO(response.content)
            df = pd.read_excel(excel_data, sheet_name='Monthly')

            # データを処理
            return self._process_excel_data(df)

        except Exception as e:
            logger.error(f"[Nationwide HPI] Error fetching Excel: {e}")
            return None

    def _process_excel_data(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        ExcelのDataFrameからMoM/YoYデータを抽出

        Column indices:
        - 0: Date (Unnamed: 0)
        - 4: Monthly % Change (SA)
        - 5: Year % Change
        """
        try:
            yoy_data = []
            mom_data = []

            for _, row in df.iterrows():
                date_val = row.iloc[0]
                mom_val = row.iloc[4]
                yoy_val = row.iloc[5]

                # 日付をYYYY-MM-01形式に変換
                if pd.notna(date_val):
                    try:
                        date_str = pd.to_datetime(date_val).strftime('%Y-%m-01')
                    except Exception:
                        continue

                    # YoYデータ（小数 → %に変換: 0.024 → 2.4）
                    if pd.notna(yoy_val):
                        yoy_data.append({
                            "date": date_str,
                            "value": round(float(yoy_val) * 100, 2),
                            "forecast": None,
                            "previous": None,
                        })

                    # MoMデータ（小数 → %に変換: 0.0025 → 0.25）
                    if pd.notna(mom_val):
                        mom_data.append({
                            "date": date_str,
                            "value": round(float(mom_val) * 100, 2),
                            "forecast": None,
                            "previous": None,
                        })

            # 日付順にソート（昇順）
            yoy_data = sorted(yoy_data, key=lambda x: x["date"])
            mom_data = sorted(mom_data, key=lambda x: x["date"])

            logger.info(f"[Nationwide HPI] Processed Excel: {len(yoy_data)} YoY, {len(mom_data)} MoM records")

            return {
                "yoy": yoy_data,
                "mom": mom_data,
            }

        except Exception as e:
            logger.error(f"[Nationwide HPI] Error processing Excel data: {e}")
            return None

    def _load_mom_from_db(self) -> List[Dict[str, Any]]:
        """DBから前月比データを取得（フォールバック用）"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                query = text("""
                    SELECT datetime_utc, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'UK'
                      AND event ILIKE '%Nationwide Housing Prices MoM%'
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query).fetchall()

                result = []
                seen_dates = set()

                for row in rows:
                    dt_utc, actual, estimate, previous = row
                    if dt_utc:
                        date_str = dt_utc.strftime("%Y-%m-01")
                        if date_str in seen_dates:
                            continue
                        seen_dates.add(date_str)

                        result.append({
                            "date": date_str,
                            "value": float(actual) if actual else None,
                            "forecast": float(estimate) if estimate else None,
                            "previous": float(previous) if previous else None,
                        })

                logger.info(f"[Nationwide HPI] Loaded {len(result)} MoM records from DB")
                return result

        except Exception as e:
            logger.error(f"[Nationwide HPI] Error loading MoM from DB: {e}")
            return []

    def _load_yoy_from_db(self) -> List[Dict[str, Any]]:
        """DBから前年比データを取得（フォールバック用）"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                query = text("""
                    SELECT datetime_utc, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'UK'
                      AND event ILIKE '%Nationwide Housing Prices YoY%'
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query).fetchall()

                result = []
                seen_dates = set()

                for row in rows:
                    dt_utc, actual, estimate, previous = row
                    if dt_utc:
                        date_str = dt_utc.strftime("%Y-%m-01")
                        if date_str in seen_dates:
                            continue
                        seen_dates.add(date_str)

                        result.append({
                            "date": date_str,
                            "value": float(actual) if actual else None,
                            "forecast": float(estimate) if estimate else None,
                            "previous": float(previous) if previous else None,
                        })

                logger.info(f"[Nationwide HPI] Loaded {len(result)} YoY records from DB")
                return result

        except Exception as e:
            logger.error(f"[Nationwide HPI] Error loading YoY from DB: {e}")
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP 3分方式）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[Nationwide HPI] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[Nationwide HPI] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Nationwide House Price Index",
            "source": "Excel (Nationwide)",
            "excel_url": NATIONWIDE_HPI_URL,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "mom_count": len(cached_data.get("mom", [])) if cached_data else 0,
            "yoy_count": len(cached_data.get("yoy", [])) if cached_data else 0,
            "latest_mom": cached_data.get("latest_mom") if cached_data else None,
            "latest_yoy": cached_data.get("latest_yoy") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
nationwide_hpi_service = NationwideHPIService()
