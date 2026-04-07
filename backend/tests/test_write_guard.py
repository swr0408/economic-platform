"""
WriteOperationGuardMiddleware のテスト

- is_write_request の純関数ユニットテスト
- ミドルウェアの統合テスト (FastAPI TestClient = httpx ベース)

実行:
    cd backend && pytest tests/test_write_guard.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

# backend/ をパスに追加 (`from core.xxx import` を解決するため)
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.datastructures import QueryParams

from core.auth.models import ROLE_GENERAL, ROLE_MASTER, ROLE_SPECIAL
from core.auth.security import create_access_token
from core.auth.write_guard import WriteOperationGuardMiddleware, is_write_request


# =====================================================================
# Unit tests: is_write_request (純関数)
# =====================================================================


def _qp(**kwargs) -> QueryParams:
    return QueryParams([(k, str(v)) for k, v in kwargs.items()])


class TestIsWriteRequestPassthrough:
    """通過すべき (= 更新系ではない) リクエスト"""

    def test_get_without_refresh(self):
        assert is_write_request("GET", "/api/usa/economy/dashboard", _qp()) is False

    def test_get_with_unrelated_query(self):
        assert is_write_request("GET", "/api/usa/cpi", _qp(year=2026)) is False

    def test_auth_login_post(self):
        assert is_write_request("POST", "/api/auth/login", _qp()) is False

    def test_auth_logout_post(self):
        assert is_write_request("POST", "/api/auth/logout", _qp()) is False

    def test_auth_change_password_post(self):
        assert is_write_request("POST", "/api/auth/change-password", _qp()) is False

    def test_options_preflight(self):
        assert is_write_request("OPTIONS", "/api/anything", _qp()) is False

    def test_head_request(self):
        assert is_write_request("HEAD", "/api/anything", _qp()) is False

    def test_get_with_force_refresh_false(self):
        assert is_write_request("GET", "/api/x", _qp(force_refresh="false")) is False


class TestIsWriteRequestDeny:
    """更新系扱い (master 必須) のリクエスト"""

    def test_get_with_force_refresh_true(self):
        assert is_write_request("GET", "/api/usa/cpi", _qp(force_refresh="true")) is True

    def test_get_with_force_refresh_1(self):
        assert is_write_request("GET", "/api/usa/cpi", _qp(force_refresh="1")) is True

    def test_get_with_refresh_yes(self):
        assert is_write_request("GET", "/api/usa/cpi", _qp(refresh="yes")) is True

    def test_post_dashboard_clear(self):
        assert is_write_request("POST", "/api/usa/economy/dashboard/clear", _qp()) is True

    def test_post_market_sync(self):
        assert is_write_request("POST", "/api/market/sync/1", _qp()) is True

    def test_delete_market_cleanup(self):
        assert is_write_request("DELETE", "/api/market/cleanup", _qp()) is True

    def test_put_calendar_event(self):
        assert is_write_request("PUT", "/api/calendar/event/1", _qp()) is True

    def test_patch_some_resource(self):
        assert is_write_request("PATCH", "/api/some/resource", _qp()) is True

    def test_post_headlines_root(self):
        # /save 等のサフィックスでも /save/ でも無いので更新扱い
        assert is_write_request("POST", "/api/headlines/refresh", _qp()) is True

    def test_post_market_impact_fetch(self):
        assert is_write_request("POST", "/api/market_impact/fetch", _qp()) is True

    def test_categories_post_now_master(self):
        # whitelist 撤去後: category CRUD も master 必須
        assert is_write_request("POST", "/api/categories", _qp()) is True

    def test_categories_put_now_master(self):
        assert is_write_request("PUT", "/api/categories/5", _qp()) is True

    def test_categories_delete_now_master(self):
        assert is_write_request("DELETE", "/api/categories/5", _qp()) is True

    def test_headlines_save_post_now_master(self):
        # Headlines save も master 必須に変更
        assert is_write_request("POST", "/api/headlines/123/save", _qp()) is True

    def test_headlines_retranslate_post_now_master(self):
        assert is_write_request("POST", "/api/headlines/123/retranslate", _qp()) is True

    def test_headlines_save_delete_now_master(self):
        assert is_write_request("DELETE", "/api/headlines/save/789", _qp()) is True


# =====================================================================
# Integration tests: WriteOperationGuardMiddleware
# =====================================================================


@pytest.fixture
def app() -> FastAPI:
    """ミドルウェアだけを適用した最小 FastAPI を作る"""
    application = FastAPI()
    application.add_middleware(WriteOperationGuardMiddleware)

    @application.get("/api/usa/cpi")
    async def get_cpi():
        return {"value": 1}

    @application.post("/api/usa/economy/dashboard/clear")
    async def clear_dashboard():
        return {"ok": True}

    @application.delete("/api/market/cleanup")
    async def cleanup():
        return {"deleted": 0}

    @application.post("/api/auth/login")
    async def login():
        return {"token": "x"}

    @application.post("/api/categories")
    async def create_category():
        return {"id": 1}

    @application.post("/api/headlines/123/save")
    async def save_headline():
        return {"saved": True}

    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _bearer(role: str, *, user_id: int = 1, username: str = "tester") -> dict:
    token = create_access_token(user_id=user_id, username=username, role=role)
    return {"Authorization": f"Bearer {token}"}


class TestMiddlewarePassthrough:
    def test_get_without_refresh_no_auth_ok(self, client: TestClient):
        r = client.get("/api/usa/cpi")
        assert r.status_code == 200
        assert r.json() == {"value": 1}

    def test_auth_login_no_auth_ok(self, client: TestClient):
        r = client.post("/api/auth/login")
        assert r.status_code == 200

    def test_categories_post_no_auth_returns_401(self, client: TestClient):
        # whitelist 撤去後: category CRUD も master 必須
        r = client.post("/api/categories")
        assert r.status_code == 401

    def test_headlines_save_no_auth_returns_401(self, client: TestClient):
        # whitelist 撤去後: headlines save も master 必須
        r = client.post("/api/headlines/123/save")
        assert r.status_code == 401

    def test_categories_post_master_returns_200(self, client: TestClient):
        r = client.post("/api/categories", headers=_bearer(ROLE_MASTER))
        assert r.status_code == 200

    def test_headlines_save_master_returns_200(self, client: TestClient):
        r = client.post("/api/headlines/123/save", headers=_bearer(ROLE_MASTER))
        assert r.status_code == 200

    def test_categories_post_general_returns_403(self, client: TestClient):
        r = client.post("/api/categories", headers=_bearer(ROLE_GENERAL))
        assert r.status_code == 403

    def test_headlines_save_general_returns_403(self, client: TestClient):
        r = client.post("/api/headlines/123/save", headers=_bearer(ROLE_GENERAL))
        assert r.status_code == 403


class TestMiddlewareWriteOperations:
    def test_post_no_auth_returns_401(self, client: TestClient):
        r = client.post("/api/usa/economy/dashboard/clear")
        assert r.status_code == 401
        assert r.json() == {"detail": "Not authenticated"}

    def test_post_invalid_token_returns_401(self, client: TestClient):
        r = client.post(
            "/api/usa/economy/dashboard/clear",
            headers={"Authorization": "Bearer not.a.real.token"},
        )
        assert r.status_code == 401
        assert r.json() == {"detail": "Invalid or expired token"}

    def test_post_invalid_authz_format_returns_401(self, client: TestClient):
        r = client.post(
            "/api/usa/economy/dashboard/clear",
            headers={"Authorization": "Basic xyz"},
        )
        assert r.status_code == 401
        assert r.json() == {"detail": "Invalid authorization header"}

    def test_post_general_role_returns_403(self, client: TestClient):
        r = client.post(
            "/api/usa/economy/dashboard/clear",
            headers=_bearer(ROLE_GENERAL),
        )
        assert r.status_code == 403
        assert r.json() == {"detail": "Requires role in ['master']"}

    def test_post_special_role_returns_403(self, client: TestClient):
        r = client.post(
            "/api/usa/economy/dashboard/clear",
            headers=_bearer(ROLE_SPECIAL),
        )
        assert r.status_code == 403
        assert r.json() == {"detail": "Requires role in ['master']"}

    def test_post_master_role_returns_200(self, client: TestClient):
        r = client.post(
            "/api/usa/economy/dashboard/clear",
            headers=_bearer(ROLE_MASTER),
        )
        assert r.status_code == 200
        assert r.json() == {"ok": True}

    def test_delete_master_role_returns_200(self, client: TestClient):
        r = client.delete("/api/market/cleanup", headers=_bearer(ROLE_MASTER))
        assert r.status_code == 200

    def test_delete_general_role_returns_403(self, client: TestClient):
        r = client.delete("/api/market/cleanup", headers=_bearer(ROLE_GENERAL))
        assert r.status_code == 403


class TestMiddlewareForceRefresh:
    def test_get_force_refresh_no_auth_returns_401(self, client: TestClient):
        r = client.get("/api/usa/cpi", params={"force_refresh": "true"})
        assert r.status_code == 401

    def test_get_force_refresh_general_returns_403(self, client: TestClient):
        r = client.get(
            "/api/usa/cpi",
            params={"force_refresh": "true"},
            headers=_bearer(ROLE_GENERAL),
        )
        assert r.status_code == 403

    def test_get_force_refresh_master_returns_200(self, client: TestClient):
        r = client.get(
            "/api/usa/cpi",
            params={"force_refresh": "true"},
            headers=_bearer(ROLE_MASTER),
        )
        assert r.status_code == 200

    def test_get_refresh_query_master_returns_200(self, client: TestClient):
        r = client.get(
            "/api/usa/cpi",
            params={"refresh": "1"},
            headers=_bearer(ROLE_MASTER),
        )
        assert r.status_code == 200

    def test_get_force_refresh_false_no_auth_ok(self, client: TestClient):
        # force_refresh=false は更新扱いでは無いので素通し
        r = client.get("/api/usa/cpi", params={"force_refresh": "false"})
        assert r.status_code == 200
