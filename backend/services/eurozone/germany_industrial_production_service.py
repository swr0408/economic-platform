"""
ドイツ鉱工業生産サービス
GENESIS-Online API（Destatis）からドイツ鉱工業生産データを取得

指標:
- 鉱工業生産指数 MoM（前月比）: 季節・カレンダー調整済み (seasonally and calendar adjusted)
- 鉱工業生産指数 YoY（前年比）: カレンダー調整済み (calendar adjusted)

データソース:
- GENESIS-Online: テーブルID 42153-0001 (Indices of production in manufacturing)
- FMP economic_calendar_events（速報値補完用）

発表スケジュール:
- 月次（通常、対象月の翌々月初旬）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import os
import re
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.eurozone.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
CET = ZoneInfo("Europe/Berlin")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "germany_industrial_production_cache.json"


class GermanyIndustrialProductionService:
    """ドイツ鉱工業生産サービス (GENESIS-Online + FMP)"""

    DATA_CACHE_KEY = "economy:germany_industrial_production:data"
    ECONALPHA_ID = "germany_industrial_production"

    # Destatis API設定
    BASE_URL = "https://www-genesis.destatis.de/genesisWS/rest/2020"
    TABLE_ID = "42153-0001"  # Indices of production in manufacturing

    # 月名から月番号へのマッピング
    MONTH_MAP = {
        'January': '01', 'February': '02', 'March': '03',
        'April': '04', 'May': '05', 'June': '06',
        'July': '07', 'August': '08', 'September': '09',
        'October': '10', 'November': '11', 'December': '12'
    }

    MONTH_ABBR_MAP = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }

    def __init__(self, username: str = None, password: str = None):
        self.username = username or os.getenv('DESTATIS_USERNAME', '')
        self.password = password or os.getenv('DESTATIS_PASSWORD', '')

    def get_germany_industrial_production_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        ドイツ鉱工業生産データを取得

        Returns:
            {
                "mom": [...],  # 前月比データ
                "yoy": [...],  # 前年比データ
                "latest_mom": {...},
                "latest_yoy": {...},
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
                    next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
                    return {
                        "mom": cached_data.get("mom", []),
                        "yoy": cached_data.get("yoy", []),
                        "latest_mom": cached_data.get("latest_mom"),
                        "latest_yoy": cached_data.get("latest_yoy"),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # 1. Destatis APIからデータを取得
        destatis_data = self._load_from_destatis()

        # 2. FMP DBから速報データを取得
        fmp_data = self._load_from_fmp_db()

        # 3. データをマージ（Destatis < FMP の順で上書き）
        merged_data = self._merge_sources(destatis_data, fmp_data)

        mom_data = merged_data.get("mom", [])
        yoy_data = merged_data.get("yoy", [])

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
                "source": "destatis + fmp",
                "last_updated": last_updated
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
            return {
                "mom": file_cache.get("mom", []),
                "yoy": file_cache.get("yoy", []),
                "latest_mom": file_cache.get("latest_mom"),
                "latest_yoy": file_cache.get("latest_yoy"),
                "next_release": next_release,
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

    # =========================================================================
    # Destatis API関連メソッド
    # =========================================================================

    def _make_request(self, endpoint: str, data: Dict) -> Optional[requests.Response]:
        """Destatis APIへのリクエストを実行"""
        url = f"{self.BASE_URL}/{endpoint}"
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'username': self.username,
            'password': self.password
        }

        try:
            response = requests.post(url, headers=headers, data=data, timeout=30)
            return response
        except requests.exceptions.RequestException as e:
            print(f"[GermanyIndustrialProduction] Request error: {e}")
            return None

    def _load_from_destatis(self) -> Dict[str, List[Dict[str, Any]]]:
        """Destatis GENESIS APIからデータを取得"""
        print("[GermanyIndustrialProduction] Fetching data from Destatis API...")

        data = {
            'name': self.TABLE_ID,
            'area': 'all',
            'language': 'en',
            'format': 'csv',
            'job': 'false',
            'startyear': '2015',
            'endyear': str(datetime.now().year)
        }

        response = self._make_request('data/table', data)
        if not response or response.status_code != 200:
            print(f"[GermanyIndustrialProduction] Failed to fetch data: {response.status_code if response else 'No response'}")
            return {"mom": [], "yoy": []}

        content_type = response.headers.get('Content-Type', '')

        if 'json' in content_type:
            result = response.json()
            status = result.get('Status', {})
            if status.get('Code') == 0:
                csv_content = result.get('Object', {}).get('Content', '')
                return self._parse_industrial_production_csv(csv_content)
            else:
                print(f"[GermanyIndustrialProduction] API error: {status.get('Content')}")
                return {"mom": [], "yoy": []}
        else:
            return self._parse_industrial_production_csv(response.text)

    def _parse_industrial_production_csv(self, csv_content: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        鉱工業生産CSVをパース

        テーブル42153-0001の構造:
        - Industry (経済活動分類)
        - Year
        - Month
        - Unadjusted values (指数、未調整)
        - Calendar adjusted (指数、カレンダー調整済み)
        - Calendar and seasonally adjusted (指数、季節・カレンダー調整済み)
        - BV4.1 calendar and seasonally adjusted
        - BV4.1 trend

        指数値から前月比・前年比を計算:
        - MoM: 季節・カレンダー調整済み指数から計算
        - YoY: カレンダー調整済み指数から計算
        """
        lines = csv_content.strip().split('\n')

        # データ行を抽出（"Industry;"で始まる行）
        data_lines = []
        for line in lines:
            if line.startswith('Industry;'):
                data_lines.append(line)

        # 指数データを日付順に収集
        index_data: Dict[str, Dict[str, float]] = {}

        for line in data_lines:
            parts = [p.strip() for p in line.split(';')]
            if len(parts) >= 6:
                # Industry;Year;Month;Unadjusted;Calendar adjusted;Calendar and seasonally adjusted;...
                year = parts[1]
                month = parts[2]
                calendar_adjusted = parts[4]  # カレンダー調整済み（YoY計算用）
                seasonally_adjusted = parts[5]  # 季節・カレンダー調整済み（MoM計算用）

                try:
                    month_num = self.MONTH_MAP.get(month)
                    if not month_num:
                        continue

                    date_str = f"{year}-{month_num}-01"

                    # 指数値をパース
                    cal_adj_value = self._parse_index(calendar_adjusted)
                    seas_adj_value = self._parse_index(seasonally_adjusted)

                    if cal_adj_value is not None or seas_adj_value is not None:
                        index_data[date_str] = {
                            'calendar_adjusted': cal_adj_value,
                            'seasonally_adjusted': seas_adj_value,
                        }

                except (ValueError, KeyError):
                    continue

        # 日付順にソート
        sorted_dates = sorted(index_data.keys())

        mom_data = []
        yoy_data = []

        for i, date_str in enumerate(sorted_dates):
            current = index_data[date_str]

            # MoM計算（前月との比較）
            if i > 0 and current.get('seasonally_adjusted') is not None:
                prev_date = sorted_dates[i - 1]
                prev = index_data[prev_date]
                if prev.get('seasonally_adjusted') is not None and prev['seasonally_adjusted'] != 0:
                    mom_value = round(
                        (current['seasonally_adjusted'] - prev['seasonally_adjusted']) / prev['seasonally_adjusted'] * 100,
                        1
                    )
                    mom_data.append({
                        'date': date_str,
                        'value': mom_value,
                        'source': 'destatis',
                        'adjustment': 'seasonally and calendar adjusted'
                    })

            # YoY計算（前年同月との比較）
            year = int(date_str[:4])
            month = date_str[5:7]
            prev_year_date = f"{year - 1}-{month}-01"

            if prev_year_date in index_data and current.get('calendar_adjusted') is not None:
                prev_year = index_data[prev_year_date]
                if prev_year.get('calendar_adjusted') is not None and prev_year['calendar_adjusted'] != 0:
                    yoy_value = round(
                        (current['calendar_adjusted'] - prev_year['calendar_adjusted']) / prev_year['calendar_adjusted'] * 100,
                        1
                    )
                    yoy_data.append({
                        'date': date_str,
                        'value': yoy_value,
                        'source': 'destatis',
                        'adjustment': 'calendar adjusted'
                    })

        print(f"[GermanyIndustrialProduction] Loaded {len(mom_data)} MoM, {len(yoy_data)} YoY records from Destatis")
        return {"mom": mom_data, "yoy": yoy_data}

    def _parse_index(self, value: str) -> Optional[float]:
        """指数値をパース"""
        if not value or value == '...' or value == '-':
            return None
        try:
            return float(value.replace(',', '.'))
        except ValueError:
            return None

    def _parse_percent(self, value: str) -> Optional[float]:
        """パーセンテージ値をパース"""
        if not value or value == '...' or value == '-':
            return None
        try:
            return float(value.replace('+', '').replace(',', '.'))
        except ValueError:
            return None

    # =========================================================================
    # FMP DB関連メソッド
    # =========================================================================

    def _load_from_fmp_db(self) -> Dict[str, List[Dict[str, Any]]]:
        """FMP economic_calendar_eventsから速報データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                # MoMデータ
                mom_query = text("""
                    SELECT datetime_utc, event, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'DE'
                      AND event ILIKE '%Industrial Production MoM%'
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                mom_rows = session.execute(mom_query).fetchall()

                # YoYデータ
                yoy_query = text("""
                    SELECT datetime_utc, event, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'DE'
                      AND event ILIKE '%Industrial Production YoY%'
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                yoy_rows = session.execute(yoy_query).fetchall()

                mom_result = []
                yoy_result = []
                seen_mom_dates = set()
                seen_yoy_dates = set()

                for row in mom_rows:
                    dt_utc, event, actual, estimate, previous = row
                    if dt_utc:
                        # イベント名から対象月を抽出
                        target_date = self._extract_target_date_from_event(event, dt_utc)
                        if not target_date:
                            target_date = dt_utc.strftime("%Y-%m-01")

                        if target_date in seen_mom_dates:
                            continue
                        seen_mom_dates.add(target_date)

                        mom_result.append({
                            "date": target_date,
                            "value": float(actual) if actual else None,
                            "forecast": float(estimate) if estimate else None,
                            "previous": float(previous) if previous else None,
                            "source": "fmp",
                        })

                for row in yoy_rows:
                    dt_utc, event, actual, estimate, previous = row
                    if dt_utc:
                        target_date = self._extract_target_date_from_event(event, dt_utc)
                        if not target_date:
                            target_date = dt_utc.strftime("%Y-%m-01")

                        if target_date in seen_yoy_dates:
                            continue
                        seen_yoy_dates.add(target_date)

                        yoy_result.append({
                            "date": target_date,
                            "value": float(actual) if actual else None,
                            "forecast": float(estimate) if estimate else None,
                            "previous": float(previous) if previous else None,
                            "source": "fmp",
                        })

                print(f"[GermanyIndustrialProduction] Loaded {len(mom_result)} MoM, {len(yoy_result)} YoY records from FMP DB")
                return {"mom": mom_result, "yoy": yoy_result}

        except Exception as e:
            print(f"[GermanyIndustrialProduction] Error loading from FMP DB: {e}")
            return {"mom": [], "yoy": []}

    def _extract_target_date_from_event(self, event: str, dt_utc: datetime) -> Optional[str]:
        """イベント名から対象月の日付文字列を抽出"""
        # (Dec), (Jan) などの形式から月を抽出
        match = re.search(r'\((\w{3})\)', event)
        if match:
            month_abbr = match.group(1).lower()
            if month_abbr in self.MONTH_ABBR_MAP:
                target_month = self.MONTH_ABBR_MAP[month_abbr]
                target_year = dt_utc.year
                # 発表月より対象月が大きい場合は前年のデータ
                if target_month > dt_utc.month:
                    target_year -= 1
                return f"{target_year}-{target_month:02d}-01"
        return None

    # =========================================================================
    # データマージ
    # =========================================================================

    def _merge_sources(
        self,
        destatis_data: Dict[str, List[Dict[str, Any]]],
        fmp_data: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        DestatisとFMPのデータをマージ
        優先順位: destatis_data < fmp_data（FMPの速報が最新）
        """
        # MoMデータのマージ
        mom_merged: Dict[str, Dict[str, Any]] = {}

        for d in destatis_data.get("mom", []):
            mom_merged[d["date"]] = d.copy()

        # FMP速報で上書き（最新データ優先）
        for d in fmp_data.get("mom", []):
            date = d["date"]
            if date in mom_merged:
                # Destatisデータより新しい場合のみ上書き
                # FMPは速報なので、Destatisに確報がない最新月のみ上書き
                if mom_merged[date].get("source") != "destatis":
                    mom_merged[date] = d.copy()
            else:
                # Destatisにない新しいデータ
                mom_merged[date] = d.copy()

        # YoYデータのマージ
        yoy_merged: Dict[str, Dict[str, Any]] = {}

        for d in destatis_data.get("yoy", []):
            yoy_merged[d["date"]] = d.copy()

        for d in fmp_data.get("yoy", []):
            date = d["date"]
            if date in yoy_merged:
                if yoy_merged[date].get("source") != "destatis":
                    yoy_merged[date] = d.copy()
            else:
                yoy_merged[date] = d.copy()

        mom_result = sorted(mom_merged.values(), key=lambda x: x["date"])
        yoy_result = sorted(yoy_merged.values(), key=lambda x: x["date"])

        return {"mom": mom_result, "yoy": yoy_result}

    # =========================================================================
    # キャッシュ関連メソッド
    # =========================================================================

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日時ベース）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[GermanyIndustrialProduction] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[GermanyIndustrialProduction] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Germany Industrial Production",
            "source": "Destatis (GENESIS-Online) + FMP",
            "table_id": self.TABLE_ID,
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
germany_industrial_production_service = GermanyIndustrialProductionService()
