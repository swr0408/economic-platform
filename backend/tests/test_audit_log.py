"""
Audit log tests.

- Verify that audit_write_operation writes a JSON-Lines record to a temp dir
- Verify that the WriteOperationGuardMiddleware emits records for both
  successful master actions and 401/403 failures.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import audit_log as audit_log_module
from core.auth.audit_log import audit_write_operation
from core.auth.models import ROLE_GENERAL, ROLE_MASTER
from core.auth.security import create_access_token
from core.auth.write_guard import WriteOperationGuardMiddleware


@pytest.fixture
def isolated_audit_log(tmp_path, monkeypatch):
    """Redirect audit log writes to a temp dir and reset the cached handler."""
    monkeypatch.setenv("AUDIT_LOG_DIR", str(tmp_path))
    # Remove handlers cached from previous tests so the new dir is picked up
    logger = logging.getLogger("economic_platform.audit")
    for h in list(logger.handlers):
        try:
            h.close()
        except Exception:  # noqa: BLE001
            pass
        logger.removeHandler(h)
    yield tmp_path
    # Cleanup handlers after test
    for h in list(logger.handlers):
        try:
            h.close()
        except Exception:  # noqa: BLE001
            pass
        logger.removeHandler(h)


def _read_log_lines(log_dir: Path) -> list[dict]:
    log_path = log_dir / "audit.log"
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class TestAuditWriteOperation:
    def test_writes_jsonline_record(self, isolated_audit_log):
        audit_write_operation(
            method="POST",
            path="/api/test/clear",
            user_id=42,
            username="alice",
            role="master",
            status_code=200,
            client_ip="10.0.0.1",
        )
        # Force flush
        for h in logging.getLogger("economic_platform.audit").handlers:
            h.flush()
        records = _read_log_lines(isolated_audit_log)
        assert len(records) == 1
        rec = records[0]
        assert rec["event"] == "write_operation"
        assert rec["method"] == "POST"
        assert rec["path"] == "/api/test/clear"
        assert rec["user_id"] == 42
        assert rec["username"] == "alice"
        assert rec["role"] == "master"
        assert rec["status_code"] == 200
        assert rec["client_ip"] == "10.0.0.1"
        assert "ts" in rec


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.add_middleware(WriteOperationGuardMiddleware)

    @application.post("/api/admin/clear")
    async def clear():
        return {"ok": True}

    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


class TestMiddlewareAuditing:
    def test_master_success_logged(self, isolated_audit_log, client: TestClient):
        token = create_access_token(user_id=1, username="root", role=ROLE_MASTER)
        r = client.post(
            "/api/admin/clear",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        for h in logging.getLogger("economic_platform.audit").handlers:
            h.flush()
        records = _read_log_lines(isolated_audit_log)
        assert len(records) == 1
        assert records[0]["status_code"] == 200
        assert records[0]["username"] == "root"
        assert records[0]["role"] == "master"
        assert records[0]["path"] == "/api/admin/clear"

    def test_general_403_logged(self, isolated_audit_log, client: TestClient):
        token = create_access_token(user_id=2, username="bob", role=ROLE_GENERAL)
        r = client.post(
            "/api/admin/clear",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403
        for h in logging.getLogger("economic_platform.audit").handlers:
            h.flush()
        records = _read_log_lines(isolated_audit_log)
        assert len(records) == 1
        assert records[0]["status_code"] == 403
        assert records[0]["username"] == "bob"
        assert records[0]["role"] == "general"

    def test_no_auth_401_logged(self, isolated_audit_log, client: TestClient):
        r = client.post("/api/admin/clear")
        assert r.status_code == 401
        for h in logging.getLogger("economic_platform.audit").handlers:
            h.flush()
        records = _read_log_lines(isolated_audit_log)
        assert len(records) == 1
        assert records[0]["status_code"] == 401
        assert records[0]["user_id"] is None
        assert records[0]["username"] is None

    def test_passthrough_not_logged(self, isolated_audit_log, client: TestClient):
        # GET without force_refresh should not be logged
        @client.app.get("/api/public")
        async def _public():
            return {"ok": True}

        r = client.get("/api/public")
        assert r.status_code == 200
        for h in logging.getLogger("economic_platform.audit").handlers:
            h.flush()
        records = _read_log_lines(isolated_audit_log)
        assert records == []
