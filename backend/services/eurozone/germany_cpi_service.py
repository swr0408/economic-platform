"""
ドイツCPI/HICPサービス
DB積み上げ方式：Destatis（確報値）+ FMP（速報値）を統合

指標:
- CPI (Consumer Price Index) - Table: 61111-0002
- HICP (Harmonized Index of Consumer Prices) - Table: 61121-0002
- 前年比 (YoY)
- 前月比 (MoM)
- 指数値 (Index)

データソース（優先順位）:
1. germany_cpi_history テーブル - 長期時系列データ（ベース）
2. Destatis GENESIS API - 確報値で上書き更新
3. economic_calendar_events - FMP速報値で上書き更新

発表スケジュール:
- 速報: 毎月8-16日頃 15:00 CET (夏) / 16:00 CET (冬)
- 確定: 毎月28日-翌月6日頃 21:00 CET (夏) / 22:00 CET (冬)

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import os
import re
import requests
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client
from services.eurozone.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")
CET = ZoneInfo("Europe/Berlin")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "germany_cpi_cache.json"


class GermanyCPIService:
    """ドイツCPI/HICPサービス (DB積み上げ方式)"""

    DATA_CACHE_KEY = "eurozone:germany_cpi:data"
    ECONALPHA_ID = "germany_cpi"
    FMP_COUNTRY = "DE"
    FMP_EVENT_PATTERN = "Inflation Rate YoY"

    # Destatis API設定
    BASE_URL = "https://www-genesis.destatis.de/genesisWS/rest/2020"

    # FMPイベントパターン
    FMP_EVENT_PATTERNS = {
        "cpi_yoy": ["Inflation Rate YoY", "CPI"],
        "cpi_mom": ["Inflation Rate MoM", "CPI"],
        "hicp_yoy": ["HICP YoY", "Harmonised Inflation Rate YoY"],
        "hicp_mom": ["HICP MoM", "Harmonised Inflation Rate MoM"],
    }

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

    def get_germany_cpi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        ドイツCPI/HICPデータを取得

        Returns:
            {
                "data": [...],  # マージされたデータ配列
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
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # 1. 履歴DBからベースデータを取得
        history_data = self._load_from_history_db()

        # 2. Destatis APIから確報データを取得
        destatis_data = self._load_from_destatis()

        # 3. FMP DBから速報データを取得
        fmp_data = self._load_from_fmp_db()

        # データをマージ（履歴DB → Destatis → FMP の順で上書き）
        merged_data = self._merge_three_sources(history_data, destatis_data, fmp_data)

        if merged_data:
            next_release = get_next_release_by_pattern(
                self.FMP_EVENT_PATTERN,
                country=self.FMP_COUNTRY
            )

            cache_payload = {
                "data": merged_data,
                "metadata": {
                    "source": "History DB + Destatis + FMP",
                    "country": "Germany (DE)",
                    "cpi_table": "61111-0002",
                    "hicp_table": "61121-0002",
                    "cpi_base_year": "2020=100",
                    "hicp_base_year": "2015=100",
                    "description": "ドイツ消費者物価指数 / 調和消費者物価指数",
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": merged_data,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "history_db + destatis + fmp",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_history_db(self) -> List[Dict[str, Any]]:
        """germany_cpi_historyテーブルから長期時系列データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                query = text("""
                    SELECT date, cpi_index, cpi_yoy_change, cpi_mom_change,
                           hicp_index, hicp_yoy_change, hicp_mom_change,
                           source, is_preliminary
                    FROM germany_cpi_history
                    ORDER BY date ASC
                """)
                rows = session.execute(query).fetchall()

                result = []
                for row in rows:
                    date_val = row[0]
                    date_str = date_val.strftime('%Y-%m-%d') if hasattr(date_val, 'strftime') else str(date_val)

                    result.append({
                        "date": date_str,
                        "cpi_index": float(row[1]) if row[1] is not None else None,
                        "cpi_yoy_change": float(row[2]) if row[2] is not None else None,
                        "cpi_mom_change": float(row[3]) if row[3] is not None else None,
                        "hicp_index": float(row[4]) if row[4] is not None else None,
                        "hicp_yoy_change": float(row[5]) if row[5] is not None else None,
                        "hicp_mom_change": float(row[6]) if row[6] is not None else None,
                        "source": row[7],
                        "is_preliminary": row[8],
                    })

                print(f"[GermanyCPI] Loaded {len(result)} records from history DB")
                return result

        except Exception as e:
            print(f"[GermanyCPI] Error loading from history DB: {e}")
            return []

    def _load_from_destatis(self) -> List[Dict[str, Any]]:
        """Destatis GENESIS APIから確報データを取得"""
        print("[GermanyCPI] Fetching data from Destatis API...")

        cpi_data = self._fetch_cpi_monthly()
        hicp_data = self._fetch_hicp_monthly()

        if not cpi_data and not hicp_data:
            print("[GermanyCPI] Failed to fetch data from Destatis API")
            return []

        merged = self._merge_cpi_hicp(cpi_data, hicp_data)
        print(f"[GermanyCPI] Loaded {len(merged)} records from Destatis API")
        return merged

    def _load_from_fmp_db(self) -> List[Dict[str, Any]]:
        """FMP economic_calendar_eventsから速報データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                # CPI YoY, CPI MoM, HICP YoY, HICP MoMを取得
                query = text("""
                    SELECT datetime_utc, event, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'DE'
                      AND (
                          event ILIKE '%Inflation Rate YoY%'
                          OR event ILIKE '%Inflation Rate MoM%'
                          OR event ILIKE '%HICP YoY%'
                          OR event ILIKE '%HICP MoM%'
                          OR event ILIKE '%Harmonised Inflation%'
                          OR (event ILIKE '%CPI%' AND event NOT ILIKE '%Core%')
                      )
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query).fetchall()

                # 日付ごとにデータをまとめる
                date_map: Dict[str, Dict[str, Any]] = {}

                for row in rows:
                    dt_utc, event, actual, estimate, previous = row
                    if not dt_utc:
                        continue

                    # イベント名から対象月を抽出
                    target_date = self._extract_target_date_from_event(event, dt_utc)
                    if not target_date:
                        continue

                    if target_date not in date_map:
                        date_map[target_date] = {
                            "date": target_date,
                            "cpi_index": None,
                            "cpi_yoy_change": None,
                            "cpi_mom_change": None,
                            "hicp_index": None,
                            "hicp_yoy_change": None,
                            "hicp_mom_change": None,
                            "source": "fmp",
                            "is_preliminary": True,
                        }

                    # イベント種別に応じて値を設定
                    # 注意: FMPでは「CPI (Dec)」= 前月比、「Inflation Rate YoY (Dec)」= 前年比
                    event_lower = event.lower()
                    # 0.0も有効な値なので、actual is not Noneでチェック
                    value = float(actual) if actual is not None else None

                    # 州別CPIは除外（Baden Wuerttemberg, Bavaria, Saxony等）
                    if any(state in event_lower for state in [
                        'baden', 'bavaria', 'saxony', 'brandenburg',
                        'north rhine', 'hesse', 'rhineland'
                    ]):
                        continue

                    if 'hicp' in event_lower or 'harmonised' in event_lower:
                        # HICP系
                        if 'mom' in event_lower:
                            date_map[target_date]["hicp_mom_change"] = value
                        else:
                            date_map[target_date]["hicp_yoy_change"] = value
                    elif 'inflation rate yoy' in event_lower:
                        # CPI YoY (= Inflation Rate YoY)
                        date_map[target_date]["cpi_yoy_change"] = value
                    elif 'inflation rate mom' in event_lower:
                        # CPI MoM (= Inflation Rate MoM)
                        date_map[target_date]["cpi_mom_change"] = value
                    elif event_lower.strip() == 'cpi' or event_lower.startswith('cpi ('):
                        # 「CPI (Dec)」のような形式 = 前月比
                        date_map[target_date]["cpi_mom_change"] = value

                result = sorted(date_map.values(), key=lambda x: x["date"])
                print(f"[GermanyCPI] Loaded {len(result)} records from FMP DB")
                return result

        except Exception as e:
            print(f"[GermanyCPI] Error loading from FMP DB: {e}")
            return []

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

    def _merge_three_sources(
        self,
        history_data: List[Dict[str, Any]],
        destatis_data: List[Dict[str, Any]],
        fmp_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        3つのデータソースをマージ
        優先順位: history_data < destatis_data < fmp_data（後のものが上書き）
        """
        merged: Dict[str, Dict[str, Any]] = {}

        # 1. 履歴DBデータをベースに
        for d in history_data:
            merged[d["date"]] = d.copy()

        # 2. Destatis確報データで上書き（確報は速報より信頼性高い）
        for d in destatis_data:
            date = d["date"]
            if date in merged:
                # 既存データを更新（Noneでない値のみ上書き）
                for key in ["cpi_index", "cpi_yoy_change", "cpi_mom_change",
                           "hicp_index", "hicp_yoy_change", "hicp_mom_change"]:
                    if d.get(key) is not None:
                        merged[date][key] = d[key]
                merged[date]["source"] = "destatis"
                merged[date]["is_preliminary"] = False
            else:
                merged[date] = d.copy()
                merged[date]["source"] = "destatis"
                merged[date]["is_preliminary"] = False

        # 3. FMP速報データで上書き（最新データ優先）
        for d in fmp_data:
            date = d["date"]
            if date in merged:
                # 既存データがDestatis確報の場合は上書きしない
                if merged[date].get("source") == "destatis" and not merged[date].get("is_preliminary"):
                    continue
                # 速報データで上書き
                for key in ["cpi_yoy_change", "cpi_mom_change",
                           "hicp_yoy_change", "hicp_mom_change"]:
                    if d.get(key) is not None:
                        merged[date][key] = d[key]
                merged[date]["source"] = "fmp"
                merged[date]["is_preliminary"] = True
            else:
                merged[date] = d.copy()

        result = sorted(merged.values(), key=lambda x: x["date"])

        # nullの前月比をインデックス値から補填
        result = self._fill_missing_mom_changes(result)

        return result

    def _fill_missing_mom_changes(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        nullの前月比をインデックス値から計算して補填

        インデックス値が同じ場合、前月比は0%
        例: 2017年4月 index=96.2, 2017年5月 index=96.2 → 前月比=0%
        """
        if len(data) < 2:
            return data

        for i in range(1, len(data)):
            current = data[i]
            previous = data[i - 1]

            # CPI前月比がnullで、両方のインデックスが存在する場合
            if current.get("cpi_mom_change") is None:
                curr_idx = current.get("cpi_index")
                prev_idx = previous.get("cpi_index")
                if curr_idx is not None and prev_idx is not None and prev_idx != 0:
                    # 前月比を計算: ((current - previous) / previous) * 100
                    mom_change = round((curr_idx - prev_idx) / prev_idx * 100, 1)
                    current["cpi_mom_change"] = mom_change

            # HICP前月比がnullで、両方のインデックスが存在する場合
            if current.get("hicp_mom_change") is None:
                curr_idx = current.get("hicp_index")
                prev_idx = previous.get("hicp_index")
                if curr_idx is not None and prev_idx is not None and prev_idx != 0:
                    mom_change = round((curr_idx - prev_idx) / prev_idx * 100, 1)
                    current["hicp_mom_change"] = mom_change

        return data

    # =====================================================================
    # Destatis API関連メソッド
    # =====================================================================

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
            print(f"[GermanyCPI] Request error: {e}")
            return None

    def _fetch_cpi_monthly(self) -> Optional[Dict]:
        """CPIデータを取得 (Table: 61111-0002)"""
        data = {
            'name': '61111-0002',
            'area': 'all',
            'language': 'en',
            'format': 'csv',
            'job': 'false',
            'startyear': '2015',
            'endyear': str(datetime.now().year)
        }

        response = self._make_request('data/table', data)
        if not response or response.status_code != 200:
            print(f"[GermanyCPI] Failed to fetch CPI data: {response.status_code if response else 'No response'}")
            return None

        content_type = response.headers.get('Content-Type', '')

        if 'json' in content_type:
            result = response.json()
            status = result.get('Status', {})
            if status.get('Code') == 0:
                csv_content = result.get('Object', {}).get('Content', '')
                return self._parse_cpi_csv(csv_content)
            else:
                print(f"[GermanyCPI] API error: {status.get('Content')}")
                return None
        else:
            return self._parse_cpi_csv(response.text)

    def _fetch_hicp_monthly(self) -> Optional[Dict]:
        """HICPデータを取得 (Table: 61121-0002)"""
        data = {
            'name': '61121-0002',
            'area': 'all',
            'language': 'en',
            'format': 'csv',
            'job': 'false',
            'startyear': '2015',
            'endyear': str(datetime.now().year)
        }

        response = self._make_request('data/table', data)
        if not response or response.status_code != 200:
            print(f"[GermanyCPI] Failed to fetch HICP data: {response.status_code if response else 'No response'}")
            return None

        content_type = response.headers.get('Content-Type', '')

        if 'json' in content_type:
            result = response.json()
            status = result.get('Status', {})
            if status.get('Code') == 0:
                csv_content = result.get('Object', {}).get('Content', '')
                return self._parse_hicp_csv(csv_content)
            else:
                print(f"[GermanyCPI] HICP API error: {status.get('Content')}")
                return None
        else:
            return self._parse_hicp_csv(response.text)

    def _parse_cpi_csv(self, csv_content: str) -> Dict:
        """CPI CSVをパース"""
        lines = csv_content.strip().split('\n')
        data_lines = []

        for line in lines[6:]:
            if line.startswith('__') or line.startswith('"'):
                break
            if line.strip():
                data_lines.append(line)

        cpi_data = []
        for line in data_lines:
            parts = [p.strip() for p in line.split(';')]
            if len(parts) >= 5:
                year = parts[0]
                month = parts[1]
                index_value = parts[2]
                yoy_change = parts[3]
                mom_change = parts[4]

                if index_value == '...' or index_value == '':
                    continue

                try:
                    month_num = self.MONTH_MAP.get(month)
                    if not month_num:
                        continue

                    date_str = f"{year}-{month_num}-01"

                    cpi_data.append({
                        'date': date_str,
                        'index': float(index_value),
                        'yoy_change': self._parse_percent(yoy_change),
                        'mom_change': self._parse_percent(mom_change)
                    })
                except (ValueError, KeyError) as e:
                    continue

        return {'data': cpi_data, 'base_year': '2020=100'}

    def _parse_hicp_csv(self, csv_content: str) -> Dict:
        """HICP CSVをパース"""
        lines = csv_content.strip().split('\n')
        data_lines = []

        for line in lines[6:]:
            if line.startswith('__') or line.startswith('"'):
                break
            if line.strip():
                data_lines.append(line)

        hicp_data = []
        for line in data_lines:
            parts = [p.strip() for p in line.split(';')]
            if len(parts) >= 5:
                year = parts[0]
                month = parts[1]
                index_value = parts[2]
                yoy_change = parts[3]
                mom_change = parts[4]

                if index_value == '...' or index_value == '':
                    continue

                try:
                    month_num = self.MONTH_MAP.get(month)
                    if not month_num:
                        continue

                    date_str = f"{year}-{month_num}-01"

                    hicp_data.append({
                        'date': date_str,
                        'index': float(index_value),
                        'yoy_change': self._parse_percent(yoy_change),
                        'mom_change': self._parse_percent(mom_change)
                    })
                except (ValueError, KeyError) as e:
                    continue

        return {'data': hicp_data, 'base_year': '2015=100'}

    def _parse_percent(self, value: str) -> Optional[float]:
        """パーセンテージ値をパース"""
        if not value or value == '...' or value == '-':
            return None
        try:
            return float(value.replace('+', ''))
        except ValueError:
            return None

    def _merge_cpi_hicp(self, cpi_data: Optional[Dict], hicp_data: Optional[Dict]) -> List[Dict]:
        """CPIとHICPデータをマージ"""
        merged = {}

        if cpi_data:
            for point in cpi_data.get('data', []):
                date = point['date']
                merged[date] = {
                    'date': date,
                    'cpi_index': point.get('index'),
                    'cpi_yoy_change': point.get('yoy_change'),
                    'cpi_mom_change': point.get('mom_change'),
                    'hicp_index': None,
                    'hicp_yoy_change': None,
                    'hicp_mom_change': None,
                }

        if hicp_data:
            for point in hicp_data.get('data', []):
                date = point['date']
                if date in merged:
                    merged[date]['hicp_index'] = point.get('index')
                    merged[date]['hicp_yoy_change'] = point.get('yoy_change')
                    merged[date]['hicp_mom_change'] = point.get('mom_change')
                else:
                    merged[date] = {
                        'date': date,
                        'cpi_index': None,
                        'cpi_yoy_change': None,
                        'cpi_mom_change': None,
                        'hicp_index': point.get('index'),
                        'hicp_yoy_change': point.get('yoy_change'),
                        'hicp_mom_change': point.get('mom_change'),
                    }

        result = sorted(merged.values(), key=lambda x: x['date'])
        return result

    # =====================================================================
    # キャッシュ関連メソッド
    # =====================================================================

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_pattern(
            self.FMP_EVENT_PATTERN,
            last_updated_str,
            country=self.FMP_COUNTRY
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)

            if "data" in cached and isinstance(cached["data"], list):
                return cached

            # 旧形式の変換
            if "cpi_yoy" in cached or "hicp_yoy" in cached:
                return self._convert_legacy_format(cached)

            return None
        except Exception as e:
            print(f"[GermanyCPI] Failed to load file cache: {e}")
            return None

    def _convert_legacy_format(self, legacy_cache: Dict[str, Any]) -> Dict[str, Any]:
        """旧形式のキャッシュを変換"""
        merged = {}

        for key, field in [
            ("cpi_yoy", "cpi_yoy_change"),
            ("cpi_mom", "cpi_mom_change"),
            ("hicp_yoy", "hicp_yoy_change"),
            ("hicp_mom", "hicp_mom_change"),
        ]:
            for item in legacy_cache.get(key, []):
                date = item.get("date")
                if not date:
                    continue
                if date not in merged:
                    merged[date] = {
                        "date": date,
                        "cpi_index": None,
                        "cpi_yoy_change": None,
                        "cpi_mom_change": None,
                        "hicp_index": None,
                        "hicp_yoy_change": None,
                        "hicp_mom_change": None,
                    }
                merged[date][field] = item.get("value")

        return {
            "data": sorted(merged.values(), key=lambda x: x["date"]),
            "metadata": legacy_cache.get("metadata", {}),
            "next_release": legacy_cache.get("next_release"),
            "last_updated": legacy_cache.get("last_updated"),
        }

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[GermanyCPI] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Germany CPI / HICP",
            "source": "History DB + Destatis + FMP",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "next_release": get_next_release_by_pattern(
                self.FMP_EVENT_PATTERN,
                country=self.FMP_COUNTRY
            ),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
germany_cpi_service = GermanyCPIService()
