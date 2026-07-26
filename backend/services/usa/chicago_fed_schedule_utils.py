"""
Chicago Fed発表スケジュールユーティリティ

Chicago Fed Data Release Calendarから発表日を取得する共通関数を提供。

使用方法:
    from services.usa.chicago_fed_schedule_utils import (
        get_carts_next_release,
        should_refresh_by_chicago_fed_schedule,
    )

    # 次回発表日を取得
    next_release = get_carts_next_release()
    # -> {'date': '2025-01-09', 'datetime_jst': '2025-01-09T22:30:00+09:00', 'label': 'November 2024 (Preliminary)'}

    # 発表日に基づく更新判定
    if should_refresh_by_chicago_fed_schedule(last_updated_str):
        # データ更新処理

データソース:
- URL: https://www.chicagofed.org/research/data/data-release-calendar#carts-table
- テーブルID: carts-table
- 発表時刻: 8:30 ET
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

# Chicago Fed Data Release Calendar URL
CHICAGO_FED_SCHEDULE_URL = "https://www.chicagofed.org/research/data/data-release-calendar"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CARTS_SCHEDULE_CACHE_FILE = CACHE_DIR / "carts_schedule.json"

# Redisキャッシュキー
CARTS_SCHEDULE_CACHE_KEY = "chicagofed:carts:schedule"

# スケジュールキャッシュの有効期間（7日）
SCHEDULE_CACHE_TTL = 7 * 24 * 60 * 60  # 604800秒

# 発表時刻設定（ET）
RELEASE_HOUR_ET = 8
RELEASE_MINUTE_ET = 30

# 発表後の更新チェック期間（分）- 3分方式
UPDATE_WINDOW_MINUTES = 3


def fetch_carts_schedule() -> List[Dict[str, Any]]:
    """
    Chicago Fedカレンダーページからcarts-tableをスクレイピング

    Returns:
        発表日リスト: [{'date': 'YYYY-MM-DD', 'label': str, 'type': 'preliminary'|'final'}, ...]
    """
    try:
        print(f"Fetching CARTS schedule from {CHICAGO_FED_SCHEDULE_URL}...")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        response = requests.get(CHICAGO_FED_SCHEDULE_URL, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # carts-tableを探す
        carts_table = soup.find('table', id='carts-table')
        if not carts_table:
            # idで見つからない場合、アンカーリンクを探す
            carts_section = soup.find('a', {'name': 'carts-table'}) or soup.find('div', id='carts-table')
            if carts_section:
                carts_table = carts_section.find_next('table')

        if not carts_table:
            print("CARTS table not found on page")
            return []

        schedule = []
        rows = carts_table.find_all('tr')

        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                continue

            # ヘッダー行をスキップ
            if row.find('th'):
                continue

            date_text = cells[0].get_text(strip=True)
            reference_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""

            # 日付をパース（例: "December 5, 2025" or "2025年12月5日"）
            parsed_date = _parse_release_date(date_text)
            if not parsed_date:
                continue

            # 予備版/確定版の判定
            release_type = "final"
            if "preliminary" in reference_text.lower():
                release_type = "preliminary"
            elif "final" in reference_text.lower():
                release_type = "final"

            schedule.append({
                "date": parsed_date.strftime("%Y-%m-%d"),
                "label": reference_text,
                "type": release_type,
            })

        print(f"Fetched {len(schedule)} CARTS release dates")
        return schedule

    except Exception as e:
        print(f"Error fetching CARTS schedule: {e}")
        import traceback
        traceback.print_exc()
        return []


def _parse_release_date(date_text: str) -> Optional[date]:
    """
    日付テキストをパース

    対応フォーマット:
    - "December 5, 2025"
    - "Dec 5, 2025"
    - "2025-12-05"
    """
    import locale

    # 複数のフォーマットを試す
    formats = [
        "%B %d, %Y",      # December 5, 2025
        "%b %d, %Y",      # Dec 5, 2025
        "%Y-%m-%d",       # 2025-12-05
        "%m/%d/%Y",       # 12/05/2025
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_text, fmt).date()
        except ValueError:
            continue

    # 数字のみ抽出してパース
    match = re.search(r'(\w+)\s+(\d{1,2}),?\s+(\d{4})', date_text)
    if match:
        month_str, day_str, year_str = match.groups()
        month_map = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12,
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
            'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        month = month_map.get(month_str.lower())
        if month:
            try:
                return date(int(year_str), month, int(day_str))
            except ValueError:
                pass

    return None


def get_carts_schedule(use_cache: bool = True) -> List[Dict[str, Any]]:
    """
    CARTSスケジュールを取得（キャッシュ利用）

    Args:
        use_cache: キャッシュを使用するか

    Returns:
        発表日リスト
    """
    if use_cache:
        # Redisキャッシュチェック
        cached = redis_client.get(CARTS_SCHEDULE_CACHE_KEY)
        if cached:
            return cached.get("schedule", [])

        # ファイルキャッシュチェック
        if CARTS_SCHEDULE_CACHE_FILE.exists():
            try:
                with open(CARTS_SCHEDULE_CACHE_FILE, 'r', encoding='utf-8') as f:
                    file_cache = json.load(f)
                    last_updated_str = file_cache.get("last_updated")
                    if last_updated_str:
                        last_updated = datetime.fromisoformat(last_updated_str)
                        if (datetime.now(JST) - last_updated.replace(tzinfo=JST)).total_seconds() < SCHEDULE_CACHE_TTL:
                            # Redisにも保存
                            redis_client.set(CARTS_SCHEDULE_CACHE_KEY, file_cache, expire=SCHEDULE_CACHE_TTL)
                            return file_cache.get("schedule", [])
            except Exception as e:
                print(f"Error loading schedule cache: {e}")

    # スクレイピングで取得
    schedule = fetch_carts_schedule()

    if schedule:
        cache_payload = {
            "schedule": schedule,
            "last_updated": datetime.now(JST).isoformat()
        }
        # Redisに保存
        redis_client.set(CARTS_SCHEDULE_CACHE_KEY, cache_payload, expire=SCHEDULE_CACHE_TTL)
        # ファイルにも保存
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(CARTS_SCHEDULE_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving schedule cache: {e}")

    return schedule


def get_carts_next_release(use_cache: bool = True) -> Optional[Dict[str, Any]]:
    """
    CARTSの次回発表日を取得

    Args:
        use_cache: キャッシュを使用するか

    Returns:
        次回発表日情報:
        {
            'date': 'YYYY-MM-DD',
            'datetime_jst': 'ISO形式',
            'time_jst': 'HH:MM',
            'label': '参照期間',
            'type': 'preliminary' | 'final'
        }
    """
    schedule = get_carts_schedule(use_cache)
    if not schedule:
        return None

    today = date.today()

    for item in schedule:
        release_date = datetime.strptime(item["date"], "%Y-%m-%d").date()
        if release_date >= today:
            # 発表日時をJSTに変換
            release_datetime_et = datetime(
                release_date.year, release_date.month, release_date.day,
                RELEASE_HOUR_ET, RELEASE_MINUTE_ET, 0,
                tzinfo=ET
            )
            release_datetime_jst = release_datetime_et.astimezone(JST)

            return {
                "date": item["date"],
                "datetime_jst": release_datetime_jst.isoformat(),
                "time_jst": release_datetime_jst.strftime("%H:%M"),
                "label": item.get("label", ""),
                "type": item.get("type", "unknown"),
            }

    return None


def get_carts_last_release(use_cache: bool = True) -> Optional[Dict[str, Any]]:
    """
    CARTSの直近の発表日を取得（過去）

    Args:
        use_cache: キャッシュを使用するか

    Returns:
        直近の発表日情報
    """
    schedule = get_carts_schedule(use_cache)
    if not schedule:
        return None

    today = date.today()
    past_releases = []

    for item in schedule:
        release_date = datetime.strptime(item["date"], "%Y-%m-%d").date()
        if release_date <= today:
            # 発表日時をJSTに変換
            release_datetime_et = datetime(
                release_date.year, release_date.month, release_date.day,
                RELEASE_HOUR_ET, RELEASE_MINUTE_ET, 0,
                tzinfo=ET
            )
            release_datetime_jst = release_datetime_et.astimezone(JST)

            past_releases.append({
                "date": item["date"],
                "datetime_jst": release_datetime_jst.isoformat(),
                "time_jst": release_datetime_jst.strftime("%H:%M"),
                "label": item.get("label", ""),
                "type": item.get("type", "unknown"),
            })

    if past_releases:
        # 日付降順でソートして最新を返す
        past_releases.sort(key=lambda x: x["date"], reverse=True)
        return past_releases[0]

    return None


def should_refresh_by_chicago_fed_schedule(last_updated_str: str) -> bool:
    """
    Chicago Fedスケジュールに基づいて、3分方式でキャッシュ更新が必要かを判定

    判定ロジック（3分方式）:
    1. 直近の発表日時を取得
    2. 現在時刻が発表日時を過ぎているか確認
    3. 発表日時から3分以内なら、最終更新が発表日時より前なら更新
    4. 発表日時を3分以上過ぎていて、まだ更新していなければ更新

    Args:
        last_updated_str: 最終更新日時のISO文字列

    Returns:
        True: 更新が必要
        False: キャッシュ有効
    """
    try:
        # 最終更新日時をパース
        last_updated = datetime.fromisoformat(last_updated_str)
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=JST)

        now = datetime.now(JST)

        # max-age フォールバック（発表レース凍結の自己回復）:
        # 発表時刻ちょうどの再取得でソース未反映のまま last_updated=now を刻むと、
        # 下の発表日時判定(last_updated < release_datetime)が False となり次回発表まで
        # 凍結する。週次のため48hで必ず再取得させ当該週内に自己回復させる。
        if (now - last_updated).total_seconds() > 48 * 3600:
            return True

        # 直近の発表日時を取得
        last_release_info = get_carts_last_release()
        if not last_release_info:
            # スケジュールが取得できない場合はフォールバック（24時間TTL）
            elapsed_hours = (now - last_updated).total_seconds() / 3600
            return elapsed_hours >= 24

        # 発表日時をパース
        release_datetime_str = last_release_info.get("datetime_jst")
        if not release_datetime_str:
            return False

        release_datetime = datetime.fromisoformat(release_datetime_str)

        # 発表時刻より前なら更新不要
        if now < release_datetime:
            return False

        # 3分方式での判定
        update_window_end = release_datetime + timedelta(minutes=UPDATE_WINDOW_MINUTES)
        in_update_window = now <= update_window_end

        if in_update_window:
            # 3分以内: 最終更新が発表時刻より前なら更新
            if last_updated < release_datetime:
                return True
        else:
            # 3分経過後: 発表時刻以降に更新していなければ更新
            if last_updated < release_datetime:
                return True

        return False

    except Exception as e:
        print(f"Error checking refresh by Chicago Fed schedule: {e}")
        return False


def invalidate_carts_schedule_cache() -> bool:
    """
    CARTSスケジュールキャッシュを無効化
    """
    try:
        redis_client.delete(CARTS_SCHEDULE_CACHE_KEY)
        if CARTS_SCHEDULE_CACHE_FILE.exists():
            CARTS_SCHEDULE_CACHE_FILE.unlink()
        return True
    except Exception as e:
        print(f"Error invalidating CARTS schedule cache: {e}")
        return False
