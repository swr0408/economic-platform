"""
日本 有効求人倍率サービス
e-Stat + DBから有効求人倍率データを取得

指標:
- 有効求人倍率（季節調整値）

データソース:
- e-Stat: 一般職業紹介状況 長期時系列表（1963年〜）
- DB: economic_calendar_events（FMP蓄積データ、直近データ）
- 原データ: 厚生労働省 一般職業紹介状況

発表スケジュール:
- 毎月末（翌月分）08:30 JST

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import requests
import pandas as pd
import logging
from io import BytesIO
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.japan.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)
from services.japan.estat_file_source import download_estat_excel_matching_title

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "job_offers_ratio_cache.json"
TEMP_DIR = CACHE_DIR / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


class JobOffersRatioService:
    """日本 有効求人倍率サービス"""

    DATA_CACHE_KEY = "japan:employment:job_offers_ratio:data"
    NEXT_RELEASE_CACHE_KEY = "japan:employment:job_offers_ratio:next_release"
    ECONALPHA_ID = "jp_job_offers_ratio"

    # e-Stat Excel File Download URL
    ESTAT_EXCEL_URL = "https://www.e-stat.go.jp/stat-search/file-download"

    # e-Stat Data Catalog API で現行 statInfId を動的解決するためのパラメータ。
    # statInfId はリリース毎にローテートし旧 ID は 404 になる（固定 ID 直叩きだと
    # 長期時系列が取れず DB(FMP) の直近 1 年分のみに痩せる）ため動的解決する。
    # 政府統計コード 00450222 = 職業安定業務統計（一般職業紹介状況）
    ESTAT_STATS_CODE = "00450222"
    ESTAT_TABLE_FILTER = "有効求人倍率"
    # 同コード下に「パートを含む/除く/パート」の 3 ファイルが並ぶため、データシート
    # A1 タイトルで「パートタイムを含む一般」を選別する。
    ESTAT_TITLE_SUBSTRINGS = ["パートタイムを含む一般"]

    # API 失敗時の既知 statInfId（新しい順）
    FALLBACK_STAT_INF_IDS = [
        "000040457545",  # 長期時系列表 3-1 有効求人倍率（パートタイムを含む一般）- 現行(.xlsx)
        "000040391059",  # 旧・新フォーマット版（現在は 404）
        "000031942496",  # 長期時系列表 3 有効求人倍率（実数及び季節調整値）- 旧版(.xls)
    ]

    def __init__(self):
        self.temp_dir = TEMP_DIR
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def get_job_offers_ratio_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        有効求人倍率データを取得

        Returns:
            {
                "data": [...],
                "latest": {...},
                "next_release": {...},
                "cached": bool,
                "source": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    next_release = self._get_next_release()
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # 1. e-Statから長期時系列データを取得
        estat_data = self._load_from_estat()

        # 2. DBから直近データを取得（e-Statより新しい可能性）
        db_data = self._load_from_db()

        # データをマージ（e-Stat + DB）
        merged_data = self._merge_data(estat_data, db_data)

        if merged_data:
            next_release = self._get_next_release()
            latest = merged_data[-1] if merged_data else None

            cache_payload = {
                "data": merged_data,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            source = "e-Stat + DB" if estat_data and db_data else (
                "e-Stat" if estat_data else "DB"
            )
            return {
                "data": merged_data,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": source,
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """FMPから次回発表日時を取得"""
        try:
            # キャッシュを確認
            cached = redis_client.get(self.NEXT_RELEASE_CACHE_KEY)
            if cached:
                return cached

            # FMPから取得
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            if next_release:
                # 1時間キャッシュ
                redis_client.set(self.NEXT_RELEASE_CACHE_KEY, next_release, expire=3600)

            return next_release

        except Exception as e:
            logger.error(f"Error getting next release from FMP: {e}")
            return None

    def _load_from_estat(self) -> List[Dict[str, Any]]:
        """e-Statから長期時系列データを取得"""
        try:
            excel_content = self._download_excel_content()
            if not excel_content:
                return []

            return self._parse_excel_file(excel_content)

        except Exception as e:
            logger.error(f"Error loading from e-Stat: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _download_excel_content(self) -> Optional[bytes]:
        """e-Statから有効求人倍率Excelをダウンロード（現行statInfIdを動的解決）。

        Data Catalog API で現行 statInfId を解決し、A1 タイトルで
        「パートタイムを含む一般」のファイルを選別して内容(bytes)を返す。
        """
        try:
            content = download_estat_excel_matching_title(
                self.ESTAT_STATS_CODE,
                self.ESTAT_TABLE_FILTER,
                self.ESTAT_TITLE_SUBSTRINGS,
                self.FALLBACK_STAT_INF_IDS,
                timeout=60,
            )
            if content:
                logger.info(f"Downloaded job offers ratio Excel ({len(content)} bytes) from e-Stat")
            else:
                logger.warning("e-Stat download returned no matching file for job offers ratio")
            return content
        except Exception as e:
            logger.error(f"Error downloading job offers ratio Excel: {e}")
            return None

    def _parse_excel_file(self, excel_content: bytes) -> List[Dict[str, Any]]:
        """
        有効求人倍率Excelを解析

        Excel structure (statInfId: 000040457545, sheet 0 = パートタイムを含む一般):
        - Row 0: Title (有効求人倍率（パートタイムを含む一般）)
        - Row 3: Headers (西暦, 和暦, 1月, 2月, ... 12月, ... 季節調整値)
        - Row 5+: Data (1963年〜)
        - Column 0: 西暦年（1963年, 2024年など）
        - Column 2-13: 1月〜12月の実数値
        - Column 20-31: 1月〜12月の季節調整値
        """
        try:
            logger.info("Parsing job offers ratio Excel file from e-Stat content")

            df = pd.read_excel(BytesIO(excel_content), sheet_name=0, header=None)
            logger.info(f"Excel shape: {df.shape}")

            series_data = []

            # データは5行目から（0-indexed: row 5）
            for idx in range(5, len(df)):
                row = df.iloc[idx]

                try:
                    # 西暦年を取得（列0）- "1963年" or "2024年"
                    year_val = row[0]
                    if pd.isna(year_val):
                        continue

                    year_str = str(year_val).strip()
                    if not year_str or year_str == 'nan':
                        continue

                    # 注釈行をスキップ（例: "（注1）昭和48年以降...）"）
                    if year_str.startswith('（') or year_str.startswith('('):
                        continue

                    # "1963年" or "2024年" → 1963 or 2024
                    year_num_str = year_str.replace('年', '').strip()
                    if not year_num_str.isdigit():
                        continue

                    year = int(year_num_str)

                    # 各月の季節調整値を取得（列20-31が1月〜12月）
                    for month in range(1, 13):
                        col_idx = 19 + month  # 20=1月, 21=2月, ... 31=12月

                        if col_idx >= len(row):
                            continue

                        value = row[col_idx]
                        if pd.isna(value):
                            continue

                        try:
                            value_float = float(value)
                        except (ValueError, TypeError):
                            continue

                        date_str = f"{year}-{month:02d}-01"
                        series_data.append({
                            "date": date_str,
                            "value": round(value_float, 2)
                        })

                except Exception as e:
                    logger.debug(f"Error processing row {idx}: {e}")
                    continue

            # 日付でソート
            series_data.sort(key=lambda x: x["date"])

            logger.info(f"Parsed {len(series_data)} job offers ratio records from e-Stat")
            return series_data

        except Exception as e:
            logger.error(f"Error parsing job offers ratio Excel: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _load_from_db(self) -> List[Dict[str, Any]]:
        """DBから直近データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                query = text("""
                    SELECT datetime_utc, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'JP'
                      AND event ILIKE '%jobs/applications ratio%'
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query).fetchall()

                result = []
                seen_dates = set()

                for row in rows:
                    dt_utc, actual, estimate, previous = row
                    if dt_utc:
                        # 月初日に正規化（例: 2025-11-27 → 2025-11-01）
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

                logger.info(f"Loaded {len(result)} job offers ratio records from DB")
                return result

        except Exception as e:
            logger.error(f"Error loading from DB: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _merge_data(
        self,
        estat_data: List[Dict[str, Any]],
        db_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        e-StatとDBのデータをマージ

        DBデータがe-Statより新しい場合はDBを優先
        """
        if not estat_data and not db_data:
            return []

        if not estat_data:
            return db_data

        if not db_data:
            return estat_data

        # 日付をキーとした辞書を作成
        merged = {}

        # e-Statデータを追加
        for item in estat_data:
            merged[item["date"]] = item

        # DBデータを追加（上書き）
        for item in db_data:
            date = item["date"]
            if date in merged:
                # DBにforecast/previousがある場合は追加
                merged[date]["forecast"] = item.get("forecast")
                merged[date]["previous"] = item.get("previous")
                # 値が異なる場合はDBを優先（最新データの可能性）
                if item.get("value") is not None:
                    merged[date]["value"] = item["value"]
            else:
                merged[date] = item

        # 日付でソートしてリストに変換
        result = sorted(merged.values(), key=lambda x: x["date"])

        logger.info(f"Merged data: {len(result)} records (e-Stat: {len(estat_data)}, DB: {len(db_data)})")
        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

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
        redis_client.delete(self.NEXT_RELEASE_CACHE_KEY)
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "JP Job Offers Ratio (有効求人倍率)",
            "source": "e-Stat + Database (FMP)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
job_offers_ratio_service = JobOffersRatioService()
