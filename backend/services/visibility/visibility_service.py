"""
indicator_visibility 操作サービス

責務:
- visibility テーブルの取得 / 更新 (admin 用)
- ロール別の閲覧可否判定 (can_view)
- 一覧フィルタ (filter_visible)
- 5 秒キャッシュ (頻繁にアクセスされるため)

ロール別ルール:
    public  : すべてのロールが閲覧可
    special : special, master のみ閲覧可
    master  : master のみ閲覧可

未登録 indicator_code は public 扱い (フェイルオープン)。
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Iterable, List, Optional

try:
    from backend.core.database import get_db_connection
    from backend.core.auth.models import ROLE_GENERAL, ROLE_MASTER, ROLE_SPECIAL
except ImportError:
    from core.database import get_db_connection
    from core.auth.models import ROLE_GENERAL, ROLE_MASTER, ROLE_SPECIAL

logger = logging.getLogger(__name__)

VIS_PUBLIC = "public"
VIS_SPECIAL = "special"
VIS_MASTER = "master"
_VALID_VIS = (VIS_PUBLIC, VIS_SPECIAL, VIS_MASTER)

# 5 秒キャッシュ (admin が変えた直後でも数秒で反映)
_CACHE_TTL_SEC = 5.0


class _VisibilityCache:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._data: Dict[str, str] = {}
        self._loaded_at: float = 0.0

    def get_all(self) -> Dict[str, str]:
        now = time.time()
        with self._lock:
            if now - self._loaded_at < _CACHE_TTL_SEC and self._data:
                return self._data
            self._refresh_locked()
            return self._data

    def invalidate(self) -> None:
        with self._lock:
            self._loaded_at = 0.0
            self._data = {}

    def _refresh_locked(self) -> None:
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT indicator_code, visibility FROM indicator_visibility"
                    )
                    rows = cur.fetchall()
            self._data = {r[0]: r[1] for r in rows}
            self._loaded_at = time.time()
        except Exception as e:
            logger.error(f"[visibility] cache refresh failed: {e}")
            # 失敗時は古いキャッシュを保持 (フェイルオープン)


_cache = _VisibilityCache()


def invalidate_cache() -> None:
    """更新時に呼ぶ (admin 系)。"""
    _cache.invalidate()


def get_visibility(indicator_code: str) -> str:
    """指標の可視性を取得。未登録なら 'public'。"""
    return _cache.get_all().get(indicator_code, VIS_PUBLIC)


def can_view(role: Optional[str], indicator_code: str) -> bool:
    """ロールが指標を閲覧できるか判定。

    role=None (未ログイン) は public のみ閲覧可。
    """
    vis = get_visibility(indicator_code)
    return _can_view_visibility(role, vis)


def _can_view_visibility(role: Optional[str], vis: str) -> bool:
    if vis == VIS_PUBLIC:
        return True
    if role == ROLE_MASTER:
        return True
    if vis == VIS_SPECIAL and role == ROLE_SPECIAL:
        return True
    return False


def filter_visible(role: Optional[str], indicator_codes: Iterable[str]) -> List[str]:
    """ロールが見られる indicator_code のみ返す。"""
    all_vis = _cache.get_all()
    result: List[str] = []
    for code in indicator_codes:
        vis = all_vis.get(code, VIS_PUBLIC)
        if _can_view_visibility(role, vis):
            result.append(code)
    return result


# ---------- 管理 API 用 ----------


def list_all_visibilities() -> List[Dict[str, str]]:
    """全 visibility 行を取得 (admin)。"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT indicator_code, visibility, reason, updated_at, updated_by
                    FROM indicator_visibility
                    ORDER BY indicator_code
                """)
                cols = [d[0] for d in cur.description]
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]
                for r in rows:
                    if r.get("updated_at"):
                        r["updated_at"] = r["updated_at"].isoformat()
                return rows
    except Exception as e:
        logger.error(f"[visibility] list failed: {e}")
        return []


def upsert_visibility(
    indicator_code: str,
    visibility: str,
    reason: Optional[str] = None,
    updated_by: Optional[int] = None,
) -> Dict[str, str]:
    """visibility を upsert (admin)。"""
    if visibility not in _VALID_VIS:
        raise ValueError(f"Invalid visibility: {visibility}. Must be one of {_VALID_VIS}")
    if not indicator_code or len(indicator_code) > 128:
        raise ValueError("indicator_code is required and must be <= 128 chars")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO indicator_visibility (indicator_code, visibility, reason, updated_by)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (indicator_code) DO UPDATE SET
                    visibility = EXCLUDED.visibility,
                    reason = EXCLUDED.reason,
                    updated_at = CURRENT_TIMESTAMP,
                    updated_by = EXCLUDED.updated_by
                RETURNING indicator_code, visibility, reason
            """, (indicator_code, visibility, reason, updated_by))
            row = cur.fetchone()
            conn.commit()

    invalidate_cache()
    return {
        "indicator_code": row[0],
        "visibility": row[1],
        "reason": row[2],
    }


def delete_visibility(indicator_code: str) -> bool:
    """visibility 行を削除 (admin)。削除後は public 扱いになる。"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM indicator_visibility WHERE indicator_code = %s",
                (indicator_code,),
            )
            deleted = cur.rowcount > 0
            conn.commit()
    if deleted:
        invalidate_cache()
    return deleted
