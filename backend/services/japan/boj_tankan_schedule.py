"""日銀短観 調査全容(zenyo)の公表スケジュールに基づく鮮度判定。

短観は 3/6/9/12 月調査。**概要**（GA_J1.xlsx 等）は各四半期の翌月初
（12 月調査のみ当月中旬）に公表されるが、業況判断DI・価格DI等の源である
**調査全容 (zenyo) の Excel は概要の概ね翌営業日**に公表される（例: 2026年
3月調査は概要 4/1・調査全容 4/2、6月調査は概要 7/1・調査全容 7/2）。

このため「概要の発表日（FMPカレンダー）」でキャッシュ鮮度を判定すると、
発表当日に再取得しても調査全容がまだ 404 で取れず、旧四半期のまま固着し、
次の発表（3か月後）まで再取得されない。

本モジュールは「今日時点で調査全容が公表済みであるべき最新調査四半期末日」を
返し、保有データがそれに未達なら（レート制限付きで）再取得を促す。実ファイル
未公表時の空振りは last_updated ベースのレート制限で吸収する。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional


def expected_latest_quarter_end(now: Optional[datetime] = None) -> str:
    """今日時点で調査全容(zenyo)が公表済みであるべき最新調査四半期の四半期末日 (YYYY-MM-DD)。

    境界は概要日に置く（調査全容の 1 日遅れは呼び出し側のレート制限付き再取得で吸収）:
      3月調査 → 4/1 以降   (四半期末 3-31)
      6月調査 → 7/1 以降   (四半期末 6-30)
      9月調査 → 10/1 以降  (四半期末 9-30)
      12月調査 → 12/13 以降 (四半期末 12-31, 12月調査は概要も中旬)
    境界前は直前四半期を最新とみなす。
    """
    now = now or datetime.now()
    y = now.year
    if now.month == 12 and now.day >= 13:
        return f"{y}-12-31"
    if now.month >= 10:
        return f"{y}-09-30"
    if now.month >= 7:
        return f"{y}-06-30"
    if now.month >= 4:
        return f"{y}-03-31"
    return f"{y - 1}-12-31"


def _latest_date(cached: Dict[str, Any]) -> str:
    data = (cached or {}).get("data") or []
    latest = ""
    if isinstance(data, list):
        for p in data:
            if isinstance(p, dict):
                d = p.get("date") or ""
                if d and d > latest:
                    latest = d
    return latest


def needs_release_refetch(
    cached: Optional[Dict[str, Any]],
    now: Optional[datetime] = None,
    recheck_seconds: int = 6 * 3600,
) -> bool:
    """保有データが公表済みであるべき調査四半期に未達なら再取得を促す（レート制限付き）。

    - 最新四半期を保持済みなら False（キャッシュを返して良い）。
    - 未達でも last_updated から recheck_seconds 未満なら False（調査全容の公表待ち
      期間に BOJ を叩き続けないための空振り連打防止）。
    - cached が空/None なら False（呼び出し側の既存分岐に委ねる）。
    """
    if not cached:
        return False
    now = now or datetime.now()
    latest = _latest_date(cached)
    if latest and latest >= expected_latest_quarter_end(now):
        return False  # 最新四半期を保持済み → 再取得不要

    lu_str = cached.get("last_updated")
    if lu_str:
        try:
            lu = datetime.fromisoformat(lu_str)
            if lu.tzinfo is not None:
                lu = lu.replace(tzinfo=None)
            base = now.replace(tzinfo=None) if now.tzinfo is not None else now
            if (base - lu).total_seconds() < recheck_seconds:
                return False  # 直近で試行済み → 全容公表までレート制限
        except Exception:
            pass
    return True
