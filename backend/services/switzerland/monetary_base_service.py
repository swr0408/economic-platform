"""
マネタリーベース（Monetary Base）サービス
SNB Data Portalからマネタリーベースデータを取得

指標:
- マネタリーベース（Monetary base）

データソース:
- SNB Data Portal: https://data.snb.ch/api/cube/snbmoba/data/csv/en?dimSel=D0(N0)&fromDate=1950-01

発表スケジュール:
- 週次（Weekly）
- 週の最初の営業日 10:00（チューリッヒ時間）
- 参照: https://data.snb.ch/en/calendar
  "Important monetary policy data - Weekly - On the first working day of the week (10.00 am)"

キャッシュ方式: 発表日ベース判定
"""
import json
import io
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd

from core.redis_client import redis_client
from services.switzerland.swiss_holidays import get_swiss_holidays


JST = ZoneInfo("Asia/Tokyo")
ZURICH = ZoneInfo("Europe/Zurich")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "switzerland" / "monetary_policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "monetary_base_cache.json"


class MonetaryBaseService:
    """マネタリーベースサービス"""

    DATA_CACHE_KEY = "switzerland:monetary_base:data"

    # SNB Data Portal API URL
    # snbmoba = Monetary base
    # D0=N0: マネタリーベース（Monetary base）
    DATA_SOURCE_URL = "https://data.snb.ch/api/cube/snbmoba/data/csv/en?dimSel=D0(N0)&fromDate=1950-01"

    def __init__(self):
        self._publishing_date: Optional[datetime] = None

    def get_monetary_base_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """マネタリーベースデータを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                publishing_date_str = cached_data.get("publishing_date")
                if last_updated_str and not self._should_refresh(last_updated_str, publishing_date_str):
                    next_release = self._calculate_next_release()
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "last_publishing_date": publishing_date_str,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # SNB APIからデータ取得
        result, publishing_date = self._load_from_api()
        if result:
            latest = result[-1] if result else None
            publishing_date_str = publishing_date.strftime("%Y-%m-%d %H:%M") if publishing_date else None
            next_release = self._calculate_next_release()

            from services.usa.fmp_next_release_utils import guarded_last_updated
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
            )
            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Swiss National Bank",
                    "indicator": "Monetary Base",
                    "description": "マネタリーベース",
                    "unit": "CHF (millions)",
                },
                "publishing_date": publishing_date_str,
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "last_publishing_date": publishing_date_str,
                "cached": False,
                "source": "api",
                "last_updated": last_updated,
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            publishing_date_str = file_cache.get("publishing_date")
            next_release = self._calculate_next_release()
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "last_publishing_date": publishing_date_str,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": None,
            "last_publishing_date": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_api(self) -> tuple[List[Dict[str, Any]], Optional[datetime]]:
        """SNB Data Portal APIからデータを取得

        Returns:
            tuple: (データリスト, PublishingDate)
        """
        try:
            print(f"[MonetaryBase] Fetching data from: {self.DATA_SOURCE_URL}")

            resp = requests.get(self.DATA_SOURCE_URL, timeout=60)
            resp.raise_for_status()

            # CSVをパース
            csv_content = resp.content.decode('utf-8')
            lines = csv_content.strip().split('\n')

            # メタデータからPublishingDateを取得
            # 形式: "PublishingDate";"2026-01-21 09:49"
            publishing_date = None
            for line in lines[:5]:
                if 'PublishingDate' in line:
                    parts = line.split(';')
                    if len(parts) >= 2:
                        date_str = parts[1].strip('"').strip()
                        try:
                            publishing_date = datetime.strptime(date_str[:16], "%Y-%m-%d %H:%M")
                            publishing_date = publishing_date.replace(tzinfo=ZURICH)
                            print(f"[MonetaryBase] PublishingDate: {publishing_date}")
                        except ValueError as e:
                            print(f"[MonetaryBase] Error parsing PublishingDate '{date_str}': {e}")
                    break

            # データ部分をDataFrameに読み込み
            df = pd.read_csv(io.StringIO(csv_content), sep=';', skiprows=2)

            print(f"[MonetaryBase] CSV columns: {df.columns.tolist()}")
            print(f"[MonetaryBase] Total rows: {len(df)}")

            result = []
            for _, row in df.iterrows():
                date_str = row['Date']
                value = row['Value']

                # 日付をYYYY-MM-01形式に変換
                if pd.notna(date_str) and pd.notna(value):
                    try:
                        # YYYY-MM形式をYYYY-MM-01に変換
                        date_formatted = f"{date_str}-01"
                        # 値は百万CHF単位
                        result.append({
                            "date": date_formatted,
                            "value": float(value),
                        })
                    except (ValueError, TypeError) as e:
                        print(f"[MonetaryBase] Error parsing row: {e}")
                        continue

            # 日付でソート
            result.sort(key=lambda x: x["date"])

            print(f"[MonetaryBase] Loaded {len(result)} records")
            if result:
                print(f"[MonetaryBase] Date range: {result[0]['date']} to {result[-1]['date']}")
                print(f"[MonetaryBase] Latest: value={result[-1].get('value')}")

            return result, publishing_date

        except Exception as e:
            print(f"[MonetaryBase] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return [], None

    def _calculate_next_release(self) -> Optional[str]:
        """次回発表日を計算

        マネタリーベースは週次（Weekly）で発表
        発表日: 週の最初の営業日 10:00（チューリッヒ時間）
        参照: https://data.snb.ch/en/calendar

        Returns:
            次回発表日（"YYYY-MM-DD HH:MM"形式）
        """
        try:
            now = datetime.now(ZURICH)

            # 今週の最初の営業日を探す
            this_week_first_bday = self._get_first_business_day_of_week(now)
            release_time = this_week_first_bday.replace(hour=10, minute=0, second=0, microsecond=0, tzinfo=ZURICH)

            # 今週の発表時刻がまだ来ていなければそれを返す
            if now < release_time:
                return release_time.strftime("%Y-%m-%d %H:%M")

            # 来週の最初の営業日を取得
            next_week = now + timedelta(days=7 - now.weekday())  # 次の月曜日
            next_week_first_bday = self._get_first_business_day_of_week(next_week)
            next_release_time = next_week_first_bday.replace(hour=10, minute=0, second=0, microsecond=0, tzinfo=ZURICH)

            return next_release_time.strftime("%Y-%m-%d %H:%M")

        except Exception as e:
            print(f"[MonetaryBase] Error calculating next release: {e}")
            return None

    def _get_first_business_day_of_week(self, date: datetime) -> datetime:
        """指定日が含まれる週の最初の営業日を取得

        営業日 = 平日（月〜金）かつスイスの祝日でない日

        Args:
            date: 基準日

        Returns:
            その週の最初の営業日
        """
        # スイス祝日を取得
        swiss_holidays = get_swiss_holidays(date.year)

        # その週の月曜日を取得
        monday = date - timedelta(days=date.weekday())

        # 月曜から順に営業日を探す
        for i in range(7):
            check_date = monday + timedelta(days=i)
            # 土曜（5）または日曜（6）でない
            if check_date.weekday() < 5:
                date_str = check_date.strftime("%Y-%m-%d")
                if date_str not in swiss_holidays:
                    return check_date

        # 営業日が見つからなかった場合（通常はあり得ない）
        return monday

    def _should_refresh(self, last_updated_str: str, publishing_date_str: Optional[str]) -> bool:
        """キャッシュを更新すべきかどうかを判定

        週次発表のため、発表日を過ぎていたら更新
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(ZURICH)

            # 次回発表日を計算
            next_release_str = self._calculate_next_release()
            if next_release_str:
                # 今週の発表日を取得（next_releaseが来週なら今週は終了）
                this_week_first_bday = self._get_first_business_day_of_week(now)
                this_week_release = this_week_first_bday.replace(hour=10, minute=0, second=0, microsecond=0, tzinfo=ZURICH)

                # 今週の発表時刻を過ぎていて、最後の更新がその前なら更新
                if now > this_week_release and last_updated.astimezone(ZURICH) < this_week_release:
                    print(f"[MonetaryBase] Data is stale, this week's release was {this_week_release}")
                    return True

            # 7日以上経過していたら更新
            if (now - last_updated.astimezone(ZURICH)).days >= 7:
                print("[MonetaryBase] Cache is older than 7 days, refreshing")
                return True

            return False
        except Exception as e:
            print(f"[MonetaryBase] Error checking refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[MonetaryBase] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[MonetaryBase] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        publishing_date_str = cached_data.get("publishing_date") if cached_data else None

        return {
            "indicator": "Monetary Base",
            "source": "Swiss National Bank Data Portal",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "publishing_date": publishing_date_str,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._calculate_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
monetary_base_service = MonetaryBaseService()
