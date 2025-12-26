"""Check next release date for unemployment rate"""
import sys
sys.path.insert(0, "C:/Users/owner/Desktop/economic-platform/backend")
from services.usa.unemployment_rate_service import unemployment_rate_service
from datetime import date, datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
now_et = datetime.now(ET)
print(f"Current time (ET): {now_et}")
print(f"Current date (ET): {now_et.date()}")

# スケジュールキャッシュを直接確認
cached_schedule = unemployment_rate_service._get_cached_schedule()
print(f"\nCached schedule: {cached_schedule}")

# 次回発表日を直接取得
next_release = unemployment_rate_service._get_next_release()
print(f"\nNext release: {next_release}")

# フォールバック計算を確認
fallback = unemployment_rate_service._calculate_next_release_fallback()
print(f"\nFallback calculation: {fallback}")

# 2025年1月の第1金曜日を計算
import calendar
year = 2025
month = 1
cal = calendar.monthcalendar(year, month)
first_friday = None
for week in cal:
    if week[4] != 0:
        first_friday = week[4]
        break
print(f"\n2025/1 first Friday: {year}-{month:02d}-{first_friday:02d}")
