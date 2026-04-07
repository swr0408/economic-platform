"""
visibility_service の純関数ユニットテスト

DB に依存しない純関数 (_can_view_visibility) と
DB をモックした関数 (filter_visible, get_visibility, upsert_visibility のバリデーション)
をテストする。

実行:
    cd backend && pytest tests/test_visibility_service.py -v
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
from services.visibility import visibility_service as vs
from services.visibility.visibility_service import (
    VIS_MASTER,
    VIS_PUBLIC,
    VIS_SPECIAL,
    _can_view_visibility,
    filter_visible,
    get_visibility,
    upsert_visibility,
)


# =====================================================================
# _can_view_visibility (純関数: 全 3x3 + None)
# =====================================================================


class TestCanViewVisibility:
    # ----- public は誰でも見える -----
    def test_public_master(self):
        assert _can_view_visibility(ROLE_MASTER, VIS_PUBLIC) is True

    def test_public_special(self):
        assert _can_view_visibility(ROLE_SPECIAL, VIS_PUBLIC) is True

    def test_public_general(self):
        assert _can_view_visibility(ROLE_GENERAL, VIS_PUBLIC) is True

    def test_public_anonymous(self):
        assert _can_view_visibility(None, VIS_PUBLIC) is True

    # ----- special は special / master のみ -----
    def test_special_master(self):
        assert _can_view_visibility(ROLE_MASTER, VIS_SPECIAL) is True

    def test_special_special(self):
        assert _can_view_visibility(ROLE_SPECIAL, VIS_SPECIAL) is True

    def test_special_general_blocked(self):
        assert _can_view_visibility(ROLE_GENERAL, VIS_SPECIAL) is False

    def test_special_anonymous_blocked(self):
        assert _can_view_visibility(None, VIS_SPECIAL) is False

    # ----- master は master のみ -----
    def test_master_master(self):
        assert _can_view_visibility(ROLE_MASTER, VIS_MASTER) is True

    def test_master_special_blocked(self):
        assert _can_view_visibility(ROLE_SPECIAL, VIS_MASTER) is False

    def test_master_general_blocked(self):
        assert _can_view_visibility(ROLE_GENERAL, VIS_MASTER) is False

    def test_master_anonymous_blocked(self):
        assert _can_view_visibility(None, VIS_MASTER) is False

    # ----- 未知の visibility 値はフェイルクローズ (master のみ) -----
    def test_unknown_visibility_master_passes(self):
        # vis 文字列が public/special/master のいずれでも無い場合
        # 現実装は master だけ通す (return True 直後)
        assert _can_view_visibility(ROLE_MASTER, "unknown") is True

    def test_unknown_visibility_general_blocked(self):
        assert _can_view_visibility(ROLE_GENERAL, "unknown") is False


# =====================================================================
# get_visibility / filter_visible (キャッシュをモック)
# =====================================================================


@pytest.fixture(autouse=True)
def _reset_cache():
    """各テストでキャッシュをクリア"""
    vs._cache.invalidate()
    yield
    vs._cache.invalidate()


class TestGetVisibility:
    def test_unregistered_returns_public(self):
        with patch.object(vs._cache, "get_all", return_value={}):
            assert get_visibility("usa:cpi") == VIS_PUBLIC

    def test_registered_special(self):
        with patch.object(
            vs._cache, "get_all", return_value={"usa:cpi": VIS_SPECIAL}
        ):
            assert get_visibility("usa:cpi") == VIS_SPECIAL

    def test_registered_master(self):
        with patch.object(
            vs._cache, "get_all", return_value={"feature:secret": VIS_MASTER}
        ):
            assert get_visibility("feature:secret") == VIS_MASTER

    def test_registered_explicit_public(self):
        with patch.object(
            vs._cache, "get_all", return_value={"usa:cpi": VIS_PUBLIC}
        ):
            assert get_visibility("usa:cpi") == VIS_PUBLIC


class TestFilterVisible:
    @pytest.fixture
    def mock_cache(self):
        """3 種類の visibility を持つ DB を擬似"""
        data = {
            "usa:cpi": VIS_PUBLIC,           # 全員 OK
            "usa:nfp": VIS_SPECIAL,          # special / master のみ
            "feature:secret": VIS_MASTER,    # master のみ
            # "usa:gdp" は未登録 → public 扱い
        }
        with patch.object(vs._cache, "get_all", return_value=data):
            yield

    def test_master_sees_everything(self, mock_cache):
        codes = ["usa:cpi", "usa:nfp", "feature:secret", "usa:gdp"]
        assert filter_visible(ROLE_MASTER, codes) == codes

    def test_special_sees_public_and_special(self, mock_cache):
        codes = ["usa:cpi", "usa:nfp", "feature:secret", "usa:gdp"]
        assert filter_visible(ROLE_SPECIAL, codes) == [
            "usa:cpi",
            "usa:nfp",
            "usa:gdp",
        ]

    def test_general_sees_only_public(self, mock_cache):
        codes = ["usa:cpi", "usa:nfp", "feature:secret", "usa:gdp"]
        assert filter_visible(ROLE_GENERAL, codes) == ["usa:cpi", "usa:gdp"]

    def test_anonymous_sees_only_public(self, mock_cache):
        codes = ["usa:cpi", "usa:nfp", "feature:secret", "usa:gdp"]
        assert filter_visible(None, codes) == ["usa:cpi", "usa:gdp"]

    def test_empty_input(self, mock_cache):
        assert filter_visible(ROLE_GENERAL, []) == []

    def test_preserves_order(self, mock_cache):
        codes = ["usa:gdp", "usa:cpi", "usa:nfp"]
        # general は usa:nfp(special) を弾く
        assert filter_visible(ROLE_GENERAL, codes) == ["usa:gdp", "usa:cpi"]

    def test_iterable_generator_input(self, mock_cache):
        codes = (c for c in ["usa:cpi", "usa:nfp"])
        assert filter_visible(ROLE_GENERAL, codes) == ["usa:cpi"]


# =====================================================================
# upsert_visibility のバリデーション (DB は呼ばないでエラーで弾かれることを確認)
# =====================================================================


class TestUpsertValidation:
    def test_invalid_visibility_raises(self):
        with pytest.raises(ValueError, match="Invalid visibility"):
            upsert_visibility("usa:cpi", "wrong")

    def test_invalid_visibility_empty_raises(self):
        with pytest.raises(ValueError, match="Invalid visibility"):
            upsert_visibility("usa:cpi", "")

    def test_empty_indicator_code_raises(self):
        with pytest.raises(ValueError, match="indicator_code"):
            upsert_visibility("", VIS_PUBLIC)

    def test_too_long_indicator_code_raises(self):
        with pytest.raises(ValueError, match="<= 128 chars"):
            upsert_visibility("a" * 129, VIS_PUBLIC)

    def test_max_length_indicator_code_passes_validation(self):
        """128 文字ちょうどはバリデーションを通る (DB は呼ばれる前にモックでショート)。"""
        # DB 接続前に validation だけが走る → 128 文字はバリデーション OK
        # その後 DB 呼び出しで失敗するので、ValueError 以外の例外が出ることを期待
        with pytest.raises(Exception) as exc_info:
            upsert_visibility("a" * 128, VIS_PUBLIC)
        # ValueError ではないことを確認 (= バリデーションは通った)
        assert not isinstance(exc_info.value, ValueError)
