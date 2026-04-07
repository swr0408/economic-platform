"""
path_resolver.resolve_indicator_code の純関数ユニットテスト

DB やネットワークに依存しないので軽量に走る。

実行:
    cd backend && pytest tests/test_path_resolver.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from services.visibility.path_resolver import resolve_indicator_code


# =====================================================================
# 制御対象外 (None を返す)
# =====================================================================


class TestPassthrough:
    def test_empty_path(self):
        assert resolve_indicator_code("") is None

    def test_root_path(self):
        assert resolve_indicator_code("/") is None

    def test_unknown_dashboard(self):
        assert resolve_indicator_code("/api/usa/economy/dashboard") is None

    def test_unknown_cpi(self):
        assert resolve_indicator_code("/api/usa/cpi") is None

    def test_unknown_calendar(self):
        assert resolve_indicator_code("/api/calendar") is None

    def test_headlines_public_passthrough(self):
        # /api/headlines/public は明示的に制御対象外 (新規 endpoint で個別判定)
        assert resolve_indicator_code("/api/headlines/public") is None

    def test_admin_visibility_passthrough(self):
        # admin/visibility 自体は router 側 require_role で保証
        assert resolve_indicator_code("/api/admin/visibility") is None


# =====================================================================
# Headlines / Categories
# =====================================================================


class TestHeadlinesAndCategories:
    def test_headlines_root(self):
        assert (
            resolve_indicator_code("/api/headlines")
            == "feature:headlines_inbox_translated"
        )

    def test_headlines_root_trailing_slash(self):
        assert (
            resolve_indicator_code("/api/headlines/")
            == "feature:headlines_inbox_translated"
        )

    def test_headlines_by_id(self):
        assert (
            resolve_indicator_code("/api/headlines/123")
            == "feature:headlines_inbox_translated"
        )

    def test_categories_root(self):
        assert (
            resolve_indicator_code("/api/categories")
            == "feature:headlines_categories_crud"
        )

    def test_categories_by_id(self):
        assert (
            resolve_indicator_code("/api/categories/5")
            == "feature:headlines_categories_crud"
        )


# =====================================================================
# Fear & Greed / Market Impact
# =====================================================================


class TestMarketEndpoints:
    def test_fear_greed_underscore(self):
        assert resolve_indicator_code("/api/market/fear_greed") == "market:fear_greed"

    def test_fear_greed_dash(self):
        assert resolve_indicator_code("/api/market/fear-greed") == "market:fear_greed"

    def test_fear_greed_legacy(self):
        assert resolve_indicator_code("/api/fear_greed") == "market:fear_greed"

    def test_market_impact_chart(self):
        assert (
            resolve_indicator_code("/api/market-impact/chart/cpi")
            == "feature:market_impact_chart"
        )

    def test_market_impact_compare(self):
        assert (
            resolve_indicator_code("/api/market-impact/compare?a=cpi&b=ppi")
            == "feature:market_impact_compare"
        )

    def test_market_impact_releases(self):
        assert (
            resolve_indicator_code("/api/market-impact/releases/123")
            == "feature:market_impact_chart"
        )


# =====================================================================
# スクリーンショット系 (含有マッチ)
# =====================================================================


class TestScreenshots:
    def test_li_keqiang_underscore(self):
        assert (
            resolve_indicator_code("/api/china/economy/li_keqiang_index")
            == "screenshot:cn_li_keqiang"
        )

    def test_li_keqiang_dash(self):
        assert (
            resolve_indicator_code("/api/screenshot/li-keqiang")
            == "screenshot:cn_li_keqiang"
        )

    def test_baidu_migration(self):
        assert (
            resolve_indicator_code("/api/china/baidu_migration/data")
            == "screenshot:cn_baidu_migration"
        )

    def test_central_parity(self):
        assert (
            resolve_indicator_code("/api/china/central_parity")
            == "screenshot:cn_central_parity"
        )

    def test_credit_impulse(self):
        assert (
            resolve_indicator_code("/api/china/credit_impulse")
            == "screenshot:cn_credit_impulse"
        )

    def test_fixing_repo(self):
        assert (
            resolve_indicator_code("/api/china/fixing_repo_rate")
            == "screenshot:cn_fixing_repo_rate"
        )

    def test_government_bond_issuance(self):
        assert (
            resolve_indicator_code("/api/china/government_bond_issuance")
            == "screenshot:cn_government_bond_issuance"
        )

    def test_shibor(self):
        assert resolve_indicator_code("/api/china/shibor") == "screenshot:cn_shibor"

    def test_nab_business_confidence(self):
        # screenshot 専用パスは /api/australia/nab/cost-price/... のみマッチ
        assert (
            resolve_indicator_code("/api/australia/nab/cost-price")
            == "screenshot:au_nab_business_confidence"
        )
        assert (
            resolve_indicator_code("/api/australia/nab/cost-price/cost_growth")
            == "screenshot:au_nab_business_confidence"
        )

    def test_nab_business_confidence_public_not_blocked(self):
        # 公開エンドポイント /api/australia/abs/nab-business-confidence は
        # 部分一致で screenshot に巻き込まれてはならない (= None)
        assert (
            resolve_indicator_code("/api/australia/abs/nab-business-confidence")
            is None
        )

    def test_rba_expectations(self):
        assert (
            resolve_indicator_code("/api/au/rba_expectations")
            == "screenshot:au_rba_expectations"
        )

    def test_rba_ois(self):
        assert resolve_indicator_code("/api/au/rba_ois") == "screenshot:au_rba_ois"

    def test_anz_business_sentiment(self):
        assert (
            resolve_indicator_code("/api/nz/anz_business_sentiment")
            == "screenshot:nz_anz_business_sentiment"
        )

    def test_boc_rate_cuts(self):
        assert (
            resolve_indicator_code("/api/ca/boc_rate_cuts")
            == "screenshot:ca_boc_rate_cuts_expectation"
        )

    def test_ecb_rate_cuts(self):
        assert (
            resolve_indicator_code("/api/eu/ecb_rate_cuts")
            == "screenshot:eu_ecb_rate_cuts_expectation"
        )

    def test_cme_fedwatch(self):
        assert (
            resolve_indicator_code("/api/usa/cme_fedwatch")
            == "screenshot:usa_cme_fedwatch"
        )

    def test_komtrax(self):
        assert (
            resolve_indicator_code("/api/global/komtrax") == "screenshot:global_komtrax"
        )


# =====================================================================
# 優先順位: 正規表現マッチが先 (含有マッチより優先)
# =====================================================================


class TestPriority:
    def test_headlines_takes_precedence_over_substring(self):
        # 仮に headlines の path に "shibor" が含まれていてもヘッドライン扱いになる
        # (現実には起きないが正規表現が先に走ることの確認)
        path = "/api/headlines/shibor-test"
        # 正規表現は ^/api/headlines/\d+/?$ なので /shibor-test はマッチしない
        # → 含有マッチで shibor を拾う
        assert resolve_indicator_code(path) == "screenshot:cn_shibor"
