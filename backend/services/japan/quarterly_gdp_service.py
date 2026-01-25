"""
四半期GDP成長率サービス
内閣府CSVから日本の四半期GDP成長率データを取得

指標:
- GDP成長率（前期比年率）: nritu-jk{YYMM}.csv
- GDP成長率（前年同期比）: ritu-jg{YYMM}.csv

データソース:
- 内閣府 国民経済計算 GDP速報CSV

発表スケジュール:
- 四半期毎（速報・改定値）
- FMPカレンダーで更新判定

キャッシュ方式: FMP発表日時ベース判定方式
"""
import csv
import io
import json
import logging
import os
import re
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from zoneinfo import ZoneInfo

from core.redis_client import redis_client
from services.usa.fred_utils import load_file_cache, save_file_cache

logger = logging.getLogger(__name__)

# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# キャッシュ設定
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
QOQ_CACHE_FILE = CACHE_DIR / "quarterly_gdp_qoq.json"  # 前期比（非年率）
QOQ_ANNUALIZED_CACHE_FILE = CACHE_DIR / "quarterly_gdp_qoq_annualized.json"  # 前期比年率
YOY_CACHE_FILE = CACHE_DIR / "quarterly_gdp_yoy.json"  # 前年比

# Redisキー
QOQ_REDIS_KEY = "japan:gdp:qoq"  # 前期比（非年率）
QOQ_ANNUALIZED_REDIS_KEY = "japan:gdp:qoq_annualized"  # 前期比年率
YOY_REDIS_KEY = "japan:gdp:yoy"  # 前年比


class QuarterlyGDPService:
    """四半期GDP成長率サービス（内閣府CSV直接取得・自動URL検出）"""

    # CSV URL パターン
    # 前年比: ritu-jg{YYQR}.csv (例: ritu-jg2532.csv = 2025年Q3 2次改定)
    # 年率換算（前期比年率）: nritu-jk{YYQR}.csv
    # URL例: https://www.esri.cao.go.jp/jp/sna/data/data_list/sokuhou/files/2025/qe253_2/tables/ritu-jg2532.csv

    BASE_URL = "https://www.esri.cao.go.jp/jp/sna/data/data_list/sokuhou/files"

    # ファイル名パターン
    YOY_FILENAME_PATTERN = "ritu-jg{yy}{q}{rev}.csv"  # 前年比
    QOQ_FILENAME_PATTERN = "ritu-jk{yy}{q}{rev}.csv"  # 前期比（非年率）
    QOQ_ANNUALIZED_FILENAME_PATTERN = "nritu-jk{yy}{q}{rev}.csv"  # 年率換算

    # FMPイベント名（更新判定用）
    FMP_EVENT_PATTERN = "GDP Growth Rate QoQ"

    # URL検出キャッシュ（クラス変数）
    _detected_url_info: Optional[Dict[str, Any]] = None
    _detected_url_timestamp: Optional[datetime] = None
    _URL_CACHE_HOURS = 24  # URL検出結果のキャッシュ時間

    def __init__(self):
        """Initialize Quarterly GDP service"""
        pass

    def _detect_latest_csv_url(self) -> Optional[Dict[str, Any]]:
        """
        最新のCSV URLを自動検出

        現在日時から逆算して、最新のGDP速報CSVを探す。
        四半期ごとに1次速報(1)、2次速報(2)が発表される。

        Returns:
            {"year": int, "quarter": int, "revision": int} or None
        """
        # キャッシュチェック
        if (self._detected_url_info and self._detected_url_timestamp and
            (datetime.now(JST) - self._detected_url_timestamp).total_seconds() < self._URL_CACHE_HOURS * 3600):
            return self._detected_url_info

        now = datetime.now(JST)
        current_year = now.year
        current_month = now.month

        # 現在の四半期を計算（1-3月=Q4前年, 4-6月=Q1, 7-9月=Q2, 10-12月=Q3）
        # GDP速報は四半期終了後約1.5ヶ月後に発表
        # 例: Q3(7-9月)のデータは11月に発表

        # 検索順序: 最新から古い順に試す
        # 最大で過去2年分を検索
        candidates = []

        for year in range(current_year, current_year - 2, -1):
            for quarter in [4, 3, 2, 1]:
                # 各四半期で revision 2 → 1 の順で試す
                for revision in [2, 1]:
                    candidates.append((year, quarter, revision))

        # 候補を試す
        for year, quarter, revision in candidates:
            yy = year % 100
            # YoY CSVで存在確認
            filename = self.YOY_FILENAME_PATTERN.format(yy=yy, q=quarter, rev=revision)
            url = f"{self.BASE_URL}/{year}/qe{yy}{quarter}_{revision}/tables/{filename}"

            try:
                response = requests.head(url, timeout=5)
                if response.status_code == 200:
                    logger.info(f"Detected latest GDP CSV: year={year}, quarter={quarter}, revision={revision}")
                    QuarterlyGDPService._detected_url_info = {
                        "year": year,
                        "quarter": quarter,
                        "revision": revision
                    }
                    QuarterlyGDPService._detected_url_timestamp = datetime.now(JST)
                    return QuarterlyGDPService._detected_url_info
            except requests.RequestException:
                continue

        logger.warning("Could not detect latest GDP CSV URL")
        return None

    def _get_csv_url(self, data_type: str = "yoy") -> Optional[str]:
        """
        CSVのURLを生成（自動検出）

        Args:
            data_type: "yoy" (前年比), "qoq" (前期比), or "qoq_annualized" (年率換算)

        Returns:
            CSV URL or None if detection fails
        """
        url_info = self._detect_latest_csv_url()
        if not url_info:
            return None

        year = url_info["year"]
        yy = year % 100
        q = url_info["quarter"]
        rev = url_info["revision"]

        if data_type == "yoy":
            filename = self.YOY_FILENAME_PATTERN.format(yy=yy, q=q, rev=rev)
        elif data_type == "qoq":
            filename = self.QOQ_FILENAME_PATTERN.format(yy=yy, q=q, rev=rev)
        else:
            filename = self.QOQ_ANNUALIZED_FILENAME_PATTERN.format(yy=yy, q=q, rev=rev)

        url = f"{self.BASE_URL}/{year}/qe{yy}{q}_{rev}/tables/{filename}"
        return url

    def _fetch_csv_data(self, data_type: str = "yoy") -> List[Dict[str, Any]]:
        """
        内閣府CSVからGDPデータを取得

        Args:
            data_type: "yoy" (前年比) or "qoq_annualized" (年率換算)

        Returns:
            List of data points
        """
        try:
            url = self._get_csv_url(data_type)
            if not url:
                logger.error("Could not determine GDP CSV URL")
                return []
            logger.info(f"Fetching GDP CSV from: {url}")

            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Shift-JISでデコード
            content = response.content.decode('shift_jis', errors='replace')

            # CSVをパース
            reader = csv.reader(io.StringIO(content))
            rows = list(reader)

            if len(rows) < 5:
                logger.error("CSV has insufficient rows")
                return []

            # データ行を探す
            # CSVフォーマット:
            # - 最初の年は "1994/ 1- 3." のようなフォーマット
            # - 続く四半期は "4- 6.", "7- 9.", "10-12." のようなフォーマット
            data = []
            current_year = None

            for row in rows:
                if not row or len(row) < 2:
                    continue

                date_cell = row[0].strip()

                # フルフォーマット: "1994/ 1- 3." or "2024/10-12."
                full_match = re.match(r'^(\d{4})/\s*(\d{1,2})-\s*(\d{1,2})\.?$', date_cell)
                if full_match:
                    current_year = int(full_match.group(1))
                    start_month = int(full_match.group(2))
                else:
                    # 四半期のみ: "4- 6." or "10-12."
                    quarter_match = re.match(r'^(\d{1,2})-\s*(\d{1,2})\.?$', date_cell)
                    if quarter_match and current_year:
                        start_month = int(quarter_match.group(1))
                    else:
                        continue

                year = current_year
                if year is None:
                    continue

                # 四半期を判定
                quarter_map = {1: "Q1", 4: "Q2", 7: "Q3", 10: "Q4"}
                quarter = quarter_map.get(start_month)
                if not quarter:
                    continue

                # GDP値（2列目）
                gdp_value_str = row[1].strip() if len(row) > 1 else ""
                if gdp_value_str == "***" or not gdp_value_str:
                    continue

                try:
                    gdp_value = float(gdp_value_str)
                except ValueError:
                    continue

                date_str = f"{year}-{quarter}"

                data.append({
                    "date": date_str,
                    "value": round(gdp_value, 2)
                })

            # 日付でソート
            data.sort(key=lambda x: (int(x["date"][:4]), x["date"][5:]))

            # 2000年以降のデータのみ
            data = [p for p in data if p["date"] >= "2000-Q1"]

            logger.info(f"Fetched {len(data)} GDP {data_type} data points from CSV")
            return data

        except requests.RequestException as e:
            logger.error(f"Error fetching GDP CSV: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing GDP CSV: {e}", exc_info=True)
            return []

    def _get_next_release_from_fmp(self) -> Optional[str]:
        """Get next GDP release date from FMP calendar"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                query = text("""
                    SELECT datetime_utc
                    FROM economic_calendar_events
                    WHERE country = 'JP'
                      AND event ILIKE :pattern
                      AND datetime_utc > NOW()
                    ORDER BY datetime_utc ASC
                    LIMIT 1
                """)
                result = session.execute(query, {"pattern": f"%{self.FMP_EVENT_PATTERN}%"}).fetchone()

                if result:
                    return result[0].isoformat()

            return None

        except Exception as e:
            logger.error(f"Error getting next release from FMP: {e}")
            return None

    def _should_refresh_by_fmp(self, last_updated_str: str) -> bool:
        """
        Check if cache should be refreshed based on FMP schedule

        Args:
            last_updated_str: Last update timestamp

        Returns:
            True if refresh needed
        """
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            with SessionLocal() as session:
                # Check if there's a release between last_updated and now
                query = text("""
                    SELECT datetime_utc
                    FROM economic_calendar_events
                    WHERE country = 'JP'
                      AND event ILIKE :pattern
                      AND datetime_utc > :last_updated
                      AND datetime_utc <= :now
                    ORDER BY datetime_utc DESC
                    LIMIT 1
                """)
                result = session.execute(query, {
                    "pattern": f"%{self.FMP_EVENT_PATTERN}%",
                    "last_updated": last_updated,
                    "now": now
                }).fetchone()

                if result:
                    logger.info(f"GDP release detected at {result[0]}, refresh needed")
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking FMP schedule: {e}")
            # Default to refresh every 7 days if FMP check fails
            try:
                last_updated = datetime.fromisoformat(last_updated_str)
                days_since = (datetime.now(JST) - last_updated).days
                return days_since >= 7
            except Exception:
                return True

    def get_quarterly_gdp_qoq(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get Quarterly GDP Growth Rate (QoQ) data - 前期比（非年率）

        前期比（非年率）データを内閣府CSVから取得

        Args:
            force_refresh: Force refresh from source

        Returns:
            GDP QoQ data dictionary
        """
        # Check cache
        if not force_refresh:
            cached_data = redis_client.get(QOQ_REDIS_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh_by_fmp(last_updated_str):
                    logger.info("Returning cached GDP QoQ from Redis")
                    return {**cached_data, "cached": True}

            file_cache = load_file_cache(QOQ_CACHE_FILE)
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh_by_fmp(last_updated_str):
                    logger.info("Returning cached GDP QoQ from file")
                    redis_client.set(QOQ_REDIS_KEY, file_cache, expire=0)
                    return {**file_cache, "cached": True}

        # Fetch from Cabinet Office CSV (前期比・非年率)
        qoq_data = self._fetch_csv_data("qoq")

        if qoq_data:
            latest = qoq_data[-1] if qoq_data else None
            next_release = self._get_next_release_from_fmp()

            cache_payload = {
                "data": qoq_data,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
                "source": "Cabinet Office CSV"
            }

            redis_client.set(QOQ_REDIS_KEY, cache_payload, expire=0)
            save_file_cache(QOQ_CACHE_FILE, cache_payload)

            return {**cache_payload, "cached": False}

        # Fallback to file cache
        file_cache = load_file_cache(QOQ_CACHE_FILE)
        if file_cache:
            return {**file_cache, "cached": True, "source": "file (fallback)"}

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": datetime.now(JST).isoformat(),
            "error": "No data available"
        }

    def get_quarterly_gdp_qoq_annualized(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get Quarterly GDP Growth Rate (QoQ Annualized) data - 前期比年率

        前期比年率データを内閣府CSVから取得

        Args:
            force_refresh: Force refresh from source

        Returns:
            GDP QoQ Annualized data dictionary
        """
        # Check cache
        if not force_refresh:
            cached_data = redis_client.get(QOQ_ANNUALIZED_REDIS_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh_by_fmp(last_updated_str):
                    logger.info("Returning cached GDP QoQ Annualized from Redis")
                    return {**cached_data, "cached": True}

            file_cache = load_file_cache(QOQ_ANNUALIZED_CACHE_FILE)
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh_by_fmp(last_updated_str):
                    logger.info("Returning cached GDP QoQ Annualized from file")
                    redis_client.set(QOQ_ANNUALIZED_REDIS_KEY, file_cache, expire=0)
                    return {**file_cache, "cached": True}

        # Fetch from Cabinet Office CSV (年率換算)
        qoq_data = self._fetch_csv_data("qoq_annualized")

        if qoq_data:
            latest = qoq_data[-1] if qoq_data else None
            next_release = self._get_next_release_from_fmp()

            cache_payload = {
                "data": qoq_data,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
                "source": "Cabinet Office CSV"
            }

            redis_client.set(QOQ_ANNUALIZED_REDIS_KEY, cache_payload, expire=0)
            save_file_cache(QOQ_ANNUALIZED_CACHE_FILE, cache_payload)

            return {**cache_payload, "cached": False}

        # Fallback to file cache
        file_cache = load_file_cache(QOQ_ANNUALIZED_CACHE_FILE)
        if file_cache:
            return {**file_cache, "cached": True, "source": "file (fallback)"}

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": datetime.now(JST).isoformat(),
            "error": "No data available"
        }

    def get_quarterly_gdp_yoy(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get Quarterly GDP Growth Rate (YoY) data

        前年同期比データを内閣府CSVから取得

        Args:
            force_refresh: Force refresh from source

        Returns:
            GDP YoY data dictionary
        """
        # Check cache
        if not force_refresh:
            cached_data = redis_client.get(YOY_REDIS_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh_by_fmp(last_updated_str):
                    logger.info("Returning cached GDP YoY from Redis")
                    return {**cached_data, "cached": True}

            file_cache = load_file_cache(YOY_CACHE_FILE)
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh_by_fmp(last_updated_str):
                    logger.info("Returning cached GDP YoY from file")
                    redis_client.set(YOY_REDIS_KEY, file_cache, expire=0)
                    return {**file_cache, "cached": True}

        # Fetch from Cabinet Office CSV (前年比)
        yoy_data = self._fetch_csv_data("yoy")

        if yoy_data:
            latest = yoy_data[-1] if yoy_data else None
            next_release = self._get_next_release_from_fmp()

            cache_payload = {
                "data": yoy_data,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
                "source": "Cabinet Office CSV"
            }

            redis_client.set(YOY_REDIS_KEY, cache_payload, expire=0)
            save_file_cache(YOY_CACHE_FILE, cache_payload)

            return {**cache_payload, "cached": False}

        # Fallback to file cache
        file_cache = load_file_cache(YOY_CACHE_FILE)
        if file_cache:
            return {**file_cache, "cached": True, "source": "file (fallback)"}

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": datetime.now(JST).isoformat(),
            "error": "No data available"
        }

    def invalidate_cache(self) -> bool:
        """Invalidate all GDP caches"""
        qoq_deleted = redis_client.delete(QOQ_REDIS_KEY)
        qoq_ann_deleted = redis_client.delete(QOQ_ANNUALIZED_REDIS_KEY)
        yoy_deleted = redis_client.delete(YOY_REDIS_KEY)
        return qoq_deleted or qoq_ann_deleted or yoy_deleted

    def get_cache_status(self) -> Dict[str, Any]:
        """Get cache status"""
        qoq_exists = redis_client.exists(QOQ_REDIS_KEY)
        qoq_ann_exists = redis_client.exists(QOQ_ANNUALIZED_REDIS_KEY)
        yoy_exists = redis_client.exists(YOY_REDIS_KEY)
        qoq_data = redis_client.get(QOQ_REDIS_KEY) if qoq_exists else None
        qoq_ann_data = redis_client.get(QOQ_ANNUALIZED_REDIS_KEY) if qoq_ann_exists else None
        yoy_data = redis_client.get(YOY_REDIS_KEY) if yoy_exists else None

        # 検出されたURL情報
        url_info = self._detect_latest_csv_url()

        return {
            "indicator": "Japan Quarterly GDP",
            "source": "Cabinet Office CSV (Auto-detected)",
            "detected_version": url_info,
            "qoq_csv_url": self._get_csv_url("qoq"),
            "qoq_annualized_csv_url": self._get_csv_url("qoq_annualized"),
            "yoy_csv_url": self._get_csv_url("yoy"),
            "qoq": {
                "label": "前期比（非年率）",
                "cache_key": QOQ_REDIS_KEY,
                "exists": qoq_exists,
                "last_updated": qoq_data.get("last_updated") if qoq_data else None,
                "data_count": len(qoq_data.get("data", [])) if qoq_data else 0,
                "latest": qoq_data.get("latest") if qoq_data else None,
                "file_cache_exists": QOQ_CACHE_FILE.exists()
            },
            "qoq_annualized": {
                "label": "前期比年率",
                "cache_key": QOQ_ANNUALIZED_REDIS_KEY,
                "exists": qoq_ann_exists,
                "last_updated": qoq_ann_data.get("last_updated") if qoq_ann_data else None,
                "data_count": len(qoq_ann_data.get("data", [])) if qoq_ann_data else 0,
                "latest": qoq_ann_data.get("latest") if qoq_ann_data else None,
                "file_cache_exists": QOQ_ANNUALIZED_CACHE_FILE.exists()
            },
            "yoy": {
                "label": "前年比",
                "cache_key": YOY_REDIS_KEY,
                "exists": yoy_exists,
                "last_updated": yoy_data.get("last_updated") if yoy_data else None,
                "data_count": len(yoy_data.get("data", [])) if yoy_data else 0,
                "latest": yoy_data.get("latest") if yoy_data else None,
                "file_cache_exists": YOY_CACHE_FILE.exists()
            },
            "next_release": self._get_next_release_from_fmp()
        }


# シングルトンインスタンス
_service_instance: Optional[QuarterlyGDPService] = None


def get_quarterly_gdp_service() -> QuarterlyGDPService:
    """Get or create QuarterlyGDPService singleton instance"""
    global _service_instance
    if _service_instance is None:
        _service_instance = QuarterlyGDPService()
    return _service_instance


# グローバルサービスインスタンス
quarterly_gdp_service = get_quarterly_gdp_service()
