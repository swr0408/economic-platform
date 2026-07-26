# -*- coding: utf-8 -*-
"""
Phase 1: 全時系列の正規化ローダー。

backend/data/cache/** (マクロ + market) と seasonality/input/** を再帰走査し、
「date キーを持つ dict のリスト」を全て検出して 1 つの long-format に展開する。
ファイル毎のハードコードを一切せず、複数系列/入れ子 dict/トップレベル系列キーを吸収する。

返り値:
  long_df : columns = [series_id, date, value]
  cat_df  : 系列カタログ (series_id, source, country, category, value_key, freq, n, start, end, label)
"""
import json
import glob
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .paths import CACHE_DIR, SEASONALITY_INPUT

DATE_KEYS = {"date", "time", "period", "datetime", "timestamp", "month", "quarter"}
SKIP_VALUE_KEYS = {
    "date", "time", "period", "datetime", "timestamp", "month", "quarter",
    "year", "id", "index", "unit", "source", "label", "name", "frequency",
    "raw_json", "next_release",
}
SKIP_CONTAINER_KEYS = {
    "latest", "metadata", "next_release", "last_updated", "summary",
    "current", "previous", "comparison", "current_month", "previous_month",
}

_date_re_full = re.compile(r"^\d{4}-\d{2}-\d{2}")
_date_re_ym = re.compile(r"^\d{4}-\d{2}$")
_date_re_yq = re.compile(r"^(\d{4})[-/ ]?Q([1-4])$", re.I)


_MIN_TS = pd.Timestamp("1900-01-01")
_MAX_TS = pd.Timestamp("2100-01-01")


def _clamp(ts):
    """pandas の ns 範囲外/異常年を弾く (例: 0001-01-27 のような壊れた日付)。"""
    if ts is None:
        return None
    try:
        if ts < _MIN_TS or ts > _MAX_TS:
            return None
    except Exception:
        return None
    return ts


def parse_date(v):
    if v is None or isinstance(v, (int, float)):
        return None
    s = str(v).strip()
    if not s:
        return None
    if _date_re_full.match(s):
        try:
            return _clamp(pd.Timestamp(s[:10]))
        except Exception:
            return None
    if _date_re_ym.match(s):
        try:
            return _clamp(pd.Timestamp(s + "-01"))
        except Exception:
            return None
    m = _date_re_yq.match(s)
    if m:
        y, q = int(m.group(1)), int(m.group(2))
        if y < 1900 or y > 2100:
            return None
        return pd.Timestamp(year=y, month=(q - 1) * 3 + 1, day=1)
    try:
        return _clamp(pd.Timestamp(s))
    except Exception:
        return None


def find_date_key(rec):
    for k in rec.keys():
        if k.lower() in DATE_KEYS:
            return k
    return None


def to_float(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").strip()
    if s == "" or s.lower() in ("none", "nan", "null", "-", "n/a"):
        return None
    try:
        return float(s)
    except Exception:
        return None


def infer_freq(dates):
    if len(dates) < 3:
        return "unknown"
    d = pd.Series(sorted(dates)).diff().dt.days.dropna()
    med = d.median()
    if med <= 2:
        return "daily"
    if med <= 4:
        return "businessdaily"
    if med <= 10:
        return "weekly"
    if med <= 20:
        return "biweekly"
    if med <= 45:
        return "monthly"
    if med <= 135:
        return "quarterly"
    if med <= 400:
        return "annual"
    return "irregular"


def _emit_from_list(records, path_prefix, out_rows, catalog, ctx):
    if not records or not isinstance(records[0], dict):
        return
    dk = find_date_key(records[0])
    if dk is None:
        return
    value_keys = {}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        for k, v in rec.items():
            if k == dk or k.lower() in SKIP_VALUE_KEYS:
                continue
            if to_float(v) is not None:
                value_keys[k] = value_keys.get(k, 0) + 1
    for vk, cnt in value_keys.items():
        if cnt < 5:
            continue
        sid = f"{path_prefix}::{vk}"
        rows = []
        for rec in records:
            if not isinstance(rec, dict):
                continue
            d = parse_date(rec.get(dk))
            fv = to_float(rec.get(vk))
            if d is not None and fv is not None:
                rows.append((d, fv))
        if len(rows) < 5:
            continue
        df = pd.DataFrame(rows, columns=["date", "value"]).drop_duplicates(
            "date", keep="last").sort_values("date")
        if len(df) < 5:
            continue
        for d, val in df.itertuples(index=False):
            out_rows.append((sid, d, val))
        catalog.append({
            "series_id": sid, "source": ctx["source"], "country": ctx["country"],
            "category": ctx["category"], "value_key": vk, "freq": infer_freq(df["date"]),
            "n": len(df), "start": df["date"].min().date().isoformat(),
            "end": df["date"].max().date().isoformat(), "label": ctx.get("label", ""),
        })


def _walk_json(node, path_prefix, out_rows, catalog, ctx):
    if isinstance(node, list):
        if node and isinstance(node[0], dict) and find_date_key(node[0]):
            _emit_from_list(node, path_prefix, out_rows, catalog, ctx)
        return
    if isinstance(node, dict):
        for k, v in node.items():
            if k.lower() in SKIP_CONTAINER_KEYS:
                continue
            _walk_json(v, f"{path_prefix}/{k}", out_rows, catalog, ctx)


# 国フォルダ配下に無いトップレベルキャッシュを国/カテゴリに割当 (日銀短観/BSIは日本)
_TOPLEVEL_REMAP = {
    "boj_tankan": ("japan", "economy"),
    "bsi": ("japan", "economy"),
}


def _country_category(path):
    p = Path(path).as_posix()
    parts = p.split("data/cache/")[-1].split("/")
    top = parts[0] if parts else ""
    if top in _TOPLEVEL_REMAP:
        return _TOPLEVEL_REMAP[top]
    if len(parts) >= 3:
        return parts[0], parts[1]
    if len(parts) == 2:
        return parts[0], ""
    return "", ""


# 時系列でない補助ファイル (スケジュール/状態/アラート) は除外
_SKIP_FILE_TOKENS = ("schedule", "_state", "alert", "_meta")


def _load_macro(out_rows, catalog):
    # *_cache.json だけでなく全 *.json を対象 (例: japan の quarterly_gdp_yoy.json は
    # _cache 接尾辞が無く従来取りこぼしていた)。date+数値配列を持つものだけ walk_json が拾う。
    files = glob.glob(str(CACHE_DIR / "**/*.json"), recursive=True)
    files = [f for f in files if "cache/market" not in Path(f).as_posix()
             and not any(tok in Path(f).name.lower() for tok in _SKIP_FILE_TOKENS)]
    for f in files:
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        country, category = _country_category(f)
        stem = Path(f).stem.replace("_cache", "")
        ctx = {"source": "macro", "country": country, "category": category, "label": stem}
        _walk_json(d, f"macro/{country}/{category}/{stem}", out_rows, catalog, ctx)


def _load_market(out_rows, catalog):
    files = glob.glob(str(CACHE_DIR / "market/**/*.json"), recursive=True)
    for f in files:
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        stem = Path(f).stem.replace("_cache", "")
        data = d.get("data") if isinstance(d, dict) else d
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            continue
        dk = find_date_key(data[0])
        if not dk:
            continue
        valkey = None
        for cand in ("close", "value", "settle", "price", "adj_close"):
            if cand in data[0]:
                valkey = cand
                break
        if valkey is None:
            continue
        rows = []
        for rec in data:
            dd = parse_date(rec.get(dk))
            fv = to_float(rec.get(valkey))
            if dd is not None and fv is not None:
                rows.append((dd, fv))
        if len(rows) < 30:
            continue
        df = pd.DataFrame(rows, columns=["date", "value"]).drop_duplicates(
            "date", keep="last").sort_values("date")
        sid = f"market/{stem}::{valkey}"
        for dd, val in df.itertuples(index=False):
            out_rows.append((sid, dd, val))
        label = stem
        if isinstance(d, dict):
            label = (d.get("symbol", {}) or {}).get("name", stem)
        catalog.append({
            "series_id": sid, "source": "market", "country": "", "category": "market",
            "value_key": valkey, "freq": infer_freq(df["date"]), "n": len(df),
            "start": df["date"].min().date().isoformat(),
            "end": df["date"].max().date().isoformat(), "label": label,
        })


def _load_seasonality(out_rows, catalog):
    if not SEASONALITY_INPUT.exists():
        return
    for symdir in SEASONALITY_INPUT.iterdir():
        if not symdir.is_dir():
            continue
        csvs = sorted(symdir.glob("*1D*.csv")) or sorted(symdir.glob("*.csv"))
        if not csvs:
            continue
        try:
            df = pd.read_csv(csvs[0])
        except Exception:
            continue
        cols = {c.lower(): c for c in df.columns}
        tcol = cols.get("time") or cols.get("date")
        ccol = cols.get("close")
        if not tcol or not ccol:
            continue
        df = df[[tcol, ccol]].copy()
        df.columns = ["date", "value"]
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna().drop_duplicates("date", keep="last").sort_values("date")
        df = df[(df["date"] >= _MIN_TS) & (df["date"] <= _MAX_TS)]
        if len(df) < 30:
            continue
        sym = symdir.name
        sid = f"seasonality/{sym}::close"
        for dd, val in df.itertuples(index=False):
            out_rows.append((sid, dd, val))
        catalog.append({
            "series_id": sid, "source": "seasonality", "country": "", "category": "seasonality",
            "value_key": "close", "freq": infer_freq(df["date"]), "n": len(df),
            "start": df["date"].min().date().isoformat(),
            "end": df["date"].max().date().isoformat(), "label": sym,
        })


def build_long_and_catalog():
    """全系列を読み込み (long_df, cat_df) を返す。"""
    out_rows, catalog = [], []
    _load_macro(out_rows, catalog)
    _load_market(out_rows, catalog)
    _load_seasonality(out_rows, catalog)
    long_df = pd.DataFrame(out_rows, columns=["series_id", "date", "value"])
    cat_df = pd.DataFrame(catalog).drop_duplicates("series_id", keep="first")
    return long_df, cat_df
