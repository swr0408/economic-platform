"""
ドイツ製造業新規受注サービス
GENESIS-Online API（Destatis）からドイツ製造業新規受注データを取得

指標:
- 製造業新規受注 MoM（前月比）: 季節・カレンダー調整済み (seasonally and calendar adjusted)
- 製造業新規受注 YoY（前年比）: カレンダー調整済み (calendar adjusted)
- 国内受注（Inland/Domestic）: MoM/YoY
- 国外受注（Ausland/Foreign）: MoM/YoY

データソース:
- GENESIS-Online: テーブルID 42151-0004 (Indices of new orders in manufacturing)

発表スケジュール:
- 月次（通常、対象月の翌々月初旬）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import os
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
DATA_CACHE_FILE = CACHE_DIR / "germany_factory_orders_cache.json"


class GermanyFactoryOrdersService:
    """ドイツ製造業新規受注サービス (GENESIS-Online API)"""

    DATA_CACHE_KEY = "economy:germany_factory_orders:data"
    ECONALPHA_ID = "germany_factory_orders"

    # Destatis API設定
    BASE_URL = "https://www-genesis.destatis.de/genesisWS/rest/2020"
    TABLE_ID = "42151-0004"  # Indices of new orders in manufacturing

    # 月名から月番号へのマッピング
    MONTH_MAP = {
        'January': '01', 'February': '02', 'March': '03',
        'April': '04', 'May': '05', 'June': '06',
        'July': '07', 'August': '08', 'September': '09',
        'October': '10', 'November': '11', 'December': '12'
    }

    def __init__(self, username: str = None, password: str = None):
        self.username = username or os.getenv('DESTATIS_USERNAME', '')
        self.password = password or os.getenv('DESTATIS_PASSWORD', '')

    def get_germany_factory_orders_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        ドイツ製造業新規受注データを取得

        Returns:
            {
                "mom": [...],  # 前月比データ（総合）
                "yoy": [...],  # 前年比データ（総合）
                "domestic_mom": [...],  # 国内受注 前月比
                "domestic_yoy": [...],  # 国内受注 前年比
                "foreign_mom": [...],   # 国外受注 前月比
                "foreign_yoy": [...],   # 国外受注 前年比
                "index_total": [...],     # 指数原数値（総合）
                "index_domestic": [...],  # 指数原数値（国内）
                "index_foreign": [...],   # 指数原数値（国外）
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
                        "domestic_mom": cached_data.get("domestic_mom", []),
                        "domestic_yoy": cached_data.get("domestic_yoy", []),
                        "foreign_mom": cached_data.get("foreign_mom", []),
                        "foreign_yoy": cached_data.get("foreign_yoy", []),
                        "index_total": cached_data.get("index_total", []),
                        "index_domestic": cached_data.get("index_domestic", []),
                        "index_foreign": cached_data.get("index_foreign", []),
                        "latest_mom": cached_data.get("latest_mom"),
                        "latest_yoy": cached_data.get("latest_yoy"),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # Destatis APIからデータを取得
        destatis_data = self._load_from_destatis()

        mom_data = destatis_data.get("mom", [])
        yoy_data = destatis_data.get("yoy", [])
        domestic_mom = destatis_data.get("domestic_mom", [])
        domestic_yoy = destatis_data.get("domestic_yoy", [])
        foreign_mom = destatis_data.get("foreign_mom", [])
        foreign_yoy = destatis_data.get("foreign_yoy", [])
        index_total = destatis_data.get("index_total", [])
        index_domestic = destatis_data.get("index_domestic", [])
        index_foreign = destatis_data.get("index_foreign", [])

        if mom_data or yoy_data:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
            latest_mom = mom_data[-1] if mom_data else None
            latest_yoy = yoy_data[-1] if yoy_data else None

            cache_payload = {
                "mom": mom_data,
                "yoy": yoy_data,
                "domestic_mom": domestic_mom,
                "domestic_yoy": domestic_yoy,
                "foreign_mom": foreign_mom,
                "foreign_yoy": foreign_yoy,
                "index_total": index_total,
                "index_domestic": index_domestic,
                "index_foreign": index_foreign,
                "latest_mom": latest_mom,
                "latest_yoy": latest_yoy,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "mom": mom_data,
                "yoy": yoy_data,
                "domestic_mom": domestic_mom,
                "domestic_yoy": domestic_yoy,
                "foreign_mom": foreign_mom,
                "foreign_yoy": foreign_yoy,
                "index_total": index_total,
                "index_domestic": index_domestic,
                "index_foreign": index_foreign,
                "latest_mom": latest_mom,
                "latest_yoy": latest_yoy,
                "next_release": next_release,
                "cached": False,
                "source": "destatis",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
            return {
                "mom": file_cache.get("mom", []),
                "yoy": file_cache.get("yoy", []),
                "domestic_mom": file_cache.get("domestic_mom", []),
                "domestic_yoy": file_cache.get("domestic_yoy", []),
                "foreign_mom": file_cache.get("foreign_mom", []),
                "foreign_yoy": file_cache.get("foreign_yoy", []),
                "index_total": file_cache.get("index_total", []),
                "index_domestic": file_cache.get("index_domestic", []),
                "index_foreign": file_cache.get("index_foreign", []),
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
            "domestic_mom": [],
            "domestic_yoy": [],
            "foreign_mom": [],
            "foreign_yoy": [],
            "index_total": [],
            "index_domestic": [],
            "index_foreign": [],
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
            print(f"[GermanyFactoryOrders] Request error: {e}")
            return None

    def _load_from_destatis(self) -> Dict[str, List[Dict[str, Any]]]:
        """Destatis GENESIS APIからデータを取得（期間分割で取得）"""
        print("[GermanyFactoryOrders] Fetching data from Destatis API...")

        # テーブルが大きいため、期間を分割して取得
        current_year = datetime.now().year
        year_ranges = [
            (2015, 2019),
            (2020, 2022),
            (2023, current_year + 1)
        ]

        all_csv_lines = []

        for start_year, end_year in year_ranges:
            data = {
                'name': self.TABLE_ID,
                'area': 'all',
                'language': 'en',
                'format': 'csv',
                'job': 'false',
                'startyear': str(start_year),
                'endyear': str(end_year)
            }

            response = self._make_request('data/table', data)
            if not response or response.status_code != 200:
                print(f"[GermanyFactoryOrders] Failed to fetch data for {start_year}-{end_year}: {response.status_code if response else 'No response'}")
                continue

            content_type = response.headers.get('Content-Type', '')

            if 'json' in content_type:
                result = response.json()
                status = result.get('Status', {})
                if status.get('Code') == 0:
                    csv_content = result.get('Object', {}).get('Content', '')
                    # Manufacturing;で始まる行のみを抽出
                    lines = csv_content.strip().split('\n')
                    mfg_lines = [l for l in lines if l.startswith('Manufacturing;')]
                    all_csv_lines.extend(mfg_lines)
                    print(f"[GermanyFactoryOrders] Loaded {len(mfg_lines)} lines for {start_year}-{end_year}")
                else:
                    print(f"[GermanyFactoryOrders] API error for {start_year}-{end_year}: {status.get('Content')}")
            else:
                lines = response.text.strip().split('\n')
                mfg_lines = [l for l in lines if l.startswith('Manufacturing;')]
                all_csv_lines.extend(mfg_lines)

        if not all_csv_lines:
            print("[GermanyFactoryOrders] No data retrieved from Destatis API")
            return {"mom": [], "yoy": []}

        # 全データを結合してパース
        combined_csv = '\n'.join(all_csv_lines)
        return self._parse_factory_orders_csv(combined_csv)

    def _parse_factory_orders_csv(self, csv_content: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        製造業新規受注CSVをパース

        テーブル42151-0004の構造:
        Manufacturing;Year;Month;Unadjusted(Total);Unadjusted(Domestic);...;CalAdj(Total);...;CalSeasonAdj(Total);...

        CSV列構造（実際のデータ）:
        - [0] Industry category (Manufacturing, etc.)
        - [1] Year
        - [2] Month
        - [3-7] Unadjusted values (Total, Domestic, Foreign, Euro area, Non-euro)
        - [8-12] Calendar adjusted (Total, Domestic, Foreign, Euro area, Non-euro)
        - [13-17] Calendar and seasonally adjusted (Total, Domestic, Foreign, Euro area, Non-euro)
        - [18-22] BV4.1 calendar and seasonally adjusted
        - [23-27] BV4.1 trend

        指数値から前月比・前年比を計算:
        - MoM: 季節・カレンダー調整済み指数（列13: Total, 列14: Domestic, 列15: Foreign）から計算
        - YoY: カレンダー調整済み指数（列8: Total, 列9: Domestic, 列10: Foreign）から計算
        """
        lines = csv_content.strip().split('\n')

        # データ行を抽出（"Manufacturing;"で始まる行を対象）
        # 注: _load_from_destatis()で既にManufacturing行のみを抽出済みの場合もある
        data_lines = []
        for line in lines:
            if line.startswith('Manufacturing;'):
                data_lines.append(line)
            elif ';' in line and line.split(';')[0] == '':
                # _load_from_destatis()から結合されたCSVの場合は全行がManufacturing行
                continue

        # 既にManufacturing行のみの場合
        if not data_lines:
            data_lines = lines

        # 指数データを日付順に収集
        index_data: Dict[str, Dict[str, Optional[float]]] = {}

        for line in data_lines:
            parts = [p.strip() for p in line.split(';')]
            # 最低限必要な列数をチェック（季節・カレンダー調整済みForeign = 列15）
            if len(parts) >= 16:
                # Manufacturing;Year;Month;...
                year = parts[1]
                month = parts[2]

                # Calendar adjusted (YoY計算用)
                # 列8: Total, 列9: Domestic, 列10: Foreign
                cal_adj_total = parts[8] if len(parts) > 8 else ''
                cal_adj_domestic = parts[9] if len(parts) > 9 else ''
                cal_adj_foreign = parts[10] if len(parts) > 10 else ''

                # Calendar and seasonally adjusted (MoM計算用)
                # 列13: Total, 列14: Domestic, 列15: Foreign
                seas_adj_total = parts[13] if len(parts) > 13 else ''
                seas_adj_domestic = parts[14] if len(parts) > 14 else ''
                seas_adj_foreign = parts[15] if len(parts) > 15 else ''

                try:
                    month_num = self.MONTH_MAP.get(month)
                    if not month_num:
                        continue

                    date_str = f"{year}-{month_num}-01"

                    # 指数値をパース
                    index_data[date_str] = {
                        'cal_adj_total': self._parse_index(cal_adj_total),
                        'cal_adj_domestic': self._parse_index(cal_adj_domestic),
                        'cal_adj_foreign': self._parse_index(cal_adj_foreign),
                        'seas_adj_total': self._parse_index(seas_adj_total),
                        'seas_adj_domestic': self._parse_index(seas_adj_domestic),
                        'seas_adj_foreign': self._parse_index(seas_adj_foreign),
                    }

                except (ValueError, KeyError):
                    continue

        # 日付順にソート
        sorted_dates = sorted(index_data.keys())

        # 結果格納用
        mom_data = []
        yoy_data = []
        domestic_mom = []
        domestic_yoy = []
        foreign_mom = []
        foreign_yoy = []
        index_total = []
        index_domestic = []
        index_foreign = []

        for i, date_str in enumerate(sorted_dates):
            current = index_data[date_str]

            # 指数原数値を保存（季節・カレンダー調整済み）
            if current.get('seas_adj_total') is not None:
                index_total.append({
                    'date': date_str,
                    'value': round(current['seas_adj_total'], 1),
                    'source': 'destatis',
                    'adjustment': 'seasonally and calendar adjusted'
                })
            if current.get('seas_adj_domestic') is not None:
                index_domestic.append({
                    'date': date_str,
                    'value': round(current['seas_adj_domestic'], 1),
                    'source': 'destatis',
                    'adjustment': 'seasonally and calendar adjusted'
                })
            if current.get('seas_adj_foreign') is not None:
                index_foreign.append({
                    'date': date_str,
                    'value': round(current['seas_adj_foreign'], 1),
                    'source': 'destatis',
                    'adjustment': 'seasonally and calendar adjusted'
                })

            # MoM計算（前月との比較）
            if i > 0:
                prev_date = sorted_dates[i - 1]
                prev = index_data[prev_date]

                # Total MoM
                if current.get('seas_adj_total') is not None and prev.get('seas_adj_total') is not None and prev['seas_adj_total'] != 0:
                    mom_value = round(
                        (current['seas_adj_total'] - prev['seas_adj_total']) / prev['seas_adj_total'] * 100,
                        1
                    )
                    mom_data.append({
                        'date': date_str,
                        'value': mom_value,
                        'source': 'destatis',
                        'adjustment': 'seasonally and calendar adjusted'
                    })

                # Domestic MoM
                if current.get('seas_adj_domestic') is not None and prev.get('seas_adj_domestic') is not None and prev['seas_adj_domestic'] != 0:
                    dom_mom_value = round(
                        (current['seas_adj_domestic'] - prev['seas_adj_domestic']) / prev['seas_adj_domestic'] * 100,
                        1
                    )
                    domestic_mom.append({
                        'date': date_str,
                        'value': dom_mom_value,
                        'source': 'destatis',
                        'adjustment': 'seasonally and calendar adjusted'
                    })

                # Foreign MoM
                if current.get('seas_adj_foreign') is not None and prev.get('seas_adj_foreign') is not None and prev['seas_adj_foreign'] != 0:
                    for_mom_value = round(
                        (current['seas_adj_foreign'] - prev['seas_adj_foreign']) / prev['seas_adj_foreign'] * 100,
                        1
                    )
                    foreign_mom.append({
                        'date': date_str,
                        'value': for_mom_value,
                        'source': 'destatis',
                        'adjustment': 'seasonally and calendar adjusted'
                    })

            # YoY計算（前年同月との比較）
            year = int(date_str[:4])
            month = date_str[5:7]
            prev_year_date = f"{year - 1}-{month}-01"

            if prev_year_date in index_data:
                prev_year = index_data[prev_year_date]

                # Total YoY
                if current.get('cal_adj_total') is not None and prev_year.get('cal_adj_total') is not None and prev_year['cal_adj_total'] != 0:
                    yoy_value = round(
                        (current['cal_adj_total'] - prev_year['cal_adj_total']) / prev_year['cal_adj_total'] * 100,
                        1
                    )
                    yoy_data.append({
                        'date': date_str,
                        'value': yoy_value,
                        'source': 'destatis',
                        'adjustment': 'calendar adjusted'
                    })

                # Domestic YoY
                if current.get('cal_adj_domestic') is not None and prev_year.get('cal_adj_domestic') is not None and prev_year['cal_adj_domestic'] != 0:
                    dom_yoy_value = round(
                        (current['cal_adj_domestic'] - prev_year['cal_adj_domestic']) / prev_year['cal_adj_domestic'] * 100,
                        1
                    )
                    domestic_yoy.append({
                        'date': date_str,
                        'value': dom_yoy_value,
                        'source': 'destatis',
                        'adjustment': 'calendar adjusted'
                    })

                # Foreign YoY
                if current.get('cal_adj_foreign') is not None and prev_year.get('cal_adj_foreign') is not None and prev_year['cal_adj_foreign'] != 0:
                    for_yoy_value = round(
                        (current['cal_adj_foreign'] - prev_year['cal_adj_foreign']) / prev_year['cal_adj_foreign'] * 100,
                        1
                    )
                    foreign_yoy.append({
                        'date': date_str,
                        'value': for_yoy_value,
                        'source': 'destatis',
                        'adjustment': 'calendar adjusted'
                    })

        print(f"[GermanyFactoryOrders] Loaded {len(mom_data)} MoM, {len(yoy_data)} YoY, {len(index_total)} Index records from Destatis")
        return {
            "mom": mom_data,
            "yoy": yoy_data,
            "domestic_mom": domestic_mom,
            "domestic_yoy": domestic_yoy,
            "foreign_mom": foreign_mom,
            "foreign_yoy": foreign_yoy,
            "index_total": index_total,
            "index_domestic": index_domestic,
            "index_foreign": index_foreign,
        }

    def _parse_index(self, value: str) -> Optional[float]:
        """指数値をパース"""
        if not value or value == '...' or value == '-':
            return None
        try:
            return float(value.replace(',', '.'))
        except ValueError:
            return None

    # =========================================================================
    # キャッシュ関連メソッド
    # =========================================================================

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日時ベース）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str, max_age_hours=72)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[GermanyFactoryOrders] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[GermanyFactoryOrders] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Germany Factory Orders",
            "source": "Destatis (GENESIS-Online)",
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
germany_factory_orders_service = GermanyFactoryOrdersService()
