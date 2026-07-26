# -*- coding: utf-8 -*-
"""
series_id → 人間が読める和訳ラベル。

候補指標の表示が `usa/inflation/cpi | value` や `... | bea` のように分かりにくい問題を解消する。
- 国コードを和訳プレフィックス化
- value_key / 末尾トークンを日本語化 (複合語は接尾辞を分解して合成)
- よく出る指標 stem を和訳 (未登録は接頭辞除去して整形)
"""
import re

COUNTRY_JP = {
    "usa": "米", "japan": "日", "eurozone": "欧", "uk": "英", "canada": "加",
    "australia": "豪", "newzealand": "NZ", "switzerland": "瑞", "china": "中",
    "global": "世界", "": "",
}

# ---------------------------------------------------------------------------
# 基語辞書: 複合トークン (fulltime_qoq / gfcf_yoy / exports_mom ...) の「基の語」。
# 末尾の期間/種別接尾辞 (_yoy/_mom/_qoq/_index ...) を剥がした残りをここで引く。
# ---------------------------------------------------------------------------
_BASE_JP = {
    # 需要項目 / GDP 内訳
    "gdp": "GDP", "nominal_gdp": "名目GDP", "gdp_expenditure": "GDP(支出)",
    "gfcf": "総固定資本形成", "gross_fixed_capital": "総固定資本形成",
    "hce": "家計消費", "consumption": "消費", "private_consumption": "民間消費",
    "government_consumption": "政府消費", "consumption_expenditure": "消費支出",
    "exports": "輸出", "imports": "輸入", "net_exports": "純輸出",
    "export": "輸出", "import": "輸入", "trade_balance": "貿易収支",
    "goods_services": "財・サービス", "goods": "財", "services": "サービス",
    "inventories": "在庫", "changes_in_inventories": "在庫変動",
    "primary_income": "第一次所得収支", "secondary_income": "第二次所得収支",
    "current_account": "経常収支", "capital": "資本",
    "net_total": "純計", "net_current": "純経常", "net_goods": "純財",
    "net_services": "純サービス", "net_capital": "純資本", "net_securities": "純証券",
    "net_other": "純その他",
    # 物価
    "cpi": "CPI", "core_cpi": "コアCPI", "hicp": "HICP", "ppi": "PPI",
    "core": "コア", "core_core": "コアコア", "core1": "コア1", "core2": "コア2",
    "deflator": "デフレータ", "trimmed_mean": "刈込平均", "weighted_median": "加重中央値",
    "trim": "刈込平均", "median": "中央値", "common": "共通要素",
    "food": "食料", "energy": "エネルギー", "electricity": "電気", "gas": "ガス",
    "rent": "家賃", "rents": "家賃", "rentals": "家賃", "rent_cpi": "家賃CPI",
    "shelter": "住居費", "purchase_housing": "住宅購入", "new_dwellings": "新規住宅",
    "ex_food_energy": "食料・エネルギー除く", "core_goods": "コア財", "core_services": "コアサービス",
    "nonfood": "非食品", "producer_prices": "生産者物価", "raw_material_price": "原材料価格",
    "import_price": "輸入物価", "export_price": "輸出物価", "terms_of_trade": "交易条件",
    # 雇用 / 賃金
    "employment": "雇用", "unemployment": "失業", "unemployed": "失業者",
    "employment_change": "雇用者数変化", "fulltime": "フルタイム", "parttime": "パートタイム",
    "underutilisation": "不完全就業", "underutilization": "不完全就業", "underemployment": "不完全雇用",
    "participation": "労働参加", "labor_force_participation": "労働参加",
    "labor_force_native": "労働力(国内出生)", "labor_force_foreign": "労働力(外国出生)",
    "employment_native": "雇用(国内出生)", "employment_foreign": "雇用(外国出生)",
    "wages": "賃金", "wage": "賃金", "hourly_earnings": "時給", "regular_pay": "所定内給与",
    "total_pay": "総給与", "regular_employee": "常用雇用者", "part_time": "パートタイム",
    "job_stayer": "継続就業者", "job_changer": "転職者", "job_switcher": "転職者",
    "quits_rate": "離職率", "hires": "採用", "layoffs": "解雇", "layoff": "レイオフ",
    "leavers": "離職者", "reentrants": "再参入者", "new_entrants": "新規参入者",
    "multiple_jobs": "複数就業", "nairu": "NAIRU(自然失業率)",
    "productivity": "労働生産性", "unit_labour_cost": "単位労働コスト", "unit_labor_cost": "単位労働コスト",
    # 住宅 / 建設
    "housing_starts": "住宅着工", "building_permits": "建設許可", "house_price": "住宅価格",
    "new_orders": "新規受注", "total_orders": "総受注", "in_hand_orders": "手持受注",
    "core_orders": "コア受注", "core_shipments": "コア出荷", "ex_transport": "輸送除く",
    # 金融 / マネー
    "m1": "M1", "m2": "M2", "m3": "M3", "monetary_base": "マネタリーベース",
    "bank_rate": "銀行金利", "mortgage": "住宅ローン", "non_mortgage": "非住宅ローン",
    "flow": "フロー", "stock": "ストック", "outstanding": "残高",
    # 期待 / 確率 (CSCE 等)
    "prob_lose_job": "失職確率", "prob_leave_job": "離職確率", "prob_find_job": "求職成功確率",
    "income_growth": "所得成長", "spending_growth": "支出成長",
    # 地域 / 国コード
    "worldwide": "世界", "americas": "米州", "europe": "欧州", "asia_pacific": "アジア太平洋",
    "japan": "日本", "euro_area": "ユーロ圏", "germany": "ドイツ", "france": "フランス",
    "italy": "イタリア", "spain": "スペイン",
    "de": "独", "fr": "仏", "it": "伊", "es": "西", "el": "ギリシャ",
    "usa": "米", "can": "加", "gbr": "英", "jpn": "日", "deu": "独", "aus": "豪",
    "kor": "韓", "chn": "中", "g7": "G7", "g20": "G20",
    # 業種 / PMI 内訳
    "manufacturing": "製造業", "non_manufacturing": "非製造業", "composite": "総合",
    "construction": "建設業", "supplier_delivery": "納期", "supplier_deliveries": "納期",
    "new_export_orders": "新規輸出受注", "export_new_orders": "新規輸出受注",
    "input_prices": "投入価格", "output_prices": "産出価格", "prices": "価格",
    "output": "産出", "input": "投入", "production": "生産", "youth": "若年",
    # 企業景況 (BOS 等)
    "future_sales": "売上見通し", "investment": "投資", "credit": "信用",
    "business": "企業",
    # その他
    "nominal": "名目", "real": "実質", "current": "現状", "expected": "先行き",
    "level": "水準", "index": "指数", "value": "", "raw_value": "", "value_raw": "",
    "sales": "販売", "orders": "受注",
}

# value_key / 末尾トークンの直接和訳 (基語辞書で拾えない固有のもの)
VALUE_KEY_JP = {
    "value": "", "values": "", "close": "終値", "price": "価格", "settle": "清算値",
    "yoy": "前年比", "mom": "前月比", "qoq": "前期比", "wow": "前週比",
    "yoy_change": "前年比", "mom_change": "前月比", "qoq_change": "前期比",
    "yoy_growth": "前年比", "qoq_growth": "前期比", "qoq_simple": "前期比",
    "yoy_data": "前年比", "change": "変化",
    "bea": "BEA基準", "cpi": "CPI基準", "carts_nowcast": "ナウキャスト",
    "unrate": "失業率", "u6rate": "広義U-6", "u3": "U3失業率", "nairu": "",
    "nonfarm": "非農業部門", "civilian": "民間部門",
    "total": "合計", "core": "コア", "core_yoy": "コア前年比", "core_mom": "コア前月比",
    "core_core_yoy": "コアコア前年比", "core1_yoy": "コア1前年比", "core2_yoy": "コア2前年比",
    "annualized": "年率", "annualized_3m": "3ヶ月年率", "annualized_6m": "6ヶ月年率",
    "ratio": "比率", "index": "指数", "level": "水準",
    "balance": "収支", "exports": "輸出", "imports": "輸入",
    "deposit_facility": "中銀預金金利", "all_items": "総合", "all_yoy": "総合前年比",
    "ex_auto": "自動車除く", "ex_auto_yoy": "自動車除く前年比", "ex_auto_mom": "自動車除く前月比",
    "ex_auto_gas_yoy": "自動車・ガソリン除く前年比", "ex_auto_gas_mom": "自動車・ガソリン除く前月比",
    "median_cpi": "中央値CPI", "trimmed_mean_16": "刈込平均16", "twelve_month": "12ヶ月",
    "headline": "総合", "composite": "総合", "manufacturing": "製造業", "services": "サービス業",
    "non_manufacturing": "非製造業", "construction": "建設業",
    "spread": "スプレッド", "sales_amount": "販売額", "indeed": "", "icsa": "", "ic4wsa": "4週平均",
    "previous": "前回値", "worldwide": "世界", "americas": "米州", "europe": "欧州",
    "asia_pacific": "アジア太平洋", "japan": "日本", "gdp": "GDP", "employment": "雇用",
    "ma3": "3ヶ月移動平均", "ma_3m": "3ヶ月移動平均", "ma_12m": "12ヶ月移動平均", "ma3_yoy": "3ヶ月平均前年比",
    "raw_value": "", "value_raw": "", "value_millions": "(百万)", "value_trillion": "(兆)",
    "value_chf": "(CHF)", "chf": "(CHF)", "usd": "(USD)", "ytd": "年初来",
    "new_orders": "新規受注", "supplier_delivery": "納期", "sale_price": "販売価格",
    "input_price": "投入価格", "producer_prices": "生産者物価",
    # 日銀短観 / BSI の業種・現状先行き
    "large_manufacturing": "大企業製造業", "large_non_manufacturing": "大企業非製造業",
    "large_manufacturing_outlook": "大企業製造業(先行き)", "large_manufacturing_current": "大企業製造業(現状)",
    "large_non_manufacturing_outlook": "大企業非製造業(先行き)", "large_non_manufacturing_current": "大企業非製造業(現状)",
    "large_all_industries": "大企業全産業", "medium_all_industries": "中堅企業全産業",
    "small_all_industries": "中小企業全産業", "all_industries_current": "全産業(現状)",
    "small_manufacturing": "中小企業製造業", "ref3_actual": "実績", "actual": "実績",
    # マネーマーケット金利テナー (そのまま表示)
    "on": "翌日物", "1w": "1週間", "2w": "2週間", "1m": "1ヶ月", "3m": "3ヶ月",
    "6m": "6ヶ月", "9m": "9ヶ月", "1y": "1年",
}

# 期間/種別 接尾辞。複合トークンの末尾から剥がして基語に付け足す (長いものを先に)。
_SUFFIX_JP = [
    ("_yoy_change", "前年比"), ("_mom_change", "前月比"), ("_qoq_change", "前期比"),
    ("_yoy_diff", "前年差"), ("_qoq_diff", "前期差"), ("_mom_diff", "前月差"),
    ("_yoy_data", "前年比"), ("_yoy_growth", "前年比"), ("_qoq_growth", "前期比"),
    ("_mma_yoy_data", "前年比(移動平均)"), ("_mma_data", "(移動平均)"),
    ("_contribution", "寄与度"), ("_3m_avg", "3ヶ月平均"), ("_3ma", "3ヶ月移動平均"),
    ("_yoy", "前年比"), ("_mom", "前月比"), ("_qoq", "前期比"), ("_wow", "前週比"),
    ("_index", "指数"), ("_level", "水準"), ("_change", "変化"), ("_growth", "成長率"),
    ("_diff", "差分"), ("_data", ""), ("_value", ""), ("_pch", "変化率"),
]

# 指標 stem (パス末尾の意味トークン) の和訳。未登録は接頭辞除去+整形でフォールバック。
STEM_JP = {
    "cpi": "CPI", "core_cpi": "コアCPI", "national_cpi": "全国CPI", "tokyo_cpi": "東京都区部CPI",
    "cpi_categories": "CPI内訳", "cpi_item": "CPI品目別", "median_cpi": "中央値CPI", "trimmed_mean_pce": "刈込平均PCE",
    "pce": "PCE", "pce_deflator": "PCEデフレータ", "core_pce_deflator": "コアPCEデフレータ",
    "ppi": "PPI", "core_ppi": "コアPPI", "germany_ppi": "独PPI", "quarterly_ppi": "四半期PPI",
    "ecb_hicp": "HICP", "abs_monthly_cpi": "月次CPI", "spain_hicp_cpi": "スペインHICP",
    "abs_cpi_categories": "CPI内訳", "abs_quarterly_cpi": "四半期CPI", "ch_cpi": "CPI",
    "nz_cpi": "CPI", "ons_cpih": "CPIH", "import_export_price": "輸出入物価",
    "import_prices": "輸入物価", "export_prices": "輸出物価", "japan_terms_of_trade": "交易条件", "terms_of_trade": "交易条件",
    "rent_cpi": "家賃CPI", "used_car_prices": "中古車価格", "ippi": "産業製品価格指数(IPPI)",
    "supply_and_demand_driven_pce_inflation": "供給・需要要因別PCEインフレ",
    "retail_sales": "小売売上", "retail_control": "小売コントロール", "advance_real_retail_sales": "実質小売速報",
    "ecb_retail_trade": "小売取引", "ons_retail_sales": "小売売上", "nz_retail_sales": "小売売上",
    "ch_retail_trade": "小売取引", "brc_retail_sales": "BRC小売売上", "brc_shop_price": "BRC店頭価格",
    "household_spending": "家計支出", "consumer_spending": "個人消費",
    "au_household_spending": "家計支出", "au_consumer_spending": "個人消費", "consumption_expenditure": "消費支出",
    "affinity_spend": "Affinity消費", "carts_weekly": "シカゴ連銀小売指数(CARTS)", "carts_price": "CARTS価格",
    "visa_spending": "Visa消費", "redbook": "レッドブック小売", "total_vehicle_sales": "自動車販売台数",
    "personal_consumption_expenditures_services": "個人消費支出(サービス)", "pce_food_recreation": "PCE(食料・娯楽)",
    "nonfarm_payrolls": "非農業部門雇用者数", "adp_employment": "ADP雇用者数", "initial_claims": "新規失業保険申請件数",
    "continued_claims": "継続受給者数", "unemployment_rate": "失業率", "ons_unemployment": "失業率",
    "unemployment": "失業率", "unemployment_by_reason": "失業理由別", "underutilization": "不完全就業率",
    "challenger_job_cuts": "チャレンジャー人員削減", "jolts_indeed": "JOLTS求人件数", "jolts": "JOLTS求人件数",
    "jolts_hires_layoffs": "JOLTS求人(採用・解雇)", "job_openings_per_unemployed": "求人倍率",
    "job_offers_ratio": "有効求人倍率", "job_vacancies": "求人件数", "job_vacancy_rate": "求人率",
    "claimant_count": "失業給付申請者数", "participation_rate": "労働参加率",
    "labor_force_participation": "労働参加率", "labour_force_participation": "労働参加率",
    "labor_force_participation_rate": "労働参加率", "fullpart_time_employment": "フル・パートタイム雇用",
    "fulltime_parttime": "フルタイム・パートタイム雇用", "multiple_jobs_parttime": "複数就業(パート)",
    "temporary_help_services": "臨時就業者数", "overtime_hours": "残業時間", "nairu": "NAIRU(自然失業率)",
    "sahm_rule": "サームルール", "average_hourly_earnings": "平均時給", "atlanta_fed_wage": "賃金トラッカー",
    "employment_cost_index": "雇用コスト指数", "average_hourly_wage": "平均時給", "weekly_average_salary": "週平均賃金",
    "us_average_weekly_working_hours": "週平均労働時間", "cash_earnings": "現金給与総額", "real_wage": "実質賃金",
    "ch_nominal_wage_growth": "名目賃金", "indeed_euro_wage": "Indeed賃金", "nz_wages": "賃金", "wages": "賃金",
    "real_wages": "実質賃金", "unit_labour_costs": "単位労働コスト", "unit_labor_cost": "単位労働コスト",
    "indeed_wage_tracker": "Indeed賃金トラッカー", "adp_wage_growth": "ADP賃金上昇率", "shuntou": "春闘賃上げ率",
    "number_of_employees": "雇用者数", "employed_persons": "就業者数", "employment_type": "雇用形態",
    "number_of_workers_by_place_of_birth": "出生地別就業者数", "ca_employment": "雇用",
    "ons_employment": "雇用", "ecb_employment": "雇用", "ecb_unemployment": "失業率",
    "germany_unemployment": "失業率", "ecb_labor_productivity": "労働生産性", "productivity": "労働生産性",
    "gdp_growth_rate": "GDP成長率", "gdp_growth": "GDP成長率", "gdp_monthly": "月次GDP",
    "quarterly_gdp_yoy": "四半期GDP前年比", "quarterly_gdp_qoq": "四半期GDP前期比",
    "quarterly_gdp_qoq_annualized": "四半期GDP(前期比年率)", "potential_growth": "潜在成長率",
    "ecb_gdp": "GDP", "ons_gdp": "GDP", "ch_growth_rate": "GDP成長率", "nz_gdp_growth_rate": "GDP成長率",
    "au_gdp_growth_rate": "GDP成長率", "cn_gdp_growth_rate": "GDP成長率", "ecb_gdp_components": "GDP内訳",
    "gdp_components": "GDP内訳", "gdp_item": "GDP内訳", "gdp_price_related": "GDP(価格関連)",
    "gdp_economic_related": "GDP(経済関連)", "capital_investment": "設備投資", "fixed_asset_investment": "固定資産投資",
    "private_new_capital_expenditure": "民間設備投資",
    "ism_manufacturing": "ISM製造業", "ism_non_manufacturing": "ISM非製造業", "ism_components": "ISM内訳",
    "pmi": "PMI", "eu_pmi": "PMI", "uk_pmi": "PMI", "cn_pmi": "PMI", "caixin_pmi": "財新PMI",
    "sp_pmi": "S&P PMI", "ivey_pmi": "Ivey PMI", "manufacturing_pmi": "製造業PMI", "pmi_outlook": "PMI見通し",
    "headline": "総合", "manufacturing_sub": "製造業", "non_manufacturing_sub": "非製造業",
    "cn_caixin_pmi": "財新PMI", "jpmorgan_global_manufacturing_pmi": "世界製造業PMI", "oecd_cli": "OECD景気先行指数",
    "michigan_consumer_sentiment": "ミシガン大消費者信頼感", "nfib_price_plans": "NFIB価格計画",
    "nfib_optimism": "NFIB楽観指数", "nfib_compensation": "NFIB報酬計画", "nfib_actual_compensation": "NFIB実際報酬",
    "nfib_capex": "NFIB設備投資計画", "cb_jobs_labor_differential": "労働環境格差", "cb_consumer_confidence": "CB消費者信頼感",
    "michigan_consumer": "ミシガン大消費者", "ifo_business_climate": "Ifo企業景況感", "zew_economic_sentiment": "ZEW景況感",
    "consumer_confidence_gfk": "GfK消費者信頼感", "germany_gfk": "GfK消費者信頼感", "gfk_consumer_confidence": "GfK消費者信頼感",
    "consumer_sentiment": "消費者信頼感", "eurostat_consumer_confidence": "消費者信頼感",
    "france_business_confidence": "企業景況感", "business_confidence": "企業景況感", "nab_business_confidence": "NAB企業景況感",
    "westpac_consumer_confidence": "Westpac消費者信頼感", "kof_economic_barometer": "KOF景気指標",
    "boj_policy_rate": "日銀政策金利", "ecb_rates": "ECB政策金利", "au_rba_rate": "RBA政策金利",
    "boe_bank_rate": "BOE政策金利", "ca_boc_rate": "BOC政策金利", "snb_rate": "SNB政策金利",
    "ch_snb_rate": "SNB政策金利", "cn_reverse_repo_rate": "リバースレポ金利", "cn_fixing_repo_rate": "レポ金利",
    "reverse_repo_rate": "リバースレポ金利", "rbnz_rate": "RBNZ政策金利", "corra": "CORRA(翌日物金利)",
    "sonia": "SONIA(翌日物金利)", "lpr_1y": "ローンプライムレート(1年)", "lpr_5y": "ローンプライムレート(5年)",
    "shibor": "SHIBOR", "rrr": "預金準備率", "qt": "量的引き締め(QT)", "mpc_voting": "MPC投票",
    "bank_interest_rates": "銀行金利", "housing_lending_rates": "住宅貸出金利", "bank_lending": "銀行貸出",
    "boj_gdp_gap": "需給ギャップ", "japan_gdp_gap": "需給ギャップ", "japan_price_di_spread": "価格DIスプレッド",
    "japan_inflation_outlook": "物価見通し", "household_expected_inflation": "家計期待インフレ",
    "inflation_expectations": "期待インフレ", "nz_inflation_expectations": "期待インフレ",
    "ecb_inflation_expectations": "期待インフレ", "michigan_inflation_expectations": "ミシガン期待インフレ",
    "ny_inflation_expectations": "NY期待インフレ", "ces_wage_expectations": "CES賃金期待",
    "trade_balance": "貿易収支", "cn_trade_balance": "貿易収支", "balance_of_trade": "貿易収支",
    "international_trade": "貿易", "japan_balance_of_trade": "貿易収支",
    "eu_international_trade": "貿易", "current_account": "経常収支", "ca_current_account": "経常収支",
    "current_account_balance": "経常収支", "uk_current_account": "経常収支", "nz_current_account_gdp_ratio": "経常収支対GDP比",
    "current_account_gdp_ratio": "経常収支対GDP比", "boj_current_account_balance": "日銀当座預金残高",
    "kr_semiconductor_exports": "韓国半導体輸出", "taiwan_export_orders": "台湾輸出受注",
    "semiconductor_sales": "半導体売上", "south_korean_exports": "韓国輸出", "us_export_dependence": "対米輸出依存度",
    "electrical_equipment_exports": "電機機器輸出", "integrated_circuit_manufacturing": "集積回路生産",
    "electronics_stock": "電子部品在庫",
    "boc_balance_sheet": "BOCバランスシート", "frb_total_assets": "FRB総資産", "oas_hy_spread": "ハイイールドスプレッド",
    "oas_hy_yield": "ハイイールド利回り", "oas_ig_spread": "投資適格スプレッド", "cre_loan_delinquency": "商業用不動産ローン延滞",
    "balance_sheet": "バランスシート", "bank_balance_sheet": "銀行バランスシート",
    "central_bank_balance_sheet": "中央銀行バランスシート", "canada_banks_balance_sheet": "カナダ銀行バランスシート",
    "ecb_balance_sheet": "ECBバランスシート", "snb_balance_sheet": "SNBバランスシート", "boj_lending": "日銀貸出",
    "settlement_balances": "決済残高", "settlement_balances_daily": "決済残高(日次)",
    "reserve_balances": "準備預金残高", "reserve_balances_wresbal": "準備預金残高(WRESBAL)", "tga": "TGA(財務省一般勘定)",
    "on_rrp": "ON RRP(翌日物リバースレポ)", "sight_deposits": "要求払預金", "monetary_base": "マネタリーベース",
    "monetary_aggregate_m2": "マネーサプライM2", "m1_m2": "マネーサプライM1・M2", "m3": "マネーサプライM3",
    "government_deposits": "政府預金", "foreign_currency_reserves": "外貨準備高", "gold_reserves_service": "金準備高",
    "aggregate_financing": "社会融資総量", "adjusted_loans": "調整済み貸出", "labour_cost_index": "労働コスト指数",
    "brent_oil": "ブレント原油", "crude_oil": "WTI原油", "wti": "WTI原油", "copper": "銅", "gold": "ゴールド",
    "ca_slos": "カナダ銀行貸出調査", "boe_inflation_attitudes": "BOEインフレ意識調査", "bls": "銀行貸出調査(BLS)",
    "boe_cpi_components": "BOE CPI内訳", "germany_retail_sales": "独小売売上", "germany_gfk": "GfK消費者信頼感",
    "case_shiller": "ケースシラー住宅価格", "housing_indicators": "住宅指標", "ch_housing_prices": "住宅価格",
    "house_price": "住宅価格", "house_price_index": "住宅価格指数", "new_housing_price_index": "新築住宅価格指数",
    "uk_house_price": "住宅価格", "rightmove_house_price": "Rightmove住宅価格", "halifax_house_price": "Halifax住宅価格",
    "nationwide_hpi": "Nationwide住宅価格", "rics_house_price": "RICS住宅価格", "redfin_median_price": "Redfin住宅価格中央値",
    "zillow_rent_index": "Zillow家賃指数", "rental_vacancy_rate": "賃貸空室率", "nahb_hmi": "NAHB住宅市場指数",
    "housing_starts": "住宅着工", "housing_starts_permits": "住宅着工・許可", "building_permits": "建設許可",
    "number_of_building_permits": "建設許可件数", "existing_home_sales": "中古住宅販売", "new_home_sales": "新築住宅販売",
    "pending_home_sales": "住宅販売保留", "housing_loan_arrears": "住宅ローン延滞率", "cotality_home_prices": "Cotality住宅価格",
    "mortgage_balance": "住宅ローン残高", "mortgage_rates": "住宅ローン金利", "mortgage_lending": "住宅ローン貸出",
    "new_mortgage_loans": "新規住宅ローン", "freddie_mac_mortgage_rates": "フレディマック住宅ローン金利",
    "commercial_residential_sales": "商業・住宅販売",
    "retail_food_services_price": "小売・飲食サービス価格", "nikkei225": "日経平均", "sp500": "S&P500",
    "nasdaq": "NASDAQ", "us02y": "米2年債利回り", "us10y": "米10年債利回り", "us30y": "米30年債利回り",
    "vix": "VIX", "eurusd": "ユーロドル", "usdjpy": "ドル円",
    "japan_cgpi": "企業物価", "japan_cgpi_food_agriculture": "企業物価(食料)", "wage_price_index": "賃金物価指数",
    "japan_sppi": "企業向けサービス価格指数(SPPI)", "japan_pos_uvpi": "POS単価指数(UVPI)",
    "boj_tankan": "日銀短観", "boj_tankan_di": "日銀短観DI", "boj_tankan_capital_investment": "日銀短観設備投資計画",
    "boj_tankan_employment": "日銀短観(雇用)", "boj_tankan_production_facilities": "日銀短観(生産設備)",
    "boj_tankan_purchase_price": "日銀短観(仕入価格)", "boj_tankan_selling_price": "日銀短観(販売価格)",
    "boj_cai": "日銀CAI(景気指数)", "reuters_tankan": "ロイター短観", "tertiary_industry_index": "第三次産業活動指数",
    "machine_tool_orders": "工作機械受注", "machinery_orders": "機械受注", "factory_orders": "製造業受注",
    "durable_goods": "耐久財受注", "industrial_production": "鉱工業生産", "ca_industrial_production": "鉱工業生産",
    "cn_industrial_production": "鉱工業生産", "capacity_utilization": "設備稼働率", "iip": "鉱工業生産指数(IIP)",
    "iip_yoy": "鉱工業生産指数(前年比)", "production": "鉱工業生産", "capital_flows": "資本フロー",
    "overseas_investor_flow": "海外投資家フロー", "land_sales_income": "土地譲渡収入", "local_bonds": "地方債",
    "bsi": "BSI景況判断", "bsi_ref3": "BSI景況判断", "bsi_data": "BSI景況判断",
    "bsi_ref1_actual": "BSI景況判断", "bsi_ref2_actual": "BSI景況判断",
    "bsi_ref3_actual": "BSI景況判断", "bsi_ref4_actual": "BSI景況判断",
    "csce": "消費者期待調査(CSCE)", "bos": "企業景況感調査(BOS)", "cbs": "企業景況調査(CBS)",
    "cbi_industrial_trends": "CBI製造業受注", "anz_job_advertisements": "ANZ求人広告",
    "anz_business_outlook_survey": "ANZ企業見通し調査", "nzier_business_conditions_index": "NZIER業況指数",
    "global_dairy_trade": "世界乳製品貿易(GDT)", "pci": "NZ総合PMI(PCI)", "psi": "NZサービス業PMI(PSI)",
    # 財政 / マクロ
    "productivity_ons": "労働生産性", "gva": "粗付加価値(GVA)", "eurostat_esi": "ESI(経済信頼感)",
    "eurostat_job_vacancy": "求人件数", "eurostat_wages": "賃金", "negotiated_wages": "妥結賃金",
    "public_sector_net_borrowing": "公的部門純借入", "government_debt_to_gdp_ratio": "政府債務対GDP比",
    "federal_budget": "連邦財政収支", "debt_service_ratio": "債務返済比率",
    "disposable_income": "可処分所得", "disposable_personal_income": "可処分所得", "personal_income": "個人所得",
    "personal_saving_rate": "個人貯蓄率", "household_saving_ratio": "家計貯蓄率", "consumer_credit": "消費者信用",
    "delinquency_rate": "延滞率", "cre_loan": "商業用不動産ローン", "households_and_npish": "家計・対家計非営利団体",
    "spf": "ECB専門家予測(SPF)", "spf_core": "ECB専門家予測(コア)", "cash_earnings_stem": "現金給与総額",
    "usd_fundamental_index": "USDファンダメンタル指数", "cpi_service_rent": "CPI(サービス・家賃)",
    "central_parity": "基準値(中心レート)", "beijing_pm25": "北京PM2.5",
    "china_shanghai_container_freight_index": "上海コンテナ運賃指数", "electronics_stock": "電子部品在庫",
    "ecb_ciss": "システミックストレス指標(CISS)", "ciss": "システミックストレス指標(CISS)",
    "global_epu": "世界経済政策不確実性(EPU)", "daily_epu": "経済政策不確実性(日次)", "monthly_epu": "経済政策不確実性(月次)",
    "euro_policy_uncertainty": "欧州政策不確実性", "gscpi": "GSCPI(世界サプライチェーン圧力)", "sofr_volatility": "SOFRボラティリティ",
    "economic_activity": "経済活動",
    # 市場指数 / コモディティ (market ソース用)
    "cac40": "CAC40", "dax": "DAX", "ftse100": "FTSE100", "dow": "NYダウ", "hangseng": "香港ハンセン",
    "eurostoxx50": "ユーロストックス50", "nasdaq100": "ナスダック100", "russell2000": "ラッセル2000",
    "topix": "TOPIX", "sox": "SOX(半導体指数)", "twii": "台湾加権指数", "tsmc": "TSMC",
    "silver": "シルバー", "platinum": "プラチナ", "natural_gas": "天然ガス", "aluminum": "アルミ",
    "copper_to_gold_ratio": "銅金レシオ", "sge_gold": "上海金", "dxy": "ドル指数",
    "financial_stress_index": "金融ストレス指数", "cushing_inventory": "クッシング在庫",
    "distillate_fuel_inventories": "留出油在庫", "us_natural_gas_storage": "米天然ガス貯蔵",
    "eu_natural_gas_production": "EU天然ガス生産", "north_america_rig_count": "北米リグ稼働数",
    "api_weekly_crude_oil_inventories": "API週次原油在庫", "gex_dix": "GEX/DIX", "roni": "RONI", "adjustments": "調整",
    # サブトークン (ネストパス末尾) の和訳
    "cpih_all_yoy": "総合前年比", "cpih_core_yoy": "コア前年比", "cpi_all_yoy": "総合前年比",
    "cpi_core_yoy": "コア前年比", "cpih_all_mom": "総合前月比", "total_hicp": "総合", "core_hicp": "コア",
    "non_manufacturing_sub2": "非製造業", "manufacturing_sub2": "製造業", "non_manufacturing": "非製造業",
    "manufacturing": "製造業",
    "per_person_yoy": "一人当たり前年比", "per_hour_yoy": "時間当たり前年比", "per_person": "一人当たり",
    "employment_yoy": "前年比", "employment_qoq": "前期比", "gdp_growth_yoy": "前年比", "gdp_growth_qoq": "前期比",
    "import_price_index": "輸入物価指数", "export_price_index": "輸出物価指数",
    "retail_yoy": "前年比", "retail_mom": "前月比", "supplier_delivery": "納期", "five_years": "5年先",
    "next_12_months": "今後12ヶ月", "ten_year": "10年", "two_year": "2年", "one_year": "1年", "three_year": "3年",
    "exp5y_median": "5年先(中央値)", "exp1y_median": "1年先(中央値)", "selling_price_outlook": "販売価格見通し",
}

# --- 追加バッチ: ネスト sub-token / 固有 value_key の補完和訳 ---------------
_BASE_JP.update({
    "agriculture": "農産物", "floor_sold": "床面積販売", "floor_started": "床面積着工",
    "export_yen": "円建て輸出", "import_yen": "円建て輸入", "import_contract": "契約輸入",
    "food_services": "外食", "recreation": "娯楽", "avg_hourly_earnings": "平均時給",
    "domestic": "国内", "foreign": "海外", "sofr": "SOFR",
    "per_person": "一人当たり", "per_hour": "時間当たり",
})
VALUE_KEY_JP.update({
    # 日銀 価格DIスプレッド
    "all_industries_purchase": "全産業(仕入価格)", "all_industries_selling": "全産業(販売価格)",
    "all_industries_spread": "全産業(スプレッド)", "large_manufacturing_purchase": "大企業製造業(仕入)",
    "large_manufacturing_selling": "大企業製造業(販売)", "large_manufacturing_spread": "大企業製造業(スプレッド)",
    # 家計期待インフレ
    "current_mean": "現在(平均)", "current_median": "現在(中央値)", "exp1y_mean": "1年先(平均)",
    "exp1y_median": "1年先(中央値)", "exp5y_mean": "5年先(平均)", "exp5y_median": "5年先(中央値)",
    # CSCE / カナダ期待インフレ
    "inflation_1y": "1年先インフレ", "inflation_2y": "2年先インフレ", "inflation_5y": "5年先インフレ",
    "exp_1y": "1年先", "exp_2y": "2年先", "exp_5y": "5年先",
    "wage_next_12m": "今後12ヶ月賃金", "wage_past_12m": "過去12ヶ月賃金",
    # 日銀CAI / 春闘 / 物価見通し
    "nominal_cai": "名目CAI", "real_cai": "実質CAI", "union_member": "労組員", "wage_increase": "賃上げ",
    "general_price_outlook": "総合物価見通し", "selling_price_outlook": "販売価格見通し",
    # 中心レート / 金準備 / リバースレポ入札
    "fixing": "基準値", "spot": "直物", "gold_ounces_wan": "金保有量(万オンス)",
    "gold_value_usd_yi": "金評価額(億USD)", "bid_amount": "応札額", "win_amount": "落札額",
    # 米連邦財政
    "deficit_surplus": "財政収支", "receipts": "歳入", "outlays": "歳出", "fiscal_year": "会計年度",
    # PCE 供給・需要要因
    "demand_driven": "需要要因", "supply_driven": "供給要因", "ambiguous": "判別不能",
    # NFIB / アトランタ賃金 / CB労働環境
    "compensation_plans": "報酬計画", "hiring_plans": "雇用計画", "paid_hourly": "時給労働者",
    "overall": "全体", "job_stayer": "継続就業者", "job_switcher": "転職者",
    "differential": "格差", "hard": "就職困難", "plentiful": "求人豊富",
    # 失業理由別 / 複数就業 / 雇用コスト
    "other_losers": "その他失職", "layoff": "レイオフ", "leavers": "自発的離職",
    "reentrants": "再参入", "new_entrants": "新規参入", "parttime_econ": "経済的理由パート",
    "pch": "変化率", "ulc_pch": "ULC変化率", "productivity_pch": "生産性変化率",
    # ISM内訳 / CRE延滞 / 四半期CPI / 刈込PCE
    "order_inventory_balance": "受注在庫バランス", "order_inventory_balance_3ma": "受注在庫バランス(3ヶ月移動平均)",
    "all_banks": "全銀行", "top_100": "上位100行", "other_banks": "その他銀行",
    "cpi_sa_yoy": "季調CPI前年比", "one_month": "1ヶ月", "six_month": "6ヶ月",
    # 交易条件単価 / 独製造業受注
    "export_uv": "輸出単価指数", "import_uv": "輸入単価指数",
    "index_total": "総合指数", "index_domestic": "国内指数", "index_foreign": "海外指数",
    "production_wda": "生産(営業日調整)",
    # 英住宅種別
    "detached": "戸建", "semi_detached": "セミデタッチド", "terraced": "テラスハウス", "flat": "集合住宅",
    # Ifo / ZEW / 労働生産性
    "climate": "景況", "expectations": "期待", "sentiment": "期待", "situation": "現況",
    # ECB 銀行貸出調査(BLS)
    "consumer_current": "消費者(現状)", "consumer_expected": "消費者(先行き)",
    "enterprises_current": "企業(現状)", "enterprises_expected": "企業(先行き)",
    "housing_current": "住宅(現状)", "housing_expected": "住宅(先行き)",
    # ECB 銀行金利 / 調整済み貸出
    "corporations": "企業向け", "households": "家計向け", "housing": "住宅向け", "nfc": "非金融企業",
    # ECB SPF / 期待インフレ
    "hicp_12m": "HICP(12ヶ月先)", "hicp_24m": "HICP(24ヶ月先)", "hicp_lt": "HICP(長期)",
    "core_12m": "コア(12ヶ月先)", "core_24m": "コア(24ヶ月先)", "core_lt": "コア(長期)",
    "inflation_12m": "12ヶ月先", "inflation_3y": "3年先", "inflation_5y": "5年先",
    "core_excl_unprocessed_food": "コア(未加工食品除く)",
    # ONS CPIH / BOE意識 / 各種期先
    "cpi_all_mom": "総合前月比", "cpi_core_mom": "コア前月比", "following_12_months": "今後12ヶ月",
    "five_year": "5年先", "one_year": "1年先", "two_year": "2年先", "ten_year": "10年先", "three_year": "3年先",
    # 半導体売上 移動平均 / USDファンダ / 中古車
    "mma_data": "(移動平均)", "mma_yoy_data": "前年比(移動平均)",
    "germany_mfg": "ドイツ製造業", "ism_non_mfg": "ISM非製造業",
    "fred_yoy": "FRED前年比", "manheim_yoy": "Manheim前年比", "fred_data": "FRED", "manheim_data": "Manheim",
    "zillow": "Zillow",
    # SOFR / コンテナ運賃 / PM2.5
    "sofr": "SOFR", "sofr_change": "SOFR変化", "volatility_20d": "ボラティリティ(20日)",
    "ccfi": "CCFI(コンテナ運賃)", "scfi": "SCFI(輸出コンテナ運賃)",
    "pm25": "PM2.5", "pm25_avg": "PM2.5平均", "pm25_ma30": "PM2.5(30日移動平均)",
    # 英 財政 / 経常
    "psnb_ex": "PSNB(公的部門純借入)", "psnd_ex": "PSND(公的部門純債務)",
    "psnd_gdp": "PSND対GDP比", "cgnb": "中央政府純借入", "gdp_ratio": "対GDP比",
    # 米労働時間 / 継続申請 (FRED系列コード)
    "awhaetp": "全従業員", "awhman": "製造業", "awhnonag": "非農業",
    "ccsa": "継続申請(季調)", "cc4wsa": "4週平均(季調)",
    # スイス住宅ローン金利バケット
    "variable_500k_1m": "変動(50-100万CHF)", "variable_1m_5m": "変動(100-500万CHF)",
    "fixed_500k_1m": "固定(50-100万CHF)", "fixed_1m_5m": "固定(100-500万CHF)",
    # 豪 住宅貸出金利 / 延滞
    "outstanding_oo_variable": "残高(自住・変動)", "outstanding_oo_fixed": "残高(自住・固定)",
    "outstanding_inv_variable": "残高(投資・変動)", "outstanding_inv_fixed": "残高(投資・固定)",
    "new_oo_variable": "新規(自住・変動)", "new_oo_fixed": "新規(自住・固定)",
    "past_due_30_89": "延滞30-89日", "non_performing": "不良債権", "total_arrears": "延滞合計",
    # 加 対米輸出 / 小売 / 政府預金
    "boc": "BOC", "us_export": "対米輸出", "total_export": "総輸出", "ex_auto_gas_value": "自動車・ガソリン除く",
    # 日 IIP / POS単価
    "item_code": "品目コード", "chg_uvpi_total": "単価指数変化(総合)",
    # 中 地方債 / 土地譲渡
    "monthly_total": "月間発行総額", "monthly_new_total": "月間新規発行", "monthly_new_special": "月間新規特別債",
    "monthly_avg_rate": "月平均金利", "ytd_avg_rate": "年初来平均金利", "debt_limit_total": "債務限度額",
    "debt_balance_total": "債務残高", "special_ratio": "特別債比率", "new_ratio": "新規比率",
    "headroom": "発行余地", "cost": "発行コスト", "monthly_increment": "月間増分",
    "ccdc": "中央国債登記", "shch": "上海清算所",
    # NZ CPI 貿易財区分 / 頻度構造語
    "all": "総合",
    # Fed 上級融資担当者調査(SLOOS): ci=商工業, cre=商業用不動産
    "ci_demand_large": "商工業向け需要(大企業)", "ci_demand_small": "商工業向け需要(中小)",
    "ci_standards_large": "商工業向け基準(大企業)", "ci_standards_small": "商工業向け基準(中小)",
    "cre_demand_mf": "CRE需要(集合住宅)", "cre_demand_cld": "CRE需要(建設・土地)",
    "cre_demand_nfnr": "CRE需要(非住宅)", "cre_standards_mf": "CRE基準(集合住宅)",
    "cre_standards_cld": "CRE基準(建設・土地)", "cre_standards_nfnr": "CRE基準(非住宅)",
})
_BASE_JP.update({
    "tradable": "貿易財", "non_tradable": "非貿易財", "all": "総合",
    "monthly": "月次", "quarterly": "四半期", "daily": "日次", "weekly": "週次",
})

# 意味を持たない原系列コード (ONS CDID / BoE コード等) を sub-token 抑制する集合
_OPAQUE_SUB = {"dmwo", "lzvb", "ecyz", "iumtlmv", "a4ym", "cgnb"}


def _is_opaque_code(tok):
    """ONS/BoE の原系列コード等、和名を持たない識別子か判定 (sub-token 抑制用)。"""
    if tok in _OPAQUE_SUB:
        return True
    if any(ch.isdigit() for ch in tok) and tok not in VALUE_KEY_JP and tok not in _BASE_JP and tok not in STEM_JP:
        # cfmz6jv / cfmz6k6 / ecy2 等 (英数字混在コード)。数値付き意味語は辞書登録済で除外済。
        return bool(re.match(r"^[a-z]{2,}\d", tok))
    return False

# 構造トークン (意味を持たないので除外)
_STRUCT = {"data", "series", "components", "table_data", "annual_rates", "monthly_changes",
           "breakdown_annual_rates", "countries", "indicators", "rates_data", "nominal", "real"}

# stem の接頭辞 (国/機関) を除いて整形するためのプレフィックス
_PREFIX = re.compile(r"^(ecb_|abs_|au_|cn_|ons_|boe_|ch_|nz_|rba_|us_|eu_|snb_|ca_|uk_|jp_|japan_|germany_|france_|spain_|kr_|taiwan_|china_|canada_|boj_|frb_)")


def _translate_token(tok):
    """value_key / 末尾サブトークンを和訳。複合語は期間/種別接尾辞を分解して合成。

    解決できない場合は "_"→スペースの整形英語を返す (少なくとも接尾辞は和訳)。
    """
    if not tok:
        return ""
    if tok in VALUE_KEY_JP:
        return VALUE_KEY_JP[tok]
    if tok in _BASE_JP:
        return _BASE_JP[tok]
    if tok in STEM_JP:
        return STEM_JP[tok]
    for suf, jp in _SUFFIX_JP:
        if tok.endswith(suf) and len(tok) > len(suf):
            base = tok[: -len(suf)]
            bt = _translate_token(base)
            return (bt or "") + jp
    return tok.replace("_", " ")


def _clean_stem(tok):
    if tok in STEM_JP:
        return STEM_JP[tok]
    base = _PREFIX.sub("", tok)
    if base in STEM_JP:
        return STEM_JP[base]
    # 複合語分解にフォールバック (durable_goods_yoy 等)
    return _translate_token(base)


def _vk(tok):
    return _translate_token(tok)


def readable(series_id, cat_idx=None):
    """series_id → 和訳ラベル。"""
    if "::" not in series_id:
        return series_id
    path, vk = series_id.rsplit("::", 1)
    parts = path.split("/")
    source = parts[0]

    # market / seasonality は ①stem辞書 → ②cftc/valuation分解 → ③カタログ和名 → ④ティッカー
    if source in ("market", "seasonality"):
        ticker = parts[-1]
        name = None
        if ticker in STEM_JP:
            name = STEM_JP[ticker]
        if name is None and ticker.startswith("cftc_positioning_"):
            sym = ticker[len("cftc_positioning_"):]
            name = f"建玉({STEM_JP.get(sym, sym.upper())})"
        if name is None and ticker.endswith("_valuation"):
            sym = ticker[: -len("_valuation")]
            name = f"{STEM_JP.get(sym, sym.upper())}バリュエーション"
        if name is None and cat_idx is not None:
            try:
                lab = str(cat_idx.loc[series_id, "label"] or "")
                # 英字のみの label より日本語 label を優先採用
                if lab and not lab.isascii():
                    name = lab
            except Exception:
                pass
        if name is None:
            name = ticker
        vk_jp = _vk(vk)
        return f"{name}（{vk_jp}）" if vk_jp else name

    # macro/<country>/<category>/<rest...>
    country = parts[1] if len(parts) > 1 else ""
    cjp = COUNTRY_JP.get(country, country)
    rest = parts[3:] if len(parts) > 3 else parts[2:]
    # 意味トークンを抽出 (構造トークン除外)
    toks = [t for t in rest if t not in _STRUCT]
    if not toks:
        toks = [parts[-1]]
    # stem = 先頭の意味トークン、サブ = 末尾(stemと異なれば)
    stem_jp = _clean_stem(toks[0])
    sub = ""
    if len(toks) > 1 and toks[-1] != toks[0] and not _is_opaque_code(toks[-1]):
        sub = _translate_token(toks[-1])
    body = stem_jp + (f"・{sub}" if sub and sub != stem_jp else "")

    # value_key: value/values は省略。和訳済の語が既に body に含まれていれば冗長→省略。
    vk_jp = _vk(vk)
    redundant = (vk in ("value", "values")) or (vk_jp and vk_jp in body)
    suffix = "" if (redundant or not vk_jp) else f"（{vk_jp}）"
    return f"{cjp} {body}{suffix}".strip()
