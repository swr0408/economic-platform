"""
read_visibility_guard.should_block_read の純関数ユニットテスト

path_resolver と visibility_service の組合せロジックを検証する。
visibility_service.get_visibility はモックで差し替え、外部依存を排除。

実行:
    cd backend && pytest tests/test_read_visibility_guard.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from core.auth.models import ROLE_GENERAL, ROLE_MASTER, ROLE_SPECIAL
from core.auth import read_visibility_guard as rvg
from core.auth.read_visibility_guard import should_block_read
from services.visibility.visibility_service import (
    VIS_MASTER,
    VIS_PUBLIC,
    VIS_SPECIAL,
)


# =====================================================================
# 制御対象外パス: path_resolver が None を返す → ブロックしない
# =====================================================================


class TestUnresolvedPath:
    def test_unknown_path_no_block(self):
        block, code = should_block_read("GET", "/api/usa/cpi", ROLE_GENERAL)
        # path_resolver が None を返すパス
        assert block is False
        assert code is None

    def test_unknown_path_anonymous_no_block(self):
        block, code = should_block_read("GET", "/api/usa/cpi", None)
        assert block is False
        assert code is None

    def test_dashboard_path_no_block(self):
        block, code = should_block_read(
            "GET", "/api/usa/economy/dashboard", ROLE_GENERAL
        )
        assert block is False
        assert code is None


# =====================================================================
# GET 以外は常に通す (write_guard に任せる)
# =====================================================================


class TestNonGetMethods:
    def test_post_no_block(self):
        block, code = should_block_read(
            "POST", "/api/headlines", ROLE_GENERAL
        )
        assert block is False
        assert code is None

    def test_put_no_block(self):
        block, code = should_block_read(
            "PUT", "/api/admin/visibility/x", ROLE_GENERAL
        )
        assert block is False
        assert code is None

    def test_delete_no_block(self):
        block, code = should_block_read(
            "DELETE", "/api/headlines/1", ROLE_GENERAL
        )
        assert block is False
        assert code is None

    def test_options_no_block(self):
        block, code = should_block_read("OPTIONS", "/api/anything", None)
        assert block is False
        assert code is None


# =====================================================================
# 制御対象パスかつ public → 認証無しでも素通し (middleware 側で 401 にする想定)
# =====================================================================


class TestPublicPaths:
    def test_public_general(self):
        with patch.object(rvg, "get_visibility", return_value=VIS_PUBLIC):
            block, code = should_block_read(
                "GET", "/api/headlines", ROLE_GENERAL
            )
        assert block is False
        assert code == "feature:headlines_inbox_translated"

    def test_public_anonymous(self):
        with patch.object(rvg, "get_visibility", return_value=VIS_PUBLIC):
            block, code = should_block_read("GET", "/api/headlines", None)
        assert block is False
        assert code == "feature:headlines_inbox_translated"

    def test_public_master(self):
        with patch.object(rvg, "get_visibility", return_value=VIS_PUBLIC):
            block, code = should_block_read(
                "GET", "/api/headlines", ROLE_MASTER
            )
        assert block is False
        assert code == "feature:headlines_inbox_translated"


# =====================================================================
# 制御対象パスかつ special → master / special 通過、general / 未ログイン ブロック
# =====================================================================


class TestSpecialPaths:
    def test_special_master_passes(self):
        with patch.object(rvg, "get_visibility", return_value=VIS_SPECIAL):
            block, code = should_block_read(
                "GET", "/api/market/fear_greed", ROLE_MASTER
            )
        assert block is False
        assert code == "market:fear_greed"

    def test_special_special_passes(self):
        with patch.object(rvg, "get_visibility", return_value=VIS_SPECIAL):
            block, code = should_block_read(
                "GET", "/api/market/fear_greed", ROLE_SPECIAL
            )
        assert block is False
        assert code == "market:fear_greed"

    def test_special_general_blocked(self):
        with patch.object(rvg, "get_visibility", return_value=VIS_SPECIAL):
            block, code = should_block_read(
                "GET", "/api/market/fear_greed", ROLE_GENERAL
            )
        assert block is True
        assert code == "market:fear_greed"

    def test_special_anonymous_blocked(self):
        with patch.object(rvg, "get_visibility", return_value=VIS_SPECIAL):
            block, code = should_block_read(
                "GET", "/api/market/fear_greed", None
            )
        assert block is True
        assert code == "market:fear_greed"


# =====================================================================
# 制御対象パスかつ master → master のみ通過
# =====================================================================


class TestMasterPaths:
    def test_master_master_passes(self):
        with patch.object(rvg, "get_visibility", return_value=VIS_MASTER):
            block, code = should_block_read(
                "GET", "/api/china/shibor", ROLE_MASTER
            )
        assert block is False
        assert code == "screenshot:cn_shibor"

    def test_master_special_blocked(self):
        with patch.object(rvg, "get_visibility", return_value=VIS_MASTER):
            block, code = should_block_read(
                "GET", "/api/china/shibor", ROLE_SPECIAL
            )
        assert block is True
        assert code == "screenshot:cn_shibor"

    def test_master_general_blocked(self):
        with patch.object(rvg, "get_visibility", return_value=VIS_MASTER):
            block, code = should_block_read(
                "GET", "/api/china/shibor", ROLE_GENERAL
            )
        assert block is True
        assert code == "screenshot:cn_shibor"

    def test_master_anonymous_blocked(self):
        with patch.object(rvg, "get_visibility", return_value=VIS_MASTER):
            block, code = should_block_read(
                "GET", "/api/china/shibor", None
            )
        assert block is True
        assert code == "screenshot:cn_shibor"


# =====================================================================
# screenshot: 系の含有マッチ + visibility 判定の組合せ
# =====================================================================


class TestScreenshotPathsResolution:
    """path_resolver の含有マッチが正しく効いていることを (モック無しで) 確認。"""

    def test_li_keqiang_resolves(self):
        with patch.object(rvg, "get_visibility", return_value=VIS_SPECIAL):
            block, code = should_block_read(
                "GET",
                "/api/china/economy/li_keqiang_index",
                ROLE_GENERAL,
            )
        assert block is True
        assert code == "screenshot:cn_li_keqiang"

    def test_baidu_migration_resolves(self):
        with patch.object(rvg, "get_visibility", return_value=VIS_MASTER):
            block, code = should_block_read(
                "GET",
                "/api/china/baidu_migration/data",
                ROLE_SPECIAL,
            )
        assert block is True
        assert code == "screenshot:cn_baidu_migration"

    def test_komtrax_resolves(self):
        with patch.object(rvg, "get_visibility", return_value=VIS_SPECIAL):
            block, code = should_block_read(
                "GET", "/api/global/komtrax", ROLE_MASTER
            )
        assert block is False
        assert code == "screenshot:global_komtrax"
