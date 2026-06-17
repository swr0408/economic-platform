"""
Entitlement (契約権限) サービス

収益化計画の権限モデル (Table 12) を実装する:

  ユーザー状態        role     plan_code                 entitlement_source
  Free               general  free                      signup
  βモニター           special  beta                      invite_beta
  EconAlpha有料       special  econalpha                 manual_payment / stripe
  Pro有料             special  pro                       manual_payment / stripe
  Founding割引        special  econalpha_founding / pro_founding   beta_conversion
  期限切れ            general  free                      expired

設計原則:
- role = 表示権限 (既存の可視性制御がそのまま使う) / plan_code = 契約商品
- ユーザーの「現在の契約」は status='active' の entitlement 1件のみ
  (新規付与時に旧 active は superseded に落とす)
- **master ユーザーの role は決して変更しない** (付与・降格の両方で除外)。
  master へ entitlement を付与しても表示権限はもともと全開なので実害なし。
- 期限切れスイープは current_period_end < now の active を expired にし、
  role を general へ降格 + 全トークン失効 (次のリクエストで再ログイン)。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text

try:
    from backend.core.auth.models import ROLE_GENERAL, ROLE_MASTER, ROLE_SPECIAL
    from backend.core.auth.revocation import revoke_all_for_user
    from backend.core.database import SessionLocal
except ImportError:
    from core.auth.models import ROLE_GENERAL, ROLE_MASTER, ROLE_SPECIAL
    from core.auth.revocation import revoke_all_for_user
    from core.database import SessionLocal

logger = logging.getLogger(__name__)

UTC = timezone.utc

# plan_code → 付与する role のマッピング (計画書 Table 12)
PLAN_TO_ROLE: Dict[str, str] = {
    "free": ROLE_GENERAL,
    "beta": ROLE_SPECIAL,
    "econalpha": ROLE_SPECIAL,
    "pro": ROLE_SPECIAL,
    "econalpha_founding": ROLE_SPECIAL,
    "pro_founding": ROLE_SPECIAL,
}

# PDFアーカイブを閲覧できる plan (role では EconAlpha単体と区別できないため)
PRO_PLAN_CODES = ("pro", "pro_founding")

VALID_PLAN_CODES = tuple(PLAN_TO_ROLE.keys())


def get_active_entitlement(user_id: int) -> Optional[Dict[str, Any]]:
    """ユーザーの現在有効な entitlement を返す (なければ None = Free 扱い)"""
    with SessionLocal() as session:
        row = session.execute(text("""
            SELECT id, plan_code, entitlement_source, status,
                   current_period_start, current_period_end, discount_until, memo
            FROM entitlements
            WHERE user_id = :uid AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
        """), {"uid": user_id}).fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "plan_code": row[1],
        "entitlement_source": row[2],
        "status": row[3],
        "current_period_start": row[4].isoformat() if row[4] else None,
        "current_period_end": row[5].isoformat() if row[5] else None,
        "discount_until": row[6].isoformat() if row[6] else None,
        "memo": row[7],
    }


def has_pro_access(user_id: int, role: Optional[str] = None) -> bool:
    """PDFアーカイブ等の Pro 限定機能へアクセスできるか

    master は運用上すべて閲覧可能とする (管理・検証のため)。
    それ以外は active な entitlement の plan_code が pro 系であること。
    """
    if role == ROLE_MASTER:
        return True
    ent = get_active_entitlement(user_id)
    if ent is None:
        return False
    end = ent.get("current_period_end")
    if end is not None and datetime.fromisoformat(end) < datetime.now(UTC):
        return False  # スイープ前の期限切れも弾く
    return ent["plan_code"] in PRO_PLAN_CODES


def grant_entitlement(
    user_id: int,
    plan_code: str,
    entitlement_source: str,
    valid_days: Optional[int] = None,
    current_period_end: Optional[datetime] = None,
    discount_until: Optional[datetime] = None,
    memo: Optional[str] = None,
) -> Dict[str, Any]:
    """entitlement を付与する (旧 active は superseded に落とす)

    - valid_days 指定時は now + valid_days を期限にする
    - current_period_end 指定時はそれを優先 (手動決済の入金期間に合わせる)
    - 両方 None なら無期限 (永久無料枠は原則作らない方針のため、運用上は期限推奨)
    - role を plan に応じて更新する。**master の role は変更しない**
    - role が変わる場合は既存トークンを全失効し再ログインで新 role を反映
    """
    if plan_code not in VALID_PLAN_CODES:
        raise ValueError(f"unknown plan_code: {plan_code} (valid: {VALID_PLAN_CODES})")

    now = datetime.now(UTC)
    end = current_period_end
    if end is None and valid_days is not None:
        end = now + timedelta(days=valid_days)

    target_role = PLAN_TO_ROLE[plan_code]

    with SessionLocal() as session:
        user_row = session.execute(
            text("SELECT role FROM users WHERE id = :uid"), {"uid": user_id}
        ).fetchone()
        if user_row is None:
            raise ValueError(f"user not found: {user_id}")
        current_role = user_row[0]

        # 旧 active を superseded に
        session.execute(text("""
            UPDATE entitlements
            SET status = 'superseded', updated_at = NOW()
            WHERE user_id = :uid AND status = 'active'
        """), {"uid": user_id})

        row = session.execute(text("""
            INSERT INTO entitlements
                (user_id, plan_code, entitlement_source, status,
                 current_period_start, current_period_end, discount_until, memo)
            VALUES (:uid, :plan, :source, 'active', :start, :end, :discount, :memo)
            RETURNING id
        """), {
            "uid": user_id, "plan": plan_code, "source": entitlement_source,
            "start": now, "end": end, "discount": discount_until, "memo": memo,
        }).fetchone()

        role_changed = False
        if current_role != ROLE_MASTER and current_role != target_role:
            session.execute(text("""
                UPDATE users SET role = :role WHERE id = :uid
            """), {"role": target_role, "uid": user_id})
            role_changed = True

        session.commit()

    if role_changed:
        # 旧 role の JWT を失効させ、再ログインで新 role を反映
        try:
            revoke_all_for_user(user_id)
        except Exception as e:
            logger.warning(f"[billing] token revocation failed for user {user_id}: {e}")

    logger.info(
        f"[billing] granted plan={plan_code} source={entitlement_source} "
        f"user={user_id} end={end} role_changed={role_changed}"
    )
    return {
        "entitlement_id": row[0],
        "plan_code": plan_code,
        "current_period_end": end.isoformat() if end else None,
        "role_changed": role_changed,
    }


def revoke_entitlement(user_id: int, memo: Optional[str] = None) -> bool:
    """ユーザーの active entitlement を即時取り消し、Free に戻す (master の role は不変)"""
    with SessionLocal() as session:
        updated = session.execute(text("""
            UPDATE entitlements
            SET status = 'revoked', updated_at = NOW(),
                memo = COALESCE(:memo, memo)
            WHERE user_id = :uid AND status = 'active'
        """), {"uid": user_id, "memo": memo}).rowcount

        session.execute(text("""
            UPDATE users SET role = :general
            WHERE id = :uid AND role <> :master
        """), {"uid": user_id, "general": ROLE_GENERAL, "master": ROLE_MASTER})
        session.commit()

    if updated:
        try:
            revoke_all_for_user(user_id)
        except Exception as e:
            logger.warning(f"[billing] token revocation failed for user {user_id}: {e}")
        logger.info(f"[billing] revoked entitlement for user {user_id}")
    return bool(updated)


def sweep_expired_entitlements() -> Dict[str, Any]:
    """期限切れ entitlement を expired にし、ユーザーを Free (general) に降格する

    日次スケジューラから呼ばれる。計画書 4章「β終了後は原則 Free に戻す」
    Table 11「手動決済期間は current_period_end を必ず管理する」の実装。
    **master ユーザーの role は決して降格しない。**
    """
    now = datetime.now(UTC)
    downgraded: List[int] = []

    with SessionLocal() as session:
        rows = session.execute(text("""
            UPDATE entitlements
            SET status = 'expired', updated_at = NOW()
            WHERE status = 'active'
              AND current_period_end IS NOT NULL
              AND current_period_end < :now
            RETURNING user_id, plan_code
        """), {"now": now}).fetchall()

        expired_users = sorted({r[0] for r in rows})
        for uid in expired_users:
            # 別の active entitlement が残っていれば降格しない (プラン切替直後の保護)
            still_active = session.execute(text("""
                SELECT 1 FROM entitlements
                WHERE user_id = :uid AND status = 'active' LIMIT 1
            """), {"uid": uid}).fetchone()
            if still_active:
                continue
            result = session.execute(text("""
                UPDATE users SET role = :general
                WHERE id = :uid AND role <> :master
            """), {"uid": uid, "general": ROLE_GENERAL, "master": ROLE_MASTER})
            if result.rowcount:
                downgraded.append(uid)
        session.commit()

    # 降格したユーザーのトークンを失効 (次のアクセスで再ログイン → general)
    for uid in downgraded:
        try:
            revoke_all_for_user(uid)
        except Exception as e:
            logger.warning(f"[billing] token revocation failed for user {uid}: {e}")

    summary = {
        "expired_entitlements": len(rows),
        "downgraded_users": downgraded,
        "swept_at": now.isoformat(),
    }
    if rows:
        logger.info(f"[billing] expiry sweep: {summary}")
    return summary
