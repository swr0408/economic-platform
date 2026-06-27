# -*- coding: utf-8 -*-
"""
キャッシュ鮮度モニタ admin エンドポイント (取りこぼし検知ガード)

    GET /api/admin/staleness            - 全キャッシュの鮮度フラグ一覧 (master)
    GET /api/admin/staleness?category=STUCK
    GET /api/admin/staleness?include_ok=true

ソース機構の劣化で「再取得は走るのにデータが進まない」silent failure を
個別サービスを書き換えずに横断検知するための運用エンドポイント。
"""
import asyncio
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

try:
    from backend.core.auth.dependencies import require_role
    from backend.core.auth.models import ROLE_MASTER, User
    from backend.services.monitoring.staleness_monitor import scan_stale_caches_async
    from backend.services.monitoring.verify_stale_by_refresh import verify_stale_by_refresh
    from backend.core.redis_client import redis_client
except ImportError:
    from core.auth.dependencies import require_role
    from core.auth.models import ROLE_MASTER, User
    from services.monitoring.staleness_monitor import scan_stale_caches_async
    from services.monitoring.verify_stale_by_refresh import verify_stale_by_refresh
    from core.redis_client import redis_client

_require_master = require_role(ROLE_MASTER)

router = APIRouter(tags=["AdminStaleness"])

# staleness item の "file" 形式（例: usa/consumer/xxx_cache.json）のみ許可。
# パストラバーサル/任意モジュールimportを防ぐためフォーマットを厳格化する。
_FILE_RE = re.compile(r"^[a-z0-9_]+(?:/[a-z0-9_]+)+\.json$")


@router.get("/api/admin/staleness")
async def api_staleness(
    category: str = Query(None, description="STUCK | WRITER_STOPPED | LAGGING で絞り込み"),
    include_ok: bool = Query(False, description="正常なキャッシュも含める"),
    _master: User = Depends(_require_master),
):
    """全キャッシュ (754) を走査し、期待リリース間隔より遅れているものを返す。

    走査(~12秒)は別プロセスで実行し、メインのイベントループを塞がない
    (毎リクエスト同期スキャンで全APIが遅延する事象への対策)。

    category:
      - STUCK         : 再取得は走っているのにデータが進まない (要調査・最優先)
      - WRITER_STOPPED: 再取得自体が止まっている
      - LAGGING       : やや遅延
    """
    result = await scan_stale_caches_async(include_ok=include_ok)
    if category:
        cats = {c.strip().upper() for c in category.split(",")}
        result["items"] = [r for r in result["items"] if r["category"] in cats]
        result["flagged"] = len(result["items"])
    return result


class RefreshRequest(BaseModel):
    file: str  # staleness item の "file"（例: usa/consumer/xxx_cache.json）


@router.post("/api/admin/refresh")
async def api_refresh(req: RefreshRequest, _master: User = Depends(_require_master)):
    """指定キャッシュに対応するサービスを force_refresh する（master 限定・ワンクリック更新）。

    `verify_stale_by_refresh` を 1 件だけ実行し、latest が前進したかを返す。
    - ADVANCED : 再取得されていなかっただけ → 復旧（集約キャッシュも無効化）
    - SAME     : force_refresh しても進まず → ソース未反映ラグ or fetch 破損
    - NO_SVC / NO_METH / EXC : 命名規約外・例外

    force_refresh は同期外部 I/O のため必ずワーカースレッドへ退避する
    （イベントループ枯渇による全 API 遅延の再発防止）。
    """
    file = (req.file or "").strip()
    if not _FILE_RE.match(file):
        raise HTTPException(status_code=400, detail="invalid file format")

    item = {"file": file, "category": "STUCK"}
    out = await asyncio.to_thread(verify_stale_by_refresh, [item])
    results = out.get("results") or []
    if not results:
        raise HTTPException(status_code=404, detail="no result (unknown file or service)")
    r = results[0]

    # 前進した場合は集約ダッシュボードキャッシュも無効化（file から country/category 導出）。
    # 例: usa/consumer/xxx_cache.json → usa:consumer:dashboard:v1{,:light,:heavy}
    invalidated = []
    parts = file.split("/")
    if r.get("status") == "ADVANCED" and len(parts) >= 3:
        country, category = parts[0], parts[1]
        base = f"{country}:{category}:dashboard:v1"
        for suffix in ("", ":light", ":heavy"):
            key = base + suffix
            try:
                if redis_client.delete(key):
                    invalidated.append(key)
            except Exception:
                pass

    return {
        "file": file,
        "status": r.get("status"),
        "before": r.get("before"),
        "after": r.get("after"),
        "error": r.get("error"),
        "dashboard_invalidated": invalidated,
    }
