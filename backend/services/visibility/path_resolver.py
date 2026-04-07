"""
リクエストパス → indicator_code 解決ロジック

ReadVisibilityGuardMiddleware が read リクエストの可視性を判定する際に、
URL パスから「この API がどの indicator_code に該当するか」を推定する。

設計方針:
- 可能な限り宣言的 (パターン → indicator_code) で書く
- 該当しないパスは None を返す → 「制御対象外 (= public 扱い)」
- 明示的に restricted (special/master) なものだけ判定すれば十分
  (public がデフォルトのため)
- 1 リクエストで複数の indicator にまたがるエンドポイントは「最も狭い権限」を適用

返り値:
    None       : 制御対象外 (素通し)
    "code"     : 単一 indicator_code
"""
from __future__ import annotations

import re
from typing import Optional


# ===========================================================================
# 1) スクリーンショット系 11 サービス
#    共通プレフィックス: /api/.../<service>/screenshot or /api/screenshot/<service>
#    実際のパスは router によりばらつく → 含有マッチで判定
# ===========================================================================

# (substring -> indicator_code)
_SCREENSHOT_PATTERNS: list[tuple[str, str]] = [
    ("li_keqiang", "screenshot:cn_li_keqiang"),
    ("li-keqiang", "screenshot:cn_li_keqiang"),
    ("baidu_migration", "screenshot:cn_baidu_migration"),
    ("baidu-migration", "screenshot:cn_baidu_migration"),
    ("central_parity", "screenshot:cn_central_parity"),
    ("central-parity", "screenshot:cn_central_parity"),
    ("credit_impulse", "screenshot:cn_credit_impulse"),
    ("credit-impulse", "screenshot:cn_credit_impulse"),
    ("fixing_repo", "screenshot:cn_fixing_repo_rate"),
    ("fixing-repo", "screenshot:cn_fixing_repo_rate"),
    ("government_bond_issuance", "screenshot:cn_government_bond_issuance"),
    ("government-bond-issuance", "screenshot:cn_government_bond_issuance"),
    ("shibor", "screenshot:cn_shibor"),
    # NAB Business Survey Cost & Price (= AU NAB Business Confidence の screenshot 版)
    # 公開エンドポイント /api/australia/abs/nab-business-confidence は public のため
    # 部分一致で巻き込まないように、screenshot 専用パス nab/cost-price でマッチさせる
    ("nab/cost-price", "screenshot:au_nab_business_confidence"),
    ("nab/cost_price", "screenshot:au_nab_business_confidence"),
    ("rba_expectations", "screenshot:au_rba_expectations"),
    ("rba-expectations", "screenshot:au_rba_expectations"),
    ("rba_ois", "screenshot:au_rba_ois"),
    ("rba-ois", "screenshot:au_rba_ois"),
    ("anz_business_sentiment", "screenshot:nz_anz_business_sentiment"),
    ("anz-business-sentiment", "screenshot:nz_anz_business_sentiment"),
    ("boc_rate_cuts", "screenshot:ca_boc_rate_cuts_expectation"),
    ("boc-rate-cuts", "screenshot:ca_boc_rate_cuts_expectation"),
    ("ecb_rate_cuts", "screenshot:eu_ecb_rate_cuts_expectation"),
    ("ecb-rate-cuts", "screenshot:eu_ecb_rate_cuts_expectation"),
    ("cme_fedwatch", "screenshot:usa_cme_fedwatch"),
    ("cme-fedwatch", "screenshot:usa_cme_fedwatch"),
    ("komtrax", "screenshot:global_komtrax"),
]


# ===========================================================================
# 2) ヘッドライン (FinancialJuice 由来) - inbox/saved
#    - GET /api/headlines        → headlines_inbox_translated (special)
#    - GET /api/headlines/public → public (制御対象外)
#    - 個別 GET /api/headlines/{id} → headlines_inbox_translated
# ===========================================================================

# 完全一致または接頭辞でマッチさせる (正規表現)
_PATH_REGEX_MAP: list[tuple[re.Pattern[str], str]] = [
    # /api/headlines/public は制御対象外 (新規 endpoint で個別判定)
    # /api/headlines, /api/headlines/123 は special
    (re.compile(r"^/api/headlines/?$"), "feature:headlines_inbox_translated"),
    (re.compile(r"^/api/headlines/\d+/?$"), "feature:headlines_inbox_translated"),
    # /api/categories は master 限定 (read も含む)
    (re.compile(r"^/api/categories/?$"), "feature:headlines_categories_crud"),
    (re.compile(r"^/api/categories/\d+/?$"), "feature:headlines_categories_crud"),
    # ---- Fear & Greed ----
    (re.compile(r"^/api/market/fear[-_]greed"), "market:fear_greed"),
    (re.compile(r"^/api/fear[-_]greed"), "market:fear_greed"),
    # ---- Market Impact ----
    (re.compile(r"^/api/market-impact/chart"), "feature:market_impact_chart"),
    (re.compile(r"^/api/market-impact/compare"), "feature:market_impact_compare"),
    (re.compile(r"^/api/market-impact/releases/"), "feature:market_impact_chart"),
    # ---- admin/visibility 自体は master 必須だが、router 側 require_role で保証 ----
]


def resolve_indicator_code(path: str) -> Optional[str]:
    """リクエストパスから indicator_code を解決。

    Args:
        path: リクエスト URL パス

    Returns:
        indicator_code または None (制御対象外)
    """
    if not path:
        return None

    # 1) 正規表現マッチ (より厳密)
    for pat, code in _PATH_REGEX_MAP:
        if pat.search(path):
            return code

    # 2) スクリーンショット系 (含有マッチ)
    for needle, code in _SCREENSHOT_PATTERNS:
        if needle in path:
            return code

    return None
