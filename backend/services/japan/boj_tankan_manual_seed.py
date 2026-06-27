"""
日銀短観 手動CSV種（BOJ時系列統計データ検索サイトのネイティブCSVエクスポート）取込み。

ユーザーが stat-search からダウンロードした CSV をそのまま
`data/manual_update/japan/tankan/*.csv` に置くだけで、数十年の履歴を
各チャートの系列キー構造へマッピングして返す。

ネイティブ形式:
  行0: データコード,CO'TK99...,CO'TK99...
  行1: 系列名称,"D.I./業況/大企業/製造業/実績",...
  行2+: 期間(YYYY または YYYY/MM),値,値,...

仕様:
- 検索サイトのコードは先頭 "CO'" + フラットファイルコード(20桁)。
- DI(計算形態G): 実績(実績予測=0)=現況、予測(=1)=先行き。予測値は「予測対象の期」に
  格納されるため、調査期=対象期-1四半期 に戻して保存する（zenyo解析と同じ構造）。
- 設備投資(項目109/計算C/期種FY): 年度(YYYY)→年度末(YYYY+1)-03-31。

返り値: {data_type: {date(YYYY-MM-DD): {series_key: value, ...}}}
"""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

SEED_DIR = Path(__file__).parent.parent.parent / "data" / "manual_update" / "japan" / "tankan"

_QUARTER_END_DAY = {3: 31, 6: 30, 9: 30, 12: 31}

# DI 項目コード → data_type
_DI_ITEMS = {
    "601": "business_conditions",
    "614": "selling_price",
    "615": "purchase_price",
    "607": "production_facilities",
    "608": "employment",
}


def _classify(code: str) -> Optional[Tuple[str, str, bool, str]]:
    """フラットファイルコード(20桁) → (data_type, series_key, is_forecast, period_kind)。

    対象外（例: 業況の全産業=チャート未使用、規模が大企業以外、選択肢別構成比など）は None。
    """
    if len(code) < 20 or not code.startswith("TK99"):
        return None
    industry = code[5:9]
    item = code[9:12]
    calc = code[12]
    forecast = code[15] == "1"
    size = code[16]
    detail = code[17:20]
    if detail != "000":  # 通常項目のみ（選択肢別構成比などは除外）
        return None

    # 企業の物価見通し（項目201=販売価格見通し1年後 / 204=物価全般見通し1年後、
    # 計算H=見通しの平均、規模0=全規模合計、業種0000=全産業、四半期・調査期そのまま）
    if item in ("201", "204") and calc == "H" and industry == "0000" and size == "0":
        key = "selling_price_outlook" if item == "201" else "general_price_outlook"
        return ("inflation_outlook", key, False, "Q")

    if size != "1":  # 以降は大企業のみ
        return None

    # 判断 DI（計算形態 G = D.I.）
    if item in _DI_ITEMS and calc == "G":
        dtype = _DI_ITEMS[item]
        if dtype == "business_conditions":
            base = {"1000": "large_manufacturing", "2000": "large_non_manufacturing"}.get(industry)
            if base is None:  # 業況の全産業はチャート未使用
                return None
            key = base + ("_outlook" if forecast else "_current")
        else:
            base = {"0000": "all_industries", "1000": "large_manufacturing"}.get(industry)
            if base is None:
                return None
            key = base + ("_forecast" if forecast else "_current")
        return (dtype, key, forecast, "Q")

    # 設備投資額（項目109・計算C=前年比・年度）
    if item == "109" and calc == "C":
        base = {"1000": "large_manufacturing", "2000": "large_non_manufacturing"}.get(industry)
        if base is None:
            return None
        return ("capital_investment", base, False, "FY")

    return None


def _di_date(period: str, forecast: bool, day_first: bool = False) -> Optional[str]:
    """'YYYY/MM' → 日付。予測は対象期-1四半期(=調査期)に戻す。

    day_first=True は月初(YYYY-MM-01)。inflation_outlook サービスが月初日基準のため。
    それ以外(判断DI)は zenyo 解析と同じ四半期末日。
    """
    m = re.match(r"^(\d{4})/(\d{1,2})$", period.strip())
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    if month not in _QUARTER_END_DAY:
        return None
    if forecast:
        month -= 3
        if month <= 0:
            month += 12
            year -= 1
    day = 1 if day_first else _QUARTER_END_DAY[month]
    return f"{year}-{month:02d}-{day:02d}"


def _fy_date(period: str) -> Optional[str]:
    """'YYYY' 年度 → 年度末 (YYYY+1)-03-31。"""
    s = period.strip()
    if not re.match(r"^\d{4}$", s):
        return None
    return f"{int(s) + 1}-03-31"


def _parse_file(path: Path, result: Dict[str, Dict[str, Dict[str, float]]]) -> int:
    raw = path.read_bytes()
    text = None
    for enc in ("shift_jis", "cp932", "utf-8-sig"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        return 0

    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 3:
        return 0

    header = rows[0]
    # 列インデックス → 分類（先頭列は「データコード」ラベルなのでスキップ）
    col_map: Dict[int, Tuple[str, str, bool, str]] = {}
    for idx, raw_code in enumerate(header):
        if idx == 0:
            continue
        code = raw_code.strip().strip('"')
        if code.startswith("CO'"):
            code = code[3:]
        cls = _classify(code)
        if cls:
            col_map[idx] = cls
    if not col_map:
        return 0

    count = 0
    for row in rows[2:]:  # 0=コード, 1=系列名称, 2+=データ
        if not row or not row[0].strip():
            continue
        period = row[0].strip()
        for idx, (dtype, key, forecast, kind) in col_map.items():
            if idx >= len(row):
                continue
            cell = row[idx].strip()
            if cell == "" or cell == "-":
                continue
            try:
                value = float(cell)
            except ValueError:
                continue
            if kind == "Q":
                date = _di_date(period, forecast, day_first=(dtype == "inflation_outlook"))
            else:
                date = _fy_date(period)
            if not date:
                continue
            result.setdefault(dtype, {}).setdefault(date, {})[key] = value
            count += 1
    return count


_cache: Optional[Dict[str, Dict[str, Dict[str, float]]]] = None


def load_seed(force_reload: bool = False) -> Dict[str, Dict[str, Dict[str, float]]]:
    """手動CSV種を {data_type: {date: {series_key: value}}} で返す（プロセス内メモ化）。"""
    global _cache
    if _cache is not None and not force_reload:
        return _cache
    result: Dict[str, Dict[str, Dict[str, float]]] = {}
    if SEED_DIR.exists():
        for path in sorted(SEED_DIR.glob("*.csv")):
            try:
                n = _parse_file(path, result)
                print(f"[tankan-seed] {path.name}: {n} values")
            except Exception as e:
                print(f"[tankan-seed] {path.name} failed: {e}")
    _cache = result
    return result


def seed_into(data_type: str, merged: Dict[str, Dict]) -> None:
    """data_type の手動種を merged({date: point}) に補完する（zenyo優先・未充足のみ）。"""
    by_date = load_seed().get(data_type, {})
    for date, fields in by_date.items():
        point = merged.setdefault(date, {"date": date})
        for k, v in fields.items():
            point.setdefault(k, v)  # 既存(zenyo)を優先
