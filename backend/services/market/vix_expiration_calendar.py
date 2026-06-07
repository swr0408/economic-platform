"""
VIX先物 満期日カレンダー

VIX先物の標準満期は「次月の第3金曜の30日前の水曜日」。
祝日の場合は前営業日にシフトする。

CFE仕様: https://www.cboe.com/tradable_products/vix/vix_futures/specifications/
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import List


def _third_friday(year: int, month: int) -> date:
    """指定月の第3金曜を返す"""
    d = date(year, month, 1)
    offset = (4 - d.weekday()) % 7  # Friday = 4
    first_friday = d + timedelta(days=offset)
    return first_friday + timedelta(days=14)


def _standard_vx_expiry(year: int, month: int) -> date:
    """指定月の標準VIX満期日

    CBOE仕様: 次月の第3金曜の30日前の水曜。
    ただし、次月の第3金曜がCBOE休場日（Good Friday 等）の場合は、
    その直前営業日を基準として30日前を算出する。
    """
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1
    third_fri_next = _third_friday(next_year, next_month)
    ref = third_fri_next
    if ref in _KNOWN_HOLIDAYS:
        ref = ref - timedelta(days=1)
        while ref.weekday() >= 5 or ref in _KNOWN_HOLIDAYS:
            ref -= timedelta(days=1)
    return ref - timedelta(days=30)


# NYSE/CFE 主要祝日（VX満期日の前倒し対象）
# 2013-2030をカバー。網羅性より「VX満期日近辺で前倒しを引き起こす可能性のある日」に絞る。
_KNOWN_HOLIDAYS = {
    # MLK Day (Jan 3rd Mon) -- VX expiry typically not affected (mid-month vs MLK in 3rd week)
    # Washington's Birthday (Feb 3rd Mon) -- possible conflict with Feb VX
    date(2014, 2, 17), date(2015, 2, 16), date(2016, 2, 15), date(2017, 2, 20),
    date(2018, 2, 19), date(2019, 2, 18), date(2020, 2, 17), date(2021, 2, 15),
    date(2022, 2, 21), date(2023, 2, 20), date(2024, 2, 19), date(2025, 2, 17),
    date(2026, 2, 16), date(2027, 2, 15), date(2028, 2, 21), date(2029, 2, 19), date(2030, 2, 18),
    # Good Friday -- affects Apr VX in some years
    date(2013, 3, 29), date(2014, 4, 18), date(2015, 4, 3), date(2016, 3, 25),
    date(2017, 4, 14), date(2018, 3, 30), date(2019, 4, 19), date(2020, 4, 10),
    date(2021, 4, 2), date(2022, 4, 15), date(2023, 4, 7), date(2024, 3, 29),
    date(2025, 4, 18), date(2026, 4, 3), date(2027, 3, 26), date(2028, 4, 14),
    date(2029, 3, 30), date(2030, 4, 19),
    # Juneteenth (since 2022)
    date(2022, 6, 20), date(2023, 6, 19), date(2024, 6, 19), date(2025, 6, 19),
    date(2026, 6, 19), date(2027, 6, 18), date(2028, 6, 19), date(2029, 6, 19), date(2030, 6, 19),
}


def _previous_business_day(d: date) -> date:
    out = d - timedelta(days=1)
    while out.weekday() >= 5 or out in _KNOWN_HOLIDAYS:
        out -= timedelta(days=1)
    return out


def vx_expiry_date(year: int, month: int) -> date:
    """指定月のVIX先物満期日（祝日補正済）"""
    d = _standard_vx_expiry(year, month)
    if d.weekday() >= 5 or d in _KNOWN_HOLIDAYS:
        d = _previous_business_day(d)
    return d


def list_vx_expiries(start: date, end: date) -> List[date]:
    """start以降〜end以前に満期を迎えるVIX先物の満期日一覧（昇順）"""
    out: List[date] = []
    y, m = start.year, start.month
    # 余裕を持って12ヶ月前から走査
    if m == 1:
        y -= 1
        m = 12
    else:
        m -= 1
    while True:
        exp = vx_expiry_date(y, m)
        if exp > end:
            break
        if exp >= start:
            out.append(exp)
        m += 1
        if m > 12:
            y += 1
            m = 1
    return out


def next_expiry_after(d: date, expiries: List[date]) -> int:
    """日付 d 当日含めて、これ以降の最初の満期インデックスを返す（無ければ -1）"""
    for i, exp in enumerate(expiries):
        if exp >= d:
            return i
    return -1
