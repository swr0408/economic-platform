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


def _find_refresh_method(svc):
    for mn in dir(svc):
        if not mn.startswith("get_") or "cache_status" in mn or "next" in mn:
            continue
        fn = getattr(svc, mn)
        if callable(fn) and "force_refresh" in inspect.signature(fn).parameters:
            return fn
    return None


def verify_stale_by_refresh(items: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    """STUCK 項目を force_refresh して advanced/same を判定する。

    items 省略時は staleness_monitor を自分で実行して STUCK を対象にする。
    """
    from services.monitoring.staleness_monitor import scan_stale_caches
    if items is None:
        items = [x for x in scan_stale_caches()["items"] if x["category"] == "STUCK"]

    results = []
    for x in items:
        rel = x["file"]
        country, name = rel.split("/")[0], os.path.basename(rel).replace("_cache.json", "").replace(".json", "")
        before = _cache_latest(rel)
        status, after, err = "?", before, None
        try:
            m = importlib.import_module(f"services.{country}.{name}_service")
            svc = getattr(m, f"{name}_service", None) or next(
                (v for k, v in vars(m).items()
                 if k.endswith("_service") and not isinstance(v, type) and hasattr(v, "__class__")), None)
            if svc is None:
                status = "NO_SVC"
            else:
                meth = _find_refresh_method(svc)
                if meth is None:
                    status = "NO_METH"
                else:
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        res = meth(force_refresh=True)
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
