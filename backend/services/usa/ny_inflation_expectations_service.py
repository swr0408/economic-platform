"""
NY連銀インフレ期待サービス
NY Fed SCE (Survey of Consumer Expectations) からインフレ期待データを取得

指標:
- 1年先インフレ期待 (Median one-year ahead expected inflation rate)
- 3年先インフレ期待 (Median three-year ahead expected inflation rate)
- 5年先インフレ期待 (Median five-year ahead expected inflation rate)

データソース:
- データ: https://www.newyorkfed.org/medialibrary/Interactives/sce/sce/downloads/data/FRBNY-SCE-Data.xlsx
- スケジュール: https://www.newyorkfed.org/medialibrary/research/interactives/data/cmdCalendar/cmdCalendar.csv

発表スケジュール:
- NY Fed公式カレンダーCSVから「Survey of Consumer Expectations: Press release and data update」を取得
- 発表時刻: 11:00 ET

キャッシュ方式: NY Fed公式スケジュールベース3分方式
"""
import io
import json
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ny_inflation_expectations_cache.json"
SCHEDULE_CACHE_FILE = CACHE_DIR / "ny_fed_sce_schedule_cache.json"

# NY Fed CMDカレンダーCSV URL
NY_FED_CALENDAR_CSV_URL = "https://www.newyorkfed.org/medialibrary/research/interactives/data/cmdCalendar/cmdCalendar.csv"

# SCE発表イベント名
SCE_EVENT_NAME = "Survey of Consumer Expectations: Press release and data update"

# スケジュールキャッシュTTL（1日）
SCHEDULE_CACHE_TTL_SECONDS = 86400


def fetch_ny_fed_sce_schedule_from_csv() -> List[Dict[str, Any]]:
    """
    NY Fed公式CSVからSCE発表スケジュールを取得

    Returns:
        発表スケジュールのリスト（日付昇順）
    """
    try:
        print(f"Fetching NY Fed CMD Calendar from {NY_FED_CALENDAR_CSV_URL}...")
        response = requests.get(NY_FED_CALENDAR_CSV_URL, timeout=30)
        response.raise_for_status()

        # CSVをパース
        lines = response.text.strip().split('\n')
        schedules = []

        for line in lines[1:]:  # ヘッダーをスキップ
            parts = line.split(',')
            if len(parts) >= 2:
                date_str = parts[0].strip()
                product = parts[1].strip()

                # SCE発表イベントのみ抽出
                if product == SCE_EVENT_NAME:
                    try:
                        # M/D/YYYY形式をパース
                        release_date = datetime.strptime(date_str, "%m/%d/%Y")
                        # 発表時刻は11:00 ET
                        release_time = release_date.replace(
                            hour=11, minute=0, second=0, microsecond=0, tzinfo=ET
                        )
                        release_time_jst = release_time.astimezone(JST)

                        schedules.append({
                            "date": release_time.strftime("%Y-%m-%d"),
                            "datetime_et": release_time.isoformat(),
                            "datetime_jst": release_time_jst.isoformat(),
                            "time_jst": release_time_jst.strftime("%H:%M"),
                            "label": f"NY Fed SCE ({release_time.strftime('%b %Y')})",
                        })
                    except ValueError as e:
                        print(f"Failed to parse date: {date_str} - {e}")

        # 日付昇順でソート
        schedules.sort(key=lambda x: x["date"])
        print(f"Found {len(schedules)} SCE release dates from NY Fed calendar")
        return schedules

    except Exception as e:
        print(f"Error fetching NY Fed calendar CSV: {e}")
        return []


def get_ny_fed_sce_schedule_cached() -> List[Dict[str, Any]]:
    """
    キャッシュ付きでSCE発表スケジュールを取得

    Returns:
        発表スケジュールのリスト
    """
    cache_key = "ny_fed_sce:schedule"

    # Redisキャッシュチェック
    cached = redis_client.get(cache_key)
    if cached and isinstance(cached, list) and len(cached) > 0:
        return cached

    # ファイルキャッシュチェック
    if SCHEDULE_CACHE_FILE.exists():
        try:
            with open(SCHEDULE_CACHE_FILE, 'r', encoding='utf-8') as f:
                file_cache = json.load(f)
                if file_cache.get("schedules") and file_cache.get("last_updated"):
                    last_updated = datetime.fromisoformat(file_cache["last_updated"])
                    if (datetime.now(JST) - last_updated).total_seconds() < SCHEDULE_CACHE_TTL_SECONDS:
                        schedules = file_cache["schedules"]
                        # Redisにも保存
                        redis_client.set(cache_key, schedules, expire=SCHEDULE_CACHE_TTL_SECONDS)
                        return schedules
        except Exception as e:
            print(f"Failed to load schedule cache: {e}")

    # CSVから取得
    schedules = fetch_ny_fed_sce_schedule_from_csv()

    if schedules:
        # Redisに保存
        redis_client.set(cache_key, schedules, expire=SCHEDULE_CACHE_TTL_SECONDS)

        # ファイルに保存
        try:
            with open(SCHEDULE_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    "schedules": schedules,
                    "last_updated": datetime.now(JST).isoformat()
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save schedule cache: {e}")

    return schedules


def get_next_ny_fed_sce_release() -> Optional[Dict[str, Any]]:
    """
    NY Fed SCEの次回発表日を取得（公式カレンダーベース）

    Returns:
        次回発表日情報
    """
    schedules = get_ny_fed_sce_schedule_cached()
    now = datetime.now(ET)

    for schedule in schedules:
        release_time = datetime.fromisoformat(schedule["datetime_et"])
        if release_time > now:
            return schedule

    return None


def get_last_ny_fed_sce_release() -> Optional[Dict[str, Any]]:
    """
    NY Fed SCEの直近の発表日を取得（過去、公式カレンダーベース）

    Returns:
        直近の発表日情報
    """
    schedules = get_ny_fed_sce_schedule_cached()
    now = datetime.now(ET)

    # 逆順で走査して、現在時刻以前の最新を見つける
    past_releases = [
        s for s in schedules
        if datetime.fromisoformat(s["datetime_et"]) <= now
    ]

    if past_releases:
        return past_releases[-1]  # 最新の過去発表

    return None


def invalidate_schedule_cache() -> bool:
    """
    スケジュールキャッシュを無効化

    Returns:
        成功したかどうか
    """
    redis_client.delete("ny_fed_sce:schedule")
    if SCHEDULE_CACHE_FILE.exists():
        SCHEDULE_CACHE_FILE.unlink()
    return True


class NYInflationExpectationsService:
    """NY連銀インフレ期待サービス"""

    DATA_CACHE_KEY = "inflation:ny_inflation_expectations:data"
    FALLBACK_CACHE_TTL_HOURS = 24  # フォールバック用TTL

    # 3分方式の更新ウィンドウ（分）
    UPDATE_WINDOW_MINUTES = 3

    # NY Fed SCE データURL
    SCE_DATA_URL = "https://www.newyorkfed.org/medialibrary/Interactives/sce/sce/downloads/data/FRBNY-SCE-Data.xlsx"

    def __init__(self):
        pass

    def get_inflation_expectations_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        NY連銀インフレ期待データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": {
                    "one_year": [{"date": "YYYY-MM-DD", "value": float}, ...],
                    "three_year": [...],
                    "five_year": [...]
                },
                "latest": {"one_year": float, "three_year": float, "five_year": float, "date": str},
                "next_release": {"date": str, "datetime_jst": str, "label": str} | null,
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
                    # 次回発表日を計算
                    next_release = get_next_ny_fed_sce_release()
                    return {
                        "data": cached_data.get("data", {}),
                        "latest": cached_data.get("latest"),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # NY Fed Excelからデータを取得
        result = self._fetch_from_nyfed()
        if result and any(result.get(k) for k in ["one_year", "three_year", "five_year"]):
            latest = self._get_latest_values(result)
            next_release = get_next_ny_fed_sce_release()

            cache_payload = {
                "data": result,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            # Redisに保存（TTLなし - 3分方式で管理）
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "NY Fed SCE",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            next_release = get_next_ny_fed_sce_release()
            return {
                "data": file_cache.get("data", {}),
                "latest": file_cache.get("latest"),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": {"one_year": [], "three_year": [], "five_year": []},
            "latest": None,
            "next_release": get_next_ny_fed_sce_release(),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_nyfed(self) -> Dict[str, List[Dict[str, Any]]]:
        """NY Fed SCE Excelファイルからデータを取得"""
        try:
            print(f"Fetching NY Fed SCE data from {self.SCE_DATA_URL}...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            response = requests.get(self.SCE_DATA_URL, headers=headers, timeout=60)
            response.raise_for_status()

            # ExcelファイルをDataFrameとして読み込み
            excel_data = pd.ExcelFile(io.BytesIO(response.content))
            print(f"Available sheets: {excel_data.sheet_names}")

            # Inflation Expectationsシートを読み込み（ヘッダー行は3行目）
            inflation_df = pd.read_excel(excel_data, sheet_name='Inflation expectations', header=3)
            print(f"Inflation expectations shape: {inflation_df.shape}")

            # Five-year ahead Infl Expシートを読み込み（ヘッダー行は3行目）
            five_year_df = pd.read_excel(excel_data, sheet_name='Five-year ahead Infl Exp', header=3)
            print(f"Five-year ahead shape: {five_year_df.shape}")

            # データを処理
            result = {
                "one_year": self._process_inflation_data(
                    inflation_df, "Median one-year ahead expected inflation rate"
                ),
                "three_year": self._process_inflation_data(
                    inflation_df, "Median three-year ahead expected inflation rate"
                ),
                "five_year": self._process_inflation_data(
                    five_year_df, "Median five-year ahead expected inflation rate"
                )
            }

            print(f"Fetched {len(result['one_year'])} one-year, "
                  f"{len(result['three_year'])} three-year, "
                  f"{len(result['five_year'])} five-year records")

            return result

        except Exception as e:
            print(f"Error fetching NY Fed SCE data: {e}")
            import traceback
            traceback.print_exc()
            return {"one_year": [], "three_year": [], "five_year": []}

    def _process_inflation_data(
        self, df: pd.DataFrame, column_name: str
    ) -> List[Dict[str, Any]]:
        """インフレ期待データを処理してAPI用フォーマットに変換"""
        try:
            # 日付列を特定（通常は最初の列）
            date_column = df.columns[0]

            # 対象列が存在するかチェック
            if column_name not in df.columns:
                print(f"Column '{column_name}' not found in dataframe")
                return []

            # データをクリーンアップ
            clean_df = df[[date_column, column_name]].dropna().copy()

            # YYYYMM形式（例：202201）を日付に変換
            def parse_yyyymm(value):
                try:
                    if pd.isna(value):
                        return None
                    # 整数をYYYYMM形式として解釈
                    value_str = str(int(value))
                    if len(value_str) == 6:
                        year = int(value_str[:4])
                        month = int(value_str[4:6])
                        # 月の1日として設定
                        return pd.Timestamp(year=year, month=month, day=1)
                    return None
                except Exception:
                    return None

            clean_df[date_column] = clean_df[date_column].apply(parse_yyyymm)
            clean_df = clean_df.dropna()

            # API用フォーマットに変換
            result = []
            for _, row in clean_df.iterrows():
                date_str = row[date_column].strftime('%Y-%m-%d')
                value = float(row[column_name]) if pd.notna(row[column_name]) else None

                if value is not None:
                    result.append({
                        "date": date_str,
                        "value": round(value, 2)
                    })

            # 日付順にソート
            result.sort(key=lambda x: x["date"])

            return result

        except Exception as e:
            print(f"Error processing inflation data for {column_name}: {e}")
            return []

    def _get_latest_values(
        self, data: Dict[str, List[Dict[str, Any]]]
    ) -> Optional[Dict[str, Any]]:
        """最新の値を取得"""
        latest = {}
        latest_date = None

        for horizon in ["one_year", "three_year", "five_year"]:
            if data.get(horizon):
                latest_point = data[horizon][-1]
                latest[horizon] = latest_point["value"]
                if latest_date is None or latest_point["date"] > latest_date:
                    latest_date = latest_point["date"]

        if latest_date:
            latest["date"] = latest_date

        return latest if latest else None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定（3分方式）

        判定ロジック:
        1. 直近の発表日時を計算（第2月曜日11:00 ET）
        2. 現在時刻が発表日時を過ぎているか確認
        3. 発表日時から3分以内なら、最終更新が発表日時より前なら更新
        4. 発表日時を3分以上過ぎていて、まだ更新していなければ更新
        5. フォールバック: 24時間以上経過していれば更新
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)

            # タイムゾーン情報がない場合は付与
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            # 直近の発表日時を取得
            last_release = get_last_ny_fed_sce_release()
            if last_release:
                release_datetime_str = last_release.get("datetime_jst")
                if release_datetime_str:
                    release_datetime = datetime.fromisoformat(release_datetime_str)

                    # 発表時刻より前なら更新不要
                    if now < release_datetime:
                        # フォールバックTTLチェック
                        elapsed_hours = (now - last_updated).total_seconds() / 3600
                        return elapsed_hours >= self.FALLBACK_CACHE_TTL_HOURS

                    # 3分方式での判定
                    update_window_end = release_datetime + timedelta(minutes=self.UPDATE_WINDOW_MINUTES)

                    if now <= update_window_end:
                        # 3分以内: 最終更新が発表時刻より前なら更新
                        if last_updated < release_datetime:
                            return True
                    else:
                        # 3分経過後: 発表時刻以降に更新していなければ更新
                        if last_updated < release_datetime:
                            return True

                    return False

            # フォールバック: 24時間TTL
            elapsed_hours = (now - last_updated).total_seconds() / 3600
            return elapsed_hours >= self.FALLBACK_CACHE_TTL_HOURS

        except Exception as e:
            print(f"Error checking refresh: {e}")
            return True

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

        data_counts = {}
        if cached_data and cached_data.get("data"):
            for horizon in ["one_year", "three_year", "five_year"]:
                data_counts[horizon] = len(cached_data["data"].get(horizon, []))

        # 次回・直近の発表日を取得
        next_release = get_next_ny_fed_sce_release()
        last_release = get_last_ny_fed_sce_release()

        return {
            "indicator": "NY Fed Inflation Expectations",
            "source": "NY Fed SCE",
            "cache_method": "NY Fed公式カレンダーベース3分方式",
            "schedule_source": NY_FED_CALENDAR_CSV_URL,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_counts": data_counts,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": next_release,
            "last_release": last_release,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
            "schedule_cache_exists": SCHEDULE_CACHE_FILE.exists()
        }


# シングルトンインスタンス
ny_inflation_expectations_service = NYInflationExpectationsService()
