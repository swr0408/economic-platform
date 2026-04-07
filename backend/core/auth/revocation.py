"""
JWT Revocation (即時失効) ストア

設計:
- logout / パスワード変更 / 管理者による強制失効 で、発行済み JWT を即時に無効化する
- トークンの `jti` (JWT ID) を Redis のブラックリストに登録する
- TTL はトークンの残り寿命に合わせることで、Redis 上の不要なキーが自動で消える
- Redis が落ちている場合は fail-open: False を返す (= revoke されていない扱い)
  → 認証自体は JWT 署名検証と exp で担保されているのでセキュリティ影響は限定的
- 将来 Redis が必須インフラになったら fail-closed に切り替え可能

キー設計:
- auth:revoked_jti:<jti>  値は "1" (存在すること自体が revoke 状態を意味する)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

try:
    from backend.core.redis_client import redis_client
except ImportError:
    from core.redis_client import redis_client

logger = logging.getLogger(__name__)

_REVOKED_KEY_PREFIX = "auth:revoked_jti:"


def _key(jti: str) -> str:
    return f"{_REVOKED_KEY_PREFIX}{jti}"


def revoke_jti(jti: Optional[str], exp_unix: Optional[int]) -> bool:
    """指定 jti をブラックリスト入りさせる。

    Args:
        jti: トークンの jti クレーム
        exp_unix: トークンの exp (UNIX秒)。残り寿命を TTL として使用する。

    Returns:
        Redis への書き込みに成功したかどうか。Redis 障害時は False を返す。
    """
    if not jti:
        return False
    try:
        # 残り寿命を TTL として使う
        if exp_unix is not None:
            now = int(datetime.now(tz=timezone.utc).timestamp())
            ttl = exp_unix - now
            if ttl <= 0:
                # すでに期限切れ → 登録不要
                return True
        else:
            # exp 不明 → 念のため 24h 固定
            ttl = 24 * 3600
        redis_client.client.setex(_key(jti), ttl, "1")
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("revoke_jti failed for jti=%s: %s", jti, e)
        return False


def is_jti_revoked(jti: Optional[str]) -> bool:
    """指定 jti が revoke 済みかどうかを返す。

    Redis 障害時は fail-open で False を返す (= revoke されていない扱い)。
    """
    if not jti:
        return False
    try:
        return bool(redis_client.client.exists(_key(jti)))
    except Exception as e:  # noqa: BLE001
        logger.warning("is_jti_revoked lookup failed for jti=%s: %s", jti, e)
        return False


def revoke_all_for_user(user_id: int) -> int:
    """指定ユーザーの全発行済みトークンを強制失効させるためのマーカー。

    注意: jti を DB で全件管理しているわけではないので、ここでは
    「user:<id> に対する強制失効タイムスタンプ」を保存する方式にする。
    現在は未使用 (将来 password 変更時や is_active=false 化で活用予定)。
    """
    try:
        now = int(datetime.now(tz=timezone.utc).timestamp())
        key = f"auth:force_logout_after:{user_id}"
        # 最大 30日 (長寿命トークンでもカバー)
        redis_client.client.setex(key, 30 * 24 * 3600, str(now))
        return now
    except Exception as e:  # noqa: BLE001
        logger.warning("revoke_all_for_user failed for user_id=%s: %s", user_id, e)
        return 0


def get_force_logout_after(user_id: int) -> Optional[int]:
    """指定ユーザーの強制失効タイムスタンプ (UNIX秒) を返す。未設定なら None。"""
    try:
        key = f"auth:force_logout_after:{user_id}"
        raw = redis_client.client.get(key)
        if raw is None:
            return None
        return int(raw)
    except Exception as e:  # noqa: BLE001
        logger.warning("get_force_logout_after failed for user_id=%s: %s", user_id, e)
        return None
