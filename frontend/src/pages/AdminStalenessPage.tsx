/**
 * キャッシュ鮮度モニタ / ワンクリック更新画面 (master 限定)
 *
 * - GET  /api/admin/staleness?category=...  : STUCK 等の遅延キャッシュ一覧
 * - POST /api/admin/refresh {file}          : 該当サービスを force_refresh
 *
 * バックエンド側で require_role("master") により強制されているため、
 * フロントの ProtectedRoute と二重防御となる。
 *
 * 更新結果の意味:
 *   ADVANCED : 再取得されていなかっただけ → 復旧 (集約キャッシュも無効化済)
 *   SAME     : force_refresh しても進まず → ソース未反映ラグ or fetch 破損
 *   NO_SVC / NO_METH / EXC : 命名規約外・例外 (個別調査)
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Input,
  Segmented,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd'
import { ReloadOutlined, SearchOutlined, ThunderboltOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { useAuth } from '../contexts/AuthContext'
import { COUNTRIES_DATA } from '../constants/countryData'
import { MARKET_CATEGORIES_DATA } from '../constants/marketData'

const { Title, Text } = Typography

const colors = {
  bgSecondary: '#1e293b',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  border: '#334155',
}

interface StalenessItem {
  file: string
  category: string
  freq?: string
  interval?: number
  latest?: string | null
  days_since_latest?: number | null
}

interface RefreshResult {
  status: string
  before?: string | null
  after?: string | null
  error?: string | null
}

const CATEGORY_COLORS: Record<string, string> = {
  STUCK: 'red',
  WRITER_STOPPED: 'volcano',
  LAGGING: 'gold',
  PARSE_ERROR: 'magenta',
  OK: 'green',
}

const STATUS_COLORS: Record<string, string> = {
  ADVANCED: 'green',
  SAME: 'gold',
  NO_SVC: 'default',
  NO_METH: 'default',
  EXC: 'red',
}

const CATEGORY_OPTIONS = [
  { value: 'STUCK', label: 'STUCK (最優先)' },
  { value: 'STUCK,WRITER_STOPPED', label: 'STUCK + 書込停止' },
  { value: 'STUCK,WRITER_STOPPED,LAGGING', label: '遅延すべて' },
]

// 表示モード:
//   FLAGGED = 遅延検知 (category 絞り込み・従来動作)
//   ALL     = 全指標 (include_ok=true で OK 含む全 JSON キャッシュを列挙し、
//             鮮度判定に関わらず任意の指標を手動 force_refresh できる)
type ViewMode = 'FLAGGED' | 'ALL'
const VIEW_OPTIONS = [
  { value: 'FLAGGED' as ViewMode, label: '遅延検知' },
  { value: 'ALL' as ViewMode, label: '全指標' },
]

// force_refresh は重い指標(Excel/CSV解析・遅い外部源)で時間がかかるため、
// グローバル fetch ラッパの 30s 上限ではなく専用の長いタイムアウトを使う。
// (自前 signal を渡すと fetchAuth.ts のラッパは独自タイムアウトを適用しない)
const REFRESH_TIMEOUT_MS = 180_000

// 鮮度走査も 760+ キャッシュの stat/解析で 10〜30 秒かかることがあるため、
// グローバル 30s ではなく専用の長いタイムアウトを使う。
const SCAN_TIMEOUT_MS = 120_000

// ---------------------------------------------------------------------------
// キャッシュ file パス → 日本語の指標名 (ベストエフォート)
//
// 表示名の登録元はナビゲーション定数 (countryData / marketData)。キーはチャートの
// アンカー code (ハイフン区切り) で、キャッシュ file 名 (サービス名ベース・
// アンダースコア) とは「ハイフン↔アンダースコア」変換で多くが一致する。
// scope (国 / 'market') 単位で索引し、同名 slug の国跨ぎ衝突を避ける。
// 突合できない (file 名と code が不一致 / market・global 配下の一部) ものは
// slug を整形したラベルにフォールバックする。file パスは更新キー兼デバッグ用に
// 常に併記するため、誤マッピングがあっても実害は小さい。
// ---------------------------------------------------------------------------
const INDICATOR_NAME_MAP: Record<string, string> = (() => {
  const m: Record<string, string> = {}
  const put = (scope: string, code: string, name: string) => {
    const key = `${scope}/${code.replace(/-/g, '_')}`
    if (!(key in m)) m[key] = name
  }
  for (const c of COUNTRIES_DATA)
    for (const cat of c.categories)
      for (const ind of cat.indicators) put(c.code, ind.code, ind.name)
  for (const cat of MARKET_CATEGORIES_DATA)
    for (const sub of cat.subCategories)
      for (const ind of sub.indicators) put('market', ind.code, ind.name)
  return m
})()

// 補完辞書: ナビゲーション定数と突合できないキャッシュ (file 名と
// チャート code が不一致 / 国接頭辞付き / market・global の生データ /
// schedule・metadata・pdf 等の内部成果物) を手動で日本語名に対応付ける。
// キーは displayNameOf と同じ `${scope}/${base}` 形式。
// INDICATOR_NAME_MAP の後段フォールバックとして使う (登録名が優先)。
const SUPPLEMENTAL_NAME_MAP: Record<string, string> = {
  // --- australia ---
  'australia/au_consumer_spending': '豪 消費支出',
  'australia/au_disposable_personal_income': '豪 可処分所得',
  'australia/au_household_saving_ratio': '豪 家計貯蓄率',
  'australia/au_household_spending': '豪 家計支出',
  'australia/au_nab_business_confidence': '豪 NAB企業信頼感',
  'australia/au_westpac_consumer_confidence': '豪 ウエストパック消費者信頼感',
  'australia/au_current_account': '豪 経常収支',
  'australia/au_current_account_gdp_ratio': '豪 経常収支対GDP比',
  'australia/au_gdp_economic_related': '豪 GDP（経済関連）',
  'australia/au_gdp_growth_rate': '豪 GDP成長率',
  'australia/au_gdp_price_related': '豪 GDP（物価関連）',
  'australia/au_international_trade': '豪 貿易収支',
  'australia/au_pmi': '豪 PMI',
  'australia/au_private_new_capital_expenditure': '豪 民間設備投資',
  'australia/au_terms_of_trade': '豪 交易条件',
  'australia/au_anz_job_advertisements': '豪 ANZ求人広告件数',
  'australia/au_employed_persons': '豪 就業者数',
  'australia/au_fulltime_parttime': '豪 フルタイム/パートタイム雇用',
  'australia/au_job_vacancies': '豪 求人件数',
  'australia/au_participation_rate': '豪 労働参加率',
  'australia/au_underutilization': '豪 労働力不完全利用率',
  'australia/au_unemployment_rate': '豪 失業率',
  'australia/au_wage_price_index': '豪 賃金物価指数',
  'australia/au_cotality_home_prices': '豪 住宅価格（Cotality）',
  'australia/au_number_of_building_permits': '豪 住宅建設許可件数',
  'australia/abs_cpi_categories': '豪 CPI（品目別）',
  'australia/abs_monthly_cpi': '豪 月次CPI',
  'australia/abs_quarterly_cpi': '豪 四半期CPI',
  'australia/abs_quarterly_ppi': '豪 四半期PPI',
  'australia/au_inflation_expectations': '豪 期待インフレ率',
  'australia/nab_imported_pdfs': '豪 NAB（取込PDF）',
  'australia/au_housing_lending_rates': '豪 住宅ローン金利',
  'australia/au_housing_loan_arrears': '豪 住宅ローン延滞率',
  'australia/au_rba_rate': '豪 RBA政策金利',
  'australia/rba_smp_forecast': '豪 RBA金融政策報告（SMP）見通し',
  // --- boj_tankan ---
  'boj_tankan/boj_tankan_capital_investment': '日銀短観 設備投資',
  'boj_tankan/boj_tankan_di': '日銀短観 業況判断DI',
  'boj_tankan/boj_tankan_purchase_price': '日銀短観 仕入価格判断DI',
  'boj_tankan/boj_tankan_selling_price': '日銀短観 販売価格判断DI',
  // --- bsi (法人企業景気予測調査) ---
  'bsi/bsi_data': 'BSI 法人企業景気予測調査',
  'bsi/bsi_ref1_actual': 'BSI 参考1（実績）',
  'bsi/bsi_ref1_forecast1': 'BSI 参考1（見通し1）',
  'bsi/bsi_ref1_forecast2': 'BSI 参考1（見通し2）',
  'bsi/bsi_ref2_actual': 'BSI 参考2（実績）',
  'bsi/bsi_ref3_actual': 'BSI 参考3（実績）',
  'bsi/bsi_ref4_actual': 'BSI 参考4（実績）',
  // --- canada ---
  'canada/ca_debt_service_ratio': '加 家計債務返済比率',
  'canada/ca_retail_sales': '加 小売売上高',
  'canada/ca_bos': '加 企業景況調査（BOS）',
  'canada/ca_csce': '加 消費者期待調査（CSCE）',
  'canada/ca_current_account': '加 経常収支',
  'canada/ca_current_account_gdp_ratio': '加 経常収支対GDP比',
  'canada/ca_gdp_growth': '加 GDP成長率',
  'canada/ca_gdp_monthly': '加 月次GDP',
  'canada/ca_industrial_production': '加 鉱工業生産',
  'canada/ca_ivey_pmi': '加 Ivey PMI',
  'canada/ca_slos': '加 上級貸出担当者調査（SLOS）',
  'canada/ca_sp_pmi': '加 S&P Global PMI',
  'canada/ca_trade_balance': '加 貿易収支',
  'canada/ca_us_export_dependence': '加 対米輸出依存度',
  'canada/ca_employment': '加 雇用者数',
  'canada/ca_unemployment_rate': '加 失業率',
  'canada/ca_weekly_average_salary': '加 週平均賃金',
  'canada/ca_building_permits': '加 建設許可件数',
  'canada/ca_housing_starts': '加 住宅着工件数',
  'canada/ca_new_housing_price_index': '加 新築住宅価格指数',
  'canada/ca_cpi': '加 CPI',
  'canada/ca_cpi_service_rent': '加 CPI（サービス・家賃）',
  'canada/ca_inflation_expectations': '加 期待インフレ率',
  'canada/ca_ippi': '加 産業製品価格指数（IPPI）',
  'canada/ca_boc_rate': '加 BOC政策金利',
  'canada/ca_settlement_balances_daily': '加 決済残高（日次）',
  // --- china ---
  'china/cn_retail_sales': '中 小売売上高',
  'china/cn_beijing_pm25': '中 北京PM2.5',
  'china/cn_caixin_pmi': '中 財新PMI',
  'china/cn_fixed_asset_investment': '中 固定資産投資',
  'china/cn_gdp_growth_rate': '中 GDP成長率',
  'china/cn_industrial_production': '中 鉱工業生産',
  'china/cn_pmi': '中 製造業PMI（国家統計局）',
  'china/cn_unemployment_rate': '中 失業率',
  'china/cn_commercial_residential_sales': '中 商品住宅販売',
  'china/cn_house_price_index': '中 住宅価格指数',
  'china/cn_cpi': '中 CPI',
  'china/cn_export_prices': '中 輸出物価',
  'china/cn_ppi': '中 PPI',
  'china/ch_cbs': '中 中央銀行バランスシート',
  'china/ch_m1_m2': '中 マネーサプライ（M1/M2）',
  'china/ch_reverse_repo_rate': '中 リバースレポ金利',
  'china/ch_rrr': '中 預金準備率（RRR）',
  'china/cn_aggregate_financing': '中 社会融資総量',
  'china/cn_capital_flows': '中 資本フロー',
  'china/cn_central_parity': '中 人民元基準値',
  'china/cn_fixing_repo_rate': '中 レポ金利（フィキシング）',
  'china/cn_forex_reserves': '中 外貨準備',
  'china/cn_gold_reserves_service': '中 金準備',
  'china/cn_government_bond_issuance': '中 国債発行',
  'china/cn_lpr_1y': '中 LPR（1年）',
  'china/cn_lpr_5y': '中 LPR（5年）',
  'china/cn_new_rmb_loans': '中 新規人民元建て融資',
  'china/cn_overseas_investor_flow': '中 海外投資家フロー',
  'china/cn_shibor': '中 SHIBOR',
  // --- eurozone ---
  'eurozone/eu_pmi': 'ユーロ圏 PMI',
  'eurozone/ecb_labour_cost_index': 'ユーロ圏 労働コスト指数',
  'eurozone/ecb_unemployment': 'ユーロ圏 失業率',
  'eurozone/ecb_mir_schedule': 'ユーロ圏 MIR金利（スケジュール）',
  'eurozone/eurex_ois_history': 'ユーロ圏 OIS（Eurex履歴）',
  // --- global ---
  'global/china_shanghai_container_freight_index': '上海コンテナ運賃指数（SCFI）',
  'global/global_epu': '世界経済政策不確実性指数（EPU）',
  'global/jpmorgan_global_manufacturing_pmi': 'JPモルガン世界製造業PMI',
  'global/kr_semiconductor_exports': '韓国 半導体輸出',
  'global/kr_semiconductor_history': '韓国 半導体輸出（履歴）',
  'global/south_korean_exports': '韓国 輸出',
  'global/taiwan_electrical_equipment_exports': '台湾 電子部品輸出',
  'global/us_daily_epu': '米 経済政策不確実性指数（日次）',
  'global/us_monthly_epu': '米 経済政策不確実性指数（月次）',
  'global/usd_fundamental_index': 'ドルファンダメンタル指数',
  // --- japan ---
  'japan/boj_calendar': '日銀会合カレンダー',
  'japan/retail_sales': '日 小売売上高',
  'japan/japan_balance_of_trade': '日 貿易収支',
  'japan/japan_capacity_utilization': '日 設備稼働率',
  'japan/japan_current_account': '日 経常収支',
  'japan/japan_current_account_gdp_ratio': '日 経常収支対GDP比',
  'japan/japan_gdp_gap': '日 GDPギャップ',
  'japan/japan_iip': '日 鉱工業生産指数（IIP）',
  'japan/japan_iip_forecast': '日 鉱工業生産予測指数',
  'japan/japan_iip_yoy': '日 鉱工業生産（前年比）',
  'japan/jp_pmi': '日 PMI',
  'japan/quarterly_gdp_qoq': '日 四半期GDP（前期比）',
  'japan/quarterly_gdp_qoq_annualized': '日 四半期GDP（前期比年率）',
  'japan/quarterly_gdp_yoy': '日 四半期GDP（前年比）',
  'japan/scheduled_wage_estat': '日 所定内給与（e-Stat）',
  'japan/shuntou_schedule': '日 春闘（スケジュール）',
  'japan/boj_outlook_report': '日銀 展望レポート',
  'japan/boj_policy_rate': '日銀 政策金利',
  'japan/jscc_ois_curve': '日 OISカーブ（JSCC）',
  'japan/boj_current_account_balance_schedule': '日銀 当座預金残高（スケジュール）',
  'japan/japan_cgpi': '日 企業物価指数（CGPI）',
  'japan/japan_cgpi_food_agriculture': '日 企業物価指数（食料・農産物）',
  'japan/japan_import_export_price': '日 輸出入物価指数',
  'japan/japan_pos_uvpi': '日 POS・単価物価指数（UVPI）',
  'japan/japan_price_di_spread': '日 物価DIスプレッド',
  'japan/japan_sppi': '日 企業向けサービス価格指数（SPPI）',
  'japan/japan_terms_of_trade': '日 交易条件',
  'japan/national_cpi_categories': '日 全国CPI（品目別）',
  // --- market: 為替 ---
  'market/audcad': 'AUD/CAD',
  'market/audchf': 'AUD/CHF',
  'market/audjpy': 'AUD/JPY',
  'market/audnzd': 'AUD/NZD',
  'market/audusd': 'AUD/USD',
  'market/cadchf': 'CAD/CHF',
  'market/cadjpy': 'CAD/JPY',
  'market/chfjpy': 'CHF/JPY',
  'market/euraud': 'EUR/AUD',
  'market/eurcad': 'EUR/CAD',
  'market/eurchf': 'EUR/CHF',
  'market/eurgbp': 'EUR/GBP',
  'market/eurjpy': 'EUR/JPY',
  'market/eurnzd': 'EUR/NZD',
  'market/eurusd': 'EUR/USD',
  'market/gbpaud': 'GBP/AUD',
  'market/gbpcad': 'GBP/CAD',
  'market/gbpchf': 'GBP/CHF',
  'market/gbpjpy': 'GBP/JPY',
  'market/gbpnzd': 'GBP/NZD',
  'market/gbpusd': 'GBP/USD',
  'market/nzdcad': 'NZD/CAD',
  'market/nzdchf': 'NZD/CHF',
  'market/nzdjpy': 'NZD/JPY',
  'market/nzdusd': 'NZD/USD',
  'market/usdcad': 'USD/CAD',
  'market/usdchf': 'USD/CHF',
  'market/usdjpy': 'USD/JPY',
  'market/dxy': 'ドル指数（DXY）',
  // --- market: 株価指数 ---
  'market/cac40': 'CAC40',
  'market/dax': 'DAX',
  'market/dow': 'ダウ平均',
  'market/eurostoxx50': 'ユーロストックス50',
  'market/ftse100': 'FTSE100',
  'market/hangseng': '香港ハンセン指数',
  'market/nasdaq': 'ナスダック総合',
  'market/nasdaq100': 'ナスダック100',
  'market/nikkei225': '日経225',
  'market/nikkei_yoy': '日経225（前年比）',
  'market/russell2000': 'ラッセル2000',
  'market/sox': 'フィラデルフィア半導体指数（SOX）',
  'market/sp500': 'S&P500',
  'market/topix': 'TOPIX',
  'market/stooq_daily__tpx': 'TOPIX（Stooq日次）',
  'market/tsmc': 'TSMC',
  'market/twii': '台湾加権指数',
  // --- market: 商品・エネルギー ---
  'market/aluminum': 'アルミニウム',
  'market/brent_oil': 'ブレント原油',
  'market/copper': '銅',
  'market/crude_oil': 'WTI原油',
  'market/crude_oil_yoy': 'WTI原油（前年比）',
  'market/gold': '金',
  'market/silver': '銀',
  'market/platinum': 'プラチナ',
  'market/natural_gas': '天然ガス',
  'market/natural_gas_yoy': '天然ガス（前年比）',
  'market/comex_gold_stock': 'COMEX金在庫',
  'market/comex_silver_stock': 'COMEX銀在庫',
  'market/china_gold_etf_balance_data': '中国 金ETF残高',
  'market/wgc_gold_etf_flows_usd': 'WGC 金ETFフロー（USD）',
  'market/wgc_gold_etf_holdings_ton': 'WGC 金ETF保有量（トン）',
  'market/north_america_rig_count': '北米リグ稼働数',
  'market/us_gasoline_inventories_refinery_utilization': '米 ガソリン在庫・製油所稼働率',
  'market/us_natural_gas_storage': '米 天然ガス貯蔵量',
  'market/us_natural_gas_trade': '米 天然ガス貿易',
  'market/us_shale_oil_production': '米 シェールオイル生産',
  'market/steo_previous_forecast': 'EIA STEO（前回予測）',
  'market/steo_ng_previous_forecast': 'EIA STEO 天然ガス（前回予測）',
  // --- market: 金利・ボラ・ポジション ---
  'market/us02y': '米2年債利回り',
  'market/us10y': '米10年債利回り',
  'market/us30y': '米30年債利回り',
  'market/vix': 'VIX',
  'market/naaim_exposure': 'NAAIMエクスポージャー指数',
  'market/nikkei225_options_atm_iv_history': '日経225オプション ATM IV（履歴）',
  'market/cftc_positioning_audusd': 'CFTCポジション（AUD/USD）',
  'market/cftc_positioning_brent': 'CFTCポジション（ブレント原油）',
  'market/cftc_positioning_copper': 'CFTCポジション（銅）',
  'market/cftc_positioning_crude_oil': 'CFTCポジション（WTI原油）',
  'market/cftc_positioning_dow': 'CFTCポジション（ダウ）',
  'market/cftc_positioning_eurgbp': 'CFTCポジション（EUR/GBP）',
  'market/cftc_positioning_eurjpy': 'CFTCポジション（EUR/JPY）',
  'market/cftc_positioning_eurusd': 'CFTCポジション（EUR/USD）',
  'market/cftc_positioning_gbpusd': 'CFTCポジション（GBP/USD）',
  'market/cftc_positioning_gold': 'CFTCポジション（金）',
  'market/cftc_positioning_nasdaq100': 'CFTCポジション（ナスダック100）',
  'market/cftc_positioning_natural_gas': 'CFTCポジション（天然ガス）',
  'market/cftc_positioning_nikkei225': 'CFTCポジション（日経225）',
  'market/cftc_positioning_nzdusd': 'CFTCポジション（NZD/USD）',
  'market/cftc_positioning_russell2000': 'CFTCポジション（ラッセル2000）',
  'market/cftc_positioning_silver': 'CFTCポジション（銀）',
  'market/cftc_positioning_sp500': 'CFTCポジション（S&P500）',
  'market/cftc_positioning_us02y': 'CFTCポジション（米2年債）',
  'market/cftc_positioning_us10y': 'CFTCポジション（米10年債）',
  'market/cftc_positioning_us30y': 'CFTCポジション（米30年債）',
  'market/cftc_positioning_usd_index': 'CFTCポジション（ドル指数）',
  'market/cftc_positioning_usdcad': 'CFTCポジション（USD/CAD）',
  'market/cftc_positioning_usdchf': 'CFTCポジション（USD/CHF）',
  'market/cftc_positioning_usdjpy': 'CFTCポジション（USD/JPY）',
  'market/cftc_positioning_vix': 'CFTCポジション（VIX）',
  // --- newzealand ---
  'newzealand/nz_anz_business_outlook_survey': 'NZ ANZ企業見通し調査',
  'newzealand/nz_nzier_business_conditions_index': 'NZ NZIER企業景況感指数',
  'newzealand/nz_retail_sales': 'NZ 小売売上高',
  'newzealand/nz_pci': 'NZ 総合景況指数（PCI）',
  'newzealand/nz_psi': 'NZ サービス業景況指数（PSI）',
  'newzealand/nz_labor_cost_index': 'NZ 労働コスト指数',
  'newzealand/nz_labour_force_participation': 'NZ 労働参加率',
  'newzealand/nz_number_of_employees': 'NZ 雇用者数',
  'newzealand/nz_unemployment_rate': 'NZ 失業率',
  'newzealand/nz_wages': 'NZ 賃金',
  'newzealand/nz_cpi': 'NZ CPI',
  'newzealand/nz_cpi_item': 'NZ CPI（品目別）',
  'newzealand/nz_inflation_expectations': 'NZ 期待インフレ率',
  'newzealand/nz_ppi': 'NZ PPI',
  'newzealand/nz_bank_balance_sheet': 'NZ 銀行バランスシート',
  'newzealand/nz_central_bank_balance_sheet': 'NZ 中央銀行バランスシート',
  'newzealand/nz_mps_forecast': 'NZ 金融政策声明（MPS）見通し',
  'newzealand/nz_rbnz_rate': 'NZ RBNZ政策金利',
  // --- switzerland ---
  'switzerland/snb_schedule': 'スイス SNB会合（スケジュール）',
  'switzerland/ch_retail_trade': 'スイス 小売売上高',
  'switzerland/kof_economic_barometer': 'スイス KOF景気先行指数',
  'switzerland/ch_housing_prices': 'スイス 住宅価格',
  'switzerland/ch_cpi': 'スイス CPI',
  'switzerland/ch_ppi': 'スイス PPI',
  'switzerland/ch_inflation_forecast': 'スイス インフレ見通し（SNB）',
  'switzerland/ch_snb_rate': 'スイス SNB政策金利',
  'switzerland/monetary_aggregate_m2': 'スイス マネーサプライM2',
  'switzerland/monetary_base': 'スイス マネタリーベース',
  'switzerland/snb_balance_sheet': 'スイス SNBバランスシート',
  'switzerland/snb_sight_deposits': 'スイス SNB要求払預金',
  'switzerland/swiss_holidays': 'スイス 祝日カレンダー',
  // --- uk ---
  'uk/brc_commentary': '英 BRC小売解説',
  'uk/brc_retail_sales': '英 BRC小売売上高',
  'uk/gfk_consumer_confidence': '英 GfK消費者信頼感',
  'uk/ons_retail_sales': '英 小売売上高（ONS）',
  'uk/boe_average_weekly_earnings': '英 平均週給（BOE見通し）',
  'uk/boe_cpi_components': '英 CPI項目別（BOE）',
  'uk/boe_cpi_contributions': '英 CPI寄与度（BOE）',
  'uk/boe_cpi_projections': '英 CPI見通し（BOE）',
  'uk/boe_gdp_forecast': '英 GDP見通し（BOE）',
  'uk/boe_import_prices': '英 輸入物価（BOE）',
  'uk/boe_inflation_expectations': '英 期待インフレ率（BOE）',
  'uk/boe_services_inflation': '英 サービスインフレ（BOE）',
  'uk/boe_unemployment_forecast': '英 失業率見通し（BOE）',
  'uk/boe_wage_growth': '英 賃金上昇率（BOE）',
  'uk/uk_pmi': '英 PMI',
  'uk/indeed_wage_tracker': '英 Indeed賃金トラッカー',
  'uk/ons_claimant_count': '英 失業給付申請件数',
  'uk/ons_economic_activity': '英 経済活動率',
  'uk/ons_employment': '英 雇用者数',
  'uk/ons_productivity': '英 労働生産性',
  'uk/ons_real_wages': '英 実質賃金',
  'uk/ons_unemployment': '英 失業率',
  'uk/ons_unit_labour_costs': '英 単位労働コスト',
  'uk/ons_wages': '英 賃金',
  'uk/halifax_imported_pdfs': '英 ハリファックス住宅価格（取込PDF）',
  'uk/halifax_schedule': '英 ハリファックス（スケジュール）',
  'uk/rics_imported_pdfs': '英 RICS住宅調査（取込PDF）',
  'uk/rics_residential_survey': '英 RICS住宅市場調査',
  'uk/rightmove_imported_pdfs': '英 ライトムーブ住宅価格（取込PDF）',
  'uk/boe_inflation_attitudes': '英 インフレ意識調査（BOE）',
  'uk/brc_shop_price': '英 BRC店頭価格指数',
  'uk/ons_cpih': '英 CPIH',
  'uk/ons_ppi': '英 PPI',
  'uk/ons_public_sector_net_borrowing': '英 公的部門純借入',
  // --- usa ---
  'usa/gdp_schedule': '米 GDP（スケジュール）',
  'usa/carts_price': '米 CARTS（価格）',
  'usa/carts_schedule': '米 CARTS（スケジュール）',
  'usa/carts_weekly': '米 シカゴ連銀小売指数CARTS（週次）',
  'usa/personal_consumption_expenditures_services': '米 個人消費支出（サービス）',
  'usa/retail_control': '米 小売売上高（コントロールグループ）',
  'usa/nfib_actual_compensation': '米 NFIB実際の賃金',
  'usa/nfib_optimism': '米 NFIB中小企業楽観指数',
  'usa/sp_pmi': '米 S&P Global PMI',
  'usa/cb_jobs_labor_differential': '米 CB雇用判断（差分）',
  'usa/chicago_fed_unemployment_rate_forecast': '米 シカゴ連銀 失業率予測',
  'usa/chicago_fed_unemployment_rate_forecast_schedule': '米 シカゴ連銀 失業率予測（スケジュール）',
  'usa/fullpart_time_employment': '米 フルタイム/パートタイム雇用',
  'usa/ner_pulse_schedule': '米 NERパルス週次雇用（スケジュール）',
  'usa/number_of_workers_by_place_of_birth': '米 出生地別就業者数',
  'usa/unemployment_rate': '米 失業率',
  'usa/us_average_weekly_working_hours': '米 週平均労働時間',
  'usa/fomc_schedule': '米 FOMC（スケジュール）',
  'usa/case_shiller': '米 ケース・シラー住宅価格指数',
  'usa/freddie_mac_mortgage_rates': '米 住宅ローン金利（フレディマック）',
  'usa/redfin_median_price': '米 住宅価格中央値（Redfin）',
  'usa/core_cpi': '米 コアCPI',
  'usa/core_pce_deflator': '米 コアPCEデフレーター',
  'usa/core_ppi': '米 コアPPI',
  'usa/ny_fed_sce_schedule': '米 NY連銀消費者期待調査（スケジュール）',
  'usa/rent_cpi': '米 家賃CPI',
  'usa/zillow_rent_index': '米 Zillow家賃指数',
  'usa/oas_hy_spread': '米 ハイイールドOASスプレッド',
  'usa/oas_hy_yield': '米 ハイイールド利回り',
  'usa/oas_ig_spread': '米 投資適格OASスプレッド',
  'usa/reserve_balances_wresbal': '米 準備預金残高（WRESBAL）',
}

// 日付付きアーカイブ等、辞書に列挙しきれない file 名のパターン対応。
// 末尾の日付サフィックス (figure2_20260318_metadata 等) を吸収する。
const PATTERN_NAME_RULES: Array<[RegExp, string]> = [
  [/^figure2_\d+_metadata$/, '米 FOMC経済見通し 図2（メタデータ）'],
  [/^table1_\d+_metadata$/, '米 FOMC Table1（メタデータ）'],
]

// slug (例: michigan_consumer_sentiment) を人が読めるラベルに整形
const prettifySlug = (slug: string) =>
  slug.replace(/_/g, ' ').replace(/\b\w/g, (s) => s.toUpperCase())

// file → 表示名。登録名→補完辞書→パターン規則→整形 slug の順で解決する。
const displayNameOf = (file: string): string => {
  const parts = file.split('/')
  const scope = parts[0]
  const base = parts[parts.length - 1].replace(/_cache\.json$/, '').replace(/\.json$/, '')
  const key = `${scope}/${base}`
  const hit = INDICATOR_NAME_MAP[key] ?? SUPPLEMENTAL_NAME_MAP[key]
  if (hit) return hit
  for (const [re, name] of PATTERN_NAME_RULES) if (re.test(base)) return name
  return prettifySlug(base)
}

// file パス先頭セグメント(国/マーケット)→ 表示名。未知はコードをそのまま使う。
const GROUP_LABELS: Record<string, string> = {
  usa: '米国',
  japan: '日本',
  eurozone: 'ユーロ圏',
  uk: '英国',
  china: '中国',
  australia: '豪州',
  canada: 'カナダ',
  switzerland: 'スイス',
  newzealand: 'NZ',
  korea: '韓国',
  taiwan: '台湾',
  market: 'マーケット',
  global: 'グローバル',
}

export default function AdminStalenessPage() {
  const { authFetch } = useAuth()
  const [items, setItems] = useState<StalenessItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [category, setCategory] = useState('STUCK')
  const [viewMode, setViewMode] = useState<ViewMode>('ALL')
  const [query, setQuery] = useState('')
  const [activeGroup, setActiveGroup] = useState('ALL')
  const [refreshing, setRefreshing] = useState<Record<string, boolean>>({})
  const [results, setResults] = useState<Record<string, RefreshResult>>({})

  const groupOf = (file: string) => file.split('/')[0] || 'other'

  // グループ(国/マーケット)ごとの件数とタブ定義
  const groupTabs = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const it of items) {
      const g = groupOf(it.file)
      counts[g] = (counts[g] ?? 0) + 1
    }
    const tabs = Object.keys(counts)
      .sort((a, b) => counts[b] - counts[a])
      .map((g) => ({ key: g, label: `${GROUP_LABELS[g] ?? g} (${counts[g]})` }))
    return [{ key: 'ALL', label: `すべて (${items.length})` }, ...tabs]
  }, [items])

  const visibleItems = useMemo(() => {
    const q = query.trim().toLowerCase()
    return items.filter(
      (it) =>
        (activeGroup === 'ALL' || groupOf(it.file) === activeGroup) &&
        // file パスと日本語の指標名どちらでも絞り込めるようにする
        (!q ||
          it.file.toLowerCase().includes(q) ||
          displayNameOf(it.file).toLowerCase().includes(q))
    )
  }, [items, activeGroup, query])

  // 表示モード切替の連打などで複数の走査リクエストが並ぶと、遅れて届いた
  // 古いモードの応答が新しいモードの結果を上書きする (全指標が遅延検知に
  // 戻って見える) ため、進行中リクエストの中断と古い応答の破棄を行う。
  const scanSeqRef = useRef(0)
  const scanAbortRef = useRef<AbortController | null>(null)

  const fetchStaleness = useCallback(
    async (fresh = false) => {
      scanAbortRef.current?.abort()
      const controller = new AbortController()
      scanAbortRef.current = controller
      const seq = ++scanSeqRef.current
      // グローバル fetch の 30s 上限を回避するため自前の長いタイムアウト signal を渡す
      const timer = setTimeout(() => controller.abort(), SCAN_TIMEOUT_MS)
      setLoading(true)
      setError(null)
      try {
        // 全指標モードは include_ok=true で OK 含む全キャッシュを取得 (category 絞り込み無し)。
        // 遅延検知モードは従来どおり category で絞り込む。
        // fresh=true (再走査ボタン) はサーバー側の短期スキャンキャッシュをバイパスする。
        const base =
          viewMode === 'ALL'
            ? '/api/admin/staleness?include_ok=true'
            : `/api/admin/staleness?category=${encodeURIComponent(category)}`
        const url = fresh ? `${base}&fresh=true` : base
        const res = await authFetch(url, { signal: controller.signal })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        if (seq !== scanSeqRef.current) return // 新しいリクエストに置換済み → 破棄
        setItems((data.items ?? []) as StalenessItem[])
        setActiveGroup('ALL')
      } catch (e) {
        if (seq !== scanSeqRef.current) return // 置換による中断はエラー扱いしない
        const aborted = e instanceof DOMException && e.name === 'AbortError'
        setError(
          aborted
            ? `走査がタイムアウトしました(${SCAN_TIMEOUT_MS / 1000}s)。再走査してください`
            : e instanceof Error
              ? e.message
              : '取得に失敗しました'
        )
      } finally {
        clearTimeout(timer)
        if (seq === scanSeqRef.current) setLoading(false)
      }
    },
    [authFetch, category, viewMode]
  )

  useEffect(() => {
    void fetchStaleness()
  }, [fetchStaleness])

  const onRefresh = useCallback(
    async (file: string) => {
      setRefreshing((p) => ({ ...p, [file]: true }))
      // グローバル fetch の 30s 上限を回避するため自前の長いタイムアウト signal を渡す
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), REFRESH_TIMEOUT_MS)
      try {
        const res = await authFetch('/api/admin/refresh', {
          method: 'POST',
          body: JSON.stringify({ file }),
          signal: controller.signal,
        })
        const data = (await res.json()) as RefreshResult & { detail?: string }
        if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
        setResults((p) => ({ ...p, [file]: data }))
        if (data.status === 'ADVANCED') {
          message.success(`${file}: ${data.before} → ${data.after} に更新`)
          setItems((prev) =>
            prev.map((it) =>
              it.file === file ? { ...it, latest: data.after ?? it.latest } : it
            )
          )
        } else if (data.status === 'SAME') {
          message.warning(`${file}: ソース未反映 (${data.after}) — 進みませんでした`)
        } else {
          message.error(`${file}: ${data.status}${data.error ? ` (${data.error})` : ''}`)
        }
      } catch (e) {
        const aborted = e instanceof DOMException && e.name === 'AbortError'
        message.error(
          aborted
            ? `${file}: タイムアウト(${REFRESH_TIMEOUT_MS / 1000}s)。サーバー側で継続中の場合あり、再走査で確認してください`
            : e instanceof Error
              ? e.message
              : '更新に失敗しました'
        )
      } finally {
        clearTimeout(timer)
        setRefreshing((p) => ({ ...p, [file]: false }))
      }
    },
    [authFetch]
  )

  const columns: ColumnsType<StalenessItem> = [
    {
      title: '指標名',
      dataIndex: 'file',
      key: 'file',
      sorter: (a, b) => displayNameOf(a.file).localeCompare(displayNameOf(b.file), 'ja'),
      render: (v: string) => (
        <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.3 }}>
          <Text style={{ color: colors.textPrimary, fontSize: 13 }}>{displayNameOf(v)}</Text>
          <Text style={{ color: colors.textSecondary, fontFamily: 'monospace', fontSize: 11 }}>
            {v}
          </Text>
        </div>
      ),
    },
    {
      title: '区分',
      dataIndex: 'category',
      key: 'category',
      width: 130,
      render: (v: string) => <Tag color={CATEGORY_COLORS[v] ?? 'default'}>{v}</Tag>,
    },
    {
      title: '最新',
      dataIndex: 'latest',
      key: 'latest',
      width: 110,
      render: (v: string | null) => (
        <Text style={{ color: colors.textSecondary }}>{v ?? '—'}</Text>
      ),
    },
    {
      title: '経過',
      dataIndex: 'days_since_latest',
      key: 'days_since_latest',
      width: 80,
      render: (v: number | null) => (
        <Text style={{ color: colors.textSecondary }}>{v != null ? `${v}日` : '—'}</Text>
      ),
    },
    {
      title: '頻度',
      dataIndex: 'freq',
      key: 'freq',
      width: 90,
      render: (v?: string) => <Text style={{ color: colors.textSecondary }}>{v ?? '—'}</Text>,
    },
    {
      title: '操作',
      key: 'action',
      width: 220,
      render: (_, record) => {
        const r = results[record.file]
        const refreshable = record.file.endsWith('.json')
        return (
          <Space>
            <Button
              size="small"
              type="primary"
              icon={<ThunderboltOutlined />}
              loading={!!refreshing[record.file]}
              disabled={!refreshable}
              title={refreshable ? '' : 'スクリーンショット等は専用ページから更新してください'}
              onClick={() => void onRefresh(record.file)}
            >
              今すぐ更新
            </Button>
            {r && (
              <Tag color={STATUS_COLORS[r.status] ?? 'default'}>
                {r.status === 'ADVANCED'
                  ? `${r.before}→${r.after}`
                  : r.status === 'SAME'
                    ? `未反映(${r.after})`
                    : r.status}
              </Tag>
            )}
          </Space>
        )
      },
    },
  ]

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: '0 auto' }}>
      <Card
        style={{ background: colors.bgSecondary, border: `1px solid ${colors.border}` }}
        styles={{ body: { padding: 24 } }}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 8,
            }}
          >
            <Title level={3} style={{ color: colors.textPrimary, margin: 0 }}>
              キャッシュ鮮度モニタ
            </Title>
            <Space wrap>
              <Segmented
                value={viewMode}
                onChange={(v) => setViewMode(v as ViewMode)}
                options={VIEW_OPTIONS}
              />
              {viewMode === 'FLAGGED' && (
                <Select
                  value={category}
                  onChange={setCategory}
                  options={CATEGORY_OPTIONS}
                  style={{ width: 200 }}
                />
              )}
              <Button icon={<ReloadOutlined />} onClick={() => void fetchStaleness(true)} loading={loading}>
                再走査
              </Button>
            </Space>
          </div>

          <Text style={{ color: colors.textSecondary }}>
            {viewMode === 'ALL' ? (
              <>
                全 JSON キャッシュを鮮度判定に関わらず列挙します（STUCK
                判定されない silent freeze も手動で更新可能）。
                <b style={{ color: colors.textPrimary }}> ADVANCED</b>=復旧、
                <b style={{ color: colors.textPrimary }}> SAME</b>=ソース未反映(待つべき)、
                それ以外は個別調査。
              </>
            ) : (
              <>
                遅延しているキャッシュを検出し、master 権限で個別に force_refresh します。
                <b style={{ color: colors.textPrimary }}> ADVANCED</b>=復旧、
                <b style={{ color: colors.textPrimary }}> SAME</b>=ソース未反映(待つべき)、
                それ以外は個別調査。
              </>
            )}
          </Text>

          <Input
            allowClear
            prefix={<SearchOutlined style={{ color: colors.textSecondary }} />}
            placeholder="指標名・ファイル名で絞り込み (例: 小売, retail, uk/inflation)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ maxWidth: 360 }}
          />

          {error && <Alert type="error" message={error} showIcon />}

          {items.length > 0 && (
            <Tabs
              activeKey={activeGroup}
              onChange={setActiveGroup}
              items={groupTabs}
              size="small"
            />
          )}

          <Table
            rowKey="file"
            columns={columns}
            dataSource={visibleItems}
            loading={loading}
            size="small"
            pagination={{
              defaultPageSize: 20,
              showSizeChanger: true,
              pageSizeOptions: [10, 20, 50, 100],
              hideOnSinglePage: true,
            }}
            locale={{
              emptyText: query.trim()
                ? '該当する指標がありません'
                : viewMode === 'ALL'
                  ? '指標がありません'
                  : '遅延キャッシュはありません',
            }}
          />
        </Space>
      </Card>
    </div>
  )
}
