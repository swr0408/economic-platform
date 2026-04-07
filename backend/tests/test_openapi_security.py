"""
OpenAPI security scheme verification.

Verifies that endpoints protected by `require_role(ROLE_MASTER)` are
exposed in the OpenAPI schema with a security requirement (which Swagger
UI / `/docs` renders as the lock icon next to the endpoint).
"""
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import pytest
from fastapi import Depends, FastAPI

from core.auth.dependencies import require_role
from core.auth.models import ROLE_MASTER


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI(title="security-test")
    _require_master = require_role(ROLE_MASTER)

    @application.get("/api/public")
    def public():
        return {"ok": True}

    @application.post("/api/admin/clear")
    def admin_clear(_master=Depends(_require_master)):
        return {"cleared": True}

    return application


def test_openapi_has_bearer_security_scheme(app: FastAPI):
    """Bearer auth scheme is registered globally so /docs shows Authorize."""
    schema = app.openapi()
    components = schema.get("components", {})
    security_schemes = components.get("securitySchemes", {})
    # FastAPI auto-names HTTPBearer scheme as "HTTPBearer"
    assert "HTTPBearer" in security_schemes, (
        f"HTTPBearer scheme not registered. Found: {list(security_schemes.keys())}"
    )
    bearer = security_schemes["HTTPBearer"]
    assert bearer.get("type") == "http"
    assert bearer.get("scheme") == "bearer"


def test_protected_endpoint_has_security_requirement(app: FastAPI):
    """Endpoints behind require_role show a security requirement (lock icon)."""
    schema = app.openapi()
    paths = schema.get("paths", {})
    admin_path = paths.get("/api/admin/clear", {})
    post_op = admin_path.get("post", {})
    security = post_op.get("security", [])
    assert security, (
        "Protected endpoint /api/admin/clear has no security requirement; "
        "Swagger UI will not render a lock icon."
    )
    # Should reference HTTPBearer
    assert any("HTTPBearer" in req for req in security), (
        f"Expected HTTPBearer in security requirements, got {security}"
    )


def test_public_endpoint_has_no_security_requirement(app: FastAPI):
    """Plain endpoints stay unmarked."""
    schema = app.openapi()
    paths = schema.get("paths", {})
    public_op = paths.get("/api/public", {}).get("get", {})
    # FastAPI omits the key entirely when there is no security requirement
    assert "security" not in public_op or public_op["security"] == []
