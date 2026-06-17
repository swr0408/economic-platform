"""
Pro PDF アーカイブ用 Object Storage アダプタ (Lightsail Object Storage / S3互換)

収益化計画 Table 9「public 固定URLではなく、Pro権限確認後に短時間URLを発行する」
の実装。Lightsail Object Storage は S3 互換のため boto3 の presigned URL を使う。

▼ 有効化手順 (Object Storage 契約後にやること — コード変更は不要):
  1. Lightsail コンソールでバケットを作成 (例: econalpha-pro-pdfs、アクセス=非公開)
  2. バケットのアクセスキーを発行
  3. .env / docker-compose.prod.yml に以下を設定:
       LIGHTSAIL_BUCKET_NAME=econalpha-pro-pdfs
       LIGHTSAIL_BUCKET_REGION=ap-northeast-1
       LIGHTSAIL_ACCESS_KEY_ID=...
       LIGHTSAIL_SECRET_ACCESS_KEY=...
  4. requirements.txt の boto3 をインストール (botocore は導入済み)
  5. PDF をアップロード (コンソール or upload_pdf()) し、
     管理API POST /api/admin/billing/pdf-archives で object_key を登録

未設定の間、generate_presigned_url() は ObjectStorageNotConfigured を送出し、
API 層は 503 を返す (= 「手前まで実装」の境界)。
"""
from __future__ import annotations

import logging
import os
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# 署名URLの有効期間 (秒)。短いほど安全だが、PDF表示中の再読込を考慮し10分
PRESIGNED_URL_EXPIRES_SEC = int(os.getenv("PDF_URL_EXPIRES_SEC", "600"))


class ObjectStorageNotConfigured(Exception):
    """Object Storage が未契約/未設定であることを示す (API層で503に変換)"""


def _get_config() -> Optional[dict]:
    """環境変数からストレージ設定を取得。未設定なら None"""
    bucket = os.getenv("LIGHTSAIL_BUCKET_NAME")
    region = os.getenv("LIGHTSAIL_BUCKET_REGION")
    access_key = os.getenv("LIGHTSAIL_ACCESS_KEY_ID")
    secret_key = os.getenv("LIGHTSAIL_SECRET_ACCESS_KEY")
    if not all([bucket, region, access_key, secret_key]):
        return None
    return {
        "bucket": bucket,
        "region": region,
        "access_key": access_key,
        "secret_key": secret_key,
        # Lightsail Object Storage のエンドポイント形式
        "endpoint": os.getenv(
            "LIGHTSAIL_BUCKET_ENDPOINT",
            f"https://s3.{region}.amazonaws.com",
        ),
    }


def _get_s3_client():
    cfg = _get_config()
    if cfg is None:
        raise ObjectStorageNotConfigured(
            "Object Storage is not configured yet "
            "(set LIGHTSAIL_BUCKET_NAME / REGION / ACCESS_KEY_ID / SECRET_ACCESS_KEY)"
        )
    try:
        import boto3  # 遅延import: 未インストール環境でもモジュール自体は読み込める
    except ImportError:
        raise ObjectStorageNotConfigured(
            "boto3 is not installed (pip install boto3)"
        )
    return boto3.client(
        "s3",
        region_name=cfg["region"],
        endpoint_url=cfg["endpoint"],
        aws_access_key_id=cfg["access_key"],
        aws_secret_access_key=cfg["secret_key"],
    ), cfg


def generate_presigned_url(
    object_key: str,
    bucket_name: Optional[str] = None,
    expires_in: int = PRESIGNED_URL_EXPIRES_SEC,
) -> Tuple[str, int]:
    """短時間で失効する署名付きダウンロードURLを発行する

    Args:
        object_key: バケット内のオブジェクトキー (例: "weekly/2026-06-15.pdf")
        bucket_name: 省略時は LIGHTSAIL_BUCKET_NAME
    Returns:
        (url, expires_in_seconds)
    Raises:
        ObjectStorageNotConfigured: 未設定/boto3未導入
    """
    client, cfg = _get_s3_client()
    bucket = bucket_name or cfg["bucket"]
    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": object_key},
        ExpiresIn=expires_in,
    )
    return url, expires_in


def upload_pdf(
    local_path: str,
    object_key: str,
    bucket_name: Optional[str] = None,
) -> dict:
    """PDF をアップロードする (管理スクリプト/将来の管理API用)

    使用例 (PoC 検証):
        python -X utf8 -c "from core.billing.pdf_storage import upload_pdf; \\
            print(upload_pdf('weekly.pdf', 'weekly/2026-06-15.pdf'))"
    """
    client, cfg = _get_s3_client()
    bucket = bucket_name or cfg["bucket"]
    size = os.path.getsize(local_path)
    client.upload_file(
        local_path, bucket, object_key,
        ExtraArgs={"ContentType": "application/pdf"},
    )
    logger.info(f"[pdf_storage] uploaded {local_path} -> s3://{bucket}/{object_key} ({size} bytes)")
    return {"bucket_name": bucket, "object_key": object_key, "file_size_bytes": size}


def is_configured() -> bool:
    """Object Storage が利用可能か (管理画面の状態表示用)"""
    return _get_config() is not None
