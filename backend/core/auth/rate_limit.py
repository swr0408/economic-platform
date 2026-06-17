"""
認証エンドポイント用レートリミッタ (Redis 固定ウィンドウ方式)

設計方針:
- 新規依存 (slowapi 等) を追加せず、既存の Redis を利用する
  (security.py の「新規依存追加を回避」方針に合わせる)
- 固定ウィンドウカウンタ: INCR + 初回のみ EXPIRE。実装が単純で
  ブルートフォース対策としては十分 (境界バーストは許容)
- Redis 不通時はフェイルオープン (認証可用性を優先) しつつ
  プロセス内のフォールバックカウンタで最低限の防御を維持
- ログイン失敗の連続回数によるロックアウトも提供
  (ユーザー名単位。成功でリセット)

適用 (routers/auth.py):
- POST /api/auth/login    : IP単位 10回/分 + ユーザー名単位 失敗10回で15分ロック
- POST /api/auth/register : IP単位 5回/時
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Dict, Optional, Tuple

from fastapi import HTTPException, Request, status

try:
    from backend.core.redis_client import redis_client
except ImportError:
    from core.redis_client import redis_client

logger = logging.getLogger(__name__)

# 設定 (環境変数で調整可能)
LOGIN_IP_LIMIT = int(os.getenv("AUTH_LOGIN_IP_LIMIT", "10"))            # 回/分
LOGIN_IP_WINDOW_SEC = 60
LOGIN_FAIL_LOCK_THRESHOLD = int(os.getenv("AUTH_LOGIN_FAIL_LOCK", "10"))  # 連続失敗回数
LOGIN_FAIL_LOCK_SEC = int(os.getenv("AUTH_LOGIN_LOCK_SEC", "900"))        # 15分
REGISTER_IP_LIMIT = int(os.getenv("AUTH_REGISTER_IP_LIMIT", "5"))         # 回/時
REGISTER_IP_WINDOW_SEC = 3600

_PREFIX = "auth:ratelimit"

# Redis 不通時のプロセス内フォールバック {key: (window_start, count)}
_local_counters: Dict[str, Tuple[float, int]] = {}
_local_lock = threading.Lock()


def get_client_ip(request: Request) -> str:
    """クライアントIPを取得 (リバースプロキシ経由は X-Forwarded-For 先頭)

    ※ Caddy/信頼できるプロキシの背後でのみ X-Forwarded-For を信用する。
      直接公開時は偽装可能だが、その場合も request.client にフォールバックする
      ためレート制限自体は機能する。
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _redis_raw():
    """生の redis クライアント (INCR/EXPIRE 用) を取得。失敗時 None"""
    for attr in ("client", "redis", "_client"):
        raw = getattr(redis_client, attr, None)
        if raw is not None:
            return raw
    return None


def _incr_fixed_window(key: str, window_sec: int) -> Optional[int]:
    """固定ウィンドウカウンタを +1 して現在値を返す。Redis 不通時は None"""
    try:
        raw = _redis_raw()
        if raw is None:
            return None
        full_key = f"{_PREFIX}:{key}"
        count = raw.incr(full_key)
        if count == 1:
            raw.expire(full_key, window_sec)
        return int(count)
    except Exception as e:
        logger.warning(f"[RateLimit] Redis error (fail-open with local fallback): {e}")
        return None


def _incr_local(key: str, window_sec: int) -> int:
    """プロセス内フォールバックカウンタ (Redis 不通時の最低限の防御)"""
    now = time.time()
    with _local_lock:
        start, count = _local_counters.get(key, (now, 0))
        if now - start >= window_sec:
            start, count = now, 0
        count += 1
        _local_counters[key] = (start, count)
        # 雑なガベージコレクション (肥大化防止)
        if len(_local_counters) > 10_000:
            cutoff = now - 3600
            for k in [k for k, (s, _) in _local_counters.items() if s < cutoff]:
                _local_counters.pop(k, None)
        return count


def _check(key: str, limit: int, window_sec: int, what: str) -> None:
    """制限超過なら 429 を送出"""
    count = _incr_fixed_window(key, window_sec)
    if count is None:
        count = _incr_local(key, window_sec)
    if count > limit:
        logger.warning(f"[RateLimit] {what} blocked: key={key} count={count}/{limit}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": str(window_sec)},
        )


# ---------------------------------------------------------------------------
# 公開API
# ---------------------------------------------------------------------------

def enforce_login_rate_limit(request: Request, username: str) -> None:
    """ログイン試行前に呼ぶ: IPレート制限 + ユーザー名ロックアウト確認"""
    ip = get_client_ip(request)
    _check(f"login:ip:{ip}", LOGIN_IP_LIMIT, LOGIN_IP_WINDOW_SEC, "login(ip)")

    # ロックアウト中か確認 (失敗カウンタが閾値以上)
    try:
        raw = _redis_raw()
        if raw is not None:
            fails = raw.get(f"{_PREFIX}:login:fail:{username}")
            if fails is not None and int(fails) >= LOGIN_FAIL_LOCK_THRESHOLD:
                logger.warning(f"[RateLimit] login locked out: user={username}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Account temporarily locked due to repeated failures. Try again later.",
                    headers={"Retry-After": str(LOGIN_FAIL_LOCK_SEC)},
                )
    except HTTPException:
        raise
    except Exception:
        pass  # Redis 不通時はロックアウト判定をスキップ (IP制限は上で実施済み)


def record_login_failure(username: str) -> None:
    """ログイン失敗を記録 (閾値到達でロックアウト状態になる)"""
    try:
        raw = _redis_raw()
        if raw is None:
            return
        key = f"{_PREFIX}:login:fail:{username}"
        count = raw.incr(key)
        # 失敗のたびにロック窓を更新 (最後の失敗から LOGIN_FAIL_LOCK_SEC で解除)
        raw.expire(key, LOGIN_FAIL_LOCK_SEC)
        if count == LOGIN_FAIL_LOCK_THRESHOLD:
            logger.warning(f"[RateLimit] lockout threshold reached: user={username}")
    except Exception:
        pass


def record_login_success(username: str) -> None:
    """ログイン成功時に失敗カウンタをリセット"""
    try:
        raw = _redis_raw()
        if raw is not None:
            raw.delete(f"{_PREFIX}:login:fail:{username}")
    except Exception:
        pass


def enforce_register_rate_limit(request: Request) -> None:
    """登録前に呼ぶ: IPレート制限"""
    ip = get_client_ip(request)
    _check(f"register:ip:{ip}", REGISTER_IP_LIMIT, REGISTER_IP_WINDOW_SEC, "register(ip)")
