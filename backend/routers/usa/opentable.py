# -*- coding: utf-8 -*-
"""
OpenTable レストラン予約件数（Seated Diners）手動更新 admin エンドポイント

    GET  /api/usa/opentable/status          - 現在の配置画像の状態 (master)
    POST /api/usa/opentable/upload          - 週次/月次スクショをアップロード (master)

背景:
  OpenTable の State of the Industry ページは Akamai Bot Manager 配下で、
  bundled Chromium / データセンターIP / ARM64(=Google Chrome非搭載) からの
  自動キャプチャは遮断される。そのため本指標は「手動でスクショを配置」する
  運用だが、フォルダ直接配置は master でも手間で、集約キャッシュ無効化も
  忘れやすい。このエンドポイントは master がブラウザから週次/月次のスクショを
  アップロードするだけで、正規ファイル配置 + 集約キャッシュ無効化までを
  ワンストップで行う「更新ボタン」の受け口。
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

try:
    from backend.core.auth.dependencies import require_role
    from backend.core.auth.models import ROLE_MASTER, User
    from backend.services.usa.opentable_service import opentable_service
except ImportError:
    from core.auth.dependencies import require_role
    from core.auth.models import ROLE_MASTER, User
    from services.usa.opentable_service import opentable_service

_require_master = require_role(ROLE_MASTER)

router = APIRouter(prefix="/api/usa/opentable", tags=["usa", "opentable"])

# 許可する MIME タイプ
_ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp"}
# アップロード上限 (1ファイル 8MB)
_MAX_UPLOAD_BYTES = 8 * 1024 * 1024


def _invalidate_usa_economy_cache() -> None:
    """USA economy ダッシュボードの集約キャッシュ (main/light/heavy) を無効化。

    OpenTable は light/heavy 双方の集約に含まれるため、3種すべて削除して
    次回フェッチで再構築させる。get_manual_csv_paths による mtime 検知でも
    最終的には再構築されるが、ここで明示削除して即時反映する。
    """
    try:
        from backend.core.redis_client import redis_client
    except ImportError:
        from core.redis_client import redis_client

    base_key = "usa:economy:dashboard:v1"
    for key in (base_key, f"{base_key}:light", f"{base_key}:heavy"):
        try:
            redis_client.delete(key)
        except Exception:
            pass


async def _read_upload(upload: UploadFile) -> bytes:
    """UploadFile を検証しつつバイト列で読む。"""
    if upload.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported content_type: {upload.content_type} "
            f"(allowed: {sorted(_ALLOWED_CONTENT_TYPES)})",
        )
    data = await upload.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"file too large: {len(data)} bytes (max {_MAX_UPLOAD_BYTES})",
        )
    return data


@router.get("/status")
def get_status(_master: User = Depends(_require_master)):
    """現在配置されている画像の状態を返す。"""
    return opentable_service.get_cache_status()


@router.post("/upload")
async def upload_screenshots(
    week: UploadFile | None = File(None, description="週次チャート画像 (任意)"),
    month: UploadFile | None = File(None, description="月次テーブル画像 (任意)"),
    _master: User = Depends(_require_master),
):
    """週次/月次スクリーンショットをアップロードして OpenTable 指標を更新。

    week / month は少なくとも一方が必須。アップロードされた種別のみ差し替える。
    保存後に USA economy 集約キャッシュを無効化し、最新データを返す。
    """
    if week is None and month is None:
        raise HTTPException(
            status_code=400, detail="week か month のいずれかの画像が必要です"
        )

    saved = []
    if week is not None:
        saved.append(opentable_service.save_uploaded_image("week", await _read_upload(week)))
    if month is not None:
        saved.append(opentable_service.save_uploaded_image("month", await _read_upload(month)))

    # 集約キャッシュ無効化 + サービス個別キャッシュ無効化
    opentable_service.invalidate_cache()
    _invalidate_usa_economy_cache()

    return {
        "success": True,
        "saved": saved,
        "data": opentable_service.get_opentable_data(force_refresh=True),
    }
