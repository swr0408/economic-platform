"""
Challenger人員削減数サービス
Investing.comからChallenger Job Cutsデータを取得

指標:
- Challenger Job Cuts: 米国企業の人員削減発表数

データソース:
- https://sbcharts.investing.com/events_charts/us/888.json
- イベントID: 888 (Challenger Job Cuts)
- 発表元: Challenger, Gray & Christmas

発表スケジュール:
- 発表期間: 毎月1〜31日（毎月第1木曜日頃）
- 発表時刻: 20:30 (夏) / 21:30 (冬) JST

キャッシュ方式: 発表期間ベース判定方式
"""
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# Investing.com JSONエンドポイント
INVESTING_CHALLENGER_URL = "https://sbcharts.investing.com/events_charts/us/888.json"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "challenger_job_cuts_cache.json"


class ChallengerJobCutsService:
    """Challenger人員削減数サービス"""

    DATA_CACHE_KEY = "investing:challenger_job_cuts:data"
    ECONALPHA_ID = "challenger_job_cuts"  # FMPマッピング用ID

    def __init__(self):
        pass

    def get_challenger_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Challenger人員削減数データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float, "mom": float | null, "yoy": float | null}, ...],
                "latest": {...},
                "next_release": null,
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
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # 優先順位: 1. DB(FMP蓄積) → 2. Investing.com API（フォールバック）
        db_result = self._load_from_db()
        if db_result:
            # 次回発表日をFMPから取得
            next_release = self._get_next_release_from_fmp()

            latest = db_result[-1] if db_result else None
            cache_payload = {
                "data": db_result,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)

            return {
                "data": db_result,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "database",
                "last_updated": datetime.now(JST).isoformat()
            }

        # DBにデータがない場合はInvesting.comから取得（フォールバック）
        api_data = self._fetch_from_investing()

        if api_data:
            # 変化率を計算
            processed_data = self._calculate_changes(api_data)
            latest = processed_data[-1] if processed_data else None

            cache_payload = {
                "data": processed_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": processed_data,
                "latest": latest,
                "next_release": None,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": None,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _load_from_db(self) -> List[Dict[str, Any]]:
        """DBから履歴データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text
            from datetime import timedelta

            with SessionLocal() as session:
                query = text("""
                    SELECT datetime_utc, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'US'
                      AND event ILIKE '%Challenger Job Cuts%'
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query).fetchall()

                result = []
                seen_dates = set()

                for row in rows:
                    dt_utc, actual, estimate, previous = row
                    if dt_utc:
                        # 月初日に正規化
                        date_str = dt_utc.strftime("%Y-%m-01")
                        if date_str in seen_dates:
                            continue
                        seen_dates.add(date_str)

                        result.append({
                            "date": date_str,
                            "value": float(actual) if actual else None,
                            "mom": None,
                            "yoy": None,
                        })

                # 変化率を再計算
                result = self._calculate_changes(result)
                print(f"Loaded {len(result)} Challenger Job Cuts records from DB")
                return result

        except Exception as e:
            print(f"Error loading from DB: {e}")
            return []

    def _get_next_release_from_fmp(self) -> Optional[Dict[str, Any]]:
        """FMP APIから次回発表日を取得"""
        try:
            from services.calendar.fmp_service import fmp_service
            from datetime import date, timedelta

            today = date.today()
            # FMP APIからイベントを取得
            events = fmp_service.fetch_calendar(
                today,
                today + timedelta(days=60),
                country="US"
            )

            # 対象イベントを収集（USのみ）
            candidates = []
            for event in events:
                # USイベントのみ
                if event.get("country") != "US":
                    continue
                event_name = event.get("event", "")
                # Challenger Job Cutsにマッチするイベントのみ
                if "challenger job cuts" not in event_name.lower():
                    continue
                # 将来のイベント（actual が None）
                if event.get("actual") is None:
                    dt_utc, _ = fmp_service.parse_datetime(event.get("date", ""))
                    if dt_utc and dt_utc.date() >= today:
                        candidates.append({
                            "date": dt_utc.strftime("%Y-%m-%d"),
                            "datetime_utc": dt_utc.isoformat(),
                            "label": event_name,
                            "estimate": event.get("estimate"),
                            "_dt": dt_utc,
                        })

            # 日付順でソートして最も近いイベントを返す
            if candidates:
                candidates.sort(key=lambda x: x["_dt"])
                result = candidates[0]
                del result["_dt"]
                return result

            return None

        except Exception as e:
            print(f"Error fetching next release from FMP: {e}")
            return None

    def _fetch_from_investing(self) -> List[Dict[str, Any]]:
        """Investing.comからChallenger人員削減数データを取得（JSON API）"""
        try:
            print("Fetching Challenger Job Cuts from Investing.com JSON API...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": "https://jp.investing.com/"
            }

            response = requests.get(INVESTING_CHALLENGER_URL, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            # dataからデータを抽出 [[timestamp, value, "No"], ...]
            data_list = data.get("data", [])
            if not data_list:
                print("No data found in response")
                return []

            result = []
            for item in data_list:
                if len(item) < 2:
                    continue

                timestamp = item[0]
                value = item[1]

                if timestamp is None or value is None:
                    continue

                try:
                    # タイムスタンプをミリ秒から日付に変換
                    dt = datetime.fromtimestamp(timestamp / 1000, tz=JST)
                    date_str = dt.strftime("%Y-%m-%d")

                    # 値は既に千人単位（k）なのでそのまま小数で保存
                    # 例: 71.321 = 71.321k = 71,321人
                    result.append({
                        "date": date_str,
                        "value": round(float(value), 3)
                    })
                except (ValueError, TypeError):
                    continue

            # 日付順にソート（古い順）
            result.sort(key=lambda x: x["date"])

            print(f"Fetched {len(result)} Challenger Job Cuts records from Investing.com")
            return result

        except Exception as e:
            print(f"Error fetching Challenger Job Cuts data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _get_target_month(self, announce_date: datetime) -> tuple:
        """
        発表日から対象月を計算

        Challenger Job Cutsは前月分を発表するが、発表日は通常月初旬
        - 月初旬（1-15日）に発表 → 前月分のデータ
        - 月後半（16-31日）に発表 → 当月分のデータ（稀なケース）

        例:
        - 2025-02-06 → 2025年1月分
        - 2024-10-31 → 2024年10月分（月末発表の場合は当月分）
        """
        if announce_date.day <= 15:
            # 月初旬の発表 → 前月分
            if announce_date.month == 1:
                return (announce_date.year - 1, 12)
            else:
                return (announce_date.year, announce_date.month - 1)
        else:
            # 月後半の発表 → 当月分
            return (announce_date.year, announce_date.month)

    def _calculate_changes(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        前月比と前年比を計算

        APIから取得した日付は実際の発表日（例: 2025-02-06 = 1月分のデータ）
        対象月ベースで比較するために、発表日から対象月を計算してインデックスを作成

        例: 2025-02-06（1月分）の前月比 = 12月分との比較
             2025-02-06（1月分）の前年比 = 2024年1月分との比較

        注: APIデータに同じ対象月のデータが複数ある場合（不規則な発表日）は
        最新の発表日のデータを使用
        """
        if not data:
            return []

        # 発表日を含めた対象月マップを作成
        # 同じ対象月に複数データがある場合は発表日が新しい方を採用
        month_map = {}  # key: (year, month), value: {"value": float, "announce_date": str}
        for item in data:
            dt = datetime.strptime(item["date"], "%Y-%m-%d")
            # 対象月を計算
            target_year, target_month = self._get_target_month(dt)
            key = (target_year, target_month)

            # 既存データより新しい発表日の場合のみ更新
            if key not in month_map or item["date"] > month_map[key]["announce_date"]:
                month_map[key] = {"value": item["value"], "announce_date": item["date"]}

        result = []
        for item in data:
            current_date = datetime.strptime(item["date"], "%Y-%m-%d")
            current_value = item["value"]

            # 対象月を計算
            target_year, target_month = self._get_target_month(current_date)

            # 前月比（MoM）を計算
            # 対象月の前月のキー
            if target_month == 1:
                prev_month_key = (target_year - 1, 12)
            else:
                prev_month_key = (target_year, target_month - 1)

            prev_month_data = month_map.get(prev_month_key)
            prev_month_value = prev_month_data["value"] if prev_month_data else None
            mom = None
            if prev_month_value and prev_month_value != 0:
                mom = round((current_value - prev_month_value) / prev_month_value * 100, 1)

            # 前年比（YoY）を計算
            # 対象月の前年同月のキー
            prev_year_key = (target_year - 1, target_month)
            prev_year_data = month_map.get(prev_year_key)
            prev_year_value = prev_year_data["value"] if prev_year_data else None
            yoy = None
            if prev_year_value and prev_year_value != 0:
                yoy = round((current_value - prev_year_value) / prev_year_value * 100, 1)

            result.append({
                "date": item["date"],
                "value": current_value,
                "mom": mom,
                "yoy": yoy
            })

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP 3分方式）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

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
            print(f"Challenger Job Cuts cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Challenger Job Cuts",
            "source": "Investing.com",
            "url": INVESTING_CHALLENGER_URL,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
challenger_job_cuts_service = ChallengerJobCutsService()
