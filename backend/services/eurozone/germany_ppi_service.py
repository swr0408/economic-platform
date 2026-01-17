"""
ドイツPPIサービス
DB積み上げ方式：Destatis（確報値）+ FMP（速報値）を統合

指標:
- PPI (Producer Price Index) - 生産者物価指数
- 前年比 (YoY)
- 前月比 (MoM)
- 指数値 (Index)

データソース（優先順位）:
1. germany_ppi_history テーブル - 長期時系列データ（ベース）
2. Destatis GENESIS API - 確報値で上書き更新
3. economic_calendar_events - FMP速報値で上書き更新

発表スケジュール:
- 発表日: 毎月4日〜23日頃
- 発表時刻: 15:00-16:10 CET（冬時間: 16:00-16:10 CET）

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

# 環境変数をロード（シングルトン作成前に必要）
from dotenv import load_dotenv
load_dotenv()

from core.redis_client import redis_client
from services.eurozone.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")
CET = ZoneInfo("Europe/Berlin")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "germany_ppi_cache.json"


class GermanyPPIService:
    """ドイツPPIサービス (DB積み上げ方式)"""

    DATA_CACHE_KEY = "eurozone:germany_ppi:data"
    ECONALPHA_ID = "germany_ppi"
    FMP_COUNTRY = "DE"
    FMP_EVENT_PATTERN = "Producer Price Index"

    # Destatis API設定
    BASE_URL = "https://www-genesis.destatis.de/genesisWS/rest/2020"

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

    def get_germany_ppi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        ドイツPPIデータを取得

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
                    "ppi_table": "61241-0002",
                    "base_year": "2021=100",
                    "description": "ドイツ生産者物価指数（PPI）",
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
        """
        germany_ppi_historyテーブルから長期時系列データを取得

        Note: このテーブルは現在存在しない（Destatis APIで十分なため）
        将来的に長期データが必要な場合に使用
        """
        # germany_ppi_historyテーブルは現在未作成
        # Destatis APIから2015年以降のデータを取得可能なため、
        # historyテーブルは不要
        return []

    def _load_from_destatis(self) -> List[Dict[str, Any]]:
        """Destatis GENESIS APIから確報データを取得"""
        print("[GermanyPPI] Fetching data from Destatis API...")

        ppi_data = self._fetch_ppi_monthly()

        if not ppi_data:
            print("[GermanyPPI] Failed to fetch data from Destatis API")
            return []

        result = []
        for point in ppi_data.get('data', []):
            result.append({
                'date': point['date'],
                'ppi_index': point.get('index'),
                'ppi_yoy_change': point.get('yoy_change'),
                'ppi_mom_change': point.get('mom_change'),
                'source': 'destatis',
                'is_preliminary': False,
            })

        print(f"[GermanyPPI] Loaded {len(result)} records from Destatis API")
        return result

    def _load_from_fmp_db(self) -> List[Dict[str, Any]]:
        """FMP economic_calendar_eventsから速報データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                # PPI YoY, PPI MoMを取得
                query = text("""
                    SELECT datetime_utc, event, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'DE'
                      AND (
                          event ILIKE '%Producer Price Index YoY%'
                          OR event ILIKE '%Producer Price Index MoM%'
                          OR event ILIKE '%PPI YoY%'
                          OR event ILIKE '%PPI MoM%'
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
                            "ppi_index": None,
                            "ppi_yoy_change": None,
                            "ppi_mom_change": None,
                            "source": "fmp",
                            "is_preliminary": True,
                        }

                    # イベント種別に応じて値を設定
                    event_lower = event.lower()
                    value = float(actual) if actual is not None else None

                    if 'yoy' in event_lower:
                        date_map[target_date]["ppi_yoy_change"] = value
                    elif 'mom' in event_lower:
                        date_map[target_date]["ppi_mom_change"] = value

                result = sorted(date_map.values(), key=lambda x: x["date"])
                print(f"[GermanyPPI] Loaded {len(result)} records from FMP DB")
                return result

        except Exception as e:
            print(f"[GermanyPPI] Error loading from FMP DB: {e}")
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
                for key in ["ppi_index", "ppi_yoy_change", "ppi_mom_change"]:
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
                for key in ["ppi_yoy_change", "ppi_mom_change"]:
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
        """
        if len(data) < 2:
            return data

        for i in range(1, len(data)):
            current = data[i]
            previous = data[i - 1]

            # PPI前月比がnullで、両方のインデックスが存在する場合
            if current.get("ppi_mom_change") is None:
                curr_idx = current.get("ppi_index")
                prev_idx = previous.get("ppi_index")
                if curr_idx is not None and prev_idx is not None and prev_idx != 0:
                    # 前月比を計算: ((current - previous) / previous) * 100
                    mom_change = round((curr_idx - prev_idx) / prev_idx * 100, 1)
                    current["ppi_mom_change"] = mom_change

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
            print(f"[GermanyPPI] Request error: {e}")
            return None

    def _fetch_ppi_monthly(self) -> Optional[Dict]:
        """PPIデータを取得 (Table: 61241-0002)"""
        data = {
            'name': '61241-0002',
            'area': 'all',
            'language': 'en',
            'format': 'csv',
            'job': 'false',
            'startyear': '2015',
            'endyear': str(datetime.now().year)
        }

        response = self._make_request('data/table', data)
        if not response or response.status_code != 200:
            print(f"[GermanyPPI] Failed to fetch PPI data: {response.status_code if response else 'No response'}")
            return None

        content_type = response.headers.get('Content-Type', '')

        if 'json' in content_type:
            result = response.json()
            status = result.get('Status', {})
            if status.get('Code') == 0:
                csv_content = result.get('Object', {}).get('Content', '')
                return self._parse_ppi_csv(csv_content)
            else:
                print(f"[GermanyPPI] API error: {status.get('Content')}")
                return None
        else:
            return self._parse_ppi_csv(response.text)

    def _parse_ppi_csv(self, csv_content: str) -> Dict:
        """PPI CSVをパース"""
        lines = csv_content.strip().split('\n')
        data_lines = []

        for line in lines[6:]:
            if line.startswith('__') or line.startswith('"'):
                break
            if line.strip():
                data_lines.append(line)

        ppi_data = []
        for line in data_lines:
            parts = [p.strip() for p in line.split(';')]
            if len(parts) >= 5:
                year = parts[0]
                month = parts[1]
                index_value = parts[2]
                # CSV列順: Index, MoM, YoY
                mom_change = parts[3]
                yoy_change = parts[4]

                if index_value == '...' or index_value == '':
                    continue

                try:
                    month_num = self.MONTH_MAP.get(month)
                    if not month_num:
                        continue

                    date_str = f"{year}-{month_num}-01"

                    ppi_data.append({
                        'date': date_str,
                        'index': float(index_value),
                        'yoy_change': self._parse_percent(yoy_change),
                        'mom_change': self._parse_percent(mom_change)
                    })
                except (ValueError, KeyError) as e:
                    continue

        return {'data': ppi_data, 'base_year': '2021=100'}

    def _parse_percent(self, value: str) -> Optional[float]:
        """パーセンテージ値をパース"""
        if not value or value == '...' or value == '-':
            return None
        try:
            return float(value.replace('+', ''))
        except ValueError:
            return None

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
            if "ppi_yoy" in cached or "ppi_mom" in cached:
                return self._convert_legacy_format(cached)

            return None
        except Exception as e:
            print(f"[GermanyPPI] Failed to load file cache: {e}")
            return None

    def _convert_legacy_format(self, legacy_cache: Dict[str, Any]) -> Dict[str, Any]:
        """旧形式のキャッシュを変換"""
        merged = {}

        for key, field in [
            ("ppi_yoy", "ppi_yoy_change"),
            ("ppi_mom", "ppi_mom_change"),
        ]:
            for item in legacy_cache.get(key, []):
                date = item.get("date")
                if not date:
                    continue
                if date not in merged:
                    merged[date] = {
                        "date": date,
                        "ppi_index": None,
                        "ppi_yoy_change": None,
                        "ppi_mom_change": None,
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
            print(f"[GermanyPPI] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Germany PPI",
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
germany_ppi_service = GermanyPPIService()
