"""
indicator_visibility 初期データ投入

Phase 1-6 で確定した分類方針 (public / special / master) を反映する。
冪等: 既に行が存在する indicator_code は触らない (UPSERT で上書きしない)。

分類方針 (Prompt 1〜2 で確定):

[public]
- 公式 API 由来の指標 (FRED / ECB SDW / e-Stat / FMP / BLS / 公式統計局)
- ハンドブック (handbook)
- /inbox の元データ (未翻訳の生ヘッドライン)
- シーズナリティ基本 (騰落率)
- SQ/MSQ 分析

[special, master]
- スクリーンショット系 11 サービス (CN/EU/JP の半官製ダッシュボード)
- Discord 取得 / RSS バックフィル (FinancialJuice 由来)
- 翻訳済みヘッドライン (/inbox の翻訳 ver)
- 翻訳済み HeadlinePanel
- Fear & Greed (CNN 内部 API)
- Market Impact チャート/比較
- シーズナリティの「見送りモデル / 品質モデル / 後継モデル」(未実装)
- signal/inference 表示 (未実装)
- stats_lab 由来の研究記事 (未実装、フラグだけ準備)

[master]
- ヘッドライン保存 / カテゴリ CRUD / 再翻訳 (write_guard で保証)
- /saved (保存済みヘッドライン管理画面)
- 各種 admin/* (RSS 手動実行など)

備考:
- visibility='master' は indicator というよりは "管理画面/CRUD" 系。
- このテーブルでは「読み取り画面」用の制御を主目的とする。
- write 系は引き続き WriteOperationGuardMiddleware で master 強制。
"""
from __future__ import annotations

import logging

from sqlalchemy import text

try:
    from backend.core.database import engine
except ImportError:
    from core.database import engine

logger = logging.getLogger(__name__)


# (indicator_code, visibility, reason)
# indicator_code の命名規則:
#   - 国別指標: "{country}:{category}:{indicator}"   ex: "usa:economy:gdpnow"
#   - グローバル/マーケット系: "market:{category}" ex: "market:fear_greed"
#   - 機能/画面: "feature:{name}"                  ex: "feature:headlines_inbox_translated"
#   - スクリーンショット系: "screenshot:{name}"     ex: "screenshot:cn_li_keqiang"
#
# 既定値は public のため、ここには非 public のものを中心にリストする。
# (public のものも明示登録した方が管理画面で見やすいので主要な代表を入れる)

# ---- public (代表) ----
_PUBLIC_SEED: list[tuple[str, str]] = [
    # ハンドブック / シーズナリティ基本
    ("feature:handbook", "ハンドブック (研究寄り解説)"),
    ("feature:seasonality_basic", "シーズナリティ基本 (騰落率)"),
    ("feature:sq_msq_analysis", "SQ / MSQ 分析"),
    ("feature:headlines_inbox_raw", "/inbox の生 (未翻訳) ヘッドライン"),
    ("feature:headlines_public_curated", "master が is_public_visible=TRUE で curate したヘッドライン"),
    # 公式 API 由来の主要指標 (代表)
    ("usa:economy:gdp_growth", "FRED 公式 API"),
    ("usa:inflation:cpi", "BLS / FRED 公式 API"),
    ("usa:employment:nfp", "BLS 公式 API"),
    ("eurozone:economy:gdp", "ECB SDW 公式 API"),
    ("japan:economy:gdp", "e-Stat / 内閣府"),
]

# ---- special / master (非公開) ----
_RESTRICTED_SEED: list[tuple[str, str, str]] = [
    # ---- スクリーンショット系 11 サービス ----
    ("screenshot:cn_li_keqiang", "special", "中国李克強指数 (スクリーンショット取得)"),
    ("screenshot:cn_baidu_migration", "special", "中国 百度遷徙 (スクリーンショット取得)"),
    ("screenshot:cn_central_parity", "special", "中国 中央パリティ (スクリーンショット取得)"),
    ("screenshot:cn_credit_impulse", "special", "中国 クレジットインパルス (スクリーンショット取得)"),
    ("screenshot:cn_fixing_repo_rate", "special", "中国 Fixing Repo Rate (スクリーンショット取得)"),
    ("screenshot:cn_government_bond_issuance", "special", "中国 国債発行 (スクリーンショット取得)"),
    ("screenshot:cn_shibor", "special", "SHIBOR (スクリーンショット取得)"),
    ("screenshot:au_nab_business_confidence", "special", "AU NAB 企業信頼感 (スクリーンショット取得)"),
    ("screenshot:au_rba_expectations", "special", "AU RBA 利下げ期待 (スクリーンショット取得)"),
    ("screenshot:au_rba_ois", "special", "AU RBA OIS (スクリーンショット取得)"),
    ("screenshot:nz_anz_business_sentiment", "special", "NZ ANZ 企業センチ (スクリーンショット取得)"),
    ("screenshot:ca_boc_rate_cuts_expectation", "special", "CA BoC 利下げ期待 (スクリーンショット取得)"),
    ("screenshot:eu_ecb_rate_cuts_expectation", "special", "EU ECB 利下げ期待 (スクリーンショット取得)"),
    ("screenshot:usa_cme_fedwatch", "special", "USA CME FedWatch (スクリーンショット取得)"),
    ("screenshot:global_komtrax", "special", "Komtrax (スクリーンショット取得)"),

    # ---- ヘッドライン (FinancialJuice 由来) ----
    ("feature:headlines_discord", "special", "Discord (FinancialJuice) 取得ヘッドライン"),
    ("feature:headlines_rss", "special", "RSS (FinancialJuice) バックフィルヘッドライン"),
    ("feature:headlines_inbox_translated", "special", "/inbox の翻訳済みヘッドライン (翻訳コスト)"),
    ("feature:headlines_panel_translated", "special", "国別ページ HeadlinePanel の翻訳済み"),

    # ---- Fear & Greed (CNN 内部 API) ----
    ("market:fear_greed", "special", "CNN Fear & Greed Index (CNN 内部 API, 半スクレイピング)"),

    # ---- Market Impact ----
    ("feature:market_impact_chart", "special", "Market Impact チャート (Dukascopy 負荷)"),
    ("feature:market_impact_compare", "special", "Market Impact 比較 (Dukascopy 負荷)"),

    # ---- シーズナリティの非公開モデル (未実装、フラグのみ) ----
    ("feature:seasonality_skip_model", "special", "シーズナリティ 見送りモデル (未実装)"),
    ("feature:seasonality_quality_model", "special", "シーズナリティ 品質モデル (未実装)"),
    ("feature:seasonality_successor_model", "special", "シーズナリティ 後継モデル (未実装)"),

    # ---- 推論/シグナル系 (未実装、フラグのみ) ----
    ("feature:signal_display", "special", "signal/inference 表示 (未実装)"),
    ("feature:stats_lab_articles", "special", "stats_lab 由来の研究記事 (未実装)"),

    # ---- master 限定 (管理画面/CRUD) ----
    ("feature:headlines_saved_management", "master", "/saved 保存済みヘッドライン管理"),
    ("feature:headlines_categories_crud", "master", "ヘッドラインカテゴリ CRUD"),
    ("feature:headlines_save_action", "master", "ヘッドライン保存/解除アクション"),
    ("feature:headlines_retranslate", "master", "ヘッドライン再翻訳"),
    ("feature:admin_visibility", "master", "可視性管理画面"),
    ("feature:admin_users", "master", "ユーザー管理画面"),
    ("feature:admin_rss_backfill", "master", "RSS 手動バックフィル"),
    ("feature:admin_discord_status", "master", "Discord 接続状態確認"),
]


_INSERT_SQL = text("""
INSERT INTO public.indicator_visibility (indicator_code, visibility, reason)
VALUES (:code, :vis, :reason)
ON CONFLICT (indicator_code) DO NOTHING
""")


def seed_indicator_visibility() -> int:
    """初期データを投入。既存行は触らない (冪等)。

    Returns:
        新規挿入された行数
    """
    inserted = 0
    try:
        with engine.begin() as conn:
            for code, reason in _PUBLIC_SEED:
                result = conn.execute(
                    _INSERT_SQL,
                    {"code": code, "vis": "public", "reason": reason},
                )
                inserted += result.rowcount or 0

            for code, vis, reason in _RESTRICTED_SEED:
                result = conn.execute(
                    _INSERT_SQL,
                    {"code": code, "vis": vis, "reason": reason},
                )
                inserted += result.rowcount or 0

        logger.info(f"[visibility] seeded {inserted} new indicator_visibility rows")
    except Exception as e:
        logger.error(f"[visibility] seed failed: {e}")
        raise
    return inserted
