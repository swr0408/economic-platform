"""
SNB中央銀行バランスシート（Central Bank Balance Sheet）サービス
SNB Data Portalからバランスシートデータを取得

指標:
- SNBバランスシート合計（Total Assets / Total Liabilities）

データソース:
- SNB Data Portal: https://data.snb.ch/api/cube/snbbipo/data/csv/en

発表スケジュール:
- 月次
- 毎月最終営業日 09:00（チューリッヒ時間）
- 参照: https://data.snb.ch/en/calendar
  "SNB balance sheet items - Monthly - Last working day of the month (9.00 am)"

キャッシュ方式: 発表日ベース判定（PublishingDateの変更を検知）
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
DATA_CACHE_FILE = CACHE_DIR / "snb_balance_sheet_cache.json"


class SNBBalanceSheetService:
    """SNB中央銀行バランスシートサービス"""

    DATA_CACHE_KEY = "switzerland:snb_balance_sheet:data"

    # SNB Data Portal API URL
    DATA_SOURCE_URL = "https://data.snb.ch/api/cube/snbbipo/data/csv/en"

    # バランスシート合計の指標コード
    # T0 = Total assets（資産合計 / Bilanzsumme）
    # 注: GFGは金・外貨準備のみで、Total Assetsではない
    TOTAL_ASSETS_CODE = "T0"

    def __init__(self):
        self._publishing_date: Optional[datetime] = None

    def get_balance_sheet_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """SNBバランスシートデータを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                publishing_date_str = cached_data.get("publishing_date")
                if last_updated_str and not self._should_refresh(last_updated_str, publishing_date_str):
                    # 次回発表日を計算
                    next_release = self._calculate_next_release(publishing_date_str)
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # SNB APIからデータ取得
        result, publishing_date = self._load_from_api()
        if result:
            latest = result[-1] if result else None
            publishing_date_str = publishing_date.strftime("%Y-%m-%d %H:%M") if publishing_date else None
            next_release = self._calculate_next_release(publishing_date_str)

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Swiss National Bank",
                    "indicator": "Central Bank Balance Sheet",
                    "description": "SNB中央銀行バランスシート（総資産）",
                    "unit": "Million CHF",
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
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            publishing_date_str = file_cache.get("publishing_date")
            next_release = self._calculate_next_release(publishing_date_str)
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": None,
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
            print(f"[SNBBalanceSheet] Fetching data from: {self.DATA_SOURCE_URL}")

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
                            print(f"[SNBBalanceSheet] PublishingDate: {publishing_date}")
                        except ValueError as e:
                            print(f"[SNBBalanceSheet] Error parsing PublishingDate '{date_str}': {e}")
                    break

            # データ部分をDataFrameに読み込み
            df = pd.read_csv(io.StringIO(csv_content), sep=';', skiprows=2)

            print(f"[SNBBalanceSheet] CSV columns: {df.columns.tolist()}")
            print(f"[SNBBalanceSheet] Total rows: {len(df)}")

            # バランスシート合計（T0 = Total assets）のみをフィルタ
            df_total = df[df['D0'] == self.TOTAL_ASSETS_CODE].copy()
            print(f"[SNBBalanceSheet] Total assets rows (T0): {len(df_total)}")

            result = []
            for _, row in df_total.iterrows():
                date_str = row['Date']
                value = row['Value']

                # 日付をYYYY-MM-01形式に変換
                if pd.notna(date_str) and pd.notna(value):
                    try:
                        # YYYY-MM形式をYYYY-MM-01に変換
                        date_formatted = f"{date_str}-01"
                        result.append({
                            "date": date_formatted,
                            "value": float(value),
                        })
                    except (ValueError, TypeError) as e:
                        print(f"[SNBBalanceSheet] Error parsing row: {e}")
                        continue

            # 日付でソート
            result.sort(key=lambda x: x["date"])

            print(f"[SNBBalanceSheet] Loaded {len(result)} records")
            if result:
                print(f"[SNBBalanceSheet] Date range: {result[0]['date']} to {result[-1]['date']}")
                print(f"[SNBBalanceSheet] Latest: value={result[-1].get('value')}")

            return result, publishing_date

        except Exception as e:
            print(f"[SNBBalanceSheet] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return [], None

    def _calculate_next_release(self, publishing_date_str: Optional[str]) -> Optional[str]:
        """次回発表日を計算

        SNBバランスシートは毎月最終営業日 09:00（チューリッヒ時間）に発表される
        参照: https://data.snb.ch/en/calendar

        Args:
            publishing_date_str: 最後の発表日時文字列（"YYYY-MM-DD HH:MM"形式）

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
            print(f"[SNBBalanceSheet] Error calculating next release: {e}")
            return None

    def _get_last_business_day(self, year: int, month: int) -> datetime:
        """指定月の最終営業日を取得

        営業日 = 平日（月〜金）かつスイスの祝日でない日
        祝日はNager.Date APIから自動取得（swiss_holidaysモジュール）

        Args:
            year: 年
            month: 月

        Returns:
            最終営業日のdatetimeオブジェクト
        """
        import calendar

        # スイス祝日を取得（APIから自動取得、キャッシュあり）
        swiss_holidays = get_swiss_holidays(year)

        # 月末日を取得
        _, last_day = calendar.monthrange(year, month)
        current_date = datetime(year, month, last_day)

        # 営業日が見つかるまで遡る
        while True:
            # 土曜（5）または日曜（6）でない
            if current_date.weekday() < 5:
                # スイスの祝日でない
                date_str = current_date.strftime("%Y-%m-%d")
                if date_str not in swiss_holidays:
                    return current_date

            # 前日に移動
            current_date = current_date - timedelta(days=1)

            # 月を跨いだ場合は安全策として終了（通常はあり得ない）
            if current_date.month != month:
                print(f"[SNBBalanceSheet] Warning: Could not find business day in {year}-{month:02d}")
                return datetime(year, month, last_day)

    def _should_refresh(self, last_updated_str: str, publishing_date_str: Optional[str]) -> bool:
        """キャッシュを更新すべきかどうかを判定

        発表日を過ぎていたら更新する
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)

            # PublishingDateがある場合、次回発表日を計算
            if publishing_date_str:
                next_release_str = self._calculate_next_release(publishing_date_str)
                if next_release_str:
                    next_release = datetime.strptime(next_release_str, "%Y-%m-%d")
                    next_release = next_release.replace(hour=9, minute=0, tzinfo=ZURICH)

                    # 次回発表日を過ぎていて、最後の更新が発表前なら更新
                    if now.astimezone(ZURICH) > next_release and last_updated.astimezone(ZURICH) < next_release:
                        print(f"[SNBBalanceSheet] Data is stale, next release was {next_release_str}")
                        return True

            # 7日以上経過していたら更新
            if (now - last_updated).days >= 7:
                return True

            return False
        except Exception as e:
            print(f"[SNBBalanceSheet] Error checking refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[SNBBalanceSheet] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[SNBBalanceSheet] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        publishing_date_str = cached_data.get("publishing_date") if cached_data else None

        return {
            "indicator": "SNB Central Bank Balance Sheet",
            "source": "Swiss National Bank Data Portal",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "publishing_date": publishing_date_str,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._calculate_next_release(publishing_date_str),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
snb_balance_sheet_service = SNBBalanceSheetService()
