"""
httpOnly Cookie 認証のテスト

- core.auth.cookies のヘルパ関数の単体テスト
- write_guard / read_visibility_guard が Authorization ヘッダ無しで
  Cookie 経由のトークンを認識して通すことを統合テストで確認

実行:
    cd backend && pytest tests/test_cookie_auth.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

# backend/ をパスに追加 (`from core.xxx import` を解決するため)
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth.cookies import (
    ACCESS_TOKEN_COOKIE_NAME,
    extract_token_from_cookie,
)
from core.auth.models import ROLE_GENERAL, ROLE_MASTER, ROLE_SPECIAL
from core.auth.read_visibility_guard import ReadVisibilityGuardMiddleware
from core.auth.security import create_access_token
from core.auth.write_guard import WriteOperationGuardMiddleware
from core.auth import read_visibility_guard as rvg
from services.visibility.visibility_service import VIS_PUBLIC, VIS_SPECIAL


# =====================================================================
# Unit tests: extract_token_from_cookie
# =====================================================================


class TestExtractTokenFromCookie:
    def test_none_header(self):
        assert extract_token_from_cookie(None) is None

    def test_empty_header(self):
        assert extract_token_from_cookie("") is None

    def test_single_cookie(self):
        header = f"{ACCESS_TOKEN_COOKIE_NAME}=abc.def.ghi"
        assert extract_token_from_cookie(header) == "abc.def.ghi"

    def test_multiple_cookies(self):
        header = f"foo=bar; {ACCESS_TOKEN_COOKIE_NAME}=abc.def.ghi; baz=qux"
        assert extract_token_from_cookie(header) == "abc.def.ghi"

    def test_missing_token_cookie(self):
        header = "foo=bar; baz=qux"
        assert extract_token_from_cookie(header) is None

    def test_empty_token_value(self):
        header = f"{ACCESS_TOKEN_COOKIE_NAME}="
        assert extract_token_from_cookie(header) is None

    def test_whitespace_handling(self):
        header = f"  foo=bar ;   {ACCESS_TOKEN_COOKIE_NAME}=abc.def.ghi  "
        assert extract_token_from_cookie(header) == "abc.def.ghi"

    def test_malformed_segment_skipped(self):
        header = f"foo; {ACCESS_TOKEN_COOKIE_NAME}=abc.def.ghi"
        assert extract_token_from_cookie(header) == "abc.def.ghi"


# =====================================================================
# Integration tests: WriteOperationGuardMiddleware + Cookie 認証
# =====================================================================


@pytest.fixture
def write_app() -> FastAPI:
    application = FastAPI()
    application.add_middleware(WriteOperationGuardMiddleware)

    @application.post("/api/usa/economy/dashboard/clear")
    async def clear_dashboard():
        return {"ok": True}

    return application


@pytest.fixture
def write_client(write_app: FastAPI) -> TestClient:
    return TestClient(write_app)


def _make_token(role: str) -> str:
    return create_access_token(user_id=1, username="tester", role=role)


class TestWriteGuardCookieAuth:
    def test_post_with_cookie_master_returns_200(self, write_client: TestClient):
        token = _make_token(ROLE_MASTER)
        write_client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, token)
        r = write_client.post("/api/usa/economy/dashboard/clear")
        assert r.status_code == 200
        assert r.json() == {"ok": True}

    def test_post_with_cookie_general_returns_403(self, write_client: TestClient):
        token = _make_token(ROLE_GENERAL)
        write_client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, token)
        r = write_client.post("/api/usa/economy/dashboard/clear")
        assert r.status_code == 403

    def test_post_with_cookie_special_returns_403(self, write_client: TestClient):
        token = _make_token(ROLE_SPECIAL)
        write_client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, token)
        r = write_client.post("/api/usa/economy/dashboard/clear")
        assert r.status_code == 403

    def test_post_with_invalid_cookie_returns_401(self, write_client: TestClient):
        write_client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, "not.a.real.token")
        r = write_client.post("/api/usa/economy/dashboard/clear")
        assert r.status_code == 401
        assert r.json() == {"detail": "Invalid or expired token"}

    def test_authorization_header_takes_precedence(self, write_client: TestClient):
        # Cookie は general、Header は master の場合は header 側を使う
        bad_token = _make_token(ROLE_GENERAL)
        good_token = _make_token(ROLE_MASTER)
        write_client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, bad_token)
        r = write_client.post(
            "/api/usa/economy/dashboard/clear",
            headers={"Authorization": f"Bearer {good_token}"},
        )
        assert r.status_code == 200


# =====================================================================
# Integration tests: ReadVisibilityGuardMiddleware + Cookie 認証
# =====================================================================


@pytest.fixture
def read_app() -> FastAPI:
    application = FastAPI()
    application.add_middleware(ReadVisibilityGuardMiddleware)

    @application.get("/api/market/fear_greed")
    async def fear_greed():
        return {"value": 50}

    # 制御対象外 (path_resolver が None を返す) の public エンドポイント
    # → ログイン済みなら誰でも 200、未ログインは 401 になるべき
    @application.get("/api/usa/cpi")
    async def cpi():
        return {"value": 3.2}

    # 認証例外プレフィックス (/api/health, /api/auth/*) の擬似エンドポイント
    @application.get("/api/health")
    async def health():
        return {"status": "ok"}

    @application.get("/api/auth/me")
    async def me():
        return {"user": "anonymous"}

    # /static/screenshots/ は visibility ガード対象 (会員制)
    # /static/seasonality/ は例外プレフィックス (公開)
    @application.get("/static/screenshots/{filename:path}")
    async def screenshot(filename: str):
        return {"file": filename}

    @application.get("/static/seasonality/{filename:path}")
    async def seasonality(filename: str):
        return {"file": filename}

    return application


@pytest.fixture
def read_client(read_app: FastAPI) -> TestClient:
    return TestClient(read_app)


class TestReadGuardCookieAuth:
    def test_get_with_cookie_master_passes(self, read_client: TestClient):
        token = _make_token(ROLE_MASTER)
        read_client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, token)
        with patch.object(rvg, "get_visibility", return_value=VIS_SPECIAL):
            r = read_client.get("/api/market/fear_greed")
        assert r.status_code == 200
        assert r.json() == {"value": 50}

    def test_get_with_cookie_special_passes(self, read_client: TestClient):
        token = _make_token(ROLE_SPECIAL)
        read_client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, token)
        with patch.object(rvg, "get_visibility", return_value=VIS_SPECIAL):
            r = read_client.get("/api/market/fear_greed")
        assert r.status_code == 200

    def test_get_with_cookie_general_blocked(self, read_client: TestClient):
        token = _make_token(ROLE_GENERAL)
        read_client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, token)
        with patch.object(rvg, "get_visibility", return_value=VIS_SPECIAL):
            r = read_client.get("/api/market/fear_greed")
        assert r.status_code == 403
        body = r.json()
        assert body["indicator_code"] == "market:fear_greed"

    def test_get_no_auth_blocked(self, read_client: TestClient):
        with patch.object(rvg, "get_visibility", return_value=VIS_SPECIAL):
            r = read_client.get("/api/market/fear_greed")
        assert r.status_code == 401

    def test_get_with_invalid_cookie_returns_401(self, read_client: TestClient):
        read_client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, "not.a.real.token")
        with patch.object(rvg, "get_visibility", return_value=VIS_SPECIAL):
            r = read_client.get("/api/market/fear_greed")
        assert r.status_code == 401

    def test_get_public_with_cookie_passes(self, read_client: TestClient):
        token = _make_token(ROLE_GENERAL)
        read_client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, token)
        with patch.object(rvg, "get_visibility", return_value=VIS_PUBLIC):
            r = read_client.get("/api/market/fear_greed")
        assert r.status_code == 200


# =====================================================================
# Member-only enforcement: /api/* GET は path_resolver 非該当でも認証必須
# (= public visibility = ログイン済み一般ユーザ向け公開)
# =====================================================================


class TestMemberOnlyAccess:
    """EconAlpha は会員制サイト。/api/* GET は例外プレフィックス以外
    全て認証必須 (未ログインは 401)。"""

    def test_unresolved_path_no_auth_returns_401(self, read_client: TestClient):
        # path_resolver が None を返す制御対象外パスでも、未ログインなら 401
        r = read_client.get("/api/usa/cpi")
        assert r.status_code == 401

    def test_unresolved_path_with_general_cookie_returns_200(
        self, read_client: TestClient
    ):
        # ログイン済みなら general でも public エンドポイントは閲覧可
        token = _make_token(ROLE_GENERAL)
        read_client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, token)
        r = read_client.get("/api/usa/cpi")
        assert r.status_code == 200
        assert r.json() == {"value": 3.2}

    def test_unresolved_path_with_master_cookie_returns_200(
        self, read_client: TestClient
    ):
        token = _make_token(ROLE_MASTER)
        read_client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, token)
        r = read_client.get("/api/usa/cpi")
        assert r.status_code == 200

    def test_unresolved_path_with_invalid_cookie_returns_401(
        self, read_client: TestClient
    ):
        read_client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, "not.a.real.token")
        r = read_client.get("/api/usa/cpi")
        assert r.status_code == 401

    def test_health_endpoint_no_auth_returns_200(self, read_client: TestClient):
        # /api/health は監視用のため未ログインで 200
        r = read_client.get("/api/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_auth_endpoint_no_auth_returns_200(self, read_client: TestClient):
        # /api/auth/* は未ログインで素通し (ログイン/me/etc)
        r = read_client.get("/api/auth/me")
        assert r.status_code == 200


# =====================================================================
# Static asset gating: /static/screenshots/ は会員制、
# /static/seasonality/ は公開
# =====================================================================


class TestStaticAssetAccess:
    """/static/screenshots/ は special/master 限定指標の画像を含むため、
    未ログインには 401 を返す。/static/seasonality/ は公開画像 (素通し)。"""

    def test_screenshots_no_auth_returns_401(self, read_client: TestClient):
        # visibility ガード対象の静的画像は未ログインで 401
        r = read_client.get("/static/screenshots/usa/fear_greed.png")
        assert r.status_code == 401

    def test_screenshots_with_invalid_cookie_returns_401(
        self, read_client: TestClient
    ):
        read_client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, "not.a.real.token")
        r = read_client.get("/static/screenshots/usa/fear_greed.png")
        assert r.status_code == 401

    def test_screenshots_with_general_cookie_returns_200(
        self, read_client: TestClient
    ):
        # path_resolver が None を返すファイル名なら general でも閲覧可
        # (visibility 非対象 = public = ログイン済み誰でも)
        token = _make_token(ROLE_GENERAL)
        read_client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, token)
        r = read_client.get("/static/screenshots/misc/icon.png")
        assert r.status_code == 200

    def test_screenshots_with_master_cookie_returns_200(
        self, read_client: TestClient
    ):
        token = _make_token(ROLE_MASTER)
        read_client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, token)
        r = read_client.get("/static/screenshots/misc/icon.png")
        assert r.status_code == 200

    def test_seasonality_no_auth_returns_200(self, read_client: TestClient):
        # /static/seasonality/ は例外プレフィックス (公開)
        r = read_client.get("/static/seasonality/SPY.png")
        assert r.status_code == 200
