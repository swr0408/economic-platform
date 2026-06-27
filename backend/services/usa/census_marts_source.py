"""
Census MARTS (Advance Monthly Retail Trade Survey) ソース

リテールコントロール(コントロールグループ)を、公式の標準定義どおり構成要素の
引き算で算出する。

    コントロールグループ(標準) =
        総合(44X72) − 自動車&部品(441) − ガソリン(447) − 建材&園芸(444) − 飲食(722)

- 季節調整済(SA)の月次水準を Census econ_export(XLS, APIキー不要)から取得。
- Census の SA 系列は加法的(検証済: total−722=Retail / total−441−447=excl auto&gas が
  厳密一致)なので、引き算で控除群の水準が一貫して得られる。
- 値は「最新改定版」(FRED と同じ思想)。当時の発表値(速報)とは改定/ベンチマークにより
  ずれるが、定義に忠実で全履歴(1992-)・自動更新できる点を優先する。
"""
import io
from datetime import datetime
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

import pandas as pd
import requests

JST = ZoneInfo("Asia/Tokyo")

# Census MARTS カテゴリコード
_TOTAL = "44X72"                      # Retail & Food Services: Total
_EXCLUSIONS = ["441", "447", "444", "722"]  # 自動車&部品 / ガソリン / 建材&園芸 / 飲食
_CATS = [_TOTAL] + _EXCLUSIONS

_BASE_URL = "https://www.census.gov/econ_export/"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def _fetch_series(cat: str, start_year: int, end_year: int) -> Dict[str, float]:
    """指定カテゴリの季調済(SA)月次水準を {YYYY-MM-01: value} で返す。"""
    params = {
        "format": "xls",
        "mode": "report",
        "program": "MARTS",
        "startYear": str(start_year),
        "endYear": str(end_year),
        "categories[0]": cat,
        "dataType": "SM",          # Sales - Monthly (水準)
        "geoLevel": "US",
        "adjusted": "true",        # 季節調整済
        "notAdjusted": "false",
        "errorData": "false",
        "vert": "1",
    }
    resp = requests.get(_BASE_URL, params=params, headers=_HEADERS, timeout=60)
    resp.raise_for_status()

    df = pd.ExcelFile(io.BytesIO(resp.content)).parse("CIDR", header=None)

    # "Period" / "Value" のヘッダー行を探す
    header_row = None
    for i in range(len(df)):
        if str(df.iloc[i, 0]).strip() == "Period":
            header_row = i
            break
    if header_row is None:
        return {}

    out: Dict[str, float] = {}
    for _, row in df.iloc[header_row + 1:].iterrows():
        period, value = row[0], row[1]
        if pd.isna(period) or pd.isna(value):
            continue
        try:
            d = datetime.strptime(str(period).strip(), "%b-%Y")  # 例 "May-2026"
            out[d.strftime("%Y-%m-01")] = float(value)
        except (ValueError, TypeError):
            continue
    return out


def fetch_control_group(start_year: int = 1992) -> List[Dict[str, Any]]:
    """
    コントロールグループの月次系列を算出して返す。

    Returns:
        [{"date": "YYYY-MM-01", "mom": float|None, "yoy": float|None,
          "level": float}, ...]  (日付昇順)
        取得失敗時は [] (呼び出し側でファイルキャッシュにフォールバックする)。
    """
    end_year = datetime.now(JST).year

    series: Dict[str, Dict[str, float]] = {}
    for cat in _CATS:
        s = _fetch_series(cat, start_year, end_year)
        if not s:
            # いずれかの構成要素が取れなければ算出不能 → 空で返す(既存キャッシュ維持)
            print(f"[CensusMARTS] category {cat} returned no data; aborting")
            return []
        series[cat] = s

    total = series[_TOTAL]

    # 控除群水準 = total − 除外要素。全要素が揃う月のみ算出。
    levels: Dict[str, float] = {}
    for date, tot in total.items():
        try:
            lvl = tot - sum(series[c][date] for c in _EXCLUSIONS)
        except KeyError:
            continue
        levels[date] = lvl

    dates = sorted(levels)
    by_date = dict(levels)
    result: List[Dict[str, Any]] = []
    for i, date in enumerate(dates):
        cur = levels[date]
        mom = None
        if i >= 1:
            prev = levels[dates[i - 1]]
            if prev:
                mom = round((cur - prev) / prev * 100, 2)
        # YoY: 12ヶ月前(同月)
        yoy = None
        y, m = int(date[:4]), int(date[5:7])
        ago = f"{y - 1}-{m:02d}-01"
        if ago in by_date and by_date[ago]:
            yoy = round((cur - by_date[ago]) / by_date[ago] * 100, 2)
        result.append({
            "date": date,
            "mom": mom,
            "yoy": yoy,
            "level": round(cur, 1),
        })
    return result
