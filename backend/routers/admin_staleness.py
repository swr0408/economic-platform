# -*- coding: utf-8 -*-
"""
キャッシュ鮮度モニタ admin エンドポイント (取りこぼし検知ガード)

    GET /api/admin/staleness            - 全キャッシュの鮮度フラグ一覧 (master)
    GET /api/admin/staleness?category=STUCK
    GET /api/admin/staleness?include_ok=true

ソース機構の劣化で「再取得は走るのにデータが進まない」silent failure を
個別サービスを書き換えずに横断検知するための運用エンドポイント。
"""
from fastapi import APIRouter, Depends, Query

try:
    from backend.core.auth.dependencies import require_role
    from backend.core.auth.models import ROLE_MASTER, User
    from backend.services.monitoring.staleness_monitor import scan_stale_caches
except ImportError:
    from core.auth.dependencies import require_role
    from core.auth.models import ROLE_MASTER, User
    from services.monitoring.staleness_monitor import scan_stale_caches

_require_master = require_role(ROLE_MASTER)

router = APIRouter(tags=["AdminStaleness"])


@router.get("/api/admin/staleness")
def api_staleness(
    category: str = Query(None, description="STUCK | WRITER_STOPPED | LAGGING で絞り込み"),
    include_ok: bool = Query(False, description="正常なキャッシュも含める"),
    _master: User = Depends(_require_master),
):
    """全キャッシュ (754) を走査し、期待リリース間隔より遅れているものを返す。

    category:
      - STUCK         : 再取得は走っているのにデータが進まない (要調査・最優先)
      - WRITER_STOPPED: 再取得自体が止まっている
      - LAGGING       : やや遅延
    """
    result = scan_stale_caches(include_ok=include_ok)
    if category:
        cats = {c.strip().upper() for c in category.split(",")}
        result["items"] = [r for r in result["items"] if r["category"] in cats]
        result["flagged"] = len(result["items"])
    return result
