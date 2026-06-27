"""
ドイツ小売売上高サービス

指標:
- 小売売上高前年比 (Retail Sales YoY) - 45212-0005 列5(カレンダー調整指数)から計算
- 小売売上高前月比 (Retail Sales MoM) - 45212-0005 列6(カレンダー+季節調整指数)から計算

データソース:
- Destatis GENESIS API
  - 45212-0005: 実質調整済み指数（X13 JDemetra+, 2015=100）
    - 列5: kalenderbereinigt（カレンダー調整）→ YoY計算用
    - 列6: kalender- und saisonbereinigt（カレンダー+季節調整）→ MoM計算用
  - 注: 旧実装はYoYを45212-0004(原数値=未調整)から取得し公式値とズレていた（暦影響）

発表スケジュール:
- 毎月（不定期）
- プレスリリース発表から約2週間後にGENESIS/keh331テーブル更新

キャッシュ方式: FMP発表日時ベース判定方式

注意:
- MoMは季節調整済み指数（X13 JDemetra+ kalender- und saisonbereinigt）から計算
- keh331テーブル（Destatis Webサイト）と同じデータソース
- プレスリリースの速報値とGENESIS APIのデータには約2週間のタイムラグがある
"""
import json
import os
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

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "germany_retail_sales_cache.json"


class GermanyRetailSalesService:
    """ドイツ小売売上高サービス"""

    DATA_CACHE_KEY = "eurozone:germany_retail_sales:data"
    ECONALPHA_ID = "germany_retail_sales"
    FMP_COUNTRY = "DE"
    FMP_EVENT_PATTERN = "Retail Sales"

    # Destatis API設定
    DESTATIS_BASE_URL = "https://www-genesis.destatis.de/genesisWS/rest/2020"

    # 月名マッピング（ドイツ語）
    GERMAN_MONTHS = {
        'januar': 1, 'februar': 2, 'märz': 3, 'april': 4,
        'mai': 5, 'juni': 6, 'juli': 7, 'august': 8,
        'september': 9, 'oktober': 10, 'november': 11, 'dezember': 12
    }

    def __init__(self):
        self.username = os.getenv('DESTATIS_USERNAME', '')
        self.password = os.getenv('DESTATIS_PASSWORD', '')

    def get_germany_retail_sales_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        ドイツ小売売上高データを取得

        Returns:
            {
                "retail_sales_yoy": [...],  # 前年比データ配列
                "retail_sales_mom": [...],  # 前月比データ配列
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
                        "retail_sales_yoy": cached_data.get("retail_sales_yoy", []),
                        "retail_sales_mom": cached_data.get("retail_sales_mom", []),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # Destatis APIから季節調整済みデータを取得
        destatis_data = self._load_from_destatis()

        yoy_data = destatis_data.get("yoy", [])
        mom_data = destatis_data.get("mom", [])

        if yoy_data or mom_data:
            next_release = get_next_release_by_pattern(
                self.FMP_EVENT_PATTERN,
                country=self.FMP_COUNTRY
            )

            cache_payload = {
                "retail_sales_yoy": yoy_data,
                "retail_sales_mom": mom_data,
                "metadata": {
                    "source": "Destatis",
                    "country": "Germany (DE)",
                    "table": "45212-0005 (実質調整済み指数: 列6→MoM, 列5→YoY)",
                    "description": "ドイツ小売売上高（実質・調整済み）",
                    "unit": "%",
                    "adjustment": "X13 JDemetra+ (MoM=kalender- und saisonbereinigt, YoY=kalenderbereinigt)",
                    "note": "MoMはX13カレンダー+季節調整指数(列6)、YoYはカレンダー調整指数(列5)から計算。Destatis公式headline/Eurostatと一致。プレスリリース速報から約2週間後にGENESIS更新(改定あり)",
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "retail_sales_yoy": yoy_data,
                "retail_sales_mom": mom_data,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "destatis",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "retail_sales_yoy": file_cache.get("retail_sales_yoy", []),
                "retail_sales_mom": file_cache.get("retail_sales_mom", []),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "retail_sales_yoy": [],
            "retail_sales_mom": [],
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_destatis(self) -> Dict[str, List[Dict[str, Any]]]:
        """Destatis GENESIS APIから調整済み小売売上高データを取得

        テーブル 45212-0005（実質・in konstanten Preisen）の調整済み指数を使用:
        - 列5: X13 JDemetra+ kalenderbereinigt（カレンダー調整済み指数）→ YoY計算用
        - 列6: X13 JDemetra+ kalender- und saisonbereinigt（カレンダー+季節調整済み指数）→ MoM計算用

        MoMは季節+カレンダー調整(列6)、YoYはカレンダー調整(列5)から計算する。
        これがDestatis公式headline／Eurostatと一致する基準。
        旧実装は YoY を 45212-0004（原数値=未調整）から取得していたため、暦影響の大きい月
        (例: 2026-04 で -2.3% vs 正しい +0.1%) で公式値と大きくズレていた。
        """
        print("[GermanyRetailSales] Fetching data from Destatis API...")

        # テーブル45212-0005から調整済み指数(列5/列6)を取得
        index_records = self._fetch_index_from_45212_0005()

        # MoM = 季節+カレンダー調整指数(列6)から、YoY = カレンダー調整指数(列5)から計算
        mom_data = self._calculate_mom_from_index(index_records)
        yoy_data = self._calculate_yoy_from_index(index_records)

        return {"yoy": yoy_data, "mom": mom_data}

    def _fetch_index_from_45212_0005(self) -> List[Dict[str, Any]]:
        """45212-0005テーブルから調整済み指数(列5=カレンダー調整, 列6=カレンダー+季節調整)を取得

        テーブルが大きいため、年ごとに分割して取得。
        各レコードは {'date', 'index'(=列6), 'index_cal'(=列5)} を持つ。
        """
        all_index_data = []

        # 年ごとに分割して取得（2015年から現在まで）
        current_year = datetime.now().year
        for year in range(2015, current_year + 2):
            index_data = self._fetch_45212_0005_for_year(year)
            all_index_data.extend(index_data)

        print(f"[GermanyRetailSales] Total: {len(all_index_data)} index records from 45212-0005")
        return all_index_data

    def _fetch_45212_0005_for_year(self, year: int) -> List[Dict[str, Any]]:
        """45212-0005テーブルから特定年の季節調整済み指数を取得"""
        url = f"{self.DESTATIS_BASE_URL}/data/table"
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'username': self.username,
            'password': self.password
        }
        data = {
            'name': '45212-0005',
            'area': 'all',
            'language': 'de',
            'format': 'datencsv',
            'job': 'false',
            'startyear': str(year),
            'endyear': str(year),
            'classifyingvariable1': 'WZ08E6',
            'classifyingkey1': 'WZ08-47',
        }

        try:
            response = requests.post(url, headers=headers, data=data, timeout=30)
            if response.status_code != 200:
                return []

            result = response.json()
            if result.get('Status', {}).get('Code') != 0:
                return []

            content = result.get('Object', {}).get('Content', '')
            return self._parse_sa_index_csv(content)

        except Exception as e:
            print(f"[GermanyRetailSales] Error fetching 45212-0005 for {year}: {e}")
            return []

    def _parse_sa_index_csv(self, csv_content: str) -> List[Dict[str, Any]]:
        """45212-0005のCSVをパースして調整済み指数を抽出

        列構成 (実質 in konstanten Preisen):
        - 列4: Originalwerte（原数値）
        - 列5: X13 JDemetra+ kalenderbereinigt（カレンダー調整済み）→ YoY用
        - 列6: X13 JDemetra+ kalender- und saisonbereinigt（カレンダー+季節調整済み）→ MoM用
        """
        index_data = []
        lines = csv_content.strip().split('\n')

        for line in lines:
            if not line.startswith('WZ08-47;'):
                continue

            parts = [p.strip() for p in line.split(';')]
            if len(parts) < 7:
                continue

            try:
                year = parts[2]
                month_de = parts[3].lower()
                month_num = self.GERMAN_MONTHS.get(month_de)
                if not month_num:
                    continue

                # 列6: X13 kalender- und saisonbereinigt（MoM用、必須）
                sa_index_str = parts[6]
                if not sa_index_str or sa_index_str in ('...', '-'):
                    continue
                sa_index = float(sa_index_str.replace(',', '.'))

                # 列5: X13 kalenderbereinigt（YoY用、欠損許容）
                cal_index = None
                cal_index_str = parts[5]
                if cal_index_str and cal_index_str not in ('...', '-'):
                    cal_index = float(cal_index_str.replace(',', '.'))

                date_str = f"{year}-{month_num:02d}-01"
                index_data.append({
                    'date': date_str,
                    'index': sa_index,       # 列6: カレンダー+季節調整（MoM用）
                    'index_cal': cal_index,  # 列5: カレンダー調整（YoY用）
                })

            except (ValueError, IndexError):
                continue

        return index_data

    def _calculate_mom_from_index(self, index_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """季節調整済み指数からMoMを計算

        計算式: MoM = ((当月指数 - 前月指数) / 前月指数) * 100
        """
        if len(index_data) < 2:
            return []

        # 日付順にソート
        sorted_data = sorted(index_data, key=lambda x: x['date'])

        mom_data = []
        for i in range(1, len(sorted_data)):
            prev = sorted_data[i - 1]
            curr = sorted_data[i]

            if prev['index'] and prev['index'] != 0:
                mom = round((curr['index'] - prev['index']) / prev['index'] * 100, 1)
                mom_data.append({
                    'date': curr['date'],
                    'value': mom,
                })

        return mom_data

    def _calculate_yoy_from_index(self, index_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """カレンダー調整済み指数(列5)から前年同月比(YoY)を計算

        計算式: YoY = ((当月指数 - 前年同月指数) / 前年同月指数) * 100
        YoYは季節性が同月比較で相殺されるため、カレンダー調整のみ(列5)を用いる。
        これがDestatis公式headline／Eurostat(DE, calendar adjusted)と一致する。
        """
        # 日付→カレンダー調整済み指数のマップ（列5が欠損する月はスキップ）
        cal_by_date = {
            item['date']: item['index_cal']
            for item in index_data
            if item.get('index_cal') is not None
        }

        yoy_data = []
        for date_str, cal_index in sorted(cal_by_date.items()):
            # 前年同月の日付キー（YYYY-MM-01 の年を-1）
            year = int(date_str[:4])
            prev_year_date = f"{year - 1}{date_str[4:]}"
            prev_index = cal_by_date.get(prev_year_date)

            if prev_index and prev_index != 0:
                yoy = round((cal_index - prev_index) / prev_index * 100, 1)
                yoy_data.append({
                    'date': date_str,
                    'value': yoy,
                })

        return yoy_data

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
            print(f"[GermanyRetailSales] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[GermanyRetailSales] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Germany Retail Sales (Seasonally Adjusted)",
            "source": "Destatis + FMP",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "yoy_count": len(cached_data.get("retail_sales_yoy", [])) if cached_data else 0,
            "mom_count": len(cached_data.get("retail_sales_mom", [])) if cached_data else 0,
            "next_release": get_next_release_by_pattern(
                self.FMP_EVENT_PATTERN,
                country=self.FMP_COUNTRY
            ),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
germany_retail_sales_service = GermanyRetailSalesService()
