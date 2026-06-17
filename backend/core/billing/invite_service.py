"""
招待コードサービス (クローズドβ / 手動オンボーディング用)

収益化計画 4章「β版はクローズドβとして運用する」の実装。
コードに plan_code / role_to_grant / valid_days を持たせることで、
βモニター招待 (plan=beta, 30-60日) と有料会員の手動オンボーディング
(plan=econalpha/pro, 入金期間分) の両方を同じ仕組みで扱える。

同時登録の競合は UPDATE ... WHERE used_count < max_uses の
条件付き更新で防ぐ (先に上限へ達した方だけが成功する)。
"""
from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text

try:
    from backend.core.database import SessionLocal
except ImportError:
    from core.database import SessionLocal

logger = logging.getLogger(__name__)

UTC = timezone.utc

# 紛らわしい文字 (0/O, 1/I/l) を除いたコード用アルファベット
_CODE_ALPHABET = "".join(
    c for c in (string.ascii_uppercase + string.digits) if c not in "0O1I"
)


def _generate_code(length: int = 12) -> str:
    body = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))
    # 視認性のため4文字ごとにハイフン区切り (例: K3HX-9TPM-W7RC)
    return "-".join(body[i:i + 4] for i in range(0, length, 4))


def create_invite_code(
    created_by: int,
    role_to_grant: str = "general",
    plan_code: str = "free",
    entitlement_source: str = "invite",
    valid_days: Optional[int] = None,
    max_uses: int = 1,
    expires_at: Optional[datetime] = None,
    memo: Optional[str] = None,
) -> Dict[str, Any]:
    """招待コードを発行する (master 管理APIから呼ばれる)"""
    code = _generate_code()
    with SessionLocal() as session:
        row = session.execute(text("""
            INSERT INTO invite_codes
                (code, role_to_grant, plan_code, entitlement_source,
                 valid_days, max_uses, expires_at, memo, created_by)
            VALUES (:code, :role, :plan, :source, :days, :max_uses, :expires, :memo, :by)
            RETURNING id, code
        """), {
            "code": code, "role": role_to_grant, "plan": plan_code,
            "source": entitlement_source, "days": valid_days,
            "max_uses": max_uses, "expires": expires_at, "memo": memo,
            "by": created_by,
        }).fetchone()
        session.commit()
    logger.info(
        f"[billing] invite code created: id={row[0]} plan={plan_code} "
        f"role={role_to_grant} max_uses={max_uses} by user={created_by}"
    )
    return {"id": row[0], "code": row[1]}


def list_invite_codes(include_inactive: bool = False) -> List[Dict[str, Any]]:
    """招待コード一覧 (master 管理APIから)"""
    where = "" if include_inactive else "WHERE is_active = TRUE"
    with SessionLocal() as session:
        rows = session.execute(text(f"""
            SELECT id, code, role_to_grant, plan_code, entitlement_source,
                   valid_days, max_uses, used_count, expires_at, is_active,
                   memo, created_at
            FROM invite_codes
            {where}
            ORDER BY created_at DESC
        """)).fetchall()
    return [{
        "id": r[0], "code": r[1], "role_to_grant": r[2], "plan_code": r[3],
        "entitlement_source": r[4], "valid_days": r[5],
        "max_uses": r[6], "used_count": r[7],
        "expires_at": r[8].isoformat() if r[8] else None,
        "is_active": r[9], "memo": r[10],
        "created_at": r[11].isoformat() if r[11] else None,
    } for r in rows]


def deactivate_invite_code(code_id: int) -> bool:
    """招待コードを無効化する"""
    with SessionLocal() as session:
        updated = session.execute(text("""
            UPDATE invite_codes SET is_active = FALSE WHERE id = :id
        """), {"id": code_id}).rowcount
        session.commit()
    return bool(updated)


def consume_invite_code(code: str, user_id: int) -> Optional[Dict[str, Any]]:
    """招待コードを消費する (登録フローから呼ばれる)

    Returns:
        成功時: {"role_to_grant", "plan_code", "entitlement_source", "valid_days"}
        無効/上限到達/期限切れ: None
    """
    normalized = code.strip().upper()
    with SessionLocal() as session:
        # 条件付き UPDATE で同時登録の競合を防ぐ
        row = session.execute(text("""
            UPDATE invite_codes
            SET used_count = used_count + 1
            WHERE code = :code
              AND is_active = TRUE
              AND used_count < max_uses
              AND (expires_at IS NULL OR expires_at > NOW())
            RETURNING id, role_to_grant, plan_code, entitlement_source, valid_days
        """), {"code": normalized}).fetchone()

        if row is None:
            session.rollback()
            return None

        session.execute(text("""
            INSERT INTO invite_code_uses (code_id, user_id) VALUES (:cid, :uid)
        """), {"cid": row[0], "uid": user_id})
        session.commit()

    logger.info(f"[billing] invite code consumed: code_id={row[0]} by user={user_id}")
    return {
        "role_to_grant": row[1],
        "plan_code": row[2],
        "entitlement_source": row[3],
        "valid_days": row[4],
    }


def validate_invite_code(code: str) -> bool:
    """コードが現在有効か (消費せずに確認のみ。登録前のバリデーション用)"""
    normalized = code.strip().upper()
    with SessionLocal() as session:
        row = session.execute(text("""
            SELECT 1 FROM invite_codes
            WHERE code = :code
              AND is_active = TRUE
              AND used_count < max_uses
              AND (expires_at IS NULL OR expires_at > NOW())
            LIMIT 1
        """), {"code": normalized}).fetchone()
    return row is not None
