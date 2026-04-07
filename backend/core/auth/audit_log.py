"""
監査ログ (audit log)

設計:
- master ロールが更新系エンドポイントを実行した際の操作を記録する
- アプリ本体の logger とは独立した専用 logger / handler を用意し、
  ログファイルを別ファイル (`backend/logs/audit.log`) に分離する
- 1 行 1 JSON (= JSON Lines) 形式で書き出すことで、将来的な
  Cloud Logging / ELK / Loki 等への取り込みを容易にする
- ファイルハンドラは RotatingFileHandler で 10MB × 5 世代の自動ローテーション
- 環境変数 `AUDIT_LOG_DIR` でログディレクトリを上書き可能
- ファイルへの書き込みに失敗してもアプリ本体は止めない (best-effort)

使用例:
    from core.auth.audit_log import audit_write_operation
    audit_write_operation(
        method="POST",
        path="/api/usa/economy/dashboard/clear",
        user_id=1,
        username="admin",
        role="master",
        status_code=200,
        client_ip="127.0.0.1",
    )
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

# 専用 logger (アプリ全体の root logger とは伝播させない)
_AUDIT_LOGGER_NAME = "economic_platform.audit"
_audit_logger = logging.getLogger(_AUDIT_LOGGER_NAME)
_audit_logger.setLevel(logging.INFO)
_audit_logger.propagate = False  # ルートロガーへ伝播させない (重複出力防止)


def _resolve_log_dir() -> Path:
    env_dir = os.getenv("AUDIT_LOG_DIR")
    if env_dir:
        return Path(env_dir)
    # backend/logs/ をデフォルトに
    return Path(__file__).resolve().parents[2] / "logs"


def _ensure_handler() -> None:
    """ファイルハンドラが未登録なら一度だけ登録する。"""
    if _audit_logger.handlers:
        return
    try:
        log_dir = _resolve_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "audit.log"
        handler = RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        # 既に JSON 文字列を渡すので余計なフォーマットは付けない
        handler.setFormatter(logging.Formatter("%(message)s"))
        _audit_logger.addHandler(handler)
    except Exception as e:  # noqa: BLE001
        # ログ書き込み環境が無い場合 (Read-only FS 等) でもアプリは継続
        logging.getLogger(__name__).warning(
            "audit_log handler init failed: %s", e
        )


def audit_write_operation(
    *,
    method: str,
    path: str,
    user_id: Optional[int],
    username: Optional[str],
    role: Optional[str],
    status_code: int,
    client_ip: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """更新系操作 1 件を JSON Lines 形式で監査ログに書き出す。

    `_extract_role` が成功した後にミドルウェアから呼ばれる想定。
    失敗系 (401/403) も記録する。
    """
    _ensure_handler()
    record: Dict[str, Any] = {
        "ts": datetime.now(tz=timezone.utc).isoformat(),
        "event": "write_operation",
        "method": method,
        "path": path,
        "user_id": user_id,
        "username": username,
        "role": role,
        "status_code": status_code,
        "client_ip": client_ip,
    }
    if extra:
        record.update(extra)
    try:
        _audit_logger.info(json.dumps(record, ensure_ascii=False))
    except Exception as e:  # noqa: BLE001
        logging.getLogger(__name__).warning(
            "audit_log write failed: %s", e
        )
