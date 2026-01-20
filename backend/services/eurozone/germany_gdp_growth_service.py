"""
ドイツGDP成長率サービス
Destatis GENESIS APIおよびFMP DBからGDP成長率データを取得

指標:
- GDP成長率 前期比 (QoQ) - テーブル 81000-0002
- GDP成長率 前年比 (YoY) - テーブル 81000-0002

データソース:
1. Destatis GENESIS API - 確報値（季節調整済み）
2. FMP economic_calendar_events - 速報値

発表スケジュール:
- 速報: 四半期終了後約30日
- 確定: 四半期終了後約55日

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

from dotenv import load_dotenv
load_dotenv()

from core.redis_client import redis_client
from services.eurozone.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")
CET = ZoneInfo("Europe/Berlin")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "germany_gdp_growth_cache.json"


class GermanyGDPGrowthService:
    """ドイツGDP成長率サービス"""

    DATA_CACHE_KEY = "eurozone:germany_gdp_growth:data"
    ECONALPHA_ID = "de_gdp_growth"
    FMP_COUNTRY = "DE"
    FMP_EVENT_PATTERN = "GDP Growth Rate"

    # Destatis API設定
    DESTATIS_BASE_URL = "https://www-genesis.destatis.de/genesisWS/rest/2020"

    # ドイツ語の四半期名マッピング
    GERMAN_QUARTERS = {
        '1. quartal': 1, '1. vierteljahr': 1, '1.quartal': 1,
        '2. quartal': 2, '2. vierteljahr': 2, '2.quartal': 2,
        '3. quartal': 3, '3. vierteljahr': 3, '3.quartal': 3,
        '4. quartal': 4, '4. vierteljahr': 4, '4.quartal': 4,
    }

    # 英語の四半期名マッピング
    ENGLISH_QUARTERS = {
        '1st quarter': 1, 'q1': 1, 'first quarter': 1,
        '2nd quarter': 2, 'q2': 2, 'second quarter': 2,
        '3rd quarter': 3, 'q3': 3, 'third quarter': 3,
        '4th quarter': 4, 'q4': 4, 'fourth quarter': 4,
    }

    def __init__(self):
        self.username = os.getenv('DESTATIS_USERNAME', '')
        self.password = os.getenv('DESTATIS_PASSWORD', '')

    def get_germany_gdp_growth_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        ドイツGDP成長率データを取得

        Returns:
            {
                "gdp_growth_qoq": [...],  # 前期比データ配列
                "gdp_growth_yoy": [...],  # 前年比データ配列
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
                        "gdp_growth_qoq": cached_data.get("gdp_growth_qoq", []),
                        "gdp_growth_yoy": cached_data.get("gdp_growth_yoy", []),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # 1. Destatis APIからデータを取得
        destatis_data = self._load_from_destatis()

        # 2. FMP DBから速報データを取得
        fmp_data = self._load_from_fmp_db()

        # 3. データをマージ
        merged_data = self._merge_data_sources(destatis_data, fmp_data)

        qoq_data = merged_data.get("qoq", [])
        yoy_data = merged_data.get("yoy", [])

        # Destatisからデータが取得できなかった場合（API障害等）、ファイルキャッシュを優先
        destatis_qoq_count = len(destatis_data.get("qoq", []))
        if destatis_qoq_count == 0:
            print("[GermanyGDPGrowth] Destatis API failed, checking file cache...")
            file_cache = self._load_file_cache()
            if file_cache and len(file_cache.get("gdp_growth_qoq", [])) > len(qoq_data):
                print(f"[GermanyGDPGrowth] Using file cache ({len(file_cache.get('gdp_growth_qoq', []))} records)")
                # FMPの最新データでファイルキャッシュを補完
                cached_qoq = {d["date"]: d for d in file_cache.get("gdp_growth_qoq", [])}
                cached_yoy = {d["date"]: d for d in file_cache.get("gdp_growth_yoy", [])}
                for d in fmp_data.get("qoq", []):
                    if d["date"] not in cached_qoq:
                        cached_qoq[d["date"]] = d
                for d in fmp_data.get("yoy", []):
                    if d["date"] not in cached_yoy:
                        cached_yoy[d["date"]] = d
                qoq_data = sorted(cached_qoq.values(), key=lambda x: x["date"])
                yoy_data = sorted(cached_yoy.values(), key=lambda x: x["date"])

        if qoq_data or yoy_data:
            next_release = get_next_release_by_pattern(
                self.FMP_EVENT_PATTERN,
                country=self.FMP_COUNTRY
            )

            cache_payload = {
                "gdp_growth_qoq": qoq_data,
                "gdp_growth_yoy": yoy_data,
                "metadata": {
                    "source": "Destatis + FMP",
                    "country": "Germany (DE)",
                    "table": "81000-0002",
                    "description": "ドイツGDP成長率",
                    "unit": "%",
                    "qoq_adjustment": "price, seasonal and calendar adjusted (preisbereinigt, saison- und kalenderbereinigt)",
                    "yoy_adjustment": "price adjusted (preisbereinigt)",
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            # ファイルキャッシュは Destatis 成功時のみ更新（API障害時に上書きしない）
            if destatis_qoq_count > 0:
                self._save_file_cache(cache_payload)

            return {
                "gdp_growth_qoq": qoq_data,
                "gdp_growth_yoy": yoy_data,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "destatis + fmp" if destatis_qoq_count > 0 else "file_cache + fmp",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック（FMPもない場合）
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "gdp_growth_qoq": file_cache.get("gdp_growth_qoq", []),
                "gdp_growth_yoy": file_cache.get("gdp_growth_yoy", []),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "gdp_growth_qoq": [],
            "gdp_growth_yoy": [],
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_destatis(self) -> Dict[str, List[Dict[str, Any]]]:
        """Destatis GENESIS APIからGDP成長率データを取得"""
        print("[GermanyGDPGrowth] Fetching data from Destatis API...")

        url = f"{self.DESTATIS_BASE_URL}/data/table"
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'username': self.username,
            'password': self.password
        }
        data = {
            'name': '81000-0002',
            'area': 'all',
            'language': 'de',
            'format': 'datencsv',
            'job': 'false',
            'startyear': '2000',
            'endyear': str(datetime.now().year + 1),
        }

        try:
            response = requests.post(url, headers=headers, data=data, timeout=30)
            if response.status_code != 200:
                print(f"[GermanyGDPGrowth] Destatis API error: {response.status_code}")
                return {"qoq": [], "yoy": []}

            result = response.json()
            if result.get('Status', {}).get('Code') != 0:
                print(f"[GermanyGDPGrowth] Destatis API error: {result.get('Status', {}).get('Content')}")
                return {"qoq": [], "yoy": []}

            content = result.get('Object', {}).get('Content', '')
            return self._parse_destatis_csv(content)

        except Exception as e:
            print(f"[GermanyGDPGrowth] Error fetching from Destatis: {e}")
            return {"qoq": [], "yoy": []}

    def _parse_destatis_csv(self, csv_content: str) -> Dict[str, List[Dict[str, Any]]]:
        """Destatis CSVをパースしてQoQとYoYを抽出

        テーブル81000-0002はピボット形式:
        - 行7: 年ヘッダー (2020;2020;2020;2020;2021;...)
        - 行8: 四半期ヘッダー (1. Quartal;2. Quartal;3. Quartal;4. Quartal;...)

        公式発表に合わせたデータ抽出（CSVの末尾ドキュメントに基づく）:
        - YoY (前年比): Originalwerte; preisbereinigt, Kettenindex; Veränderung
          → 「Veränderung gegenüber dem Vorjahresquartal in %」= 価格調整済み前年同期比
        - QoQ (前期比): X13 JDemetra+ kalender- und saisonbereinigt; preisbereinigt, Kettenindex; Veränderung
          → 「Veränderung gegenüber dem Vorquartal in %」= 価格・季節・カレンダー調整済み前期比
        """
        qoq_data = []
        yoy_data = []

        lines = csv_content.strip().split('\n')
        print(f"[GermanyGDPGrowth] Parsing {len(lines)} lines from Destatis (pivot format)")

        if len(lines) < 40:
            print("[GermanyGDPGrowth] Unexpected CSV format - too few lines")
            return {"qoq": [], "yoy": []}

        # 年と四半期のヘッダーを解析（行7, 8）
        year_header = None
        quarter_header = None
        for i, line in enumerate(lines):
            parts = [p.strip() for p in line.split(';')]
            # 年ヘッダーを探す（4列目以降が年の連続）
            if len(parts) > 4 and re.match(r'^\d{4}$', parts[4]):
                year_header = parts
                print(f"[GermanyGDPGrowth] Found year header at line {i}")
            # 四半期ヘッダーを探す
            if len(parts) > 4 and '1. Quartal' in parts[4]:
                quarter_header = parts
                print(f"[GermanyGDPGrowth] Found quarter header at line {i}")
                break

        if not year_header or not quarter_header:
            print("[GermanyGDPGrowth] Could not find year/quarter headers")
            return {"qoq": [], "yoy": []}

        # 四半期インデックスを構築（列インデックス -> (年, 四半期)）
        quarter_map = {}
        for col_idx in range(4, len(year_header)):
            year_str = year_header[col_idx] if col_idx < len(year_header) else None
            quarter_str = quarter_header[col_idx] if col_idx < len(quarter_header) else None

            if year_str and re.match(r'^\d{4}$', year_str):
                year = int(year_str)
                quarter = None
                if quarter_str:
                    q_lower = quarter_str.lower()
                    for qname, qnum in self.GERMAN_QUARTERS.items():
                        if qname in q_lower:
                            quarter = qnum
                            break
                if quarter:
                    quarter_map[col_idx] = (year, quarter)

        print(f"[GermanyGDPGrowth] Built quarter map with {len(quarter_map)} entries")

        # データ行を解析
        for line in lines:
            parts = [p.strip() for p in line.split(';')]
            if len(parts) < 5:
                continue

            # YoY行を特定（Originalwerte; preisbereinigt, Kettenindex; Bruttoinlandsprodukt (Veränderung)）
            # ドキュメント: 「Originalwerte: Veränderung gegenüber dem Vorjahresquartal in %」
            is_yoy_row = (
                'Originalwerte' in parts[0] and
                'preisbereinigt' in parts[1] and
                'Kettenindex' in parts[1] and
                'Bruttoinlandsprodukt' in parts[2] and
                'Veränderung' in parts[2]
            )

            # QoQ行を特定（X13 JDemetra+ kalender- und saisonbereinigt; preisbereinigt, Kettenindex; Bruttoinlandsprodukt (Veränderung)）
            # ドキュメント: 「Kalender- und saisonbereinigte Werte: Veränderung gegenüber dem Vorquartal in %」
            is_qoq_row = (
                'X13' in parts[0] and
                'saisonbereinigt' in parts[0] and
                'preisbereinigt' in parts[1] and
                'Kettenindex' in parts[1] and
                'Bruttoinlandsprodukt' in parts[2] and
                'Veränderung' in parts[2]
            )

            if is_yoy_row or is_qoq_row:
                target_list = yoy_data if is_yoy_row else qoq_data

                for col_idx, (year, quarter) in quarter_map.items():
                    if col_idx < len(parts):
                        value_str = parts[col_idx].replace(',', '.').replace('+', '').strip()
                        if value_str and value_str not in ['...', '-', '.', '']:
                            try:
                                value = float(value_str)
                                date_str = f"{year}-Q{quarter}"
                                target_list.append({
                                    'date': date_str,
                                    'value': value,
                                })
                            except ValueError:
                                pass

        # 日付でソート
        qoq_data.sort(key=lambda x: x['date'])
        yoy_data.sort(key=lambda x: x['date'])

        print(f"[GermanyGDPGrowth] Parsed {len(qoq_data)} QoQ, {len(yoy_data)} YoY records from Destatis")
        return {"qoq": qoq_data, "yoy": yoy_data}

    def _load_from_fmp_db(self) -> Dict[str, List[Dict[str, Any]]]:
        """FMP economic_calendar_eventsからGDP成長率データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                query = text("""
                    SELECT datetime_utc, event, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'DE'
                      AND (
                          event ILIKE '%GDP Growth Rate QoQ%'
                          OR event ILIKE '%GDP Growth Rate YoY%'
                          OR event ILIKE '%Gross Domestic Product QoQ%'
                          OR event ILIKE '%Gross Domestic Product YoY%'
                      )
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query).fetchall()

                qoq_map: Dict[str, Dict[str, Any]] = {}
                yoy_map: Dict[str, Dict[str, Any]] = {}

                for row in rows:
                    dt_utc, event, actual, estimate, previous = row
                    if not dt_utc:
                        continue

                    # 四半期を計算
                    quarter = (dt_utc.month - 1) // 3 + 1
                    # 発表日の前四半期のデータとして記録
                    if dt_utc.month <= 3:
                        target_year = dt_utc.year - 1
                        target_quarter = 4
                    else:
                        target_year = dt_utc.year
                        target_quarter = quarter - 1 if quarter > 1 else 4

                    date_str = f"{target_year}-Q{target_quarter}"
                    event_lower = event.lower()

                    data_point = {
                        'date': date_str,
                        'value': float(actual) if actual is not None else None,
                        'forecast': float(estimate) if estimate is not None else None,
                        'previous': float(previous) if previous is not None else None,
                        'source': 'fmp',
                    }

                    if 'qoq' in event_lower:
                        if date_str not in qoq_map:
                            qoq_map[date_str] = data_point
                    elif 'yoy' in event_lower:
                        if date_str not in yoy_map:
                            yoy_map[date_str] = data_point

                qoq_data = sorted(qoq_map.values(), key=lambda x: x['date'])
                yoy_data = sorted(yoy_map.values(), key=lambda x: x['date'])

                print(f"[GermanyGDPGrowth] Loaded {len(qoq_data)} QoQ, {len(yoy_data)} YoY records from FMP DB")
                return {"qoq": qoq_data, "yoy": yoy_data}

        except Exception as e:
            print(f"[GermanyGDPGrowth] Error loading from FMP DB: {e}")
            return {"qoq": [], "yoy": []}

    def _merge_data_sources(
        self,
        destatis_data: Dict[str, List[Dict[str, Any]]],
        fmp_data: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Destatis確報とFMP速報をマージ
        Destatis確報を優先し、最新期はFMP速報で補完
        """
        merged_qoq: Dict[str, Dict[str, Any]] = {}
        merged_yoy: Dict[str, Dict[str, Any]] = {}

        # 1. Destatis確報をベースに
        for d in destatis_data.get("qoq", []):
            merged_qoq[d["date"]] = d.copy()
            merged_qoq[d["date"]]["source"] = "destatis"

        for d in destatis_data.get("yoy", []):
            merged_yoy[d["date"]] = d.copy()
            merged_yoy[d["date"]]["source"] = "destatis"

        # 2. FMP速報で補完（Destatisにないものだけ追加）
        for d in fmp_data.get("qoq", []):
            if d["date"] not in merged_qoq:
                merged_qoq[d["date"]] = d.copy()

        for d in fmp_data.get("yoy", []):
            if d["date"] not in merged_yoy:
                merged_yoy[d["date"]] = d.copy()

        qoq_result = sorted(merged_qoq.values(), key=lambda x: x["date"])
        yoy_result = sorted(merged_yoy.values(), key=lambda x: x["date"])

        return {"qoq": qoq_result, "yoy": yoy_result}

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
            return cached
        except Exception as e:
            print(f"[GermanyGDPGrowth] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[GermanyGDPGrowth] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Germany GDP Growth Rate",
            "source": "Destatis + FMP",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "qoq_count": len(cached_data.get("gdp_growth_qoq", [])) if cached_data else 0,
            "yoy_count": len(cached_data.get("gdp_growth_yoy", [])) if cached_data else 0,
            "next_release": get_next_release_by_pattern(
                self.FMP_EVENT_PATTERN,
                country=self.FMP_COUNTRY
            ),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
germany_gdp_growth_service = GermanyGDPGrowthService()
