"""
日本 実質消費支出サービス
家計調査データを取得

指標:
- Household Spending MoM: 前月比 (%)
- Household Spending YoY: 前年比 (%)

データソース:
- プライマリ: e-Stat API（総務省統計局）
- セカンダリ: DB economic_calendar_events（FMP蓄積データ）

発表スケジュール:
- 毎月上旬（対象月の翌々月）
- 例: 10月分は12月上旬発表

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.japan.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "japan" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "consumption_expenditure_cache.json"


class ConsumptionExpenditureService:
    """日本 実質消費支出サービス"""

    DATA_CACHE_KEY = "japan:consumer:consumption_expenditure:data"

    # FMPイベントマッピング用ID
    ECONALPHA_IDS = {
        "mom": "jp_household_spending_mom",
        "yoy": "jp_household_spending_yoy",
    }

    # DBクエリ用のイベントパターン
    EVENT_PATTERNS = {
        "mom": "Household Spending MoM",
        "yoy": "Household Spending YoY",
    }

    def __init__(self):
        pass

    def get_consumption_expenditure_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        実質消費支出データを取得（MoM、YoY）

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "mom": {
                    "data": [{"date": "YYYY-MM-DD", "value": float, ...}, ...],
                    "latest": {...},
                },
                "yoy": {...},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
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

        # e-Stat APIから取得（プライマリソース）
        estat_data = self._load_from_estat()

        # DBから取得（最新データ用、FMP経由）
        db_mom_data = self._load_from_db("mom")
        db_yoy_data = self._load_from_db("yoy")

        # データをマージ（e-Stat + DB最新分）
        mom_data = self._merge_data(estat_data.get("mom", []), db_mom_data)
        yoy_data = self._merge_data(estat_data.get("yoy", []), db_yoy_data)

        if mom_data or yoy_data:
            # YoYのスケジュールで次回発表を取得
            next_release = get_next_release_from_fmp(self.ECONALPHA_IDS["yoy"])

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
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                **cache_payload,
                "cached": False,
                "source": "database",
            }

        # 取得失敗時はファイルキャッシュから返す
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

    def _load_from_estat(self) -> Dict[str, List[Dict[str, Any]]]:
        """e-Stat APIから家計調査データを取得"""
        try:
            from services.japan.estat_household_survey_service import estat_household_survey_service

            result = estat_household_survey_service.get_historical_data(from_year=2015)

            yoy_data = []
            mom_data = []

            if result.get("yoy") and result["yoy"].get("data"):
                yoy_data = [
                    {"date": d["date"], "value": d["value"]}
                    for d in result["yoy"]["data"]
                ]

            if result.get("mom") and result["mom"].get("data"):
                mom_data = [
                    {"date": d["date"], "value": d["value"]}
                    for d in result["mom"]["data"]
                ]

            print(f"Loaded {len(yoy_data)} YoY, {len(mom_data)} MoM records from e-Stat")
            return {"yoy": yoy_data, "mom": mom_data}

        except Exception as e:
            print(f"Error loading from e-Stat: {e}")
            import traceback
            traceback.print_exc()
            return {"yoy": [], "mom": []}

    def _merge_data(
        self,
        estat_data: List[Dict[str, Any]],
        db_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """e-StatとDBのデータをマージ（DBデータを優先）"""
        # 日付をキーにしたマップを作成
        merged = {d["date"]: d for d in estat_data}

        # DBデータで上書き（より新しい・正確なデータ）
        for d in db_data:
            merged[d["date"]] = d

        # 日付順にソート
        result = sorted(merged.values(), key=lambda x: x["date"])
        return result

    def _load_from_db(self, data_type: str) -> List[Dict[str, Any]]:
        """DBから履歴データを取得

        Args:
            data_type: "mom" or "yoy"
        """
        try:
            from core.database import SessionLocal
            from sqlalchemy import text
            import re

            event_pattern = self.EVENT_PATTERNS.get(data_type)
            if not event_pattern:
                return []

            with SessionLocal() as session:
                # country='JP'でフィルタリングして日本のデータのみ取得
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

                # 月名から月番号へのマッピング
                month_map = {
                    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                }

                for row in rows:
                    dt_utc, event, actual, estimate, previous = row
                    if dt_utc:
                        # イベント名から対象月を抽出（例: "Household Spending MoM (Oct)"）
                        match = re.search(r'\((\w{3})\)', event)
                        if match:
                            month_abbr = match.group(1).lower()
                            if month_abbr in month_map:
                                target_month = month_map[month_abbr]
                                # 対象月の年を決定
                                target_year = dt_utc.year
                                if target_month > dt_utc.month:
                                    target_year -= 1
                                date_str = f"{target_year}-{target_month:02d}-01"
                            else:
                                # 月名が不明な場合は発表月の前々月を使用
                                prev_month = dt_utc.month - 2 if dt_utc.month > 2 else dt_utc.month + 10
                                prev_year = dt_utc.year if dt_utc.month > 2 else dt_utc.year - 1
                                date_str = f"{prev_year}-{prev_month:02d}-01"
                        else:
                            # 括弧内に月がない場合は発表月の前々月を使用
                            prev_month = dt_utc.month - 2 if dt_utc.month > 2 else dt_utc.month + 10
                            prev_year = dt_utc.year if dt_utc.month > 2 else dt_utc.year - 1
                            date_str = f"{prev_year}-{prev_month:02d}-01"

                        # 同一月のデータが既にある場合は後のデータで上書き
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

                print(f"Loaded {len(result)} JP Household Spending {data_type.upper()} records from DB")
                return result

        except Exception as e:
            print(f"Error loading JP Household Spending {data_type} from DB: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP 5分方式）"""
        # YoYのスケジュールで判定（MoMと同時発表のため）
        return should_refresh_by_fmp_schedule(
            self.ECONALPHA_IDS["yoy"],
            last_updated_str
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None

            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
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
            "indicator": "JP Household Spending (MoM/YoY)",
            "source": "Database (FMP)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": {
                "mom": mom_count,
                "yoy": yoy_count,
            },
            "next_release": get_next_release_from_fmp(self.ECONALPHA_IDS["yoy"]),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
consumption_expenditure_service = ConsumptionExpenditureService()
