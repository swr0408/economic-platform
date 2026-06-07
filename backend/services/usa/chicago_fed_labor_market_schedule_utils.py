"""
Chicago Fed Labor Market Indicators 発表スケジュールユーティリティ

Chicago Fed の Labor Market Indicators (Real-Time Unemployment Rate Forecast 等)
の発表日を release-schedule ページからスクレイピングして取得する。

データソース:
- URL: https://www.chicagofed.org/research/data/chicago-fed-labor-market-indicators/release-schedule
- 発表時刻: 8:30 a.m. ET / 7:30 a.m. CT
- 頻度: 月2回 (Advance: NFP発表前木曜, Final: NFP発表翌週初頭)

スケジュールキャッシュ方針:
- TTL は 180日（半年）
- 加えて 1月 / 7月 のリフレッシュをトリガー（公式ページ自体が半期更新される想定）
"""
import json
import re
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, List
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from core.redis_client import redis_client


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# Chicago Fed Labor Market Indicators 公開ページ
CFLMI_SCHEDULE_URL = (
    "https://www.chicagofed.org/research/data/chicago-fed-labor-market-indicators/release-schedule"
)

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
SCHEDULE_CACHE_FILE = CACHE_DIR / "chicago_fed_unemployment_rate_forecast_schedule.json"

# Redisキャッシュキー
SCHEDULE_CACHE_KEY = "chicagofed:labor_market:schedule"

# スケジュールキャッシュTTL（60日）— 1月/7月リフレッシュおよび未来日枯渇検出が主トリガー、TTLは安全網
SCHEDULE_CACHE_TTL_SECONDS = 60 * 24 * 60 * 60

# 半期リフレッシュ対象月（Chicago Fed が概ね半期ペースで schedule を更新するため）
SEMIANNUAL_REFRESH_MONTHS = {1, 7}

# 発表時刻設定（ET）— 8:30 a.m. ET
RELEASE_HOUR_ET = 8
RELEASE_MINUTE_ET = 30

# 発表後の更新チェック期間（分）— 3分方式
UPDATE_WINDOW_MINUTES = 3

# 月名マッピング
_MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


def _parse_release_date(text: str) -> Optional[date]:
    """
    "Thursday, May 28, 2026" や "Tuesday, November 24, 2026" 等の日付テキストをパースする
    """
    if not text:
        return None
    cleaned = text.strip()
    # 曜日プレフィックス除去
    cleaned = re.sub(r"^[A-Za-z]+,\s*", "", cleaned)
    # "May 28, 2026" → 標準フォーマットで試す
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    # 月名・日・年を正規表現で抽出
    match = re.search(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", cleaned)
    if match:
        month_str, day_str, year_str = match.groups()
        month = _MONTH_MAP.get(month_str.lower())
        if month:
            try:
                return date(int(year_str), month, int(day_str))
            except ValueError:
                return None
    return None


def fetch_schedule_from_web() -> List[Dict[str, Any]]:
    """
    Chicago Fed Labor Market Indicators release-schedule ページをスクレイピング

    Returns:
        発表日リスト
        [{"date": "YYYY-MM-DD", "report": "May 2026 Advance", "type": "advance"|"final"}, ...]
    """
    try:
        print(f"Fetching Chicago Fed Labor Market schedule from {CFLMI_SCHEDULE_URL}...")
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            )
        }
        response = requests.get(CFLMI_SCHEDULE_URL, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        tables = soup.find_all("table")

        schedule: List[Dict[str, Any]] = []
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue
                if row.find("th"):
                    continue

                report_text = cells[0].get_text(" ", strip=True)
                date_text = cells[1].get_text(" ", strip=True)
                if not report_text or not date_text:
                    continue

                release_date = _parse_release_date(date_text)
                if not release_date:
                    continue

                lower_report = report_text.lower()
                if "advance" in lower_report:
                    report_type = "advance"
                elif "final" in lower_report:
                    report_type = "final"
                else:
                    report_type = "other"

                schedule.append({
                    "date": release_date.strftime("%Y-%m-%d"),
                    "report": report_text,
                    "type": report_type,
                })

        # 日付昇順
        schedule.sort(key=lambda x: x["date"])
        print(f"Fetched {len(schedule)} Chicago Fed Labor Market release dates")
        return schedule
    except Exception as e:
        print(f"Error fetching Chicago Fed Labor Market schedule: {e}")
        import traceback
        traceback.print_exc()
        return []


def _load_file_cache() -> Optional[Dict[str, Any]]:
    if not SCHEDULE_CACHE_FILE.exists():
        return None
    try:
        with open(SCHEDULE_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading schedule file cache: {e}")
        return None


def _save_file_cache(payload: Dict[str, Any]) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(SCHEDULE_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving schedule file cache: {e}")


def _needs_refresh(payload: Optional[Dict[str, Any]]) -> bool:
    """
    キャッシュペイロードを基にリフレッシュ要否を判定

    - キャッシュ無し: True
    - TTL（180日）経過: True
    - 1月 / 7月で当該月にまだリフレッシュしていない: True
    - 残り未来発表日が 1 件以下: True
    """
    if not payload:
        return True

    last_updated_str = payload.get("last_updated")
    schedule = payload.get("schedule", [])
    if not last_updated_str or not schedule:
        return True

    try:
        last_updated = datetime.fromisoformat(last_updated_str)
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=JST)
    except Exception:
        return True

    now = datetime.now(JST)

    # TTLチェック
    if (now - last_updated).total_seconds() >= SCHEDULE_CACHE_TTL_SECONDS:
        return True

    # 1月 / 7月の半期リフレッシュ
    if now.month in SEMIANNUAL_REFRESH_MONTHS:
        last_year_month = (last_updated.year, last_updated.month)
        if last_year_month != (now.year, now.month):
            return True

    # 未来の発表日が 1 件以下しか残っていなければ更新
    today = date.today()
    future_count = sum(
        1 for item in schedule
        if _safe_date_parse(item.get("date")) and _safe_date_parse(item["date"]) >= today
    )
    if future_count <= 1:
        return True

    return False


def _safe_date_parse(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return None


def get_schedule(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Chicago Fed Labor Market 発表スケジュールを取得（キャッシュ利用）

    Args:
        force_refresh: キャッシュを無視して再取得

    Returns:
        発表日リスト
    """
    # Redisキャッシュチェック
    if not force_refresh:
        cached = redis_client.get(SCHEDULE_CACHE_KEY)
        if cached and not _needs_refresh(cached):
            return cached.get("schedule", [])

    # ファイルキャッシュチェック
    if not force_refresh:
        file_cache = _load_file_cache()
        if file_cache and not _needs_refresh(file_cache):
            redis_client.set(SCHEDULE_CACHE_KEY, file_cache, expire=SCHEDULE_CACHE_TTL_SECONDS)
            return file_cache.get("schedule", [])

    # スクレイピング
    schedule = fetch_schedule_from_web()
    if not schedule:
        # 取得失敗時は既存キャッシュをフォールバック利用
        cached = redis_client.get(SCHEDULE_CACHE_KEY) or _load_file_cache()
        if cached:
            return cached.get("schedule", [])
        return []

    payload = {
        "schedule": schedule,
        "last_updated": datetime.now(JST).isoformat(),
    }
    redis_client.set(SCHEDULE_CACHE_KEY, payload, expire=SCHEDULE_CACHE_TTL_SECONDS)
    _save_file_cache(payload)
    return schedule


def _build_release_info(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    release_date = _safe_date_parse(item.get("date"))
    if not release_date:
        return None
    release_et = datetime(
        release_date.year, release_date.month, release_date.day,
        RELEASE_HOUR_ET, RELEASE_MINUTE_ET, 0,
        tzinfo=ET,
    )
    release_jst = release_et.astimezone(JST)
    return {
        "date": item["date"],
        "datetime_jst": release_jst.isoformat(),
        "time_jst": release_jst.strftime("%H:%M"),
        "label": item.get("report", ""),
        "type": item.get("type", "unknown"),
    }


def get_next_release() -> Optional[Dict[str, Any]]:
    """
    次回発表日（未来の最古日付）を取得
    """
    schedule = get_schedule()
    today = date.today()
    for item in schedule:
        release_date = _safe_date_parse(item.get("date"))
        if release_date and release_date >= today:
            return _build_release_info(item)
    return None


def get_last_release() -> Optional[Dict[str, Any]]:
    """
    直近の過去発表日を取得
    """
    schedule = get_schedule()
    today = date.today()
    past_items = [
        item for item in schedule
        if _safe_date_parse(item.get("date")) and _safe_date_parse(item["date"]) <= today
    ]
    if not past_items:
        return None
    past_items.sort(key=lambda x: x["date"], reverse=True)
    return _build_release_info(past_items[0])


def expected_reference_date_from_label(label: Optional[str]) -> Optional[date]:
    """
    report label から、Excel に含まれるべきデータの参照月を推定

    例: 'May 2026 Advance' → date(2026, 5, 15)
        'November 2026 Final' → date(2026, 11, 15)

    Excel の forecast_data の最新行は、この月の BLS reference week 終点
    （通常は月の第3週木曜前後）になる想定。
    """
    if not label:
        return None
    match = re.search(r"([A-Za-z]+)\s+(\d{4})", label)
    if not match:
        return None
    month_str, year_str = match.groups()
    month = _MONTH_MAP.get(month_str.lower())
    if not month:
        return None
    try:
        # 月の代表日として中ごろを返す
        return date(int(year_str), month, 15)
    except ValueError:
        return None


def should_refresh_by_schedule(last_updated_str: Optional[str]) -> bool:
    """
    Chicago Fed Labor Market スケジュールに基づいて、3分方式でキャッシュ更新が必要かを判定

    判定ロジック:
    - 直近の発表日時を取得
    - last_updated が直近発表時刻より前なら True

    Args:
        last_updated_str: 最終更新日時のISO文字列

    Returns:
        True: 更新が必要 / False: キャッシュ有効
    """
    if not last_updated_str:
        return True
    try:
        last_updated = datetime.fromisoformat(last_updated_str)
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=JST)

        now = datetime.now(JST)
        last_release = get_last_release()
        if not last_release:
            # フォールバック: 24h TTL
            elapsed_hours = (now - last_updated).total_seconds() / 3600
            return elapsed_hours >= 24

        release_datetime = datetime.fromisoformat(last_release["datetime_jst"])
        if now < release_datetime:
            return False
        # 発表時刻より前に更新していなければリフレッシュ
        return last_updated < release_datetime
    except Exception as e:
        print(f"Error checking Chicago Fed Labor Market refresh: {e}")
        return False


def invalidate_schedule_cache() -> bool:
    """スケジュールキャッシュを無効化"""
    try:
        redis_client.delete(SCHEDULE_CACHE_KEY)
        if SCHEDULE_CACHE_FILE.exists():
            SCHEDULE_CACHE_FILE.unlink()
        return True
    except Exception as e:
        print(f"Error invalidating Chicago Fed Labor Market schedule cache: {e}")
        return False
