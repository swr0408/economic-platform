# -*- coding: utf-8 -*-
"""
鮮度フラグの「検証」ツール (検知ガードの相棒)

staleness_monitor が STUCK と判定したキャッシュに対し、対応するサービスを
実際に force_refresh して latest が前進するかを確認する。これにより:
  - ADVANCED: 単に再取得されていなかっただけ → 復旧された (要対応なし)
  - SAME     : force_refresh しても進まない → ソースが元々その日付 (正常ラグ=誤検知)
               か、fetch が壊れて古い値を返している (真の破損)。要個別調査。

外部 API を叩く (重い) ので手動 / 低頻度の運用ツール。staleness_monitor が
「検知」、本ツールが「検証 + 軽微な取りこぼしの自動復旧」を担う。

使い方:
    python -m services.monitoring.verify_stale_by_refresh
    # or: from services.monitoring.verify_stale_by_refresh import verify_stale_by_refresh

サービス命名規約 `services/{country}/{name}_service.py -> {name}_service ->
get_*_data(force_refresh=True)` に従うものだけ対象。規約外は NO_SVC/NO_METH。
"""
from __future__ import annotations

import contextlib
import importlib
import inspect
import io
import json
import logging
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_BACKEND = Path(__file__).resolve().parents[2]
_CACHE = _BACKEND / "data" / "cache"


def _cache_latest(relpath: str):
    from services.monitoring.staleness_monitor import _find_series_dates, _to_naive_jst
    try:
        d = json.load(open(_CACHE / relpath, encoding="utf-8"))
    except Exception:
        return None
    ds = [_to_naive_jst(x) for x in _find_series_dates(d) if x]
    return max(ds).strftime("%Y-%m-%d") if ds else None


def _find_refresh_method(svc, name: str | None = None):
    """force_refresh 可能な get_* メソッドを返す。

    多出力サービス（1サービスが複数 cache を別メソッドで生成。例: PCEDeflatorService の
    get_pce_deflator_data / get_core_pce_deflator_data）では、単純な「最初の get_*」だと
    アルファベット順で誤ったメソッドを呼ぶ（pce_deflator のボタンで core が更新される等）。
    そこで cache ファイル名 `name` に厳密一致する `get_{name}_data` / `get_{name}` を優先し、
    無ければ従来どおり最初の候補にフォールバックする。
    """
    candidates = []
    for mn in dir(svc):
        if not mn.startswith("get_") or "cache_status" in mn or "next" in mn:
            continue
        fn = getattr(svc, mn)
        if callable(fn) and "force_refresh" in inspect.signature(fn).parameters:
            candidates.append((mn, fn))
    if not candidates:
        return None
    if name:
        preferred = {f"get_{name}_data", f"get_{name}"}
        for mn, fn in candidates:
            if mn in preferred:
                return fn
    return candidates[0][1]


# ---------------------------------------------------------------------------
# 事前取得 (force_refresh が「ローカルDBを読むだけ」のサービス向け)
# ---------------------------------------------------------------------------
# A. FMPカレンダー系: economic_calendar_events を読むサービス (PMI 等) は
#    force_refresh しても DB が古いと進まない。当日フラッシュ発表 (日本09:30/
#    France16:15/ドイツ16:30 JST 等) の actual は定期同期(07:00)まで未取込のため、
#    force_refresh の前に FMP カレンダーを即同期して actual を取り込む。
# B. スケジューラ蓄積DB系: 外部API取得→DB保存を別スケジューラが担う市場系
#    (金ETF/金プレミアム等) は force_refresh が外部を叩かない。対応スケジューラの
#    _run_sync() (fetch→save_to_db→clear_service_cache) を先に実行する。


def _sync_fmp_calendar_recent() -> None:
    """A: FMPカレンダーの直近を即同期し economic_calendar_events を最新化。"""
    try:
        from datetime import date, timedelta
        from services.calendar.calendar_scheduler import calendar_scheduler
        today = date.today()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            calendar_scheduler.sync_range(today - timedelta(days=3), today + timedelta(days=1))
    except Exception as e:
        logger.warning("[VerifyStale] FMP calendar sync failed: %s", e)


# B: cache相対パス -> (scheduler module, singleton属性)。
# singleton._run_sync() が「外部API取得→DB保存→サービスキャッシュ削除」を内包。
_PREFETCH_SCHEDULERS: Dict[str, tuple] = {
    "market/gold_etf_holdings_cache.json": ("scheduler.gold_etf_holdings_scheduler", "gold_etf_holdings_scheduler"),
    "market/gold_premium_cache.json": ("scheduler.gold_premium_scheduler", "gold_premium_scheduler"),
    "market/jpx_investor_trading_cache.json": ("scheduler.jpx_investor_trading_scheduler", "jpx_investor_trading_scheduler"),
    "market/china_gold_etf_balance_cache.json": ("scheduler.china_gold_etf_balance_scheduler", "china_gold_etf_balance_scheduler"),
    "market/sge_gold_cache.json": ("scheduler.sge_gold_scheduler", "sge_gold_scheduler"),
    "market/wgc_gold_etf_cache.json": ("scheduler.wgc_gold_etf_scheduler", "wgc_gold_etf_scheduler"),
}


def _prefetch_external_for(rel: str) -> None:
    """B: スケジューラ蓄積DB系は force_refresh 前に対応スケジューラで外部取得する。"""
    entry = _PREFETCH_SCHEDULERS.get(rel)
    if not entry:
        return
    module_path, attr = entry
    try:
        m = importlib.import_module(module_path)
        sched = getattr(m, attr, None)
        if sched is None or not hasattr(sched, "_run_sync"):
            return
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            sched._run_sync()
    except Exception as e:
        logger.warning("[VerifyStale] scheduler prefetch failed for %s: %s", rel, e)


# 命名規約外（cacheファイル名 ≠ サービスmodule名 / 再取得が get_*(force_refresh) 以外）の
# キャッシュを明示マップする。cache相対パス -> (module, singleton属性, method, kwargs)。
# 該当メソッドを呼ぶと file キャッシュが更新され、前後の latest 比較で ADVANCED/SAME を判定。
_REFRESH_OVERRIDES: Dict[str, tuple] = {
    # GDP発表スケジュール: ファイル名=gdp_schedule だがサービスは bea_schedule_service、
    # 再取得は update_cache()（BEAから強制取得＆保存）。
    "usa/bea_schedule/gdp_schedule.json": (
        "services.usa.bea_schedule_service", "bea_schedule_service", "update_cache", {},
    ),
    # 個人所得スケジュール（同サービス・同型）
    "usa/bea_schedule/personal_income_schedule.json": (
        "services.usa.bea_schedule_service", "bea_schedule_service", "update_personal_income_cache", {},
    ),
    # GDP成長率: サービスは gdp_service（ファイル名 gdp_growth_rate と不一致）、
    # get_gdp_growth_rate(force_refresh=True)。redis専用だったため JSON file cache も追加済み。
    "usa/economy/gdp_growth_rate_cache.json": (
        "services.usa.gdp_service", "gdp_service", "get_gdp_growth_rate", {"force_refresh": True},
    ),
    # PCEデフレータ（総合/コア）: 1つの pce_deflator_service が2ファイルを別メソッドで生成。
    # 総合は規約でも解決可だがメソッド誤選択防止のため明示。コアはファイル名 core_pce_deflator が
    # モジュール名と不一致（core_pce_deflator_service は存在しない）のため override 必須。
    "usa/inflation/pce_deflator_cache.json": (
        "services.usa.pce_deflator_service", "pce_deflator_service",
        "get_pce_deflator_data", {"force_refresh": True},
    ),
    "usa/inflation/core_pce_deflator_cache.json": (
        "services.usa.pce_deflator_service", "pce_deflator_service",
        "get_core_pce_deflator_data", {"force_refresh": True},
    ),
}


def _resolve_service_and_method(rel: str, country: str, name: str):
    """(svc, callable, call_kwargs) を返す。override 優先、無ければ命名規約で解決。"""
    override = _REFRESH_OVERRIDES.get(rel)
    if override:
        module_path, attr, method_name, call_kwargs = override
        m = importlib.import_module(module_path)
        svc = getattr(m, attr, None)
        meth = getattr(svc, method_name, None) if svc is not None else None
        return svc, meth, dict(call_kwargs)

    m = importlib.import_module(f"services.{country}.{name}_service")
    svc = getattr(m, f"{name}_service", None) or next(
        (v for k, v in vars(m).items()
         if k.endswith("_service") and not isinstance(v, type) and hasattr(v, "__class__")), None)
    meth = _find_refresh_method(svc, name) if svc is not None else None
    return svc, meth, {"force_refresh": True}


def verify_stale_by_refresh(items: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    """STUCK 項目を force_refresh して advanced/same を判定する。

    items 省略時は staleness_monitor を自分で実行して STUCK を対象にする。
    """
    from services.monitoring.staleness_monitor import scan_stale_caches
    if items is None:
        items = [x for x in scan_stale_caches()["items"] if x["category"] == "STUCK"]

    # A: FMPカレンダー系が含まれ得るなら、force_refresh 前に1回だけFMP即同期。
    # 対象が全てスケジューラ蓄積DB系(B)のみのときは不要なのでスキップ。
    if items and any(x.get("file") not in _PREFETCH_SCHEDULERS for x in items):
        _sync_fmp_calendar_recent()

    results = []
    for x in items:
        rel = x["file"]
        country, name = rel.split("/")[0], os.path.basename(rel).replace("_cache.json", "").replace(".json", "")
        before = _cache_latest(rel)
        # B: スケジューラ蓄積DB系は対応スケジューラで外部取得→DB保存してから force_refresh。
        _prefetch_external_for(rel)
        status, after, err = "?", before, None
        try:
            svc, meth, call_kwargs = _resolve_service_and_method(rel, country, name)
            if svc is None:
                status = "NO_SVC"
            elif meth is None:
                status = "NO_METH"
            else:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    res = meth(**call_kwargs)
                if isinstance(res, dict):
                    err = res.get("error")
                after = _cache_latest(rel)
                if after and (not before or after > before):
                    status = "ADVANCED"
                elif after == before:
                    status = "SAME"
        except Exception as e:
            status, err = "EXC", f"{type(e).__name__}:{str(e)[:60]}"
        results.append({"file": rel, "status": status, "before": before, "after": after, "error": err})
        logger.info("[VerifyStale] %-9s %s %s->%s %s", status, rel, before, after, err or "")

    counts = dict(Counter(r["status"] for r in results))
    return {"counts": counts,
            "advanced": [r for r in results if r["status"] == "ADVANCED"],
            "broken_or_lagging": [r for r in results if r["status"] not in ("ADVANCED",)],
            "results": results}


if __name__ == "__main__":
    import sys
    try:
        from dotenv import load_dotenv
        load_dotenv(_BACKEND.parent / ".env")
    except Exception:
        pass
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    out = verify_stale_by_refresh()
    print("counts:", out["counts"])
    print(f"ADVANCED (auto-restored): {len(out['advanced'])}")
    for r in out["advanced"]:
        print(f"   {r['file']}: {r['before']} -> {r['after']}")
