# -*- coding: utf-8 -*-
"""
主要指標レジストリ。

「概念 (CPI/政策金利/雇用/失業/GDP/小売)」を各国カタログから regex で解決する。
60 個の series_id をハードコードせず、存在するものだけを採用 (将来の系列追加に追従)。
"""
import re

COUNTRIES = ["usa", "japan", "eurozone", "uk", "canada", "australia",
             "newzealand", "switzerland", "china"]

COUNTRY_LABEL = {
    "usa": "米国", "japan": "日本", "eurozone": "ユーロ圏", "uk": "英国",
    "canada": "カナダ", "australia": "豪州", "newzealand": "NZ",
    "switzerland": "スイス", "china": "中国",
}

# 概念ごとの (優先 series_id 完全一致 or regex, 表示名)。最初にヒットした 1 系列を採用。
# {c} は国コードに置換。優先度順 (上が優先)。
# パターンは specific→generic 順。最初にマッチした 1 系列 (alpha 最小) を採用。
# 国ごとに命名が違う (日本 CPI は price/ 配下、小売は .../yoy/data::value 等) ため
# inflation|price の両ディレクトリ・ネストした /yoy/ パスも拾えるよう許容度を上げる。
CONCEPTS = [
    ("cpi_yoy", "CPI(前年比)", [
        r"^macro/{c}/inflation/cpi/data::yoy$",
        r"^macro/{c}/price/national_cpi/data::yoy$",
        r"^macro/{c}/inflation/abs_monthly_cpi/data::cpi_yoy$",          # 豪
        r"^macro/{c}/inflation/nz_cpi/data::all_yoy$",                   # NZ
        r"^macro/{c}/inflation/ch_cpi/data::cpi_yoy$",                   # スイス
        r"^macro/{c}/inflation/ecb_hicp/annual_rates/total_hicp::value$",  # ユーロ圏
        r"^macro/{c}/inflation/ons_cpih/.*cpi_all_yoy/data::value$",     # 英
        r"^macro/{c}/(inflation|price)/[a-z_]*cpi[a-z_]*/data::yoy$",
        r"^macro/{c}/(inflation|price)/.*\bcpi\b.*::cpi_yoy$",
        r"^macro/{c}/(inflation|price)/.*\bhicp\b.*::value$",
        r"^macro/{c}/(inflation|price)/.*\bcpi\b.*::yoy$",
    ]),
    ("core_cpi_yoy", "コアCPI(前年比)", [
        r"^macro/{c}/inflation/core_cpi/data::yoy$",
        r"^macro/{c}/price/national_cpi/data::core_yoy$",
        r"^macro/{c}/inflation/ecb_hicp/annual_rates/core_hicp::value$",   # ユーロ圏
        r"^macro/{c}/inflation/ch_cpi/data::core1_yoy$",                   # スイス
        r"^macro/{c}/(inflation|price)/.*core.*cpi.*::yoy$",
        r"^macro/{c}/(inflation|price)/.*cpi.*::(core_yoy|core1_yoy|core_core_yoy)$",
    ]),
    ("policy_rate", "政策金利", [
        r"^macro/{c}/(monetary_policy|policy)/[a-z_]*policy_rate[a-z_]*/data::value$",
        r"^macro/{c}/(monetary_policy|policy)/[a-z_]*(bank_rate|boc_rate|snb_rate|cash_rate|ocr|corra|repo)[a-z_]*/.*::value$",
        r"^macro/{c}/(monetary_policy|policy)/.*(policy_rate|bank_rate|cash_rate|boc_rate|ocr)[a-z_]*::(value|bank_rate)$",
    ]),
    ("unemployment", "失業率", [
        r"^macro/{c}/employment/unemployment_rate/data::(unrate|value|total)$",
        r"^macro/{c}/employment/.*unemployment_rate.*::(unrate|value|total|rate)$",
        r"^macro/{c}/employment/.*\bunemployment\b.*::(unrate|value|total|rate)$",
    ]),
    ("employment", "雇用者数", [
        r"^macro/{c}/employment/nonfarm_payrolls/data::nonfarm$",
        r"^macro/{c}/employment/.*(employed_persons|employment_change|number_of_employees|payroll)[a-z_/]*::(value|nonfarm|total|change|total_qoq)$",
        r"^macro/{c}/employment/.*(employed|employment)[a-z_/]*::(value|total|change)$",
    ]),
    ("wage_yoy", "賃金(前年比)", [
        r"^macro/{c}/employment/[a-z_]*average_hourly_(earnings|wage)/data::yoy$",  # 米/加
        r"^macro/{c}/employment/[a-z_]*wage_price_index/data::yoy$",                # 豪
        r"^macro/{c}/employment/ch_nominal_wage_growth/data::value$",               # 瑞
    ]),
    ("gdp", "GDP", [
        r"^macro/{c}/economy/gdp_growth_rate/data::value$",
        r"^macro/{c}/economy/gdp_growth_rate/data::qoq$",
        r"^macro/{c}/economy/ecb_gdp/gdp_growth_yoy::value$",            # ユーロ圏
        r"^macro/{c}/economy/ons_gdp/yoy::value$",                      # 英
        r"^macro/{c}/economy/ons_gdp/qoq::value$",
        r"^macro/{c}/economy/.*gdp.*growth[a-z_/]*::(value|yoy|qoq)$",
        r"^macro/{c}/economy/[a-z_]*quarterly_gdp[a-z_/]*::(value|yoy|qoq)$",
        r"^macro/{c}/economy/.*\bgdp\b[a-z_/]*::(yoy|qoq)$",
    ]),
    ("retail_yoy", "小売売上(前年比)", [
        r"^macro/{c}/consumer/retail_sales/data::yoy$",
        r"^macro/{c}/consumer/retail_sales/yoy/data::value$",
        r"^macro/{c}/consumer/ecb_retail_trade/retail_yoy::value$",      # ユーロ圏
        r"^macro/{c}/consumer/ons_retail_sales/yoy::value$",            # 英
        r"^macro/{c}/consumer/ch_retail_trade/data::yoy$",              # スイス
        r"^macro/{c}/consumer/nz_retail_sales/data::total_yoy$",        # NZ
        r"^macro/{c}/consumer/.*retail.*::(yoy|total_yoy)$",
        r"^macro/{c}/consumer/.*retail.*/(yoy/)?data::value$",
    ]),
]

# 主要銘柄 (curated)。series_id 完全一致候補を順に試す。
INSTRUMENTS = [
    ("日経平均", ["market/nikkei225::close"]),
    ("TOPIX", ["seasonality/TOPIX::close"]),
    ("S&P500", ["market/sp500::close", "seasonality/S&P500::close"]),
    ("NASDAQ100", ["market/nasdaq::close", "seasonality/ナスダック100::close"]),
    ("ダウ平均", ["market/dow::close", "seasonality/ダウ平均::close"]),
    ("ラッセル2000", ["seasonality/ラッセル2000::close"]),
    ("SOX(半導体)", ["market/sox::close", "seasonality/SOX::close"]),
    ("ドル円", ["market/usdjpy::close"]),
    ("ユーロドル", ["market/eurusd::close"]),
    ("ドル指数", ["seasonality/USD_INDEX::close"]),
    ("ゴールド", ["market/gold::close", "seasonality/ドル建てゴールド::close"]),
    ("WTI原油", ["market/wti::close", "seasonality/WTI原油::close"]),
    ("銅", ["market/copper::close", "seasonality/銅::close"]),
    ("米2年債利回り", ["market/us02y::close"]),
    ("米10年債利回り", ["market/us10y::close"]),
    ("VIX", ["market/vix::close", "seasonality/VIX::close"]),
]

# US 主要指標クロスマトリクス (Theme C)。読みやすさ優先で curated。
US_MATRIX = [
    ("米CPI(前年比)", "macro/usa/inflation/cpi/data::yoy"),
    ("米コアCPI(前年比)", "macro/usa/inflation/core_cpi/data::yoy"),
    ("米2年債利回り(金利パス)", "market/us02y::close"),
    ("米失業率", "macro/usa/employment/unemployment_rate/data::unrate"),
    ("米雇用者数(非農業)", "macro/usa/employment/nonfarm_payrolls/data::nonfarm"),
    ("米GDP", "macro/usa/economy/gdp_growth_rate/data::value"),
    ("米小売売上(前年比)", "macro/usa/consumer/retail_sales/data::yoy"),
    ("日経平均", "market/nikkei225::close"),
    ("ドル円", "market/usdjpy::close"),
]


# 明示オーバーライド: regex で取りこぼす/別系列を当てたいもの。
# (series_id, 表示ラベル上書き or None)。ユーザー指定の解決先を反映。
OVERRIDES = {
    ("eurozone", "policy_rate"): ("macro/eurozone/monetary_policy/ecb_rates/data::value", None),
    ("australia", "policy_rate"): ("macro/australia/policy/au_rba_rate/data::value", None),
    ("uk", "cpi_yoy"): ("macro/uk/inflation/ons_cpih/series/cpih_all_yoy/data::value", "CPIH(前年比)"),
    ("uk", "core_cpi_yoy"): ("macro/uk/inflation/ons_cpih/series/cpih_core_yoy/data::value", "コアCPIH(前年比)"),
    ("uk", "unemployment"): ("macro/uk/employment/ons_unemployment/data::value", None),
    ("switzerland", "gdp"): ("macro/switzerland/economy/ch_growth_rate/data::qoq", None),
    # 豪は小売売上の代わりに家計支出
    ("australia", "retail_yoy"): ("macro/australia/consumer/au_household_spending/data::yoy", "家計支出(前年比)"),
    # 日本GDPは quarterly_gdp_yoy.json (loader 拡張で取込可・前年比を採用)
    ("japan", "gdp"): ("macro/japan/economy/quarterly_gdp_yoy/data::value", None),
    # 米の賃金ターゲットは平均時給(前年比)を明示ラベルで固定
    ("usa", "wage_yoy"): ("macro/usa/employment/average_hourly_earnings/data::yoy", "平均時給(前年比)"),
}

_CONCEPT_LABEL = {c: lbl for c, lbl, _ in CONCEPTS}


def resolve_targets(catalog_ids):
    """カタログ series_id 集合に対し、各国×概念を解決して target リストを返す。

    返り値: list of {key, country, country_label, concept, concept_label, series_id}
    """
    idset = set(catalog_ids)
    targets = []
    for country in COUNTRIES:
        for concept, clabel, patterns in CONCEPTS:
            found = None
            label_override = None
            # 1) 明示オーバーライド優先
            ov = OVERRIDES.get((country, concept))
            if ov and ov[0] in idset:
                found, label_override = ov[0], ov[1]
            else:
                # 2) regex 解決
                for pat in patterns:
                    rx = re.compile(pat.replace("{c}", country))
                    matches = sorted(sid for sid in idset if rx.match(sid))
                    if matches:
                        found = matches[0]
                        break
            if found:
                targets.append({
                    "key": f"{country}_{concept}",
                    "country": country, "country_label": COUNTRY_LABEL[country],
                    "concept": concept, "concept_label": label_override or clabel,
                    "series_id": found,
                })
    return targets


def resolve_instruments(catalog_ids):
    idset = set(catalog_ids)
    out = []
    for label, cands in INSTRUMENTS:
        for sid in cands:
            if sid in idset:
                out.append({"label": label, "series_id": sid})
                break
    return out


def resolve_us_matrix(catalog_ids):
    idset = set(catalog_ids)
    return [(lbl, sid) for lbl, sid in US_MATRIX if sid in idset]
