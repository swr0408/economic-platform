"""
日本 小売業販売額サービス
商業動態統計調査（速報）データを取得

指標:
- Retail Sales MoM: 前月比 (%)
- Retail Sales YoY: 前年同月比 (%)
- Sales Amount: 販売額（10億円）

データソース（優先順位）:
1. jp_retail_sales_history テーブル - 長期時系列データ（ベース）
2. e-Stat Excel - 直近15ヶ月（上書き更新）
3. economic_calendar_events - FMP最新データ（上書き更新）

発表スケジュール:
- 毎月下旬（25〜31日）8:50 JST

キャッシュ方式: FMP発表日時ベース判定方式
"""
import io
import json
import requests
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.japan.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)
from services.japan.estat_file_source import download_estat_excel


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "retail_sales_cache.json"

# e-Stat 商業動態統計速報の statInfId を Data Catalog API で動的解決する。
# 速報ファイルはリリース毎に statInfId がローテートするため固定 ID 直叩きだと
# 古い版に固着する（旧実装の固定 ID 000040349027 は 2025-08 止まりの古い版を返し、
# 直近月は FMP だけが供給していた）。
# 政府統計コード 00550030 = 商業動態統計調査。
# テーブル名は毎月「商業動態統計速報(YYYY年M月分)」と変わるため、共通部分文字列で
# フィルタし公開日降順の先頭（=最新月）を取得する。
ESTAT_STATS_CODE = "00550030"
ESTAT_TABLE_FILTER = "商業動態統計速報"

# API 失敗時の既知 statInfId（新しい順）
FALLBACK_STAT_INF_IDS = [
    "000040469855",  # 商業動態統計速報(2026年5月分)
    "000040460829",  # 商業動態統計速報(2026年4月分)
    "000040450874",  # 商業動態統計速報(2026年3月分)
]


class RetailSalesService:
    """日本 小売業販売額サービス"""

    DATA_CACHE_KEY = "japan:consumer:retail_sales:data"

    ECONALPHA_IDS = {
        "mom": "jp_retail_sales_mom",
        "yoy": "jp_retail_sales_yoy",
    }

    EVENT_PATTERNS = {
        "mom": "Retail Sales MoM",
        "yoy": "Retail Sales YoY",
    }

    def __init__(self):
        pass

    def get_retail_sales_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        小売業販売額データを取得

        Returns:
            {
                "mom": {"data": [...], "latest": {...}},
                "yoy": {"data": [...], "latest": {...}},
                "next_release": {...},
                "cached": bool,
                "source": str
            }
        """
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "mom": cached_data.get("mom"),
                        "yoy": cached_data.get("yoy"),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # 1. 履歴DBからベースデータを取得（長期時系列）
        history_data = self._load_from_history_db()

        # 2. e-Stat Excelから直近データを取得
        estat_data = self._load_from_estat()

        # 3. FMP DBから最新データを取得
        fmp_mom_data = self._load_from_fmp_db("mom")
        fmp_yoy_data = self._load_from_fmp_db("yoy")

        # データをマージ（履歴DB → e-Stat → FMP の順で上書き）
        mom_data = self._merge_three_sources(
            history_data.get("mom", []),
            estat_data.get("mom", []),
            fmp_mom_data
        )
        yoy_data = self._merge_three_sources(
            history_data.get("yoy", []),
            estat_data.get("yoy", []),
            fmp_yoy_data
        )

        if mom_data or yoy_data:
            next_release = get_next_release_from_fmp(self.ECONALPHA_IDS["yoy"])
            now_str = datetime.now(JST).isoformat()
            # 発表レース対策ラグガード: 主要系列(yoy、無ければmom)の最新月が既存キャッシュを
            # 超えていなければ last_updated を据え置き、次回再取得で新月を自己回復させる。
            _new_date = (yoy_data[-1].get("date") if yoy_data else
                         (mom_data[-1].get("date") if mom_data else None))
            _existing = redis_client.get(self.DATA_CACHE_KEY)
            _old_date = None
            if isinstance(_existing, dict):
                for _k in ("yoy", "mom"):
                    _s = _existing.get(_k)
                    if isinstance(_s, dict) and isinstance(_s.get("latest"), dict):
                        _old_date = _s["latest"].get("date")
                        if _old_date:
                            break
            if _existing and _old_date and _new_date and _new_date <= _old_date:
                last_updated = _existing.get("last_updated", now_str)
            else:
                last_updated = now_str

            cache_payload = {
                "mom": {
                    "data": mom_data,
                    "latest": mom_data[-1] if mom_data else None,
                } if mom_data else None,
                "yoy": {
                    "data": yoy_data,
                    "latest": yoy_data[-1] if yoy_data else None,
                } if yoy_data else None,
                "next_release": next_release,
                "last_updated": last_updated
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                **cache_payload,
                "cached": False,
                "source": "history_db + e-Stat + FMP",
            }

        # フォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "mom": file_cache.get("mom"),
                "yoy": file_cache.get("yoy"),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "mom": None,
            "yoy": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _load_from_history_db(self) -> Dict[str, List[Dict[str, Any]]]:
        """jp_retail_sales_historyテーブルから長期時系列データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                query = text("""
                    SELECT date, sales_amount, yoy_change, mom_change
                    FROM jp_retail_sales_history
                    ORDER BY date ASC
                """)
                rows = session.execute(query).fetchall()

                yoy_data = []
                mom_data = []

                for row in rows:
                    date_val, sales_amount, yoy_change, mom_change = row
                    date_str = date_val.strftime('%Y-%m-%d') if hasattr(date_val, 'strftime') else str(date_val)

                    if yoy_change is not None:
                        yoy_data.append({
                            "date": date_str,
                            "value": float(yoy_change),
                            "sales_amount": float(sales_amount) if sales_amount else None,
                        })
                    if mom_change is not None:
                        mom_data.append({
                            "date": date_str,
                            "value": float(mom_change),
                            "sales_amount": float(sales_amount) if sales_amount else None,
                        })

                print(f"Loaded {len(yoy_data)} YoY, {len(mom_data)} MoM records from history DB")
                return {"yoy": yoy_data, "mom": mom_data}

        except Exception as e:
            print(f"Error loading from history DB: {e}")
            import traceback
            traceback.print_exc()
            return {"yoy": [], "mom": []}

    def _load_from_estat(self) -> Dict[str, List[Dict[str, Any]]]:
        """e-Stat Excelから小売業販売額データを取得"""
        try:
            excel_content = self._download_excel_file()
            if not excel_content:
                print("Failed to download e-Stat Excel file")
                return {"yoy": [], "mom": []}

            data_points = self._parse_excel_data(excel_content)
            if not data_points:
                print("Failed to parse e-Stat Excel data")
                return {"yoy": [], "mom": []}

            yoy_data = []
            mom_data = []

            for item in data_points:
                if item.get("yoy_change") is not None:
                    yoy_data.append({
                        "date": item["date"],
                        "value": item["yoy_change"],
                        "sales_amount": item.get("sales_amount"),
                    })
                if item.get("mom_change") is not None:
                    mom_data.append({
                        "date": item["date"],
                        "value": item["mom_change"],
                        "sales_amount": item.get("sales_amount"),
                    })

            print(f"Loaded {len(yoy_data)} YoY, {len(mom_data)} MoM records from e-Stat")
            return {"yoy": yoy_data, "mom": mom_data}

        except Exception as e:
            print(f"Error loading from e-Stat: {e}")
            import traceback
            traceback.print_exc()
            return {"yoy": [], "mom": []}

    def _download_excel_file(self) -> Optional[bytes]:
        """e-Stat 商業動態統計速報 Excel を動的解決した statInfId で取得"""
        return download_estat_excel(
            ESTAT_STATS_CODE,
            ESTAT_TABLE_FILTER,
            FALLBACK_STAT_INF_IDS,
            updated_days=120,
        )

    def _parse_excel_data(self, excel_content: bytes) -> List[Dict[str, Any]]:
        """Excelデータをパース"""
        try:
            excel_file = io.BytesIO(excel_content)
            df = pd.read_excel(excel_file, sheet_name='DB_MainA', header=None)

            data_points = []

            for row_idx in range(19, len(df)):
                try:
                    row = df.iloc[row_idx]
                    date_str = str(row[1])

                    if pd.isna(row[1]) or date_str == 'nan':
                        continue

                    if '年' in date_str and '月' in date_str:
                        parts = date_str.split('年')
                        year = int(parts[0])
                        month = int(parts[1].replace('月', '').strip())
                    else:
                        continue

                    sales_amount = float(row[10]) if not pd.isna(row[10]) else None
                    yoy_change = float(row[11]) if not pd.isna(row[11]) else None
                    mom_change = float(row[12]) if not pd.isna(row[12]) else None

                    date_formatted = f"{year}-{month:02d}-01"

                    data_points.append({
                        "date": date_formatted,
                        "sales_amount": round(sales_amount, 1) if sales_amount else None,
                        "yoy_change": round(yoy_change, 2) if yoy_change else None,
                        "mom_change": round(mom_change, 2) if mom_change else None,
                    })

                except (ValueError, AttributeError, IndexError) as e:
                    continue

            print(f"Parsed {len(data_points)} data points from Excel")
            return data_points

        except Exception as e:
            print(f"Error parsing Excel: {e}")
            return []

    def _load_from_fmp_db(self, data_type: str) -> List[Dict[str, Any]]:
        """FMP economic_calendar_eventsから最新データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text
            import re

            event_pattern = self.EVENT_PATTERNS.get(data_type)
            if not event_pattern:
                return []

            with SessionLocal() as session:
                query = text("""
                    SELECT datetime_utc, event, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'JP'
                      AND event ILIKE :pattern
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query, {"pattern": f"%{event_pattern}%"}).fetchall()

                result = []
                month_map = {
                    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                }

                for row in rows:
                    dt_utc, event, actual, estimate, previous = row
                    if dt_utc:
                        match = re.search(r'\((\w{3})\)', event)
                        if match:
                            month_abbr = match.group(1).lower()
                            if month_abbr in month_map:
                                target_month = month_map[month_abbr]
                                target_year = dt_utc.year
                                if target_month > dt_utc.month:
                                    target_year -= 1
                                date_str = f"{target_year}-{target_month:02d}-01"
                            else:
                                continue
                        else:
                            continue

                        existing_idx = None
                        for i, existing in enumerate(result):
                            if existing["date"] == date_str:
                                existing_idx = i
                                break

                        data_point = {
                            "date": date_str,
                            "value": float(actual) if actual else None,
                            "forecast": float(estimate) if estimate else None,
                            "previous": float(previous) if previous else None,
                        }

                        if existing_idx is not None:
                            result[existing_idx] = data_point
                        else:
                            result.append(data_point)

                print(f"Loaded {len(result)} JP Retail Sales {data_type.upper()} records from DB")
                return result

        except Exception as e:
            print(f"Error loading Retail Sales {data_type} from DB: {e}")
            return []

    def _merge_three_sources(
        self,
        history_data: List[Dict[str, Any]],
        estat_data: List[Dict[str, Any]],
        fmp_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        3つのデータソースをマージ（後のものが上書き＝優先）
        優先順位: history_data(長期ベース) < fmp_data(即時補完) < estat_data(公式・最優先)

        e-Stat はMETI公式の速報値で前月分の改定も反映するため最優先。
        FMP は e-Stat のカタログ反映が当日朝に間に合わない等のギャップ補完に使う。
        （旧実装はFMP最優先だったが、e-Statが固定IDで陳腐化していたための消極的な
          順序であり、e-Stat動的解決の修正に合わせて公式値優先に是正）
        """
        merged = {}

        # 1. 履歴DBデータをベースに（長期時系列）
        for d in history_data:
            merged[d["date"]] = d.copy()

        # 2. FMPデータで上書き（e-Stat未反映月のギャップ補完）
        for d in fmp_data:
            merged[d["date"]] = d.copy()

        # 3. e-Stat速報データで上書き（公式・改定込みで最優先）
        for d in estat_data:
            merged[d["date"]] = d.copy()

        result = sorted(merged.values(), key=lambda x: x["date"])
        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_fmp_schedule(
            self.ECONALPHA_IDS["yoy"],
            last_updated_str
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        mom_count = 0
        yoy_count = 0
        if cached_data:
            mom = cached_data.get("mom")
            yoy = cached_data.get("yoy")
            mom_count = len(mom.get("data", [])) if mom else 0
            yoy_count = len(yoy.get("data", [])) if yoy else 0

        return {
            "indicator": "JP Retail Sales (MoM/YoY)",
            "source": "History DB + e-Stat + FMP",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": {"mom": mom_count, "yoy": yoy_count},
            "next_release": get_next_release_from_fmp(self.ECONALPHA_IDS["yoy"]),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
retail_sales_service = RetailSalesService()
