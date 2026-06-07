"""
UK住宅価格指数（ONS UK House Price Index）サービス
Land Registryから住宅価格指数データを取得

指標:
- 住宅価格指数（前年比）- 全体・戸建・セミデタッチド・テラスハウス・フラット

データソース:
- Land Registry UK House Price Index
- https://landregistry.data.gov.uk/app/ukhpi/download/new.csv

発表スケジュール:
- 月次
- FMPカレンダーから取得

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import csv
import logging
import requests
from datetime import datetime, date
from io import StringIO
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "housing"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "uk_house_price_cache.json"


class UKHousePriceService:
    """UK住宅価格指数サービス"""

    DATA_CACHE_KEY = "uk:house_price:data"
    ECONALPHA_ID = "uk_house_price"

    # Land Registry House Price Index URL
    BASE_URL = "https://landregistry.data.gov.uk/app/ukhpi/download/new.csv"

    # FMPカレンダー検索パターン
    FMP_EVENT_PATTERNS = ["House Price Index MoM", "House Price Index YoY"]

    def __init__(self):
        pass

    def get_house_price_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """住宅価格指数データを取得"""
        # 次回発表日を取得
        next_release = self._get_next_release()

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "series": cached_data.get("series", {}),
                        "series_mom": cached_data.get("series_mom", {}),
                        "latest": cached_data.get("latest"),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # Land Registryから取得
        api_result = self._fetch_from_land_registry()

        if api_result:
            latest = self._get_latest_values(api_result.get("series", {}))

            cache_payload = {
                "series": api_result.get("series", {}),
                "series_mom": api_result.get("series_mom", {}),
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "series": api_result.get("series", {}),
                "series_mom": api_result.get("series_mom", {}),
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "land_registry",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "series": file_cache.get("series", {}),
                "series_mom": file_cache.get("series_mom", {}),
                "latest": file_cache.get("latest"),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "series": {},
            "series_mom": {},
            "latest": None,
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得 - FMPカレンダーから検索"""
        try:
            from services.uk.fmp_next_release_utils import get_next_release_by_pattern

            # 複数のパターンで検索し、最も近いものを返す
            candidates = []
            for pattern in self.FMP_EVENT_PATTERNS:
                result = get_next_release_by_pattern(pattern, country="GB")
                if result:
                    candidates.append(result)

            if candidates:
                # 日付が最も近いものを選択
                candidates.sort(key=lambda x: x.get("date", ""))
                return candidates[0]

            return None
        except Exception as e:
            logger.error(f"[UK House Price] Error getting next release: {e}")
            return None

    def _fetch_from_land_registry(self) -> Optional[Dict[str, Any]]:
        """Land RegistryからCSVデータを取得"""
        try:
            today = date.today()
            to_date = date(today.year, today.month, 1).strftime('%Y-%m-%d')

            params = {
                'from': '2000-01-01',
                'to': to_date,
                'location': 'http://landregistry.data.gov.uk/id/region/united-kingdom',
            }

            logger.info(f"[UK House Price] Fetching from Land Registry (from 2000-01-01 to {to_date})")

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(self.BASE_URL, params=params, headers=headers, timeout=120)
            response.raise_for_status()

            logger.info(f"[UK House Price] Downloaded {len(response.text)} bytes")

            # CSVをパース
            return self._parse_csv(response.text)

        except Exception as e:
            logger.error(f"[UK House Price] Error fetching from Land Registry: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_csv(self, csv_text: str) -> Optional[Dict[str, Any]]:
        """CSVデータをパースして構造化"""
        try:
            csv_reader = csv.DictReader(StringIO(csv_text))

            # 物件タイプ別データ（YoY）
            series = {
                "all": {"data": [], "metadata": {"name": "全物件", "name_en": "All property types"}},
                "detached": {"data": [], "metadata": {"name": "戸建", "name_en": "Detached houses"}},
                "semi_detached": {"data": [], "metadata": {"name": "セミデタッチド", "name_en": "Semi-detached houses"}},
                "terraced": {"data": [], "metadata": {"name": "テラスハウス", "name_en": "Terraced houses"}},
                "flat": {"data": [], "metadata": {"name": "フラット", "name_en": "Flats and maisonettes"}},
            }

            # 物件タイプ別データ（MoM）
            series_mom = {
                "all": {"data": [], "metadata": {"name": "全物件", "name_en": "All property types"}},
                "detached": {"data": [], "metadata": {"name": "戸建", "name_en": "Detached houses"}},
                "semi_detached": {"data": [], "metadata": {"name": "セミデタッチド", "name_en": "Semi-detached houses"}},
                "terraced": {"data": [], "metadata": {"name": "テラスハウス", "name_en": "Terraced houses"}},
                "flat": {"data": [], "metadata": {"name": "フラット", "name_en": "Flats and maisonettes"}},
            }

            for row in csv_reader:
                # 日付を取得
                date_str = row.get('Pivotable date', '').strip()
                if not date_str:
                    date_str = row.get('Period', '').strip()

                if not date_str:
                    continue

                try:
                    # 各物件タイプの前年比（YoY）を抽出
                    all_str = row.get('Percentage change (yearly) All property types', '').strip()
                    detached_str = row.get('Percentage change (yearly) Detached houses', '').strip()
                    semi_str = row.get('Percentage change (yearly) Semi-detached houses', '').strip()
                    terraced_str = row.get('Percentage change (yearly) Terraced houses', '').strip()
                    flat_str = row.get('Percentage change (yearly) Flats and maisonettes', '').strip()

                    # 各物件タイプの前月比（MoM）を抽出
                    all_mom_str = row.get('Percentage change (monthly) All property types', '').strip()
                    detached_mom_str = row.get('Percentage change (monthly) Detached houses', '').strip()
                    semi_mom_str = row.get('Percentage change (monthly) Semi-detached houses', '').strip()
                    terraced_mom_str = row.get('Percentage change (monthly) Terraced houses', '').strip()
                    flat_mom_str = row.get('Percentage change (monthly) Flats and maisonettes', '').strip()

                    # YoYデータ追加
                    if all_str:
                        series['all']['data'].append({
                            "date": date_str,
                            "value": round(float(all_str), 2)
                        })

                    if detached_str:
                        series['detached']['data'].append({
                            "date": date_str,
                            "value": round(float(detached_str), 2)
                        })

                    if semi_str:
                        series['semi_detached']['data'].append({
                            "date": date_str,
                            "value": round(float(semi_str), 2)
                        })

                    if terraced_str:
                        series['terraced']['data'].append({
                            "date": date_str,
                            "value": round(float(terraced_str), 2)
                        })

                    if flat_str:
                        series['flat']['data'].append({
                            "date": date_str,
                            "value": round(float(flat_str), 2)
                        })

                    # MoMデータ追加
                    if all_mom_str:
                        series_mom['all']['data'].append({
                            "date": date_str,
                            "value": round(float(all_mom_str), 2)
                        })

                    if detached_mom_str:
                        series_mom['detached']['data'].append({
                            "date": date_str,
                            "value": round(float(detached_mom_str), 2)
                        })

                    if semi_mom_str:
                        series_mom['semi_detached']['data'].append({
                            "date": date_str,
                            "value": round(float(semi_mom_str), 2)
                        })

                    if terraced_mom_str:
                        series_mom['terraced']['data'].append({
                            "date": date_str,
                            "value": round(float(terraced_mom_str), 2)
                        })

                    if flat_mom_str:
                        series_mom['flat']['data'].append({
                            "date": date_str,
                            "value": round(float(flat_mom_str), 2)
                        })

                except (ValueError, TypeError) as e:
                    continue

            # 日付でソート
            for key in series:
                series[key]['data'] = sorted(series[key]['data'], key=lambda x: x['date'])
            for key in series_mom:
                series_mom[key]['data'] = sorted(series_mom[key]['data'], key=lambda x: x['date'])

            # ログ出力
            for key, s in series.items():
                if s['data']:
                    logger.info(f"[UK House Price] Extracted {len(s['data'])} {key} YoY data points")
            for key, s in series_mom.items():
                if s['data']:
                    logger.info(f"[UK House Price] Extracted {len(s['data'])} {key} MoM data points")

            # 全シリーズが空なら失敗扱い（空キャッシュ保存を防ぐ）
            if not any(s['data'] for s in series.values()) and not any(s['data'] for s in series_mom.values()):
                logger.error("[UK House Price] CSV parsed but all series are empty — treating as fetch failure")
                return None

            return {"series": series, "series_mom": series_mom}

        except Exception as e:
            logger.error(f"[UK House Price] Error parsing CSV: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _get_latest_values(self, series: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """各系列の最新値を取得"""
        try:
            latest = {}
            latest_date = None

            for key, series_data in series.items():
                if series_data and series_data.get("data"):
                    data = series_data["data"]
                    if data:
                        last_point = data[-1]
                        latest[key] = last_point.get("value")
                        if latest_date is None or last_point.get("date", "") > latest_date:
                            latest_date = last_point.get("date")

            if latest_date:
                latest["date"] = latest_date

            return latest if latest else None

        except Exception as e:
            logger.error(f"[UK House Price] Error getting latest values: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        ロジック:
        - 7日以上経過していれば更新
        - FMPの発表日付近は頻繁にチェック
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            hours_since_update = (now - last_updated).total_seconds() / 3600

            # 7日以上経過していれば更新
            if hours_since_update >= 24 * 7:
                return True

            # FMPパターンベースの更新判定
            try:
                from services.uk.fmp_next_release_utils import should_refresh_by_pattern
                for pattern in self.FMP_EVENT_PATTERNS:
                    if should_refresh_by_pattern(pattern, last_updated_str, country="GB"):
                        logger.info(f"[UK House Price] FMP pattern '{pattern}' indicates refresh needed")
                        return True
            except Exception as e:
                logger.error(f"[UK House Price] Error checking FMP refresh: {e}")

            return False

        except Exception as e:
            logger.error(f"[UK House Price] Error in should_refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[UK House Price] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[UK House Price] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        series_counts = {}
        if cached_data and cached_data.get("series"):
            for key, series in cached_data["series"].items():
                if series and series.get("data"):
                    series_counts[key] = len(series["data"])

        return {
            "indicator": "UK House Price Index",
            "source": "Land Registry UK",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "series_counts": series_counts,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
uk_house_price_service = UKHousePriceService()
