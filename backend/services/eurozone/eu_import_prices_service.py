"""
EU輸入物価サービス
Eurostat APIから輸入物価指数データを取得し、YoY/MoMを計算

指標:
- Import Prices YoY (輸入物価 前年比)
- Import Prices MoM (輸入物価 前月比)

データソース:
- Eurostat API
  - ei_isin_m: Euro-Indicators - Short-term business statistics - Industry
- Series Parameters:
  - freq: M (Monthly)
  - unit: I2021 (Index 2021=100)
  - s_adj: NSA (Not seasonally adjusted)
  - nace_r2: B-D (Industry)
  - indic: IS-IMPR (Import prices)
  - geo: EA20 (Euro area - 20 countries)

発表スケジュール:
- Eurostatリリースカレンダーから取得
- https://ec.europa.eu/eurostat/o/calendars/eventsIcal
- "Industrial import prices" イベントを検索

キャッシュ方式: Eurostatリリースカレンダーベース更新
"""
import json
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "eu_import_prices_cache.json"


class EUImportPricesService:
    """EU輸入物価サービス（Eurostat API）"""

    # Eurostat API base URL
    EUROSTAT_API_BASE = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data"

    # Dataset code - ei_isin_m has longer history (from 1980)
    DATASET = "ei_isin_m"

    DATA_CACHE_KEY = "eurozone:eu_import_prices:data"
    CALENDAR_CACHE_KEY = "eurozone:eu_import_prices:calendar"

    # Eurostat リリースカレンダーURL
    EUROSTAT_CALENDAR_URL = "https://ec.europa.eu/eurostat/o/calendars/eventsIcal"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        EU輸入物価データを取得

        Returns:
            {
                "yoy": [...],          # 前年比データ
                "mom": [...],          # 前月比データ
                "latest_yoy": {...},
                "latest_mom": {...},
                "metadata": {...},
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
                if last_updated_str and not self._should_refresh(last_updated_str, cached_data):
                    return {
                        "yoy": cached_data.get("yoy", []),
                        "mom": cached_data.get("mom", []),
                        "latest_yoy": cached_data.get("latest_yoy"),
                        "latest_mom": cached_data.get("latest_mom"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str, file_cache):
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    return {
                        "yoy": file_cache.get("yoy", []),
                        "mom": file_cache.get("mom", []),
                        "latest_yoy": file_cache.get("latest_yoy"),
                        "latest_mom": file_cache.get("latest_mom"),
                        "metadata": file_cache.get("metadata", {}),
                        "next_release": file_cache.get("next_release"),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str,
                    }

        # Eurostat APIからインデックスデータを取得し、YoY/MoMを計算
        index_data = self._fetch_eurostat_index_data() or []

        if index_data:
            # YoY/MoMを計算
            yoy_data = self._calculate_yoy(index_data)
            mom_data = self._calculate_mom(index_data)
            # データ更新時にカレンダーキャッシュをクリアして再取得
            self._invalidate_calendar_cache()
            next_release = self._calculate_next_release()

            latest_yoy = yoy_data[-1] if yoy_data else None
            latest_mom = mom_data[-1] if mom_data else None

            from services.usa.fmp_next_release_utils import guarded_last_updated_keys, _max_date_of
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated_keys(
                self.DATA_CACHE_KEY, ("yoy", "mom"),
                _max_date_of(yoy_data, mom_data), now_str
            )
            cache_payload = {
                "yoy": yoy_data,
                "mom": mom_data,
                "latest_yoy": latest_yoy,
                "latest_mom": latest_mom,
                "metadata": {
                    "source": "Eurostat - Euro-Indicators (Industrial Import Prices)",
                    "dataset": self.DATASET,
                    "area": "Euro area (20 countries)",
                    "unit_yoy": "Percentage change compared to same period in previous year (calculated)",
                    "unit_mom": "Percentage change compared to previous month (calculated)",
                    "base_index": "Index 2021=100 (I2021)",
                    "frequency": "Monthly",
                    "adjustment": "Not seasonally adjusted",
                    "sector": "Industry (B-D)",
                    "description": "Industrial import price indices",
                },
                "next_release": next_release,
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "yoy": yoy_data,
                "mom": mom_data,
                "latest_yoy": latest_yoy,
                "latest_mom": latest_mom,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "eurostat_api",
                "last_updated": last_updated,
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "yoy": file_cache.get("yoy", []),
                "mom": file_cache.get("mom", []),
                "latest_yoy": file_cache.get("latest_yoy"),
                "latest_mom": file_cache.get("latest_mom"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "yoy": [],
            "mom": [],
            "latest_yoy": None,
            "latest_mom": None,
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _fetch_eurostat_index_data(self, start_period: str = "2015-01") -> Optional[List[Dict]]:
        """
        Eurostat APIからインデックスデータを取得

        Args:
            start_period: 開始期間 (YYYY-MM)

        Returns:
            インデックスデータポイントのリスト
        """
        # ei_isin_m: M.I2021.NSA.B-D.IS-IMPR.EA21
        # M = Monthly, I2021 = Index 2021=100, NSA = Not seasonally adjusted
        # B-D = Industry, IS-IMPR = Import prices, EA21 = Euro area 21
        # 2026-01ブルガリア加盟で公式集計がEA20→EA21に移行(EA21は2000-01〜の全履歴あり)
        series_key = "M.I2021.NSA.B-D.IS-IMPR.EA21"
        url = f"{self.EUROSTAT_API_BASE}/{self.DATASET}/{series_key}"

        params = {
            "format": "JSON",
            "startPeriod": start_period,
        }

        try:
            print(f"[EUImportPrices] Fetching index data from Eurostat API: {url}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Extract dimensions and values
            dimensions = data.get("dimension", {})
            time_dim = dimensions.get("time", {})
            time_category = time_dim.get("category", {})
            time_index = time_category.get("index", {})

            values = data.get("value", {})

            if not time_index or not values:
                print("[EUImportPrices] No index data found")
                return None

            # Create index to time mapping
            idx_to_time = {v: k for k, v in time_index.items()}

            # Build result list
            result = []
            for val_idx_str in sorted(values.keys(), key=lambda x: int(x)):
                val_idx = int(val_idx_str)
                time_period = idx_to_time.get(val_idx)
                value = values.get(val_idx_str)

                if time_period and value is not None:
                    # Convert YYYY-MM to YYYY-MM-01
                    date_str = f"{time_period}-01"
                    result.append({
                        "date": date_str,
                        "value": float(value)
                    })

            print(f"[EUImportPrices] Successfully fetched {len(result)} index data points")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[EUImportPrices] API request error: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[EUImportPrices] Data parsing error: {e}")
            return None

    def _calculate_yoy(self, index_data: List[Dict]) -> List[Dict]:
        """インデックスデータから前年同月比を計算"""
        # 日付をキーにしたマップを作成
        date_map = {item["date"]: item["value"] for item in index_data}
        result = []

        for item in index_data:
            date_str = item["date"]
            current_value = item["value"]

            # 12ヶ月前の日付を計算
            year = int(date_str[:4])
            month = int(date_str[5:7])
            prev_year = year - 1
            prev_date = f"{prev_year}-{month:02d}-01"

            prev_value = date_map.get(prev_date)
            if prev_value is not None and prev_value != 0:
                yoy = ((current_value - prev_value) / prev_value) * 100
                result.append({
                    "date": date_str,
                    "value": round(yoy, 1)
                })

        return result

    def _calculate_mom(self, index_data: List[Dict]) -> List[Dict]:
        """インデックスデータから前月比を計算"""
        result = []

        for i in range(1, len(index_data)):
            current = index_data[i]
            previous = index_data[i - 1]

            current_value = current["value"]
            prev_value = previous["value"]

            if prev_value is not None and prev_value != 0:
                mom = ((current_value - prev_value) / prev_value) * 100
                result.append({
                    "date": current["date"],
                    "value": round(mom, 1)
                })

        return result

    def _should_refresh(self, last_updated_str: str, cached_data: Dict[str, Any]) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        Eurostatリリースカレンダーの発表日を過ぎていれば更新
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # max-age フォールバック（発表レース凍結の自己回復）:
            # 発表時刻ちょうどの再取得で Eurostat 未反映のまま last_updated=now を刻むと、
            # 下の発表日時判定(last_updated < release_datetime)が False となり次回発表まで
            # 凍結する。168hで必ず再取得させ自己回復させる。
            if (now - last_updated).total_seconds() > 168 * 3600:
                return True

            # 次回発表日を取得
            next_release = self._get_next_release_from_calendar()
            if not next_release:
                # カレンダーが取得できない場合は24時間ごとに更新
                if (now - last_updated).total_seconds() > 86400:
                    return True
                return False

            # 発表日を過ぎているか確認
            release_date_str = next_release.get("date")
            if release_date_str:
                release_date = datetime.strptime(release_date_str, "%Y-%m-%d").replace(tzinfo=JST)
                # 発表日の11:00 CET = 19:00 JST 以降で、最終更新が発表日前なら更新
                release_datetime = release_date.replace(hour=19, minute=0, second=0)
                if now >= release_datetime and last_updated < release_datetime:
                    return True

            return False

        except Exception as e:
            print(f"[EUImportPrices] Error checking refresh status: {e}")
            return False

    def _get_next_release_from_calendar(self) -> Optional[Dict[str, Any]]:
        """
        Eurostatリリースカレンダーから次回発表日を取得
        """
        # キャッシュをチェック（1日間有効）
        cached = redis_client.get(self.CALENDAR_CACHE_KEY)
        if cached:
            cache_time = cached.get("cached_at")
            if cache_time:
                try:
                    cache_dt = datetime.fromisoformat(cache_time)
                    if (datetime.now(JST) - cache_dt).total_seconds() < 86400:
                        return cached.get("next_release")
                except Exception:
                    pass

        # カレンダーを取得
        next_release = self._fetch_calendar_data()

        # キャッシュに保存
        if next_release:
            redis_client.set(self.CALENDAR_CACHE_KEY, {
                "next_release": next_release,
                "cached_at": datetime.now(JST).isoformat()
            }, expire=86400)

        return next_release

    def _fetch_calendar_data(self) -> Optional[Dict[str, Any]]:
        """
        EurostatカレンダーからImport Pricesの次回発表日を取得
        """
        try:
            print("[EUImportPrices] Fetching Eurostat release calendar...")
            response = requests.get(self.EUROSTAT_CALENDAR_URL, timeout=30)
            response.raise_for_status()

            ical_text = response.text
            now = datetime.now(JST)

            # Industrial import pricesイベントを探す
            # パターン: DTSTART;VALUE=DATE:YYYYMMDD followed by SUMMARY:Industrial import prices
            events = []
            lines = ical_text.split('\n')
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith('DTSTART;VALUE=DATE:'):
                    date_str = line.replace('DTSTART;VALUE=DATE:', '')
                    # 次の数行でSUMMARYとX-CATEGORYを探す
                    summary = None
                    category = None
                    for j in range(i + 1, min(i + 10, len(lines))):
                        check_line = lines[j].strip()
                        if check_line.startswith('SUMMARY:'):
                            summary = check_line.replace('SUMMARY:', '')
                        if check_line.startswith('X-CATEGORY:'):
                            category = check_line.replace('X-CATEGORY:', '')
                        if check_line.startswith('END:VEVENT'):
                            break

                    # Industrial import pricesでData releaseを含むもの
                    if summary and summary == 'Industrial import prices' and category and 'Data release' in category:
                        try:
                            event_date = datetime.strptime(date_str, '%Y%m%d').replace(tzinfo=JST)
                            if event_date.date() >= now.date():
                                events.append({
                                    "date": event_date.strftime('%Y-%m-%d'),
                                    "summary": summary,
                                    "datetime_jst": event_date.replace(hour=19, minute=0).strftime('%Y-%m-%d %H:%M'),
                                    "time_jst": "19:00",
                                })
                        except ValueError:
                            pass
                i += 1

            # 最も近い発表日を返す
            if events:
                events.sort(key=lambda x: x["date"])
                next_event = events[0]
                return {
                    "date": next_event["date"],
                    "datetime_jst": next_event["datetime_jst"],
                    "time_jst": next_event["time_jst"],
                    "label": f"Import Prices ({next_event['date']})",
                }

            print("[EUImportPrices] No upcoming Industrial import prices releases found in calendar")
            return None

        except requests.exceptions.RequestException as e:
            print(f"[EUImportPrices] Calendar fetch error: {e}")
            return None
        except Exception as e:
            print(f"[EUImportPrices] Calendar parsing error: {e}")
            return None

    def _calculate_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表予定を取得（Eurostatカレンダーから）
        """
        return self._get_next_release_from_calendar()

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[EUImportPrices] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[EUImportPrices] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        self._invalidate_calendar_cache()
        return redis_client.delete(self.DATA_CACHE_KEY)

    def _invalidate_calendar_cache(self) -> bool:
        """カレンダーキャッシュを無効化"""
        return redis_client.delete(self.CALENDAR_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "EU Import Prices",
            "source": "Eurostat API (teiis011)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "yoy_count": len(cached_data.get("yoy", [])) if cached_data else 0,
            "mom_count": len(cached_data.get("mom", [])) if cached_data else 0,
            "latest_yoy": cached_data.get("latest_yoy") if cached_data else None,
            "latest_mom": cached_data.get("latest_mom") if cached_data else None,
            "next_release": self._calculate_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
eu_import_prices_service = EUImportPricesService()
