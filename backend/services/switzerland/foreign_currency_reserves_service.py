"""
外貨準備（Foreign Currency Reserves）サービス
SNB Data Portalから外貨準備データを取得

指標:
- 外貨準備（CHFとUSD）

データソース:
- SNB Data Portal: https://data.snb.ch/api/cube/snbimfra/data/csv/en

発表スケジュール:
- 月次（Monthly）
- 月末営業日 09:00（チューリッヒ時間）
- 参照: https://data.snb.ch/en/calendar
  "IMF SDDS Plus - Monthly - On the 7th day, the 14th day and the final working day of the month, at the latest (9.00 am)"

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
DATA_CACHE_FILE = CACHE_DIR / "foreign_currency_reserves_cache.json"


class ForeignCurrencyReservesService:
    """外貨準備サービス"""

    DATA_CACHE_KEY = "switzerland:foreign_currency_reserves:data"

    # SNB Data Portal API URL
    # D0=T2: 外貨準備（Foreign currency reserves）
    # D1=T0: CHF建て, D1=T1: USD建て
    DATA_SOURCE_URL = "https://data.snb.ch/api/cube/snbimfra/data/csv/en?dimSel=D0(T2),D1(T0,T1)&fromDate=1999-01"

    # 系列コード
    CHF_CODE = "T0"  # CHF建て
    USD_CODE = "T1"  # USD建て

    def __init__(self):
        self._publishing_date: Optional[datetime] = None

    def get_foreign_currency_reserves_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """外貨準備データを取得"""
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

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Swiss National Bank",
                    "indicator": "Foreign Currency Reserves",
                    "description": "外貨準備（CHF・USD）",
                    "unit": "Million",
                },
                "publishing_date": publishing_date_str,
                "last_updated": datetime.now(JST).isoformat(),
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
                "last_updated": datetime.now(JST).isoformat(),
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
            print(f"[ForeignCurrencyReserves] Fetching data from: {self.DATA_SOURCE_URL}")

            resp = requests.get(self.DATA_SOURCE_URL, timeout=60)
            resp.raise_for_status()

            # CSVをパース（エンコーディング対応）
            csv_content = resp.content.decode('utf-8')
            lines = csv_content.strip().split('\n')

            # メタデータからPublishingDateを取得
            # 形式: "PublishingDate";"2026-01-30 09:00"
            publishing_date = None
            for line in lines[:5]:  # 最初の5行をチェック
                if 'PublishingDate' in line:
                    parts = line.split(';')
                    if len(parts) >= 2:
                        date_str = parts[1].strip('"').strip()
                        try:
                            # "2026-01-30 09:00" 形式
                            publishing_date = datetime.strptime(date_str[:16], "%Y-%m-%d %H:%M")
                            publishing_date = publishing_date.replace(tzinfo=ZURICH)
                            print(f"[ForeignCurrencyReserves] PublishingDate: {publishing_date}")
                        except ValueError as e:
                            print(f"[ForeignCurrencyReserves] Error parsing PublishingDate '{date_str}': {e}")
                    break

            # データ部分をDataFrameに読み込み
            df = pd.read_csv(io.StringIO(csv_content), sep=';', skiprows=2)

            print(f"[ForeignCurrencyReserves] CSV columns: {df.columns.tolist()}")
            print(f"[ForeignCurrencyReserves] Total rows: {len(df)}")

            # 日付ごとにCHFとUSD値をまとめる
            # D1=T0: CHF, D1=T1: USD
            date_values = {}

            for _, row in df.iterrows():
                date_str = row['Date']
                d1_code = row['D1']
                value = row['Value']

                if pd.isna(date_str) or pd.isna(value):
                    continue

                # YYYY-MM形式をYYYY-MM-01に変換
                date_formatted = f"{date_str}-01"

                if date_formatted not in date_values:
                    date_values[date_formatted] = {"date": date_formatted, "chf": None, "usd": None}

                try:
                    if d1_code == self.CHF_CODE:
                        date_values[date_formatted]["chf"] = float(value)
                    elif d1_code == self.USD_CODE:
                        date_values[date_formatted]["usd"] = float(value)
                except (ValueError, TypeError) as e:
                    print(f"[ForeignCurrencyReserves] Error parsing value: {e}")
                    continue

            # リストに変換してソート
            result = list(date_values.values())
            result.sort(key=lambda x: x["date"])

            print(f"[ForeignCurrencyReserves] Loaded {len(result)} records")
            if result:
                print(f"[ForeignCurrencyReserves] Date range: {result[0]['date']} to {result[-1]['date']}")
                print(f"[ForeignCurrencyReserves] Latest: CHF={result[-1].get('chf')}, USD={result[-1].get('usd')}")

            return result, publishing_date

        except Exception as e:
            print(f"[ForeignCurrencyReserves] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return [], None

    def _calculate_next_release(self) -> Optional[str]:
        """次回発表日を計算

        外貨準備は月次で発表（IMF SDDS Plus）
        発表日: 月末営業日 09:00（チューリッヒ時間）
        参照: https://data.snb.ch/en/calendar

        Returns:
            次回発表日（"YYYY-MM-DD HH:MM"形式）
        """
        try:
            now = datetime.now(ZURICH)

            # 今月の最終営業日を取得
            this_month_last_bday = self._get_last_business_day(now.year, now.month)

            # 発表時刻（09:00 チューリッヒ時間）
            release_datetime = this_month_last_bday.replace(hour=9, minute=0, second=0, microsecond=0, tzinfo=ZURICH)

            # 今月の発表日時がまだ来ていなければそれを返す
            if now < release_datetime:
                return release_datetime.strftime("%Y-%m-%d %H:%M")

            # 来月の最終営業日を取得
            next_month = now.month + 1
            next_year = now.year
            if next_month > 12:
                next_month = 1
                next_year += 1

            next_month_last_bday = self._get_last_business_day(next_year, next_month)
            next_release_datetime = next_month_last_bday.replace(hour=9, minute=0, second=0, microsecond=0, tzinfo=ZURICH)

            return next_release_datetime.strftime("%Y-%m-%d %H:%M")

        except Exception as e:
            print(f"[ForeignCurrencyReserves] Error calculating next release: {e}")
            return None

    def _get_last_business_day(self, year: int, month: int) -> datetime:
        """指定月の最終営業日を取得

        営業日 = 平日（月〜金）かつスイスの祝日でない日

        Args:
            year: 年
            month: 月

        Returns:
            最終営業日のdatetimeオブジェクト
        """
        import calendar

        # スイス祝日を取得
        swiss_holidays = get_swiss_holidays(year)

        # 月末日を取得
        _, last_day = calendar.monthrange(year, month)
        current_date = datetime(year, month, last_day)

        # 営業日が見つかるまで遡る
        while True:
            # 土曜（5）または日曜（6）でない
            if current_date.weekday() < 5:
                date_str = current_date.strftime("%Y-%m-%d")
                if date_str not in swiss_holidays:
                    return current_date

            # 前日に移動
            current_date = current_date - timedelta(days=1)

            # 月を跨いだ場合は安全策として終了
            if current_date.month != month:
                print(f"[ForeignCurrencyReserves] Warning: Could not find business day in {year}-{month:02d}")
                return datetime(year, month, last_day)

    def _should_refresh(self, last_updated_str: str, publishing_date_str: Optional[str]) -> bool:
        """キャッシュを更新すべきかどうかを判定

        月次発表のため、発表日を過ぎていたら更新
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(ZURICH)

            # 今月の発表日を計算
            this_month_last_bday = self._get_last_business_day(now.year, now.month)
            this_month_release = this_month_last_bday.replace(hour=9, minute=0, second=0, microsecond=0, tzinfo=ZURICH)

            # 今月の発表時刻を過ぎていて、最後の更新がその前なら更新
            if now > this_month_release and last_updated.astimezone(ZURICH) < this_month_release:
                print(f"[ForeignCurrencyReserves] Data is stale, this month's release was {this_month_release}")
                return True

            # 7日以上経過していたら更新
            if (now - last_updated.astimezone(ZURICH)).days >= 7:
                print("[ForeignCurrencyReserves] Cache is older than 7 days, refreshing")
                return True

            return False
        except Exception as e:
            print(f"[ForeignCurrencyReserves] Error checking refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ForeignCurrencyReserves] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ForeignCurrencyReserves] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        publishing_date_str = cached_data.get("publishing_date") if cached_data else None

        return {
            "indicator": "Foreign Currency Reserves",
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
foreign_currency_reserves_service = ForeignCurrencyReservesService()
