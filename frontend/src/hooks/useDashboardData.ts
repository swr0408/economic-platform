/**
 * ダッシュボードデータ取得フック
 * 国・カテゴリ別のバッチAPIを呼び出し、React Queryでキャッシュ管理
 */
import { useQuery, UseQueryResult } from '@tanstack/react-query'
import { fetchWithTimeout } from '../utils/apiConfig'

// ダッシュボードAPIレスポンスの型
export interface DashboardResponse<T = Record<string, unknown>> {
  data: T
  cached: boolean
  last_updated: string | null
  response_time_ms: number
  country: string
  category: string
}

// 米国金融政策データの型
export interface USAPolicyData {
  policy_rate: PolicyRateItem[] | null
  term_premium: TermPremiumItem[] | null
  kw_term_premium: KWTermPremiumItem[] | null
  sofr_volatility: SOFRVolatilityData | null
  on_rrp: ONRRPData | null
  federal_budget: FederalBudgetData | null
  cbo_projections: CBOProjectionsData | null
  cre_loan_delinquency: CRELoanDelinquencyData | null
  frb_total_assets: FRBTotalAssetsItem[] | null
  reserve_balances: ReserveBalancesItem[] | null
  tga: TGAItem[] | null
  oas: OASData | null
  sep_dates: SEPDateItem[] | null
  fedwatch_screenshot_url: string | null
  next_fomc: NextFOMCInfo | null
}

export interface NextFOMCInfo {
  date: string
  label: string
  has_sep: boolean
}

export interface PolicyRateItem {
  date: string
  rate: number
}

export interface TermPremiumItem {
  date: string
  yield_10y: number | null
  term_premium: number | null
  expected_rate: number | null
}

export interface KWTermPremiumItem {
  date: string
  value: number
}

export interface SEPDateItem {
  date: string
  label: string
}

export interface FRBTotalAssetsItem {
  date: string
  value: number
}

export interface ReserveBalancesItem {
  date: string
  value: number
}

export interface TGAItem {
  date: string
  value: number
}

export interface OASItem {
  date: string
  value: number
}

export interface OASData {
  hy_spread: OASItem[]
  ig_spread: OASItem[]
  hy_yield: OASItem[]
}

export interface SOFRVolatilityItem {
  date: string
  sofr: number
  sofr_change: number
  volatility_20d: number | null
}

export interface ONRRPItem {
  date: string
  value: number
  value_raw: number
}

export interface ONRRPData {
  data: ONRRPItem[]
  latest: ONRRPItem | null
  metadata: {
    source?: string
    unit?: string
    description?: string
    operation_time?: string
  }
}

export interface SOFRVolatilityData {
  data: SOFRVolatilityItem[]
  latest: SOFRVolatilityItem | null
  metadata: {
    source?: string
    unit?: string
    rolling_window?: number
    description?: string
    release_time?: string
  }
}

export interface FederalBudgetItem {
  date: string
  receipts: number
  outlays: number
  deficit_surplus: number
  fiscal_year?: number
}

export interface FederalBudgetData {
  data: FederalBudgetItem[]
  latest: FederalBudgetItem | null
  metadata: {
    source?: string
    dataset?: string
    unit?: string
    description?: string
    release_schedule?: string
  }
  next_release?: { date: string; label: string } | null
}

export interface CBOProjectionItem {
  fiscal_year: number
  value: number
}

export interface CBOProjectionsData {
  data: {
    debt: CBOProjectionItem[]
    deficit: CBOProjectionItem[]
    revenue: CBOProjectionItem[]
    outlay: CBOProjectionItem[]
  }
  latest_baseline_date: string | null
  projection_years: number[]
  metadata: {
    source?: string
    dataset?: string
    unit?: string
    description?: string
    github_repo?: string
  }
}

// CREローン延滞率データの型
export interface CRELoanDelinquencyItem {
  date: string
  all_banks: number | null
  top_100: number | null
  other_banks: number | null
}

export interface CRELoanDelinquencyNextRelease {
  date: string
  label: string
}

export interface CRELoanDelinquencyData {
  data: CRELoanDelinquencyItem[]
  latest: CRELoanDelinquencyItem | null
  metadata: {
    source?: string
    description?: string
    unit?: string
    frequency?: string
    series?: Record<string, string>
  }
  next_release: CRELoanDelinquencyNextRelease | null
}

// 米国経済データの型
export interface USAEconomyData {
  gdp_growth_rate: GDPGrowthItem[] | null
  gdp_contributions: GDPContributionsData | null
  gdp_components_growth: GDPComponentsGrowthItem[] | null
  domestic_private_final_demand: DomesticPrivateFinalDemandItem[] | null
  potential_gdp: PotentialGDPData | null
  bank_lending: BankLendingData | null
  fci: FCIData | null
  nfci: NFCIData | null
  gdpnow: GDPNowData | null
  ism_manufacturing: ISMManufacturingData | null
  ism_components: ISMComponentsData | null
  ism_non_manufacturing: ISMNonManufacturingData | null
  ism_non_manufacturing_components: ISMNonManufacturingComponentsData | null
  sp_pmi: SPPMIData | null
  empire_state: EmpireStateData | null
  philadelphia_fed: PhiladelphiaFedData | null
  nfib: NFIBData | null
  nfib_capex: NFIBCapexData | null
  industrial_production: IndustrialProductionData | null
  capacity_utilization: CapacityUtilizationData | null
  durable_goods: DurableGoodsData | null
  us_flights: USFlightsData | null
  tsa_checkpoint: TSACheckpointData | null
  opentable: OpenTableData | null
  next_gdp_release: NextGDPRelease | null
  next_ism_non_manufacturing_release: NextISMNonManufacturingRelease | null
}

export interface GDPGrowthItem {
  date: string
  value: number
}

export interface GDPContributionsData {
  data: GDPContributionItem[]
  series_info: Record<string, GDPContributionSeriesInfo>
}

export interface GDPContributionItem {
  date: string
  quarter: string
  pce: number | null
  gpdi: number | null
  exports: number | null
  imports: number | null
  government: number | null
  total: number | null
}

export interface GDPContributionSeriesInfo {
  series_id: string
  name: string
  name_en: string
  color: string
}

export interface NextGDPRelease {
  date: string
  title: string
  estimate_type: string
  quarter: number
  year: number
}

// GDP項目別成長率データの型
export interface GDPComponentsGrowthItem {
  date: string
  quarter: string
  pce: number | null
  gpdi: number | null
  exports: number | null
  imports: number | null
  government: number | null
  gdp: number | null
}

// 国内民間最終需要（除くSW・PC投資 / 標準）データの型
export interface DomesticPrivateFinalDemandItem {
  date: string
  quarter: string
  ex_sw_pc: number | null  // 除くソフトウェア・コンピューター設備投資（独自推計、QoQ年率%）
  standard: number | null  // 国内民間最終需要（標準、QoQ年率%）
}

// 潜在成長率データの型
export interface PotentialGDPData {
  real: PotentialGDPItem[]
  nominal: PotentialGDPItem[]
}

export interface PotentialGDPItem {
  date: string
  value: number
}

// 銀行貸し出し態度データの型（SLOOS マルチシリーズ）
export interface BankLendingData {
  data: BankLendingItem[]
  latest: BankLendingItem | null
  next_release: BankLendingNextRelease | null
  series?: Record<string, BankLendingSeriesData>
}

export interface BankLendingSeriesData {
  data: BankLendingItem[]
  latest: BankLendingItem | null
  fred_id: string
  name_ja: string
  name_en: string
}

export interface BankLendingItem {
  date: string
  value: number
  [key: string]: string | number | null | undefined
}

export interface BankLendingNextRelease {
  date: string
  quarter: string
  title: string
}

// FCI-G（金融情勢指数）データの型
export interface FCIData {
  baseline: FCISeriesData
  oneyear: FCISeriesData
}

export interface FCISeriesData {
  data: FCIItem[]
  latest: FCIItem | null
}

export interface FCIItem {
  date: string
  value: number
  [key: string]: string | number | null | undefined
}

// シカゴ連銀金融環境指数（NFCI）データの型
export interface NFCIData {
  data: NFCIItem[]
  latest: NFCIItem | null
}

export interface NFCIItem {
  date: string
  value: number
  [key: string]: string | number | null | undefined
}

// GDPNow（リアルタイムGDP予測）データの型
export interface GDPNowData {
  data: GDPNowItem[]
  latest: GDPNowItem | null
}

export interface GDPNowItem {
  date: string
  value: number
  quarter: string
  [key: string]: string | number | null | undefined
}

// ISM製造業景況指数データの型
export interface ISMManufacturingData {
  data: ISMManufacturingItem[]
  latest: ISMManufacturingItem | null
  next_release: ISMManufacturingNextRelease | null
}

export interface ISMManufacturingItem {
  date: string
  value: number
  forecast: number | null
  previous: number | null
}

export interface ISMManufacturingNextRelease {
  date: string
  label: string
}

// ISM製造業サブインデックスデータの型
export interface ISMComponentsData {
  data: ISMComponentsItem[]
  latest: ISMComponentsItem | null
  next_release: ISMManufacturingNextRelease | null
}

export interface ISMComponentsItem {
  date: string
  new_orders: number | null
  production: number | null
  employment: number | null
  supplier_deliveries: number | null
  prices: number | null
  inventories: number | null
  order_inventory_balance: number | null
  order_inventory_balance_3ma: number | null
}

// ISM非製造業景況指数データの型
export interface ISMNonManufacturingData {
  data: ISMNonManufacturingItem[]
  latest: ISMNonManufacturingItem | null
  next_release: ISMNonManufacturingNextRelease | null
  last_updated: string | null
}

export interface ISMNonManufacturingItem {
  date: string
  value: number
}

export interface ISMNonManufacturingNextRelease {
  date: string
  label: string
}

// ISM非製造業サブインデックスデータの型
export interface ISMNonManufacturingComponentsData {
  data: ISMNonManufacturingComponentsItem[]
  latest: ISMNonManufacturingComponentsItem | null
  next_release: ISMNonManufacturingNextRelease | null
  last_updated: string | null
}

export interface ISMNonManufacturingComponentsItem {
  date: string
  new_orders: number | null
  business_activity: number | null
  employment: number | null
  supplier_deliveries: number | null
  prices: number | null
  inventories: number | null
  order_inventory_balance: number | null
  order_inventory_balance_3ma: number | null
}

// S&P Global PMIデータの型（製造業/サービス業/総合）
export interface SPPMIData {
  manufacturing: SPPMISeriesData | null
  services: SPPMISeriesData | null
  composite: SPPMISeriesData | null
  next_release: SPPMINextRelease | null
  last_updated: string | null
}

export interface SPPMISeriesData {
  data: SPPMIItem[]
  latest: SPPMIItem | null
}

export interface SPPMIItem {
  date: string
  value: number
  forecast?: number | null
  previous?: number | null
}

export interface SPPMINextRelease {
  date: string
  label?: string
}

// 次回ISM非製造業発表情報の型
export interface NextISMNonManufacturingRelease {
  date: string
  date_str: string
  title: string
  target_month: string
  type: string
}

// NY連銀製造業景気指数データの型
export interface EmpireStateData {
  data: EmpireStateItem[]
  latest: EmpireStateItem | null
  next_release: EmpireStateNextRelease | null
  last_updated: string | null
}

export interface EmpireStateItem {
  date: string
  current: number | null
  future: number | null
}

export interface EmpireStateNextRelease {
  date: string
  label: string
}

// フィラデルフィア連銀製造業景気指数データの型
export interface PhiladelphiaFedData {
  data: PhiladelphiaFedItem[]
  latest: PhiladelphiaFedItem | null
  next_release: PhiladelphiaFedNextRelease | null
  series_config: Record<string, PhiladelphiaFedSeriesConfig> | null
  last_updated: string | null
}

export interface PhiladelphiaFedItem {
  date: string
  general_activity_current: number | null
  general_activity_future: number | null
  new_orders_current: number | null
  new_orders_future: number | null
  prices_paid_current: number | null
  prices_paid_future: number | null
  employment_current: number | null
  employment_future: number | null
  capex_current: number | null
  capex_future: number | null
}

export interface PhiladelphiaFedNextRelease {
  date: string
  label: string
}

export interface PhiladelphiaFedSeriesConfig {
  name: string
  color: string
  group: string
}

// NFIB中小企業楽観指数データの型
export interface NFIBData {
  data: NFIBItem[]
  latest: NFIBItem | null
  next_release: NFIBNextRelease | null
  last_updated: string | null
}

export interface NFIBItem {
  date: string
  value: number
  [key: string]: string | number | null | undefined
}

export interface NFIBNextRelease {
  date: string
  label: string
}

// NFIB中小企業設備投資計画データの型
export interface NFIBCapexData {
  data: NFIBCapexItem[]
  latest: NFIBCapexItem | null
  next_release: NFIBNextRelease | null
  last_updated: string | null
}

export interface NFIBCapexItem {
  date: string
  value: number
  [key: string]: string | number | null | undefined
}

// 鉱工業生産データの型
export interface IndustrialProductionData {
  data: IndustrialProductionItem[]
  latest: IndustrialProductionItem | null
  next_release: IndustrialProductionNextRelease | null
  last_updated: string | null
}

export interface IndustrialProductionItem {
  date: string
  value: number
  mom: number | null  // 前月比
  yoy: number | null  // 前年比
  [key: string]: string | number | null | undefined
}

export interface IndustrialProductionNextRelease {
  date: string
  label: string
}

// 設備稼働率データの型
export interface CapacityUtilizationData {
  data: CapacityUtilizationItem[]
  latest: CapacityUtilizationItem | null
  next_release: CapacityUtilizationNextRelease | null
  last_updated: string | null
}

export interface CapacityUtilizationItem {
  date: string
  value: number
  [key: string]: string | number | null | undefined
}

export interface CapacityUtilizationNextRelease {
  date: string
  label: string
}

// 耐久財受注データの型
export interface DurableGoodsData {
  data: DurableGoodsItem[]
  latest: DurableGoodsItem | null
  next_release: DurableGoodsNextRelease | null
  last_updated: string | null
}

export interface DurableGoodsItem {
  date: string
  value: number           // 耐久財新規受注（百万ドル）
  ex_transport: number | null  // 輸送除外
  core_orders: number | null   // 非国防資本財受注（除く航空機）
  core_shipments: number | null // 非国防資本財出荷（除く航空機）
  mom: number | null      // 前月比
  yoy: number | null      // 前年比
  ex_transport_mom: number | null  // 輸送除外の前月比
  ex_transport_yoy: number | null  // 輸送除外の前年比
  core_orders_mom: number | null   // 非国防資本財受注の前月比
  core_orders_yoy: number | null   // 非国防資本財受注の前年比
  core_shipments_mom: number | null // 非国防資本財出荷の前月比
  core_shipments_yoy: number | null // 非国防資本財出荷の前年比
  [key: string]: string | number | null | undefined
}

export interface DurableGoodsNextRelease {
  date: string
  label: string
}

// 米国航空機便数データの型
export interface USFlightsData {
  image_url: string | null
  latest: USFlightsLatest | null
  next_update: USFlightsNextUpdate | null
  last_updated: string | null
  source: string | null
}

export interface USFlightsLatest {
  date: string
  description: string
}

export interface USFlightsNextUpdate {
  date: string
  time_jst: string
  label: string
}

// TSA Checkpoint旅客数データの型
export interface TSACheckpointData {
  data: TSACheckpointItem[]
  latest: TSACheckpointLatest | null
  last_updated: string | null
}

export interface TSACheckpointItem {
  date: string
  value: number        // 旅客数
  ma30: number | null  // 30日移動平均
}

export interface TSACheckpointLatest {
  date: string
  value: number
  ma30: number | null
  current_month_avg: number | null  // 当月平均
  prev_month_avg: number | null     // 前月平均
  mom_change: number | null         // 前月比
  mom_pct: number | null            // 前月比（%）
  yoy_change: number | null         // 前年同月比
  yoy_pct: number | null            // 前年同月比（%）
}

// OpenTableレストラン予約件数データの型
export interface OpenTableData {
  image_url: string | null    // スクリーンショットURL（後方互換）
  images: OpenTableImage[] | null  // 複数画像（タブ切替用）
  latest: OpenTableLatest | null
  last_updated: string | null
  source: string | null
}

export interface OpenTableImage {
  label: string       // タブ表示名
  url: string         // 画像URL
}

export interface OpenTableLatest {
  date: string
  description: string
}

// 米国消費データの型
export interface USAConsumerData {
  retail_sales: RetailSalesData | null
  retail_control: RetailControlData | null
  advance_real_retail_sales: AdvanceRealRetailSalesData | null
  carts: CartsData | null
  affinity_spend: AffinitySpendData | null
  visa_spending: VisaSpendingData | null
  total_vehicle_sales: TotalVehicleSalesData | null
  redbook: RedbookData | null
  consumer_credit: ConsumerCreditData | null
  delinquency_rate: DelinquencyRateData | null
  cb_consumer_confidence: CBConsumerConfidenceData | null
  cb_jobs_labor: CBJobsLaborData | null
  unemployment_rate: UnemploymentRateData | null  // CB雇用機会業況判断チャート用
  michigan_consumer_sentiment: MichiganConsumerSentimentData | null
  personal_saving_rate: PersonalSavingRateData | null
  personal_income: PersonalIncomeData | null
  disposable_income: DisposableIncomeData | null
  pce: PCEData | null
  personal_consumption_expenditures_services: PersonalConsumptionExpendituresServicesData | null
}

// ミシガン大学消費者信頼感指数データの型
// 毎月第2金曜日（速報版）/ 最終金曜日（確報版） 10:00 ET発表
export interface MichiganConsumerSentimentData {
  data: MichiganConsumerSentimentItem[]
  components: MichiganConsumerSentimentComponentItem[]
  latest: MichiganConsumerSentimentItem | null
  latest_components: MichiganConsumerSentimentComponentItem | null
  next_release: MichiganConsumerSentimentNextRelease | null
  last_updated: string | null
}

export interface MichiganConsumerSentimentItem {
  date: string         // YYYY-MM-DD形式
  value: number        // 消費者信頼感指数（ICS_ALL）
}

export interface MichiganConsumerSentimentComponentItem {
  date: string         // YYYY-MM-DD形式
  current: number      // 現況指数（ICC）
  expected: number | null  // 期待指数（ICE）
}

export interface MichiganConsumerSentimentNextRelease {
  date: string
  label: string
}

// 家計貯蓄率データの型（FRED PSAVERT）
// 毎月月末 8:30 ET発表（BEA Personal Income）
export interface PersonalSavingRateData {
  data: PersonalSavingRateItem[]
  latest: PersonalSavingRateItem | null
  next_release: PersonalSavingRateNextRelease | null
  last_updated: string | null
}

export interface PersonalSavingRateItem {
  date: string         // YYYY-MM-DD形式
  value: number        // 貯蓄率（%）
}

export interface PersonalSavingRateNextRelease {
  date: string
  label: string
}

// 個人所得データの型（FRED PI/RPI）
// 毎月月末 8:30 ET発表（BEA Personal Income）
export interface PersonalIncomeData {
  nominal: PersonalIncomeSeriesData | null
  real: PersonalIncomeSeriesData | null
  next_release: PersonalIncomeNextRelease | null
  last_updated: string | null
}

export interface PersonalIncomeSeriesData {
  data: PersonalIncomeItem[]
  latest: PersonalIncomeItem | null
}

export interface PersonalIncomeItem {
  date: string         // YYYY-MM-DD形式
  mom: number | null   // 前月比（%）
  yoy: number | null   // 前年比（%）
}

export interface PersonalIncomeNextRelease {
  date: string
  label: string
}

// 可処分所得データの型（FRED DSPI/DSPIC96）
// 毎月月末 8:30 ET発表（BEA Personal Income）
export interface DisposableIncomeData {
  nominal: DisposableIncomeSeriesData | null
  real: DisposableIncomeSeriesData | null
  next_release: DisposableIncomeNextRelease | null
  last_updated: string | null
}

export interface DisposableIncomeSeriesData {
  data: DisposableIncomeItem[]
  latest: DisposableIncomeItem | null
}

export interface DisposableIncomeItem {
  date: string         // YYYY-MM-DD形式
  mom: number | null   // 前月比（%）
  yoy: number | null   // 前年比（%）
}

export interface DisposableIncomeNextRelease {
  date: string
  label: string
}

// 個人消費支出データの型（FRED PCE/PCEC96）
// 毎月月末 8:30 ET発表（BEA Personal Income）
export interface PCEData {
  nominal: PCESeriesData | null
  real: PCESeriesData | null
  next_release: PCENextRelease | null
  last_updated: string | null
}

export interface PCESeriesData {
  data: PCEItem[]
  latest: PCEItem | null
}

export interface PCEItem {
  date: string         // YYYY-MM-DD形式
  mom: number | null   // 前月比（%）
  yoy: number | null   // 前年比（%）
}

export interface PCENextRelease {
  date: string
  label: string
}

// CB消費者信頼感指数データの型（DB/FMP）
// 毎月最終火曜日 10:00 ET発表
export interface CBConsumerConfidenceData {
  data: CBConsumerConfidenceItem[]
  latest: CBConsumerConfidenceItem | null
  next_release: CBConsumerConfidenceNextRelease | null
  last_updated: string | null
}

export interface CBConsumerConfidenceItem {
  date: string         // YYYY-MM-DD形式
  value: number        // 消費者信頼感指数
}

export interface CBConsumerConfidenceNextRelease {
  date: string
  label: string
}

// CB雇用機会業況判断データの型（Conference Board）
// 毎月最終火曜日 10:00 ET発表（CB消費者信頼感と同時発表）
export interface CBJobsLaborData {
  data: CBJobsLaborItem[]
  latest: CBJobsLaborItem | null
  next_release: CBJobsLaborNextRelease | null
  last_updated: string | null
}

export interface CBJobsLaborItem {
  date: string         // YYYY-MM形式
  plentiful: number    // 仕事が「豊富」と回答した割合（%）
  hard: number         // 仕事が「見つけにくい」と回答した割合（%）
  differential: number // 差分（Plentiful - Hard）
}

export interface CBJobsLaborNextRelease {
  date: string
  label: string
}

// クレジットカードローン延滞率データの型（FRB Charge-Off and Delinquency Rates）
// 四半期データを2月・5月・8月・11月に発表
export interface DelinquencyRateData {
  data: DelinquencyRateItem[]
  latest: DelinquencyRateItem | null
  next_release: DelinquencyRateNextRelease | null
  last_updated: string | null
}

export interface DelinquencyRateItem {
  date: string         // YYYY-MM-DD形式（四半期末）
  value: number        // 延滞率（%）
  qoq: number | null   // 前四半期比（ポイント差）
  yoy: number | null   // 前年比（ポイント差）
}

export interface DelinquencyRateNextRelease {
  date: string
  label: string
}

// Redbook小売売上高指数データの型
export interface RedbookData {
  data: RedbookItem[]
  latest: RedbookItem | null
  next_release: RedbookNextRelease | null
  last_updated: string | null
}

export interface RedbookItem {
  date: string
  value: number  // 前年比（%）
}

export interface RedbookNextRelease {
  date: string
  label: string
}

// クレジットカードローン残高データの型（FRB H.8）
// 週次データを月平均に集計
export interface ConsumerCreditData {
  data: ConsumerCreditItem[]
  latest: ConsumerCreditItem | null
  next_release: ConsumerCreditNextRelease | null
  last_updated: string | null
}

export interface ConsumerCreditItem {
  date: string         // YYYY-MM-01形式（月次）
  value: number        // 月平均残高（10億ドル）
  mom: number | null   // 前月比（%）
  yoy: number | null   // 前年比（%）
}

export interface ConsumerCreditNextRelease {
  date: string
  label: string
}

// Visa支出モメンタム指数データの型
export interface VisaSpendingData {
  data: VisaSpendingItem[]
  latest: VisaSpendingItem | null
  next_release: VisaSpendingNextRelease | null
  last_updated: string | null
}

export interface VisaSpendingItem {
  date: string
  value: number        // 指数値
  mom: number | null   // 前月比（ポイント差）
  yoy: number | null   // 前年比（ポイント差）
}

export interface VisaSpendingNextRelease {
  date: string
  label: string
}

// 自動車販売台数データの型
export interface TotalVehicleSalesData {
  data: TotalVehicleSalesItem[]
  latest: TotalVehicleSalesItem | null
  next_release: TotalVehicleSalesNextRelease | null
  last_updated: string | null
}

export interface TotalVehicleSalesItem {
  date: string
  value: number        // 販売台数（百万台、季節調整済み年率換算）
  mom: number | null   // 前月比（%）
  yoy: number | null   // 前年比（%）
}

export interface TotalVehicleSalesNextRelease {
  date: string
  label: string
}

// Affinityカード支出データの型
export interface AffinitySpendData {
  data: AffinitySpendItem[]
  latest: AffinitySpendItem | null
  last_commit: AffinitySpendLastCommit | null
  last_updated: string | null
}

export interface AffinitySpendItem {
  date: string
  value: number        // カード支出（2020年1月比、%）
}

export interface AffinitySpendLastCommit {
  sha: string
  date: string
  message: string
}

// シカゴ連銀小売指数（CARTS）データの型
export interface CartsData {
  weekly: CartsWeeklyData
  price: CartsPriceData
  next_release: CartsNextRelease | null
  last_updated: string | null
}

export interface CartsWeeklyData {
  data: CartsWeeklyItem[]
  latest: CartsWeeklyItem | null
}

export interface CartsWeeklyItem {
  date: string
  nominal: number | null    // 名目値（百万ドル）
  real: number | null       // 実質値（2017年基準、百万ドル）
  mom: number | null        // 前週比（%）
  yoy: number | null        // 前年比（%）
}

export interface CartsPriceData {
  data: CartsPriceItem[]
  latest: CartsPriceItem | null
}

export interface CartsPriceItem {
  date: string
  bea: number | null        // BEA 前年比（%）
  cpi: number | null        // CPI 前年比（%）
  carts_nowcast: number | null  // CARTS Nowcast 前年比（%）
}

export interface CartsNextRelease {
  date: string
  label: string
}

// 小売売上高データの型
export interface RetailSalesData {
  data: RetailSalesItem[]
  latest: RetailSalesItem | null
  next_release: RetailSalesNextRelease | null
  last_updated: string | null
}

export interface RetailSalesItem {
  date: string
  value: number              // 小売売上高（百万ドル）
  ex_auto: number | null     // 自動車除く
  mom: number | null         // 前月比
  yoy: number | null         // 前年比
  ex_auto_mom: number | null // 自動車除く前月比
  ex_auto_yoy: number | null // 自動車除く前年比
  [key: string]: string | number | null | undefined
}

export interface RetailSalesNextRelease {
  date: string
  label: string
}

// コントロールグループデータの型（DB/FMP）
export interface RetailControlData {
  data: RetailControlItem[]
  latest: RetailControlItem | null
  last_updated: string | null
}

export interface RetailControlItem {
  date: string              // 対象月（YYYY-MM-01形式、小売売上高と同じ）
  release_date: string      // 発表日
  mom: number               // 前月比（%）
  forecast: number | null   // 予想値
  revised: number | null    // 改定値
}

// Advance Real Retail and Food Services Sales データの型（FRED RRSFS）
// 小売売上高発表と同日（毎月中旬 8:30 ET）
export interface AdvanceRealRetailSalesData {
  data: AdvanceRealRetailSalesItem[]
  latest: AdvanceRealRetailSalesItem | null
  next_release: AdvanceRealRetailSalesNextRelease | null
  last_updated: string | null
}

export interface AdvanceRealRetailSalesItem {
  date: string         // YYYY-MM-DD形式
  value: number        // 実質小売売上高（百万ドル、2017年基準）
  mom: number | null   // 前月比（%）
  yoy: number | null   // 前年比（%）
}

export interface AdvanceRealRetailSalesNextRelease {
  date: string
  label: string
}

// 個人消費支出：サービス（FRED PCES）。前月比%・前年比%を表示
export interface PersonalConsumptionExpendituresServicesData {
  data: PersonalConsumptionExpendituresServicesItem[]
  latest: PersonalConsumptionExpendituresServicesItem | null
  next_release: PersonalConsumptionExpendituresServicesNextRelease | null
  last_updated: string | null
}

export interface PersonalConsumptionExpendituresServicesItem {
  date: string         // YYYY-MM-DD形式
  value: number        // 個人消費支出：サービス（10億ドル、SAAR）
  mom: number | null   // 前月比（%）
  yoy: number | null   // 前年比（%）
}

export interface PersonalConsumptionExpendituresServicesNextRelease {
  date: string
  datetime_jst?: string
  time_jst?: string
  label?: string
  estimate?: number | null
}

/**
 * ダッシュボードデータを取得するAPI関数
 */
async function fetchDashboardData<T>(
  country: string,
  category: string
): Promise<DashboardResponse<T>> {
  const response = await fetchWithTimeout(
    `/api/${country}/${category}/dashboard`,
    undefined,
    30_000,  // 30秒タイムアウト
  )

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || `Failed to fetch dashboard: ${response.status}`)
  }

  return response.json()
}

/**
 * 軽量指標のみを取得するAPI関数
 */
async function fetchDashboardLightData<T>(
  country: string,
  category: string
): Promise<DashboardResponse<T>> {
  const response = await fetchWithTimeout(
    `/api/${country}/${category}/dashboard/light`,
    undefined,
    15_000,  // 15秒タイムアウト（軽量指標は速いはず）
  )

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || `Failed to fetch light dashboard: ${response.status}`)
  }

  return response.json()
}

/**
 * 重い指標のみを取得するAPI関数
 */
async function fetchDashboardHeavyData<T>(
  country: string,
  category: string
): Promise<DashboardResponse<T>> {
  const response = await fetchWithTimeout(
    `/api/${country}/${category}/dashboard/heavy`,
    undefined,
    60_000,  // 60秒タイムアウト（スクショ等の重い処理を許容）
  )

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || `Failed to fetch heavy dashboard: ${response.status}`)
  }

  return response.json()
}

/**
 * 汎用ダッシュボードデータフック
 *
 * @param country - 国コード（例: "usa", "japan"）
 * @param category - カテゴリコード（例: "policy", "economy"）
 * @param options - React Query オプション
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useDashboardData('usa', 'policy')
 * ```
 */
export function useDashboardData<T = Record<string, unknown>>(
  country: string,
  category: string,
  options?: {
    enabled?: boolean
    staleTime?: number
    refetchOnMount?: boolean
  }
): UseQueryResult<DashboardResponse<T>, Error> {
  return useQuery({
    queryKey: ['dashboard', country, category],
    queryFn: () => fetchDashboardData<T>(country, category),
    enabled: options?.enabled ?? true,
    staleTime: options?.staleTime ?? 24 * 60 * 60 * 1000, // 1日
    refetchOnMount: options?.refetchOnMount ?? false,
  })
}

/**
 * 米国金融政策ダッシュボード専用フック
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useUSAPolicyDashboard()
 *
 * if (data) {
 *   console.log(data.data.policy_rate) // 政策金利データ
 *   console.log(data.data.term_premium) // タームプレミアムデータ
 * }
 * ```
 */
export function useUSAPolicyDashboard(): UseQueryResult<DashboardResponse<USAPolicyData>, Error> {
  return useDashboardData<USAPolicyData>('usa', 'policy')
}

/**
 * 米国経済ダッシュボード専用フック
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useUSAEconomyDashboard()
 *
 * if (data) {
 *   console.log(data.data.gdp_growth_rate) // GDP成長率データ
 *   console.log(data.data.next_gdp_release) // 次回GDP発表情報
 * }
 * ```
 */
export function useUSAEconomyDashboard(): UseQueryResult<DashboardResponse<USAEconomyData>, Error> {
  return useDashboardData<USAEconomyData>('usa', 'economy')
}

/**
 * 米国経済ダッシュボード（プログレッシブレンダリング用）
 *
 * 軽量指標を先に取得し、重い指標は遅延ロードする。
 * 初期表示を高速化するためのフック。
 *
 * @example
 * ```tsx
 * const { lightData, heavyData, isLightLoading, isHeavyLoading, mergedData } = useUSAEconomyDashboardProgressive()
 *
 * // 軽量指標は即座に表示
 * if (lightData) {
 *   console.log(lightData.data.gdp_growth_rate)
 * }
 *
 * // 重い指標は遅延ロード
 * if (heavyData) {
 *   console.log(heavyData.data.nfib)
 * }
 *
 * // マージされたデータ（両方揃った場合）
 * if (mergedData) {
 *   console.log(mergedData.gdp_growth_rate, mergedData.nfib)
 * }
 * ```
 */
export function useUSAEconomyDashboardProgressive() {
  // 軽量指標を取得（優先度高）
  const lightQuery = useQuery({
    queryKey: ['dashboard', 'usa', 'economy', 'light'],
    queryFn: () => fetchDashboardLightData<Partial<USAEconomyData>>('usa', 'economy'),
    staleTime: 24 * 60 * 60 * 1000, // 1日
    refetchOnMount: false,
  })

  // 重い指標を取得（軽量指標取得後に開始）
  const heavyQuery = useQuery({
    queryKey: ['dashboard', 'usa', 'economy', 'heavy'],
    queryFn: () => fetchDashboardHeavyData<Partial<USAEconomyData>>('usa', 'economy'),
    staleTime: 24 * 60 * 60 * 1000, // 1日
    refetchOnMount: false,
    // 軽量指標の取得完了後に開始（オプション：即座に開始したい場合はコメントアウト）
    // enabled: lightQuery.isSuccess,
  })

  // データをマージ
  const mergedData: USAEconomyData | null = lightQuery.data?.data && heavyQuery.data?.data
    ? { ...lightQuery.data.data, ...heavyQuery.data.data } as USAEconomyData
    : lightQuery.data?.data
      ? lightQuery.data.data as USAEconomyData
      : null

  return {
    lightData: lightQuery.data,
    heavyData: heavyQuery.data,
    isLightLoading: lightQuery.isLoading,
    isHeavyLoading: heavyQuery.isLoading,
    isLoading: lightQuery.isLoading, // 軽量指標のローディング状態を主として使用
    lightError: lightQuery.error,
    heavyError: heavyQuery.error,
    mergedData,
    // 全データが揃ったかどうか
    isComplete: lightQuery.isSuccess && heavyQuery.isSuccess,
  }
}

/**
 * 米国消費ダッシュボード専用フック
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useUSAConsumerDashboard()
 *
 * if (data) {
 *   console.log(data.data.retail_sales) // 小売売上高データ
 * }
 * ```
 */
export function useUSAConsumerDashboard(): UseQueryResult<DashboardResponse<USAConsumerData>, Error> {
  return useDashboardData<USAConsumerData>('usa', 'consumer')
}

// =============================================================================
// 米国雇用データの型
// =============================================================================

// 失業率データの型（FRED UNRATE / U6RATE）
// 毎月第1金曜日 8:30 ET発表（BLS Employment Situation）
export interface UnemploymentRateData {
  data: UnemploymentRateItem[]
  latest: UnemploymentRateItem | null
  next_release: UnemploymentRateNextRelease | null
  last_updated: string | null
}

export interface UnemploymentRateItem {
  date: string         // YYYY-MM-DD形式
  unrate: number       // 失業率（U-3）%
  u6rate: number | null  // 広義の失業率（U-6）%
}

export interface UnemploymentRateNextRelease {
  date: string
  label: string
}

// NAIRU / 失業率データの型（FRED NROU = 自然失業率, UNRATE = 実際の失業率）
// NROUはCBO推計の四半期データ（四半期始月のみ値を持つ）、UNRATEは月次
export interface NairuData {
  data: NairuItem[]
  latest: NairuItem | null
  next_release: UnemploymentRateNextRelease | null
  last_updated: string | null
}

export interface NairuItem {
  date: string              // YYYY-MM-DD形式
  unrate: number            // 実際の失業率（U-3）%
  nairu: number | null      // 自然失業率 / NAIRU（NROU）% ※四半期始月のみ
}

// 失業率内訳データの型（FRED LNS13023653, LNS13025699, LNS13023705, LNS13023557, LNS13023569）
// 毎月第1金曜日 8:30 ET発表（BLS Employment Situation）
export interface UnemploymentByReasonData {
  data: UnemploymentByReasonItem[]
  latest: UnemploymentByReasonItem | null
  series_config: Record<string, UnemploymentByReasonSeriesConfig>
  next_release: UnemploymentByReasonNextRelease | null
  last_updated: string | null
}

export interface UnemploymentByReasonItem {
  date: string         // YYYY-MM-DD形式
  layoff: number | null         // レイオフ（千人）
  other_losers: number | null   // レイオフ以外の失業者（千人）
  leavers: number | null        // 自発的離職者（千人）
  reentrants: number | null     // 再参入者（千人）
  new_entrants: number | null   // 新規参入者（千人）
}

export interface UnemploymentByReasonSeriesConfig {
  series_id: string
  name: string
  name_en: string
  color: string
}

export interface UnemploymentByReasonNextRelease {
  date: string
  label: string
}

// 非農業部門雇用者数データの型（FRED PAYEMS / CE16OV）
// 毎月第1金曜日 8:30 ET発表（BLS Employment Situation）
export interface NonfarmPayrollsData {
  data: NonfarmPayrollsItem[]
  latest: NonfarmPayrollsItem | null
  series_config: Record<string, NonfarmPayrollsSeriesConfig>
  next_release: NonfarmPayrollsNextRelease | null
  last_updated: string | null
}

export interface NonfarmPayrollsItem {
  date: string         // YYYY-MM-DD形式
  nonfarm: number | null    // 非農業部門雇用者数（千人）
  civilian: number | null   // 民間雇用者数（千人）
}

export interface NonfarmPayrollsSeriesConfig {
  series_id: string
  name: string
  name_en: string
  color: string
}

export interface NonfarmPayrollsNextRelease {
  date: string
  label: string
}

// フルタイム/パートタイム雇用者数データの型（FRED LNS12500000 / LNS12600000）
// 毎月第1金曜日 8:30 ET発表（BLS Employment Situation）
export interface FullPartTimeEmploymentData {
  data: FullPartTimeEmploymentItem[]
  latest: FullPartTimeEmploymentItem | null
  series_config: Record<string, FullPartTimeEmploymentSeriesConfig>
  next_release: FullPartTimeEmploymentNextRelease | null
  last_updated: string | null
}

export interface FullPartTimeEmploymentItem {
  date: string         // YYYY-MM-DD形式
  fulltime: number | null    // フルタイム雇用者数（千人）
  parttime: number | null    // パートタイム雇用者数（千人）
}

export interface FullPartTimeEmploymentSeriesConfig {
  series_id: string
  name: string
  name_en: string
  color: string
}

export interface FullPartTimeEmploymentNextRelease {
  date: string
  label: string
}

// 出生地別労働者数データの型（FRED LNU01073395 / LNU01073413 / LNU02073395 / LNU02073413）
// 毎月第1金曜日 8:30 ET発表（BLS Employment Situation / NFPと同タイミング）
export interface NumberOfWorkersByPlaceOfBirthData {
  data: NumberOfWorkersByPlaceOfBirthItem[]
  latest: NumberOfWorkersByPlaceOfBirthItem | null
  series_config: Record<string, NumberOfWorkersByPlaceOfBirthSeriesConfig>
  next_release: NumberOfWorkersByPlaceOfBirthNextRelease | null
  last_updated: string | null
}

export interface NumberOfWorkersByPlaceOfBirthItem {
  date: string                          // YYYY-MM-DD形式
  labor_force_native: number | null     // 労働力人口（国内生まれ、千人）
  labor_force_foreign: number | null    // 労働力人口（海外生まれ、千人）
  employment_native: number | null      // 雇用者数（国内生まれ、千人）
  employment_foreign: number | null     // 雇用者数（海外生まれ、千人）
}

export interface NumberOfWorkersByPlaceOfBirthSeriesConfig {
  series_id: string
  name: string
  name_en: string
  color: string
}

export interface NumberOfWorkersByPlaceOfBirthNextRelease {
  date: string
  label: string
}

// 複数の仕事を持つ人 / 経済的理由によるパートタイムデータの型（FRED LNS12026619 / LNS12032194）
// 毎月第1金曜日 8:30 ET発表（BLS Employment Situation）
export interface MultipleJobsPartTimeData {
  data: MultipleJobsPartTimeItem[]
  latest: MultipleJobsPartTimeItem | null
  series_config: Record<string, MultipleJobsPartTimeSeriesConfig>
  next_release: MultipleJobsPartTimeNextRelease | null
  last_updated: string | null
}

export interface MultipleJobsPartTimeItem {
  date: string              // YYYY-MM-DD形式
  multiple_jobs: number | null    // 複数の仕事を持つ人（千人）
  parttime_econ: number | null    // 経済的理由によるパートタイム（千人）
}

export interface MultipleJobsPartTimeSeriesConfig {
  series_id: string
  name: string
  name_en: string
  color: string
}

export interface MultipleJobsPartTimeNextRelease {
  date: string
  label: string
}

// JOLTS求人 / Indeed求人件数データの型（FRED JTSJOL / IHLIDXUS）
// JOLTSは毎月上旬 10:00 ET発表
export interface JoltsIndeedData {
  data: JoltsIndeedItem[]
  latest: JoltsIndeedItem | null
  series_config: Record<string, JoltsIndeedSeriesConfig>
  next_release: JoltsIndeedNextRelease | null
  last_updated: string | null
}

export interface JoltsIndeedItem {
  date: string              // YYYY-MM-DD形式
  jolts: number | null      // JOLTS求人件数（千人）
  indeed: number | null     // Indeed求人件数指数（2020年2月1日=100）
}

export interface JoltsIndeedSeriesConfig {
  series_id: string
  name: string
  name_en: string
  color: string
}

export interface JoltsIndeedNextRelease {
  date: string
  label: string
}

// JOLTS採用数 / 解雇数データの型（FRED JTSHIL / JTSLDL）
// JOLTSは毎月上旬 10:00 ET発表
export interface JoltsHiresLayoffsData {
  data: JoltsHiresLayoffsItem[]
  latest: JoltsHiresLayoffsItem | null
  series_config: Record<string, JoltsHiresLayoffsSeriesConfig>
  next_release: JoltsHiresLayoffsNextRelease | null
  last_updated: string | null
}

export interface JoltsHiresLayoffsItem {
  date: string              // YYYY-MM-DD形式
  hires: number | null      // JOLTS採用数（千人）
  layoffs: number | null    // JOLTS解雇数（千人）
}

export interface JoltsHiresLayoffsSeriesConfig {
  series_id: string
  name: string
  name_en: string
  color: string
}

export interface JoltsHiresLayoffsNextRelease {
  date: string
  label: string
}

// 求人倍率データの型（FRED JTSJOL / UNEMPLOY）
// JOLTSまたはEmpsit発表時に更新
export interface JobOpeningsPerUnemployedData {
  data: JobOpeningsPerUnemployedItem[]
  latest: JobOpeningsPerUnemployedItem | null
  next_release: JobOpeningsPerUnemployedNextRelease | null
  last_updated: string | null
}

export interface JobOpeningsPerUnemployedItem {
  date: string              // YYYY-MM-DD形式
  value: number             // 求人倍率（JOLTS / UNEMPLOY）
  jolts: number             // JOLTS求人件数（千人）
  unemployed: number        // 失業者数（千人）
}

export interface JobOpeningsPerUnemployedNextRelease {
  jolts: { date: string; label: string } | null
  empsit: { date: string; label: string } | null
}

// ADP雇用者数データの型（FRED ADPMNUSNERSA）
// 毎月第1水曜日 8:15 ET発表
export interface ADPEmploymentData {
  data: ADPEmploymentItem[]
  latest: ADPEmploymentItem | null
  next_release: ADPEmploymentNextRelease | null
  last_updated: string | null
}

export interface ADPEmploymentItem {
  date: string         // YYYY-MM-DD形式
  value: number        // 雇用者数（千人）
  mom: number | null   // 前月比（千人）
  yoy: number | null   // 前年比（%）
}

export interface ADPEmploymentNextRelease {
  date: string
  label: string
}

// NER Pulse（週次雇用変動）データの型
// 毎週火曜日 8:15 ET発表（月次NER発表週を除く）
export interface NERPulseData {
  data: NERPulseItem[]
  latest: NERPulseItem | null
  next_release: NERPulseNextRelease | null
  last_updated: string | null
}

export interface NERPulseItem {
  week_ending: string  // YYYY-MM-DD形式
  change: number       // 週次増減（人）
}

export interface NERPulseNextRelease {
  date: string
  label: string
}

// 新規失業保険申請件数データの型
// 毎週木曜日 8:30 ET発表（祝日による例外日あり）
export interface InitialClaimsData {
  data: InitialClaimsItem[]
  latest: InitialClaimsItem | null
  next_release: InitialClaimsNextRelease | null
  last_updated: string | null
}

export interface InitialClaimsItem {
  date: string         // YYYY-MM-DD形式
  icsa: number         // 新規申請件数（件）
  ic4wsa: number | null // 4週移動平均（件）
}

export interface InitialClaimsNextRelease {
  date: string
  label: string
}

// 継続失業保険申請件数データの型
// 毎週木曜日 8:30 ET発表（新規失業保険申請件数と同時発表）
export interface ContinuedClaimsData {
  data: ContinuedClaimsItem[]
  latest: ContinuedClaimsItem | null
  next_release: ContinuedClaimsNextRelease | null
  last_updated: string | null
}

export interface ContinuedClaimsItem {
  date: string         // YYYY-MM-DD形式
  ccsa: number         // 継続申請件数（件）
  cc4wsa: number | null // 4週移動平均（件）
}

export interface ContinuedClaimsNextRelease {
  date: string
  label: string
}

// Challenger人員削減数データの型
// 毎月第1木曜日 7:30 ET発表
export interface ChallengerJobCutsData {
  data: ChallengerJobCutsItem[]
  latest: ChallengerJobCutsItem | null
  next_release: ChallengerJobCutsNextRelease | null
  last_updated: string | null
}

export interface ChallengerJobCutsItem {
  date: string         // YYYY-MM-DD形式（発表日）
  value: number        // 人員削減数（人）
  mom: number | null   // 前月比（%）
  yoy: number | null   // 前年比（%）
}

export interface ChallengerJobCutsNextRelease {
  date: string
  label: string
}

// 平均時給/自発的離職率データの型（FRED CES0500000003 / JTSQUR）
// 毎月第1金曜日 8:30 ET発表（BLS Employment Situation）
export interface AverageHourlyEarningsData {
  data: AverageHourlyEarningsItem[]
  latest: AverageHourlyEarningsItem | null
  next_release: AverageHourlyEarningsNextRelease | null
  last_updated: string | null
}

export interface AverageHourlyEarningsItem {
  date: string         // YYYY-MM-DD形式
  yoy: number | null   // 前年比（%）
  mom: number | null   // 前月比（%）
  quits_rate: number | null  // 自発的離職率（%）
}

export interface AverageHourlyEarningsNextRelease {
  date: string
  label: string
}

// 労働参加率データの型（FRED CIVPART）
// 毎月第1金曜日 8:30 ET発表（BLS Employment Situation）
export interface LaborForceParticipationData {
  data: LaborForceParticipationItem[]
  latest: LaborForceParticipationItem | null
  next_release: LaborForceParticipationNextRelease | null
  last_updated: string | null
}

export interface LaborForceParticipationItem {
  date: string        // YYYY-MM-DD形式
  value: number | null // 労働参加率（%）
}

export interface LaborForceParticipationNextRelease {
  date: string
  label: string
}

// ADP賃金上昇率中央値データの型（ADP Pay Insights）
// 毎月第1水曜日 8:15 ET発表（ADP雇用者数と同時）
export interface ADPWageGrowthData {
  data: ADPWageGrowthItem[]
  latest: ADPWageGrowthItem | null
  next_release: ADPWageGrowthNextRelease | null
  last_updated: string | null
}

export interface ADPWageGrowthItem {
  date: string          // YYYY-MM-DD形式
  job_changer: number   // 転職者の賃金上昇率中央値（%）
  job_stayer: number    // 在職者の賃金上昇率中央値（%）
}

export interface ADPWageGrowthNextRelease {
  date: string
  label: string
}

// アトランタ連銀賃金トラッカーデータの型（Atlanta Fed）
// 毎月第2金曜日頃発表
export interface AtlantaFedWageData {
  data: AtlantaFedWageItem[]
  latest: AtlantaFedWageItem | null
  next_release: AtlantaFedWageNextRelease | null
  last_updated: string | null
}

export interface AtlantaFedWageItem {
  date: string            // YYYY-MM-DD形式
  overall: number | null  // 全体の賃金上昇率（12ヶ月移動中央値）
  fulltime: number | null // フルタイム労働者
  paid_hourly: number | null // 時給労働者
  job_stayer: number | null  // 在職者
  job_switcher: number | null // 転職者
}

export interface AtlantaFedWageNextRelease {
  date: string
  label: string
}

// Indeed賃金トラッカーデータの型（Indeed Hiring Lab）
// 毎月15日以降発表
export interface IndeedWageTrackerData {
  data: IndeedWageTrackerItem[]
  latest: IndeedWageTrackerItem | null
  next_release: IndeedWageTrackerNextRelease | null
  last_updated: string | null
}

export interface IndeedWageTrackerItem {
  date: string            // YYYY-MM-01形式
  value: number           // 求人掲載賃金の前年同月比成長率（%）
  ma3: number | null      // 3ヶ月移動平均（%）
}

export interface IndeedWageTrackerNextRelease {
  date: string
  label: string
}

// PCEデフレーター飲食宿泊・娯楽データの型（BEA NIPA T20404）
// Personal Income and Outlays（毎月末 8:30 AM ET発表）
export interface PCEFoodRecreationData {
  data: PCEFoodRecreationItem[]
  latest: PCEFoodRecreationItem | null
  next_release: PCEFoodRecreationNextRelease | null
  last_updated: string | null
}

export interface PCEFoodRecreationItem {
  date: string                      // YYYY-MM-01形式
  food_services_yoy: number | null  // 飲食宿泊 前年比（%）
  recreation_yoy: number | null     // 娯楽 前年比（%）
  avg_hourly_earnings_yoy: number | null  // 平均時給 前年比（%）
}

export interface PCEFoodRecreationNextRelease {
  date: string
  label: string
}

// 雇用コスト指数データの型（FRED ECIALLCIV）
// 四半期ごと発表（1月、4月、7月、10月）8:30 ET
export interface EmploymentCostIndexData {
  data: EmploymentCostIndexItem[]
  latest: EmploymentCostIndexItem | null
  next_release: EmploymentCostIndexNextRelease | null
  last_updated: string | null
}

export interface EmploymentCostIndexItem {
  date: string          // YYYY-MM-DD形式（四半期末日）
  pch: number           // 前期比（%）
}

export interface EmploymentCostIndexNextRelease {
  date: string
  label: string
}

// 単位労働コスト・労働生産性データの型（FRED PRS85006112/PRS85006092）
// 四半期ごと発表（2月、3月、5月、6月、8月、9月、11月、12月）8:30 ET
export interface UnitLaborCostData {
  data: UnitLaborCostItem[]
  latest: UnitLaborCostItem | null
  next_release: UnitLaborCostNextRelease | null
  last_updated: string | null
}

export interface UnitLaborCostItem {
  date: string            // YYYY-MM-DD形式（四半期末日）
  ulc_pch: number | null  // 単位労働コスト前期比（%）
  productivity_pch: number | null  // 労働生産性前期比（%）
}

export interface UnitLaborCostNextRelease {
  date: string
  label: string
}

// NFIB中小企業人件費・雇用計画データの型（NFIB PDF Report）
// 毎月第2火曜日 6:00 ET発表
export interface NFIBCompensationData {
  data: NFIBCompensationItem[]
  latest: NFIBCompensationItem | null
  next_release: NFIBCompensationNextRelease | null
  last_updated: string | null
}

export interface NFIBCompensationItem {
  date: string                        // YYYY-MM-DD形式
  compensation_plans?: number         // 人件費計画（%）
  hiring_plans?: number               // 雇用計画（%）
}

export interface NFIBCompensationNextRelease {
  date: string
  label: string
}

// NFIB労働報酬・失業率データの型（NFIB PDF + FRED UNRATE）
// NFIB: 毎月第2火曜日 6:00 ET発表 / UNRATE: 毎月第1金曜日 8:30 ET発表
export interface NFIBCompensationUnemploymentData {
  data: NFIBCompensationUnemploymentItem[]
  latest: NFIBCompensationUnemploymentItem | null
  next_release: NFIBCompensationUnemploymentNextRelease | null
  last_updated: string | null
}

export interface NFIBCompensationUnemploymentItem {
  date: string                        // YYYY-MM-DD形式
  actual_compensation?: number        // 実際の人件費変更（%）
  unemployment_rate?: number          // 失業率（%）
}

export interface NFIBCompensationUnemploymentNextRelease {
  date: string
  label: string
}

// 平均残業時間データの型（FRED AWOTMAN）
// 毎月第1金曜日 8:30 ET発表（BLS Employment Situation）
export interface OvertimeHoursData {
  data: OvertimeHoursItem[]
  latest: OvertimeHoursItem | null
  next_release: OvertimeHoursNextRelease | null
  last_updated: string | null
}

export interface OvertimeHoursItem {
  date: string        // YYYY-MM-DD形式
  value: number       // 平均週間残業時間（時間）
}

export interface OvertimeHoursNextRelease {
  date: string
  label: string
}

// 平均週労働時間データの型（FRED AWHAETP / AWHNONAG / AWHMAN）
// 毎月第1金曜日 8:30 ET発表（BLS Employment Situation）
export interface UsAverageWeeklyWorkingHoursData {
  data: UsAverageWeeklyWorkingHoursItem[]
  latest: UsAverageWeeklyWorkingHoursItem | null
  series_config: Record<string, { series_id: string; name: string; color: string }>
  next_release: UsAverageWeeklyWorkingHoursNextRelease | null
  last_updated: string | null
}

export interface UsAverageWeeklyWorkingHoursItem {
  date: string           // YYYY-MM-DD形式
  awhaetp: number        // 民間全体・全従業員の平均週労働時間（時間）
  awhnonag?: number      // 民間全体・生産労働者の平均週労働時間（時間）
  awhman?: number        // 製造業・生産労働者の平均週労働時間（時間）
}

export interface UsAverageWeeklyWorkingHoursNextRelease {
  date: string
  label: string
}

// サームルールデータの型（FRED: SAHMCURRENT）
// 毎月第1金曜日 8:30 ET発表（雇用統計と同時）
export interface SahmRuleData {
  data: SahmRuleItem[]
  latest: SahmRuleItem | null
  next_release: SahmRuleNextRelease | null
  last_updated: string | null
}

export interface SahmRuleItem {
  date: string        // YYYY-MM-DD形式
  value: number       // サームルール指標値（%）
}

export interface SahmRuleNextRelease {
  date: string
  label: string
}

// 臨時就業者数データの型（FRED TEMPHELPS）
// 毎月第1金曜日 8:30 ET発表（BLS Employment Situation）
export interface TemporaryHelpServicesData {
  data: TemporaryHelpServicesItem[]
  latest: TemporaryHelpServicesItem | null
  next_release: TemporaryHelpServicesNextRelease | null
  last_updated: string | null
}

export interface TemporaryHelpServicesItem {
  date: string        // YYYY-MM-DD形式
  value: number       // 臨時就業者数（千人）
}

export interface TemporaryHelpServicesNextRelease {
  date: string
  label: string
}

// シカゴ連銀失業率予測データの型
export interface ChicagoFedUnemploymentRateForecastItem {
  date: string
  // Rates（Sheet 1）
  layoffs_other_seps?: number | null
  hiring_rate_uw?: number | null
  fcr?: number | null
  s_cps?: number | null
  f_cps?: number | null
  // Forecast（Sheet 2）
  forecast16a?: number | null
  forecast25a?: number | null
  forecast50a?: number | null
  forecast75a?: number | null
  forecast84a?: number | null
  forecast16f?: number | null
  forecast25f?: number | null
  forecast50f?: number | null
  forecast75f?: number | null
  forecast84f?: number | null
  forecast16r?: number | null
  forecast25r?: number | null
  forecast50r?: number | null
  forecast75r?: number | null
  forecast84r?: number | null
  official_u3?: number | null
}

export interface ChicagoFedUnemploymentRateForecastNextRelease {
  date: string
  datetime_jst?: string
  time_jst?: string
  label?: string
  type?: string
}

export interface ChicagoFedUnemploymentRateForecastProbabilityBuckets {
  bucket_neg_03_or_lower: number | null
  bucket_neg_02: number | null
  bucket_neg_01: number | null
  bucket_no_change: number | null
  bucket_pos_01: number | null
  bucket_pos_02: number | null
  bucket_pos_03_or_higher: number | null
}

export interface ChicagoFedUnemploymentRateForecastRelativeOdds {
  increase: number | null
  decrease: number | null
  net: number | null
}

export interface ChicagoFedUnemploymentRateForecastProbabilityItem {
  date: string
  release: string
  buckets: ChicagoFedUnemploymentRateForecastProbabilityBuckets
  relative_odds: ChicagoFedUnemploymentRateForecastRelativeOdds
  baseline_ur?: number | null
  bucket_ur_levels?: Partial<Record<keyof ChicagoFedUnemploymentRateForecastProbabilityBuckets, number | null>>
}

export interface ChicagoFedUnemploymentRateForecastData {
  data: ChicagoFedUnemploymentRateForecastItem[]
  rates_data: ChicagoFedUnemploymentRateForecastItem[]
  forecast_data: ChicagoFedUnemploymentRateForecastItem[]
  probability_data: ChicagoFedUnemploymentRateForecastProbabilityItem[]
  latest: ChicagoFedUnemploymentRateForecastItem | null
  latest_rates: ChicagoFedUnemploymentRateForecastItem | null
  latest_probability: ChicagoFedUnemploymentRateForecastProbabilityItem | null
  metadata: Record<string, unknown>
  next_release: ChicagoFedUnemploymentRateForecastNextRelease | null
  last_updated: string | null
}

// 米国雇用ダッシュボードデータの型
export interface USAEmploymentData {
  unemployment_rate: UnemploymentRateData | null
  unemployment_by_reason: UnemploymentByReasonData | null
  chicago_fed_unemployment_rate_forecast: ChicagoFedUnemploymentRateForecastData | null
  nairu: NairuData | null
  cb_jobs_labor: CBJobsLaborData | null
  nonfarm_payrolls: NonfarmPayrollsData | null
  fullpart_time_employment: FullPartTimeEmploymentData | null
  multiple_jobs_parttime: MultipleJobsPartTimeData | null
  jolts_indeed: JoltsIndeedData | null
  jolts_hires_layoffs: JoltsHiresLayoffsData | null
  job_openings_per_unemployed: JobOpeningsPerUnemployedData | null
  adp_employment: ADPEmploymentData | null
  ner_pulse: NERPulseData | null
  initial_claims: InitialClaimsData | null
  continued_claims: ContinuedClaimsData | null
  challenger_job_cuts: ChallengerJobCutsData | null
  average_hourly_earnings: AverageHourlyEarningsData | null
  labor_force_participation: LaborForceParticipationData | null
  adp_wage_growth: ADPWageGrowthData | null
  atlanta_fed_wage: AtlantaFedWageData | null
  indeed_wage_tracker: IndeedWageTrackerData | null
  pce_food_recreation: PCEFoodRecreationData | null
  employment_cost_index: EmploymentCostIndexData | null
  unit_labor_cost: UnitLaborCostData | null
  nfib_compensation: NFIBCompensationData | null
  nfib_compensation_unemployment: NFIBCompensationUnemploymentData | null
  overtime_hours: OvertimeHoursData | null
  us_average_weekly_working_hours: UsAverageWeeklyWorkingHoursData | null
  sahm_rule: SahmRuleData | null
  temporary_help_services: TemporaryHelpServicesData | null
  number_of_workers_by_place_of_birth: NumberOfWorkersByPlaceOfBirthData | null
}

/**
 * 米国雇用ダッシュボード専用フック
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useUSAEmploymentDashboard()
 *
 * if (data) {
 *   console.log(data.data.unemployment_rate) // 失業率データ
 * }
 * ```
 */
export function useUSAEmploymentDashboard(): UseQueryResult<DashboardResponse<USAEmploymentData>, Error> {
  return useDashboardData<USAEmploymentData>('usa', 'employment')
}

// =============================================================================
// 米国物価データの型
// =============================================================================

// CPI（消費者物価指数）データの型（FRED: CPIAUCSL）
// 毎月10-15日頃 8:30 ET発表
export interface CPIData {
  data: CPIItem[]
  latest: CPIItem | null
  next_release: CPINextRelease | null
  last_updated: string | null
}

export interface CPIItem {
  date: string         // YYYY-MM-DD形式
  value: number        // YoY（メイン値）
  yoy: number | null   // 前年比（%）
  mom: number | null   // 前月比（%）
  index: number | null // 指数値（FRED原データ）
  annualized_3m: number | null  // 3か月年率（%）
  annualized_6m: number | null  // 6か月年率（%）
}

export interface CPINextRelease {
  date: string
  label: string
}

// コアCPI（食品・エネルギー除く）データの型（FRED: CPILFESL）
// 毎月10-15日頃 8:30 ET発表（CPIと同時）
export interface CoreCPIData {
  data: CoreCPIItem[]
  latest: CoreCPIItem | null
  next_release: CoreCPINextRelease | null
  last_updated: string | null
}

export interface CoreCPIItem {
  date: string         // YYYY-MM-DD形式
  value: number        // YoY（メイン値）
  yoy: number | null   // 前年比（%）
  mom: number | null   // 前月比（%）
  index: number | null // 指数値（FRED原データ）
  annualized_3m: number | null  // 3か月年率（%）
  annualized_6m: number | null  // 6か月年率（%）
}

export interface CoreCPINextRelease {
  date: string
  label: string
}

// CPI項目別データの型（FRED）
// 毎月10-15日頃 8:30 ET発表（CPIと同時）
export interface CPICategoriesData {
  data: CPICategoriesItem[]
  latest: CPICategoriesItem | null
  next_release: CPICategoriesNextRelease | null
  last_updated: string | null
}

export interface CPICategoriesItem {
  date: string           // YYYY-MM-DD形式
  food: number | null    // 食品（前年比%）
  energy: number | null  // エネルギー（前年比%）
  core_goods: number | null     // コア財（前年比%）
  core_services: number | null  // コアサービス（前年比%）
  shelter: number | null // 住居費（前年比%）
}

export interface CPICategoriesNextRelease {
  date: string
  label: string
}

// 住宅関連指標データの型（FRED）
// Zillow住宅価値指数、ケースシラー住宅価格指数、家賃CPIの前年比
export interface HousingIndicatorsData {
  data: {
    zillow: HousingIndicatorItem[]
    case_shiller: HousingIndicatorItem[]
    rent_cpi: HousingIndicatorItem[]
  }
  latest: {
    zillow: HousingIndicatorItem | null
    case_shiller: HousingIndicatorItem | null
    rent_cpi: HousingIndicatorItem | null
  }
  last_updated: string | null
}

export interface HousingIndicatorItem {
  date: string       // YYYY-MM-DD形式
  yoy: number        // 前年比（%）
}

// Zillow家賃指数データの型（Zillow CSV直接取得）
// 毎月15日前後に更新
export interface ZillowRentIndexData {
  data: ZillowRentIndexItem[]
  latest: ZillowRentIndexItem | null
  last_updated: string | null
}

export interface ZillowRentIndexItem {
  date: string       // YYYY-MM-DD形式
  yoy: number        // 前年比（%）
}

// 家賃CPIデータの型（FRED: CUUR0000SAH1）
// 毎月CPI発表と同時
export interface RentCPIData {
  data: RentCPIItem[]
  latest: RentCPIItem | null
  last_updated: string | null
}

export interface RentCPIItem {
  date: string       // YYYY-MM-DD形式
  yoy: number        // 前年比（%）
}

// PCEデフレーターデータの型（FRED: PCEPI）
// 毎月20-31日頃 8:30 ET発表
export interface PCEDeflatorNextRelease {
  date: string
  label: string
}

export interface PCEDeflatorData {
  data: PCEDeflatorItem[]
  latest: PCEDeflatorItem | null
  next_release: PCEDeflatorNextRelease | null
  last_updated: string | null
}

export interface PCEDeflatorItem {
  date: string        // YYYY-MM-DD形式
  value: number       // 前年比（%）メイン値
  yoy: number         // 前年比（%）
  mom: number | null  // 前月比（%）
  index: number       // 指数値
  annualized_3m: number | null  // 3か月年率（%）
  annualized_6m: number | null  // 6か月年率（%）
}

// コアPCEデフレーターデータの型（FRED: PCEPILFE）
// 毎月20-31日頃 8:30 ET発表（PCEと同時）
export interface CorePCEDeflatorData {
  data: CorePCEDeflatorItem[]
  latest: CorePCEDeflatorItem | null
  next_release: PCEDeflatorNextRelease | null
  last_updated: string | null
}

export interface CorePCEDeflatorItem {
  date: string        // YYYY-MM-DD形式
  value: number       // 前年比（%）メイン値
  yoy: number         // 前年比（%）
  mom: number | null  // 前月比（%）
  index: number       // 指数値
  annualized_3m: number | null  // 3か月年率（%）
  annualized_6m: number | null  // 6か月年率（%）
}

// 生産者物価指数（PPI）データの型（FRED: PPIFIS）
// 毎月9-17日頃 8:30 ET発表
export interface PPINextRelease {
  date: string
  label: string
}

export interface PPIData {
  data: PPIItem[]
  latest: PPIItem | null
  next_release: PPINextRelease | null
  last_updated: string | null
}

export interface PPIItem {
  date: string        // YYYY-MM-DD形式
  value: number       // 前年比（%）メイン値
  yoy: number         // 前年比（%）
  mom: number | null  // 前月比（%）
  index: number       // 指数値
}

// コアPPIデータの型（FRED: PPIFES）
// 毎月9-17日頃 8:30 ET発表（PPIと同時）
export interface CorePPIData {
  data: CorePPIItem[]
  latest: CorePPIItem | null
  next_release: PPINextRelease | null
  last_updated: string | null
}

export interface CorePPIItem {
  date: string        // YYYY-MM-DD形式
  value: number       // 前年比（%）メイン値
  yoy: number         // 前年比（%）
  mom: number | null  // 前月比（%）
  index: number       // 指数値
}

// PPI項目別データの型（BLS API）
// 毎月9-17日頃 8:30 ET発表（PPIと同時）
export interface PPICategoriesData {
  categories: PPICategoryItem[]
  next_release: PPINextRelease | null
  last_updated: string | null
}

export interface PPICategoryItem {
  key: string            // カテゴリキー（例: "airline_passenger"）
  series_id: string      // BLSシリーズID（例: "WPSFD42213"）
  name: string           // 日本語名（例: "航空会社乗客サービス"）
  name_en: string        // 英語名（例: "Airline Passenger Services"）
  data: PPICategoryDataPoint[]
  latest: PPICategoryDataPoint | null
}

export interface PPICategoryDataPoint {
  date: string           // YYYY-MM-DD形式
  value: number          // 指数値
  yoy: number | null     // 前年比（%）
  mom: number | null     // 前月比（%）
}

// グローバルサプライチェーン圧力指数（GSCPI）
// NY連銀のExcelファイルから取得
// 毎月第4営業日頃 10:00 ET発表
export interface GSCPIData {
  data: GSCPIItem[]
  latest: GSCPIItem | null
  next_release: GSCPINextRelease | null
  last_updated: string | null
}

export interface GSCPIItem {
  date: string           // YYYY-MM-DD形式
  value: number          // GSCPI値（0が平均、正の値は圧力上昇）
}

export interface GSCPINextRelease {
  date: string
  time: string
}

// インフレーションナウキャスティングデータの型
// Cleveland FedのInflation Nowcastingデータ（毎営業日10:00 ET頃更新）
export interface InflationNowcastingData {
  monthly_mom: InflationNowcastingItem[]
  monthly_yoy: InflationNowcastingItem[]
  last_updated: string | null
}

export interface InflationNowcastingItem {
  date: string            // "Month Year" 形式（例: "October 2025"）or "YYYY:Q1" 形式
  cpi: number | null      // CPI予測値
  core_cpi: number | null // コアCPI予測値
  pce: number | null      // PCE予測値
  core_pce: number | null // コアPCE予測値
}

// 輸入物価指数/輸出物価指数データの型
// FRED: IR（輸入物価指数）, IQ（輸出物価指数）（毎月中旬 8:30 ET発表）
export interface ImportExportPriceData {
  data: ImportExportPriceItem[]
  latest: ImportExportPriceItem | null
  next_release: ImportExportPriceNextRelease | null
  last_updated: string | null
}

export interface ImportExportPriceItem {
  date: string              // YYYY-MM-DD形式
  import_yoy: number | null // 輸入物価指数（前年比%）
  export_yoy: number | null // 輸出物価指数（前年比%）
}

export interface ImportExportPriceNextRelease {
  date: string
  label: string
}

// シカゴ連銀小売物価指数（CARTS Fig6）データの型
// Chicago Fed CARTS Retail & Food Services Prices Ex. Auto（週次更新）
export interface RetailFoodServicesPriceData {
  data: RetailFoodServicesPriceItem[]
  latest: RetailFoodServicesPriceItem | null
  last_updated: string | null
}

export interface RetailFoodServicesPriceItem {
  date: string              // YYYY-MM-DD形式
  bea: number | null        // BEA（廃止）
  cpi: number | null        // 商品CPI（自動車除く）
  carts_nowcast: number | null  // CARTS Nowcast（シカゴ連銀CPI予想）
}

// NY連銀インフレ期待データの型（NY Fed SCE）
// 毎月第2月曜日 11:00 ET発表
export interface NYInflationExpectationsData {
  data: {
    one_year: NYInflationExpectationsItem[]
    three_year: NYInflationExpectationsItem[]
    five_year: NYInflationExpectationsItem[]
  }
  latest: NYInflationExpectationsLatest | null
  next_release: NYInflationExpectationsNextRelease | null
  last_updated: string | null
}

export interface NYInflationExpectationsNextRelease {
  date: string           // YYYY-MM-DD形式
  datetime_jst: string   // ISO8601形式（JST）
  time_jst: string       // HH:MM形式
  label: string          // 例: "NY Fed SCE (Jan 2026)"
}

export interface NYInflationExpectationsItem {
  date: string    // YYYY-MM-DD形式
  value: number   // インフレ期待中央値（%）
}

export interface NYInflationExpectationsLatest {
  one_year: number   // 1年先インフレ期待（%）
  three_year: number // 3年先インフレ期待（%）
  five_year: number  // 5年先インフレ期待（%）
  date: string       // 最新データの日付
}

// ミシガン大学インフレ期待データの型（University of Michigan Survey of Consumers）
// 毎月2回発表（速報値と確報値）
export interface MichiganInflationExpectationsData {
  data: {
    one_year: MichiganInflationExpectationsItem[]
    five_year: MichiganInflationExpectationsItem[]
  }
  latest: MichiganInflationExpectationsLatest | null
  next_release: MichiganInflationExpectationsNextRelease | null
  last_updated: string | null
}

export interface MichiganInflationExpectationsNextRelease {
  date: string           // YYYY-MM-DD形式
  datetime_jst: string   // ISO8601形式（JST）
  time_jst: string       // HH:MM形式
  label: string          // 例: "Michigan Consumer Sentiment"
}

export interface MichiganInflationExpectationsItem {
  date: string    // YYYY-MM-DD形式
  value: number   // インフレ期待中央値（%）
}

export interface MichiganInflationExpectationsLatest {
  one_year: number   // 1年先インフレ期待（%）
  five_year: number  // 5年先インフレ期待（%）
  date: string       // 最新データの日付
}

// Trimmed Mean PCE Inflation Rate データの型（Dallas Fed）
// 毎月末頃発表（PCEデフレーターと同時）
export interface TrimmedMeanPCEData {
  data: TrimmedMeanPCEItem[]
  latest: TrimmedMeanPCEItem | null
  next_release: TrimmedMeanPCENextRelease | null
  last_updated: string | null
}

export interface TrimmedMeanPCEItem {
  date: string              // YYYY-MM-DD形式
  one_month: number | null  // 1ヶ月変化率（年率換算）
  six_month: number | null  // 6ヶ月変化率（年率換算）
  twelve_month: number | null  // 12ヶ月変化率
}

export interface TrimmedMeanPCENextRelease {
  date: string    // YYYY-MM-DD形式
  label: string   // 例: "PCE Deflator (Jan 31)"
}

// Median CPI データの型（Cleveland Fed）
// CPI発表と同日（毎月中旬 8:30 ET）
export interface MedianCPIData {
  data: MedianCPIItem[]
  latest: MedianCPIItem | null
  next_release: MedianCPINextRelease | null
  last_updated: string | null
}

export interface MedianCPIItem {
  date: string                 // YYYY-MM-DD形式
  median_cpi: number | null    // Median CPI（前年比）
  trimmed_mean_16: number | null  // 16% Trimmed Mean（前年比）
  cpi: number | null           // CPI（前年比）
  core_cpi: number | null      // Core CPI（前年比）
}

export interface MedianCPINextRelease {
  date: string    // YYYY-MM-DD形式
  label: string   // 例: "CPI (Feb 11)"
}

// Supply- and Demand-Driven PCE Inflation データの型（SF Fed）
// PCE発表後数日内に更新（コアPCE YoY を需要起因/供給起因/判別不能 に分解）
export interface SupplyAndDemandDrivenPceInflationData {
  data: SupplyAndDemandDrivenPceInflationItem[]
  latest: SupplyAndDemandDrivenPceInflationItem | null
  next_release: SupplyAndDemandDrivenPceInflationNextRelease | null
  last_updated: string | null
}

export interface SupplyAndDemandDrivenPceInflationItem {
  date: string              // YYYY-MM-DD形式（月初）
  demand_driven: number     // 需要起因 (% pts, YoY)
  ambiguous: number         // 判別不能 (% pts, YoY)
  supply_driven: number     // 供給起因 (% pts, YoY)
  total: number             // 合計（コアPCE YoY, %）
}

export interface SupplyAndDemandDrivenPceInflationNextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  label: string
  estimate?: number | null
}

// 中古車価格データの型（FRED CPI Used Cars + Manheim UVVI）
// FRED: CPIと同タイミングで発表（毎月10-15日頃）
// Manheim: 毎月5日以降に Cox Automotive で発表
export interface UsedCarPricesData {
  data: UsedCarPricesItem[]
  latest: UsedCarPricesItem | null
  next_release: UsedCarPricesNextRelease | null
  last_updated: string | null
}

export interface UsedCarPricesItem {
  date: string                   // YYYY-MM-DD形式（月初）
  fred_yoy: number | null        // FRED CPI Used Cars YoY (%)
  manheim_yoy: number | null     // Manheim UVVI YoY (%)
}

export interface UsedCarPricesNextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  label: string
  estimate?: number | null
}

// 米国物価ダッシュボードデータの型
export interface USAInflationData {
  cpi: CPIData | null
  core_cpi: CoreCPIData | null
  cpi_categories: CPICategoriesData | null
  housing_indicators: HousingIndicatorsData | null
  zillow_rent_index: ZillowRentIndexData | null
  rent_cpi: RentCPIData | null
  pce_deflator: PCEDeflatorData | null
  core_pce_deflator: CorePCEDeflatorData | null
  ppi: PPIData | null
  core_ppi: CorePPIData | null
  ppi_categories: PPICategoriesData | null
  gscpi: GSCPIData | null
  inflation_nowcasting: InflationNowcastingData | null
  import_export_price: ImportExportPriceData | null
  retail_food_services_price: RetailFoodServicesPriceData | null
  ny_inflation_expectations: NYInflationExpectationsData | null
  michigan_inflation_expectations: MichiganInflationExpectationsData | null
  trimmed_mean_pce: TrimmedMeanPCEData | null
  median_cpi: MedianCPIData | null
  supply_and_demand_driven_pce_inflation: SupplyAndDemandDrivenPceInflationData | null
  used_car_prices: UsedCarPricesData | null
  nfib_price_plans: NFIBPricePlansData | null
}

// NFIB中小企業価格引き上げ計画データの型
export interface NFIBPricePlansData {
  data: NFIBPricePlansItem[]
  latest: NFIBPricePlansItem | null
  next_release: NFIBNextRelease | null
  last_updated: string | null
}

export interface NFIBPricePlansItem {
  date: string
  value: number
  [key: string]: string | number | null | undefined
}

/**
 * 米国物価ダッシュボード専用フック
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useUSAInflationDashboard()
 *
 * if (data) {
 *   console.log(data.data.cpi) // CPIデータ
 *   console.log(data.data.core_cpi) // コアCPIデータ
 * }
 * ```
 */
export function useUSAInflationDashboard(): UseQueryResult<DashboardResponse<USAInflationData>, Error> {
  return useDashboardData<USAInflationData>('usa', 'inflation')
}

// =============================================================================
// 住宅データ型定義
// =============================================================================

// 30年固定住宅ローン金利データの型（Freddie Mac PMMS）
// 毎週木曜日 12:00 ET発表
export interface MortgageRatesData {
  data: MortgageRatesItem[]
  latest: MortgageRatesItem | null
  next_release: MortgageRatesNextRelease | null
  last_updated: string | null
}

export interface MortgageRatesItem {
  date: string    // YYYY-MM-DD形式
  value: number   // 金利（%）
}

export interface MortgageRatesNextRelease {
  date: string           // YYYY-MM-DD形式
  datetime_jst: string   // ISO8601形式（JST）
  time_jst: string       // HH:MM形式
  label: string          // 例: "Freddie Mac Mortgage Rates (Jan 09)"
}

// Redfin 全米住宅価格中央値（前年比）データの型
// 月次（毎月第3金曜日頃）発表
export interface RedfinMedianPriceData {
  data: RedfinMedianPriceItem[]
  latest: RedfinMedianPriceItem | null
  next_release: RedfinMedianPriceNextRelease | null
  last_updated: string | null
}

export interface RedfinMedianPriceItem {
  date: string    // YYYY-MM-DD形式
  value: number   // 前年比（%）
}

export interface RedfinMedianPriceNextRelease {
  date: string    // YYYY-MM-DD形式
  label: string   // 例: "Redfin Housing Report (Jan 17)"
}

// S&P/ケースシラー住宅価格指数データの型
// 月次（毎月最終火曜日 9:00 ET頃）発表
export interface CaseShillerData {
  data: CaseShillerItem[]
  latest: CaseShillerItem | null
  next_release: CaseShillerNextRelease | null
  last_updated: string | null
}

export interface CaseShillerItem {
  date: string    // YYYY-MM-DD形式
  value: number   // インデックス値
  yoy: number | null  // 前年比（%）
}

export interface CaseShillerNextRelease {
  date: string           // YYYY-MM-DD形式
  datetime_jst: string   // ISO8601形式（JST）
  time_jst: string       // HH:MM形式
  label: string          // 例: "S&P/Case-Shiller Home Price Index (Jan 28)"
}

// 新築住宅販売戸数データの型
// 月次（毎月下旬 10:00 ET頃）発表
export interface NewHomeSalesData {
  data: NewHomeSalesItem[]
  latest: NewHomeSalesItem | null
  next_release: NewHomeSalesNextRelease | null
  last_updated: string | null
}

export interface NewHomeSalesItem {
  date: string    // YYYY-MM-DD形式
  value: number   // 販売戸数（千戸）
  mom: number | null  // 前月比（%）
  yoy: number | null  // 前年比（%）
}

export interface NewHomeSalesNextRelease {
  date: string           // YYYY-MM-DD形式
  datetime_jst: string   // ISO8601形式（JST）
  time_jst: string       // HH:MM形式
  label: string          // 例: "New Home Sales (Dec)"
}

// 中古住宅販売保留データの型
// 月次（毎月下旬 10:00 ET頃）発表
export interface PendingHomeSalesData {
  data: PendingHomeSalesItem[]
  latest: PendingHomeSalesItem | null
  next_release: PendingHomeSalesNextRelease | null
  last_updated: string | null
}

export interface PendingHomeSalesItem {
  date: string          // YYYY-MM-DD形式
  mom: number | null    // 前月比（%）
  yoy: number | null    // 前年比（%）
}

export interface PendingHomeSalesNextRelease {
  date: string           // YYYY-MM-DD形式
  datetime_jst: string   // ISO8601形式（JST）
  time_jst: string       // HH:MM形式
  label: string          // 例: "Pending Home Sales (Dec)"
}

// 中古住宅販売戸数データの型
// 月次（毎月下旬 10:00 ET頃）発表
export interface ExistingHomeSalesData {
  data: ExistingHomeSalesItem[]
  latest: ExistingHomeSalesItem | null
  next_release: ExistingHomeSalesNextRelease | null
  last_updated: string | null
}

export interface ExistingHomeSalesItem {
  date: string          // YYYY-MM-DD形式
  value: number | null  // 販売戸数（百万戸・年率換算）
  mom: number | null    // 前月比（%）
  yoy: number | null    // 前年比（%）
}

export interface ExistingHomeSalesNextRelease {
  date: string           // YYYY-MM-DD形式
  datetime_jst: string   // ISO8601形式（JST）
  time_jst: string       // HH:MM形式
  label: string          // 例: "Existing Home Sales (Dec)"
}

// NAHB住宅市場指数データの型
// 月次（毎月15日-21日頃 10:00 ET）発表
export interface NAHBHMIData {
  data: NAHBHMIItem[]
  latest: NAHBHMIItem | null
  next_release: NAHBHMINextRelease | null
  last_updated: string | null
}

export interface NAHBHMIItem {
  date: string          // YYYY-MM-DD形式
  value: number | null  // HMI指数値
  mom: number | null    // 前月比（ポイント変化）
  yoy: number | null    // 前年比（ポイント変化）
}

export interface NAHBHMINextRelease {
  date: string           // YYYY-MM-DD形式
  datetime_jst: string   // ISO8601形式（JST）
  time_jst: string       // HH:MM形式
  label: string          // 例: "NAHB Housing Market Index (Dec)"
}

// 住宅着工件数・建設許可件数データの型
// 月次（毎月17-19日頃 8:30 ET）発表
export interface HousingStartsPermitsData {
  housing_starts: HousingStartsSeriesData | null
  building_permits: BuildingPermitsSeriesData | null
  next_release: HousingStartsNextRelease | null
  last_updated: string | null
}

export interface HousingStartsSeriesData {
  data: HousingStartsItem[]
  latest: HousingStartsItem | null
}

export interface BuildingPermitsSeriesData {
  data: BuildingPermitsItem[]
  latest: BuildingPermitsItem | null
}

export interface HousingStartsItem {
  date: string          // YYYY-MM-DD形式
  value: number | null  // 住宅着工件数（千戸）
  mom: number | null    // 前月比（%）
  yoy: number | null    // 前年比（%）
}

export interface BuildingPermitsItem {
  date: string          // YYYY-MM-DD形式
  value: number | null  // 建設許可件数（千戸）
  mom: number | null    // 前月比（%）
  yoy: number | null    // 前年比（%）
}

export interface HousingStartsNextRelease {
  date: string           // YYYY-MM-DD形式
  datetime_jst: string   // ISO8601形式（JST）
  time_jst: string       // HH:MM形式
  label: string          // 例: "Housing Starts (Dec)"
}

// 賃貸空室率データの型（FRED RRVRUSQ156N）
// 四半期データ（不定期発表）
export interface RentalVacancyRateData {
  data: RentalVacancyRateItem[]
  latest: RentalVacancyRateItem | null
  next_release: RentalVacancyRateNextRelease | null
  last_updated: string | null
}

export interface RentalVacancyRateItem {
  date: string          // YYYY-MM-DD形式
  value: number         // 賃貸空室率（%）
}

export interface RentalVacancyRateNextRelease {
  note: string          // 四半期データに関するメモ
  schedule_url: string  // Census Bureauのスケジュールページ
}

// 米国住宅ダッシュボードデータの型
export interface USAHousingData {
  mortgage_rates: MortgageRatesData | null
  redfin_median_price: RedfinMedianPriceData | null
  case_shiller: CaseShillerData | null
  new_home_sales: NewHomeSalesData | null
  pending_home_sales: PendingHomeSalesData | null
  existing_home_sales: ExistingHomeSalesData | null
  nahb_hmi: NAHBHMIData | null
  housing_starts_permits: HousingStartsPermitsData | null
  rental_vacancy_rate: RentalVacancyRateData | null
}

/**
 * 米国住宅ダッシュボード専用フック
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useUSAHousingDashboard()
 *
 * if (data) {
 *   console.log(data.data.mortgage_rates) // 住宅ローン金利データ
 * }
 * ```
 */
export function useUSAHousingDashboard(): UseQueryResult<DashboardResponse<USAHousingData>, Error> {
  return useDashboardData<USAHousingData>('usa', 'housing')
}

// =============================================================================
// 日本金融政策データの型
// =============================================================================

// 日銀政策金利データの型
export interface BOJPolicyRateData {
  data: BOJPolicyRateItem[]
  latest: BOJPolicyRateItem | null
  next_release: BOJPolicyRateNextRelease | null
}

export interface BOJPolicyRateItem {
  date: string         // YYYY-MM-DD形式
  value: number        // 政策金利（%）
  forecast: number | null
  previous: number | null
}

export interface BOJPolicyRateNextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  label: string
  estimate?: number | null
}

// 日銀バランスシートデータの型
export interface JapanBalanceSheetItem {
  date: string
  value: number // 億円
  value_trillion: number // 兆円
}

export interface JapanBalanceSheetNextRelease {
  date: string
  time?: string
  datetime_jst?: string
  as_of?: string
  label?: string
}

export interface JapanBalanceSheetData {
  data: JapanBalanceSheetItem[]
  latest: JapanBalanceSheetItem | null
  metadata: {
    source?: string
    description?: string
    unit?: string
    display_unit?: string
    frequency?: string
    series_id?: string
  }
  next_release: JapanBalanceSheetNextRelease | null
}

// 日銀当座預金残高データの型
export interface BojCurrentAccountBalanceItem {
  date: string
  value: number           // 億円
  value_trillion: number  // 兆円
}

export interface BojCurrentAccountBalanceData {
  data: BojCurrentAccountBalanceItem[]
  latest: BojCurrentAccountBalanceItem | null
  metadata: Record<string, unknown>
  next_release: { date: string; time?: string; label?: string } | null
}

// 日本金融政策ダッシュボードデータの型
export interface JapanPolicyData {
  boj_policy_rate: BOJPolicyRateData | null
  japan_balance_sheet: JapanBalanceSheetData | null
  boj_current_account_balance: BojCurrentAccountBalanceData | null
}

/**
 * 日本金融政策ダッシュボード専用フック
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useJapanPolicyDashboard()
 *
 * if (data) {
 *   console.log(data.data.boj_policy_rate) // 日銀政策金利データ
 * }
 * ```
 */
export function useJapanPolicyDashboard(): UseQueryResult<DashboardResponse<JapanPolicyData>, Error> {
  return useDashboardData<JapanPolicyData>('japan', 'policy')
}

// =============================================================================
// 日本消費データの型
// =============================================================================

// 消費支出データポイント
export interface ConsumptionExpenditureItem {
  date: string         // YYYY-MM-DD形式
  value: number | null // MoMまたはYoY（%）
  forecast?: number | null
  previous?: number | null
}

// 消費支出系列データ
export interface ConsumptionExpenditureSeriesData {
  data: ConsumptionExpenditureItem[]
  latest: ConsumptionExpenditureItem | null
}

// 次回発表情報
export interface ConsumptionExpenditureNextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  label?: string
  estimate?: number | null
}

// 消費支出データ全体
export interface ConsumptionExpenditureData {
  mom: ConsumptionExpenditureSeriesData | null
  yoy: ConsumptionExpenditureSeriesData | null
  next_release: ConsumptionExpenditureNextRelease | null
}

// 小売業販売額データポイント
export interface JapanRetailSalesItem {
  date: string         // YYYY-MM-DD形式
  value: number        // MoMまたはYoY（%）
  sales_amount?: number | null // 販売額（10億円）
  forecast?: number | null
  previous?: number | null
}

// 小売業販売額系列データ
export interface JapanRetailSalesSeriesData {
  data: JapanRetailSalesItem[]
  latest: JapanRetailSalesItem | null
}

// 小売業販売額次回発表情報
export interface JapanRetailSalesNextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  label: string
  estimate?: number | null
}

// 小売業販売額データ全体
export interface JapanRetailSalesData {
  mom: JapanRetailSalesSeriesData | null
  yoy: JapanRetailSalesSeriesData | null
  next_release: JapanRetailSalesNextRelease | null
}

// 日本消費ダッシュボードデータの型
export interface JapanConsumerData {
  consumption_expenditure: ConsumptionExpenditureData | null
  retail_sales: JapanRetailSalesData | null
}

/**
 * 日本消費ダッシュボード専用フック
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useJapanConsumerDashboard()
 *
 * if (data) {
 *   console.log(data.data.consumption_expenditure) // 消費支出データ
 * }
 * ```
 */
export function useJapanConsumerDashboard(): UseQueryResult<DashboardResponse<JapanConsumerData>, Error> {
  return useDashboardData<JapanConsumerData>('japan', 'consumer')
}

// =============================================================================
// 日本雇用データの型
// =============================================================================

// 所定内給与データポイント
export interface JapanScheduledWageDataPoint {
  date: string
  value: number
}

// 所定内給与系列データ
export interface JapanScheduledWageSeriesData {
  data: JapanScheduledWageDataPoint[]
  latest: JapanScheduledWageDataPoint | null
}

// 所定内給与次回発表
export interface JapanScheduledWageNextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  label: string
  estimate?: number | null
}

// 所定内給与データ全体（e-Stat版）
export interface JapanScheduledWageData {
  scheduled_wage: JapanScheduledWageSeriesData | null
  general: JapanScheduledWageSeriesData | null
  part_time_wage: JapanScheduledWageSeriesData | null  // パート所定内給与
  part_time_hourly: JapanScheduledWageSeriesData | null  // パート時間当
  next_release: JapanScheduledWageNextRelease | null
}

// 所定内給与データ全体（共通事業所版）
export interface JapanScheduledWageCommonData {
  scheduled_wage: JapanScheduledWageSeriesData | null
  general: JapanScheduledWageSeriesData | null
  part_time: JapanScheduledWageSeriesData | null
  next_release: JapanScheduledWageNextRelease | null
  data_type?: 'preliminary' | 'revised' | null  // 速報(p) / 確報(r)
}

// 雇用形態別労働者過不足判断D.I.データポイント
export interface JapanEmploymentTypeDataPoint {
  date: string
  value: number
}

// 雇用形態別労働者過不足判断D.I.系列データ
export interface JapanEmploymentTypeSeriesData {
  data: JapanEmploymentTypeDataPoint[]
  latest: JapanEmploymentTypeDataPoint | null
}

// 雇用形態別労働者過不足判断D.I.データ全体
export interface JapanEmploymentTypeData {
  regular_employee: JapanEmploymentTypeSeriesData | null
  part_time: JapanEmploymentTypeSeriesData | null
}

// 失業率データポイント
export interface JapanUnemploymentDataPoint {
  date: string  // YYYY-MM-DD形式
  value: number // 失業率（%）
}

// 失業率系列データ
export interface JapanUnemploymentSeriesData {
  data: JapanUnemploymentDataPoint[]
  latest: JapanUnemploymentDataPoint | null
}

// 失業率次回発表情報
export interface JapanUnemploymentNextRelease {
  date?: string
  time_jst?: string
  datetime_jst?: string
}

// 失業率データ全体
export interface JapanUnemploymentData {
  unemployment_rate: JapanUnemploymentSeriesData | null
  next_release: JapanUnemploymentNextRelease | null
}

// =============================================================================
// 日本有効求人倍率データの型
// =============================================================================

// 有効求人倍率データポイント
export interface JapanJobOffersRatioDataPoint {
  date: string  // YYYY-MM-DD形式
  value: number | null // 有効求人倍率（倍）
  forecast?: number | null
  previous?: number | null
}

// 有効求人倍率次回発表情報
export interface JapanJobOffersRatioNextRelease {
  date?: string
  time_jst?: string
  datetime_jst?: string
}

// 有効求人倍率データ全体
export interface JapanJobOffersRatioData {
  job_offers_ratio: JapanJobOffersRatioDataPoint[] | null
  latest: JapanJobOffersRatioDataPoint | null
  next_release: JapanJobOffersRatioNextRelease | null
}

// =============================================================================
// 日本 実質賃金データの型（2系列：全事業所版/共通事業所版）
// =============================================================================

// 実質賃金データポイント
export interface JapanRealWageDataPoint {
  date: string  // YYYY-MM-DD形式
  value: number // 前年比（%）
}

// 実質賃金系列データ
export interface JapanRealWageSeriesData {
  data: JapanRealWageDataPoint[]
  latest: JapanRealWageDataPoint | null
}

// 実質賃金次回発表情報
export interface JapanRealWageNextRelease {
  date?: string
  time_jst?: string
  datetime_jst?: string
}

// 実質賃金データ全体（2系列）
export interface JapanRealWageData {
  all: JapanRealWageSeriesData | null  // 全事業所版
  common: JapanRealWageSeriesData | null  // 共通事業所版
  next_release: JapanRealWageNextRelease | null
}

// =============================================================================
// 日本 現金給与額データの型
// =============================================================================

// 現金給与額データポイント
export interface JapanCashEarningsDataPoint {
  date: string  // YYYY-MM-DD形式
  value: number // 前年比（%）
}

// 現金給与額次回発表情報
export interface JapanCashEarningsNextRelease {
  date?: string
  time_jst?: string
  datetime_jst?: string
}

// 現金給与額データ全体（単一系列）
export interface JapanCashEarningsData {
  data: JapanCashEarningsDataPoint[]
  latest: JapanCashEarningsDataPoint | null
  next_release: JapanCashEarningsNextRelease | null
}

// 春闘データポイント
export interface JapanShuntouDataPoint {
  date: string  // YYYY-01-01形式（年度単位）
  value: number // 賃上げ率（%）
}

// 春闘系列データ
export interface JapanShuntouSeriesData {
  data: JapanShuntouDataPoint[]
  latest: JapanShuntouDataPoint | null
}

// 春闘プレスリリース情報
export interface JapanShuntouPressRelease {
  number: number  // 第何回速報
  url: string     // PDF URL
  year: number    // 発表年度
  title: string   // タイトル
}

// 春闘次回発表情報
export interface JapanShuntouNextRelease {
  date?: string
  label?: string  // "第3回速報" など
  estimated?: boolean  // 推定値かどうか
}

// 春闘データ全体
export interface JapanShuntouData {
  wage_increase: JapanShuntouSeriesData | null  // 賃上げ率（加重平均）
  union_member: JapanShuntouSeriesData | null   // 組合員数賃上げ率（単純平均）
  press_releases: JapanShuntouPressRelease[]
  next_release: JapanShuntouNextRelease | null
}

// 日本雇用ダッシュボードデータの型
export interface JapanEmploymentDashboardData {
  scheduled_wage: JapanScheduledWageData | null
  scheduled_wage_common: JapanScheduledWageCommonData | null
  real_wage: JapanRealWageData | null
  cash_earnings: JapanCashEarningsData | null
  employment_type: JapanEmploymentTypeData | null
  unemployment: JapanUnemploymentData | null
  job_offers_ratio: JapanJobOffersRatioData | null
  shuntou: JapanShuntouData | null
}

/**
 * 日本雇用ダッシュボード専用フック
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useJapanEmploymentDashboard()
 *
 * if (data) {
 *   console.log(data.data.scheduled_wage) // 所定内給与データ
 * }
 * ```
 */
export function useJapanEmploymentDashboard(): UseQueryResult<DashboardResponse<JapanEmploymentDashboardData>, Error> {
  return useDashboardData<JapanEmploymentDashboardData>('japan', 'employment')
}

// =============================================================================
// 日本経済データの型
// =============================================================================

// 日本経済指標の次回発表情報
export interface JapanEconomyNextRelease {
  date?: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  label?: string
}

// 四半期GDPデータポイント
export interface JapanQuarterlyGDPDataPoint {
  date: string
  qoq?: number | null
  qoq_annualized?: number | null
  yoy?: number | null
}

// 四半期GDPデータ
export interface JapanQuarterlyGDPData {
  data: JapanQuarterlyGDPDataPoint[]
  latest: JapanQuarterlyGDPDataPoint | null
  next_release?: JapanEconomyNextRelease | null
}

// 鉱工業生産データポイント
export interface JapanIIPDataPoint {
  date: string
  value?: number | null
  mom_change?: number | null
  yoy_change?: number | null
}

// 鉱工業生産データ
export interface JapanIIPData {
  data: JapanIIPDataPoint[]
  latest: JapanIIPDataPoint | null
  next_release?: JapanEconomyNextRelease | null
}

// 第三次産業活動指数データポイント
export interface JapanTertiaryIndustryDataPoint {
  date: string
  mom?: number | null
  yoy?: number | null
}

// 第三次産業活動指数データ
export interface JapanTertiaryIndustryData {
  data: JapanTertiaryIndustryDataPoint[]
  latest: JapanTertiaryIndustryDataPoint | null
  next_release?: JapanEconomyNextRelease | null
}

// 機械受注データポイント
export interface JapanMachineryOrdersDataPoint {
  date: string
  value?: number | null
  mom?: number | null
  yoy?: number | null
}

// 機械受注データ
export interface JapanMachineryOrdersData {
  data: JapanMachineryOrdersDataPoint[]
  latest: JapanMachineryOrdersDataPoint | null
  next_release?: JapanEconomyNextRelease | null
}

// 工作機械受注データポイント
export interface JapanMachineToolOrdersDataPoint {
  date: string
  value?: number | null
  total_orders?: number | null
}

// 工作機械受注データ
export interface JapanMachineToolOrdersData {
  data: JapanMachineToolOrdersDataPoint[]
  latest: JapanMachineToolOrdersDataPoint | null
  next_release?: JapanEconomyNextRelease | null
}

// 設備投資データポイント
export interface JapanCapitalInvestmentDataPoint {
  date: string
  value?: number | null
}

// 設備投資データ
export interface JapanCapitalInvestmentData {
  data: JapanCapitalInvestmentDataPoint[]
  latest: JapanCapitalInvestmentDataPoint | null
  next_release?: JapanEconomyNextRelease | null
}

// 経常収支データポイント
export interface JapanCurrentAccountDataPoint {
  date: string
  current_account: number // 10億円
  goods_services?: number | null
  primary_income?: number | null
  secondary_income?: number | null
}

// 経常収支データ
export interface JapanCurrentAccountData {
  data: JapanCurrentAccountDataPoint[]
  latest: JapanCurrentAccountDataPoint | null
  next_release?: JapanEconomyNextRelease | null
}

// 経常収支対GDP比データポイント
export interface JapanCurrentAccountGdpRatioDataPoint {
  date: string // YYYY-QN形式
  ratio: number // %
  current_account: number // 億円（四半期合計）
  nominal_gdp: number // 億円
}

// 経常収支対GDP比データ
export interface JapanCurrentAccountGdpRatioData {
  data: JapanCurrentAccountGdpRatioDataPoint[]
  latest: JapanCurrentAccountGdpRatioDataPoint | null
  next_release?: JapanEconomyNextRelease | null
}

// 貿易収支データポイント
export interface JapanBalanceOfTradeDataPoint {
  date: string
  trade_balance: number // 億円
  exports?: number | null // 億円
  imports?: number | null // 億円
}

// 貿易収支データ
export interface JapanBalanceOfTradeData {
  data: JapanBalanceOfTradeDataPoint[]
  latest: JapanBalanceOfTradeDataPoint | null
  next_release?: JapanEconomyNextRelease | null
}

// 日本経済ダッシュボードデータの型
export interface JapanEconomyDashboardData {
  quarterly_gdp: JapanQuarterlyGDPData | null
  iip: JapanIIPData | null
  iip_yoy: JapanIIPData | null
  tertiary_industry: JapanTertiaryIndustryData | null
  machinery_orders: JapanMachineryOrdersData | null
  machine_tool_orders: JapanMachineToolOrdersData | null
  capital_investment: JapanCapitalInvestmentData | null
  current_account: JapanCurrentAccountData | null
  current_account_gdp_ratio: JapanCurrentAccountGdpRatioData | null
  balance_of_trade: JapanBalanceOfTradeData | null
}

/**
 * 日本経済ダッシュボード専用フック
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useJapanEconomyDashboard()
 *
 * if (data) {
 *   console.log(data.data.quarterly_gdp) // 四半期GDPデータ
 *   console.log(data.data.tertiary_industry) // 第三次産業活動指数
 * }
 * ```
 */
export function useJapanEconomyDashboard(): UseQueryResult<DashboardResponse<JapanEconomyDashboardData>, Error> {
  return useDashboardData<JapanEconomyDashboardData>('japan', 'economy')
}

// =============================================================================
// ユーロ圏金融政策データの型
// =============================================================================

// ECB預金ファシリティ金利データの型
export interface ECBRatesData {
  data: ECBRatesItem[]
  latest: ECBRatesItem | null
  next_release: ECBRatesNextRelease | null
}

export interface ECBRatesItem {
  date: string         // YYYY-MM-DD形式
  value: number        // 政策金利（%）
  deposit_facility?: number  // 預金ファシリティ金利（%）- ECB APIからの値
  forecast?: number | null
  previous?: number | null
}

export interface ECBRatesNextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  datetime_cet?: string
  time_cet?: string
  label: string
  estimate?: number | null
}

// Eurex OISデータの型
export interface EurexOISData {
  labels: string[]
  values: number[]
  contracts: string[]
  settle_values: number[]
  previous_values: (number | null)[]
  last_updated: string
  source: string
  current_date: string | null
  previous_date: string | null
}

// ECBマクロ経済予測データの型（新API構造）
export interface ECBProjectionDataPoint {
  date: string
  value: number | null
}

export interface ECBIndicatorData {
  annual_latest: ECBProjectionDataPoint[]
  annual_previous: ECBProjectionDataPoint[]
  quarterly_latest: ECBProjectionDataPoint[]
  quarterly_previous: ECBProjectionDataPoint[]
}

export interface ECBMacroProjectionsMetadata {
  last_updated: string
  source: string
  latest_vintage: string
  previous_vintage: string
  latest_season_name: string
  previous_season_name: string
  error?: string
}

export interface ECBMacroProjectionsData {
  indicators: {
    gdp: ECBIndicatorData
    unemployment: ECBIndicatorData
    hicp: ECBIndicatorData
    core_inflation: ECBIndicatorData
    core_inflation_tax: ECBIndicatorData
    foreign_demand: ECBIndicatorData
    interest_rate: ECBIndicatorData
    private_consumption: ECBIndicatorData
    wages: ECBIndicatorData
  }
  metadata: ECBMacroProjectionsMetadata
}

// ECB M3マネーサプライデータの型
export interface ECBM3Data {
  yoy: ECBM3SeriesData      // 前年比
  level: ECBM3SeriesData    // 原数値（10億ユーロ）
  next_release: ECBM3NextRelease | null
}

export interface ECBM3SeriesData {
  data: ECBM3Item[]
  latest: ECBM3Item | null
}

export interface ECBM3Item {
  date: string         // YYYY-MM-DD形式
  value: number        // 値
}

export interface ECBM3NextRelease {
  date: string
  time_jst?: string
  datetime_jst?: string
}

// ECB Bank Interest Rates（銀行金利）データの型
export interface ECBBankInterestRatesData {
  corporations: ECBBankInterestRatesSeriesData  // 企業向け新規融資金利
  housing: ECBBankInterestRatesSeriesData       // 住宅ローン新規金利
  next_release: ECBBankInterestRatesNextRelease | null
}

export interface ECBBankInterestRatesSeriesData {
  data: ECBBankInterestRatesItem[]
  latest: ECBBankInterestRatesItem | null
}

export interface ECBBankInterestRatesItem {
  date: string   // YYYY-MM-DD形式
  value: number  // 金利（%）
}

export interface ECBBankInterestRatesNextRelease {
  date: string
  time_cet?: string
  time_jst?: string
}

// ECB調整済貸出データの型
export interface ECBAdjustedLoansData {
  nfc: ECBAdjustedLoansSeriesData          // 非金融法人向け
  households: ECBAdjustedLoansSeriesData   // 家計向け（総合）
  housing: ECBAdjustedLoansSeriesData      // 家計向け（住宅購入）
  next_release: ECBAdjustedLoansNextRelease | null
}

export interface ECBAdjustedLoansSeriesData {
  data: ECBAdjustedLoansItem[]
  latest: ECBAdjustedLoansItem | null
}

export interface ECBAdjustedLoansItem {
  date: string   // YYYY-MM-DD形式
  value: number  // 前年比（%）
}

export interface ECBAdjustedLoansNextRelease {
  date: string
  time_jst?: string
  datetime_jst?: string
}

// ECBバランスシートデータの型
export interface ECBBalanceSheetData {
  data: ECBBalanceSheetItem[]
  latest: ECBBalanceSheetItem | null
}

export interface ECBBalanceSheetItem {
  date: string
  value: number  // 百万ユーロ
}

// ユーロ圏金融政策ダッシュボードデータの型
export interface EurozonePolicyData {
  ecb_rates: ECBRatesData | null
  eurex_ois: EurexOISData | null
  ecb_macro_projections: ECBMacroProjectionsData | null
  ecb_m3: ECBM3Data | null
  ecb_bank_interest_rates: ECBBankInterestRatesData | null
  ecb_balance_sheet: ECBBalanceSheetData | null
}

// ECB CISS（システミックストレス総合指標）データの型
export interface ECBCISSData {
  data: ECBCISSDataPoint[]
  latest: ECBCISSDataPoint | null
  next_release: ECBCISSNextRelease | null
}

export interface ECBCISSDataPoint {
  date: string
  value: number
}

export interface ECBCISSNextRelease {
  date: string
  datetime_cet: string
  datetime_jst: string
  time_cet: string
  time_jst: string
  label?: string
}

// BOE Bank Rate データの型
export interface BOEBankRateData {
  data: BOEBankRateItem[]
  latest: BOEBankRateItem | null
  next_release: BOEBankRateNextRelease | null
}

export interface BOEBankRateItem {
  date: string         // YYYY-MM-DD形式
  value: number        // 政策金利（%）
}

export interface BOEBankRateNextRelease {
  date: string
  time_jst?: string
}

// BOE MPC Voting データの型
export interface BOEMPCVotingRecord {
  date: string
  bank_rate: number | null
  [key: string]: string | number | null | undefined
}

export interface BOEMPCVotingData {
  data: BOEMPCVotingRecord[]
  members: string[]
  next_release: BOEBankRateNextRelease | null
}

// BOE OISカーブデータの型
export interface BOEOISCurvePoint {
  date: string
  data: Record<string, number | null>
}

export interface BOEOISCurveMetadata {
  source?: string
  indicator?: string
  total_dates?: number
  date_range?: {
    start: string
    end: string
  }
}

export interface BOEOISCurveData {
  current: BOEOISCurvePoint | null
  previous: BOEOISCurvePoint | null
  metadata: BOEOISCurveMetadata
}

// BOE Market Expectations データの型
export interface BOEMarketExpectationsData {
  latest: BOEMarketExpectationsPoint | null
  previous: BOEMarketExpectationsPoint | null
  metadata: Record<string, unknown>
  next_release: BOEBankRateNextRelease | null
}

export interface BOEMarketExpectationsDataPoint {
  date: string
  value: number
}

export interface BOEMarketExpectationsPoint {
  date: string
  forecast_date?: string
  data: BOEMarketExpectationsDataPoint[]
}

// BOE CPI Projections データの型
export interface BOECPIProjectionsData {
  table_data: BOEProjectionTableRow[]
  chart_data: Record<string, unknown> | null
  // 2026年4月MPRのシナリオ方式: scenario_a 等のキーラベル (例: "April 2026 Scenario A")
  scenario_labels?: Record<string, string> | null
  metadata: Record<string, unknown>
  next_release: BOEBankRateNextRelease | null
}

// 旧来: latest/previous の2系列。2026年4月MPR以降のシナリオ方式では
// scenario_a/scenario_b/... + previous の動的キーになる
export interface BOEProjectionTableRow {
  quarter: string
  latest?: number | null
  previous?: number | null
  [seriesKey: string]: string | number | null | undefined
}

// BOE GDP Forecast データの型
export interface BOEGDPForecastData {
  table_data: BOEForecastTableRow[]
  chart_data: Record<string, unknown> | null
  scenario_labels?: Record<string, string> | null
  metadata: Record<string, unknown>
  next_release: BOEBankRateNextRelease | null
}

export interface BOEForecastTableRow {
  quarter: string
  latest?: number | null
  previous?: number | null
  [seriesKey: string]: string | number | null | undefined
}

// BOE Unemployment Forecast データの型
export interface BOEUnemploymentForecastData {
  table_data: BOEForecastTableRow[]
  chart_data: Record<string, unknown> | null
  scenario_labels?: Record<string, string> | null
  metadata: Record<string, unknown>
  next_release: BOEBankRateNextRelease | null
}

// BOE CPI Contributions データの型
export interface BOECPIContributionsInnerData {
  date: string[]
  food: (number | null)[]
  electricity_gas: (number | null)[]
  fuels: (number | null)[]
  other_goods: (number | null)[]
  services: (number | null)[]
  cpi: (number | null)[]
}

export interface BOECPIContributionsData {
  contributions: {
    latest_data: {
      date: string
      data: BOECPIContributionsInnerData | null
    }
  }
  metadata: Record<string, unknown>
  next_release: BOEBankRateNextRelease | null
}

// BOE Wage Growth データの型
export interface BOEWageGrowthInnerData {
  date: string[]
  series: Record<string, (number | null)[]>
}

export interface BOEWageGrowthData {
  wage_growth: {
    data: BOEWageGrowthInnerData | null
  }
  metadata: Record<string, unknown>
  next_release: BOEBankRateNextRelease | null
}

// BOE Services Inflation データの型
export interface BOEServicesInflationInnerData {
  date: string[]
  series: Record<string, (number | null)[]>
}

export interface BOEServicesInflationData {
  services_inflation: {
    data: BOEServicesInflationInnerData | null
  }
  metadata: Record<string, unknown>
  next_release: BOEBankRateNextRelease | null
}

// BOE Inflation Expectations データの型
export interface BOEInflationExpectationsInnerData {
  date: string[]
  series: Record<string, (number | null)[]>
}

export interface BOEInflationExpectationsData {
  inflation_expectations: {
    data: BOEInflationExpectationsInnerData | null
  }
  metadata: Record<string, unknown>
  next_release: BOEBankRateNextRelease | null
}

// BOE Average Weekly Earnings データの型
export interface BOEAverageWeeklyEarningsDataPoint {
  quarter: string
  value: number | null
}

export interface BOEAverageWeeklyEarningsInnerData {
  quarters: string[]
  latest: {
    date: string
    data: BOEAverageWeeklyEarningsDataPoint[]
  } | null
  previous: {
    date: string
    data: BOEAverageWeeklyEarningsDataPoint[]
  } | null
  // 2026年4月MPR以降のシナリオ方式 (latest/previous は null になり、こちらを使用)
  table_data?: BOEForecastTableRow[]
  scenario_labels?: Record<string, string> | null
  latest_forecast?: string
  previous_forecast?: string
}

export interface BOEAverageWeeklyEarningsData {
  average_weekly_earnings: BOEAverageWeeklyEarningsInnerData | null
  metadata: Record<string, unknown>
  next_release: BOEBankRateNextRelease | null
}

// BOE Unit Wage Costs データの型
export interface BOEUnitWageCostsDataPoint {
  quarter: string
  value: number | null
}

export interface BOEUnitWageCostsInnerData {
  quarters: string[]
  latest: {
    date: string
    data: BOEUnitWageCostsDataPoint[]
  } | null
  previous: {
    date: string
    data: BOEUnitWageCostsDataPoint[]
  } | null
}

export interface BOEUnitWageCostsData {
  unit_wage_costs: BOEUnitWageCostsInnerData | null
  metadata: Record<string, unknown>
  next_release: BOEBankRateNextRelease | null
}

// BOE DMP Survey (Decision Maker Panel) データの型
export interface BOEDMPCPIExpectationsData {
  date: string[]
  one_year_ahead: (number | null)[]
  three_year_ahead: (number | null)[]
}

export interface BOEDMPGrowthData {
  date: string[]
  realised_3mo_avg: (number | null)[]
  expected_3mo_avg: (number | null)[]
}

export interface BOEDMPSurveyInnerData {
  cpi_expectations: BOEDMPCPIExpectationsData | null
  price_growth: BOEDMPGrowthData | null
  wage_growth: BOEDMPGrowthData | null
  employment_growth: BOEDMPGrowthData | null
}

export interface BOEDMPSurveyNextRelease {
  date: string
  time_jst?: string
  estimated?: boolean
}

export interface BOEDMPSurveyData {
  survey_data: BOEDMPSurveyInnerData | null
  metadata: Record<string, unknown>
  next_release?: BOEDMPSurveyNextRelease | null
}

// UK Public Sector Net Borrowing（公的部門純借入）データの型
export interface UKPublicSectorNetBorrowingDataPoint {
  date: string
  value: number
}

export interface UKPublicSectorNetBorrowingLatest {
  date: string
  value: number
}

export interface UKPublicSectorNetBorrowingNextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  datetime_london?: string
  time_london?: string
  label?: string
}

export interface UKPublicSectorNetBorrowingMetadata {
  source: string
  description: string
  unit_psnb_ex: string
  unit_cgnb: string
  unit_psnd_ex: string
  unit_psnd_gdp: string
}

export interface UKPublicSectorNetBorrowingData {
  psnb_ex: UKPublicSectorNetBorrowingDataPoint[]
  cgnb: UKPublicSectorNetBorrowingDataPoint[]
  psnd_ex: UKPublicSectorNetBorrowingDataPoint[]
  psnd_gdp: UKPublicSectorNetBorrowingDataPoint[]
  latest_psnb_ex: UKPublicSectorNetBorrowingLatest | null
  latest_cgnb: UKPublicSectorNetBorrowingLatest | null
  latest_psnd_ex: UKPublicSectorNetBorrowingLatest | null
  latest_psnd_gdp: UKPublicSectorNetBorrowingLatest | null
  metadata: UKPublicSectorNetBorrowingMetadata
  next_release?: UKPublicSectorNetBorrowingNextRelease | null
}

// UK QT（APFギルト保有残高）データの型
export interface UKQTDataPoint {
  date: string
  value: number // GBP billions
}

export interface UKQTData {
  data: UKQTDataPoint[]
  latest: UKQTDataPoint | null
  metadata: {
    source?: string
    indicator?: string
    series_code?: string
    unit?: string
    frequency?: string
    description?: string
  }
  next_release?: {
    date: string
    time_london?: string
    time_jst?: string
    datetime_jst?: string
  } | null
}

// イギリス金融政策ダッシュボードデータの型（基本仕様・常設のみ）
// ※ CPI構成項目（boe_cpi_components）は2025年11月以降の拡張データのため除外
// ※ CPI寄与度（boe_cpi_contributions）は分解粒度が号で変わりやすいため除外
export interface UKPolicyData {
  boe_bank_rate: BOEBankRateData | null
  boe_mpc_voting: BOEMPCVotingData | null
  boe_ois_curve: BOEOISCurveData | null
  boe_market_expectations: BOEMarketExpectationsData | null
  boe_cpi_projections: BOECPIProjectionsData | null
  boe_gdp_forecast: BOEGDPForecastData | null
  boe_unemployment_forecast: BOEUnemploymentForecastData | null
  boe_services_inflation: BOEServicesInflationData | null
  boe_wage_growth: BOEWageGrowthData | null
  boe_average_weekly_earnings: BOEAverageWeeklyEarningsData | null
  boe_unit_wage_costs: BOEUnitWageCostsData | null
  boe_inflation_expectations: BOEInflationExpectationsData | null
  boe_dmp_survey: BOEDMPSurveyData | null
  uk_public_sector_net_borrowing: UKPublicSectorNetBorrowingData | null
  uk_government_debt_to_gdp_ratio: UKGovernmentDebtToGdpRatioData | null
  uk_qt: UKQTData | null
}

// ONS GDP データの型
export interface ONSGDPQoQDataPoint {
  date: string
  period: string
  year: number
  quarter: number
  value: number
  qoq_change: number
}

export interface ONSGDPYoYDataPoint {
  date: string
  period: string
  value: number
  yoy_change: number
}

export interface ONSGDPMetadata {
  title: string
  cdid: string
  unit: string
  release_date: string
  next_release_ons: string
  source: string
  description: string
}

export interface ONSGDPNextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  datetime_london?: string
  time_london?: string
  label?: string
  estimate?: string | null
}

export interface ONSGDPData {
  qoq: ONSGDPQoQDataPoint[]
  yoy: ONSGDPYoYDataPoint[]
  quarterly_data?: ONSGDPQoQDataPoint[]
  metadata: ONSGDPMetadata
  next_release?: ONSGDPNextRelease | null
}

// ONS GVA（月間GDP）データの型
export interface ONSGVADataPoint {
  date: string
  value: number
  period: string
}

export interface ONSGVAMoMDataPoint {
  date: string
  period: string
  value: number
  mom_change: number
}

export interface ONSGVAYoYDataPoint {
  date: string
  period: string
  value: number
  yoy_change: number
}

export interface ONSGVAMetadata {
  title: string
  cdid: string
  unit: string
  release_date: string
  next_release_ons: string
}

export interface ONSGVAED3HData {
  data: ONSGVADataPoint[]
  metadata: ONSGVAMetadata
}

export interface ONSGVAECY2Data {
  data: ONSGVADataPoint[]
  yoy: ONSGVAYoYDataPoint[]
  mom: ONSGVAMoMDataPoint[]
  '3m_yoy': ONSGVAYoYDataPoint[]
  metadata: ONSGVAMetadata
}

export interface ONSGVANextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  datetime_london?: string
  time_london?: string
  label?: string
}

export interface ONSGVAData {
  ed3h: ONSGVAED3HData
  ecy2: ONSGVAECY2Data
  metadata: {
    source: string
    description: string
    ed3h_title: string
    ecy2_title: string
  }
  next_release?: ONSGVANextRelease | null
}

// ONS Production Industries（鉱工業生産）データの型
export interface ONSProductionDataPoint {
  date: string
  period: string
  value: number
}

export interface ONSProductionMetadata {
  title: string
  cdid: string
  unit: string
  release_date: string
  next_release_ons: string
}

export interface ONSProductionSeriesData {
  data: ONSProductionDataPoint[]
  metadata: ONSProductionMetadata
}

export interface ONSProductionNextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  datetime_london?: string
  time_london?: string
  label?: string
}

export interface ONSProductionData {
  ed2t: ONSProductionSeriesData  // YoY growth
  ecyz: ONSProductionSeriesData  // MoM growth
  metadata: {
    source: string
    description: string
    ed2t_title: string
    ecyz_title: string
  }
  next_release?: ONSProductionNextRelease | null
}

// CBI製造業受注指数データの型
export interface CBIIndustrialTrendsDataPoint {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

export interface CBIIndustrialTrendsNextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  datetime_london?: string
  time_london?: string
  label?: string
}

export interface CBIIndustrialTrendsData {
  data: CBIIndustrialTrendsDataPoint[]
  latest: CBIIndustrialTrendsDataPoint | null
  next_release?: CBIIndustrialTrendsNextRelease | null
}

// UK PMIデータポイントの型
export interface UKPMIDataPoint {
  date: string
  value: number | null
}

// UK PMI次回発表日時の型
export interface UKPMINextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  datetime_london?: string
  time_london?: string
  label?: string
}

// UK PMIデータの型（製造業・サービス業・総合）
export interface UKPMIData {
  manufacturing: UKPMIDataPoint[]
  services: UKPMIDataPoint[]
  composite: UKPMIDataPoint[]
  next_release?: UKPMINextRelease | null
}

// UK貿易収支データの型
export interface UKTradeBalanceDataPoint {
  date: string
  value: number // £ billions
  value_millions?: number
}

export interface UKTradeBalanceMoMChangePoint {
  date: string
  value: number // £ billions (前月増減幅)
}

export interface UKTradeBalanceNextRelease {
  date: string
  datetime_jst?: string
  time_jst?: string
  label?: string
}

export interface UKTradeBalanceData {
  data: UKTradeBalanceDataPoint[]
  mom_change: UKTradeBalanceMoMChangePoint[]
  latest: UKTradeBalanceDataPoint | null
  metadata: {
    title?: string
    cdid?: string
    unit?: string
    source?: string
    release_date?: string
    description?: string
  }
  next_release?: UKTradeBalanceNextRelease | null
}

// UK経常収支データの型
export interface UKCurrentAccountDataPoint {
  date: string
  value: number // £ billions
  value_millions?: number
}

export interface UKCurrentAccountQoQChangePoint {
  date: string
  value: number // £ billions (前期増減幅)
}

export interface UKCurrentAccountGdpRatioPoint {
  date: string
  value: number // % of GDP
}

export interface UKCurrentAccountNextRelease {
  date: string
  datetime_jst?: string
  time_jst?: string
  label?: string
}

export interface UKCurrentAccountData {
  data: UKCurrentAccountDataPoint[]
  qoq_change: UKCurrentAccountQoQChangePoint[]
  gdp_ratio: UKCurrentAccountGdpRatioPoint[]
  latest: UKCurrentAccountDataPoint | null
  metadata: {
    title?: string
    cdid?: string
    unit?: string
    source?: string
    release_date?: string
    description?: string
  }
  next_release?: UKCurrentAccountNextRelease | null
}

// UK政府債務残高対GDP比データの型
export interface UKGovernmentDebtToGdpRatioDataPoint {
  date: string
  value: number // % of GDP
}

export interface UKGovernmentDebtToGdpRatioMoMChangePoint {
  date: string
  value: number // %ポイント（前月増減幅）
}

export interface UKGovernmentDebtToGdpRatioNextRelease {
  date: string
  datetime_jst?: string
  time_jst?: string
  label?: string
}

export interface UKGovernmentDebtToGdpRatioData {
  data: UKGovernmentDebtToGdpRatioDataPoint[]
  mom_change: UKGovernmentDebtToGdpRatioMoMChangePoint[]
  latest: UKGovernmentDebtToGdpRatioDataPoint | null
  metadata: {
    title?: string
    cdid?: string
    unit?: string
    source?: string
    release_date?: string
    description?: string
  }
  next_release?: UKGovernmentDebtToGdpRatioNextRelease | null
}

// UK経済ダッシュボードデータの型
export interface UKEconomyDashboardData {
  ons_gdp: ONSGDPData | null
  ons_gva: ONSGVAData | null
  ons_production: ONSProductionData | null
  cbi_industrial_trends: CBIIndustrialTrendsData | null
  uk_pmi: UKPMIData | null
  uk_trade_balance: UKTradeBalanceData | null
  uk_current_account: UKCurrentAccountData | null
}

/**
 * ユーロ圏金融政策ダッシュボード専用フック
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useEurozonePolicyDashboard()
 *
 * if (data) {
 *   console.log(data.data.ecb_rates) // ECB金利データ
 *   console.log(data.data.eurex_ois) // Eurex OISデータ
 * }
 * ```
 */
export function useEurozonePolicyDashboard(): UseQueryResult<DashboardResponse<EurozonePolicyData>, Error> {
  return useDashboardData<EurozonePolicyData>('eurozone', 'policy')
}

/**
 * イギリス金融政策ダッシュボード専用フック
 * BOE政策金利などを取得
 */
export function useUKPolicyDashboard(): UseQueryResult<DashboardResponse<UKPolicyData>, Error> {
  return useDashboardData<UKPolicyData>('uk', 'policy')
}

/**
 * イギリス経済ダッシュボード専用フック
 * ONS GDPなどを取得
 */
export function useUKEconomyDashboard(): UseQueryResult<DashboardResponse<UKEconomyDashboardData>, Error> {
  return useDashboardData<UKEconomyDashboardData>('uk', 'economy')
}

// ONS小売売上高データの型
export interface ONSRetailSalesDataPoint {
  date: string
  value: number
  forecast?: number | null
  previous?: number | null
}

export interface ONSRetailSalesNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  label: string
}

export interface ONSRetailSalesData {
  mom: ONSRetailSalesDataPoint[]
  yoy: ONSRetailSalesDataPoint[]
  core_mom: ONSRetailSalesDataPoint[]
  core_yoy: ONSRetailSalesDataPoint[]
  next_release?: ONSRetailSalesNextRelease | null
}

// BRC小売売上高データの型
export interface BRCRetailSalesDataPoint {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

export interface BRCRetailSalesNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  label: string
}

export interface BRCRetailSalesData {
  data: BRCRetailSalesDataPoint[]
  latest: BRCRetailSalesDataPoint | null
  next_release?: BRCRetailSalesNextRelease | null
}

// GfK消費者信頼感指数データの型
export interface GfKConsumerConfidenceDataPoint {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

export interface GfKConsumerConfidenceNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  label: string
}

export interface GfKConsumerConfidenceData {
  data: GfKConsumerConfidenceDataPoint[]
  latest: GfKConsumerConfidenceDataPoint | null
  next_release?: GfKConsumerConfidenceNextRelease | null
}

// UK消費ダッシュボードデータの型
export interface UKConsumerDashboardData {
  ons_retail_sales: ONSRetailSalesData | null
  brc_retail_sales: BRCRetailSalesData | null
  gfk_consumer_confidence: GfKConsumerConfidenceData | null
}

/**
 * イギリス消費ダッシュボード専用フック
 * ONS小売売上高などを取得
 */
export function useUKConsumerDashboard(): UseQueryResult<DashboardResponse<UKConsumerDashboardData>, Error> {
  return useDashboardData<UKConsumerDashboardData>('uk', 'consumer')
}

// ONS失業率データの型
export interface ONSUnemploymentDataPoint {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

export interface ONSUnemploymentNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  label: string
}

export interface ONSUnemploymentData {
  data: ONSUnemploymentDataPoint[]
  latest: ONSUnemploymentDataPoint | null
  next_release?: ONSUnemploymentNextRelease | null
}

// ONS失業給付申請件数データの型
export interface ONSClaimantCountDataPoint {
  date: string
  value: number | null
  mom?: number | null
  yoy?: number | null
}

export interface ONSClaimantCountNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  label: string
}

export interface ONSClaimantCountData {
  data: ONSClaimantCountDataPoint[]
  latest: ONSClaimantCountDataPoint | null
  next_release?: ONSClaimantCountNextRelease | null
}

// ONS平均賃金データの型
export interface ONSWagesDataPoint {
  date: string
  total_pay: number | null
  regular_pay: number | null
}

export interface ONSWagesNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  label: string
}

export interface ONSWagesMetadata {
  total_pay_title?: string
  total_pay_cdid?: string
  regular_pay_title?: string
  regular_pay_cdid?: string
  unit?: string
  source?: string
  description?: string
}

export interface ONSWagesData {
  data: ONSWagesDataPoint[]
  latest: ONSWagesDataPoint | null
  metadata?: ONSWagesMetadata
  next_release?: ONSWagesNextRelease | null
}

// ONS雇用者数データの型
export interface ONSEmploymentDataPoint {
  date: string
  value: number | null
  mom: number | null
  qoq: number | null
  yoy: number | null
}

export interface ONSEmploymentNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  label: string
}

export interface ONSEmploymentMetadata {
  title?: string
  cdid?: string
  unit?: string
  source?: string
  description?: string
}

export interface ONSEmploymentData {
  data: ONSEmploymentDataPoint[]
  latest: ONSEmploymentDataPoint | null
  metadata?: ONSEmploymentMetadata
  next_release?: ONSEmploymentNextRelease | null
}

// ONS実質平均賃金データの型
export interface ONSRealWagesDataPoint {
  date: string
  total_pay: number | null
  regular_pay: number | null
}

export interface ONSRealWagesNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  label: string
}

export interface ONSRealWagesMetadata {
  total_pay_title?: string
  total_pay_cdid?: string
  regular_pay_title?: string
  regular_pay_cdid?: string
  unit?: string
  source?: string
  description?: string
}

export interface ONSRealWagesData {
  data: ONSRealWagesDataPoint[]
  latest: ONSRealWagesDataPoint | null
  metadata?: ONSRealWagesMetadata
  next_release?: ONSRealWagesNextRelease | null
}

// ONS経済活動率データの型
export interface ONSEconomicActivityDataPoint {
  date: string
  value: number | null
}

export interface ONSEconomicActivityNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  label: string
}

export interface ONSEconomicActivityMetadata {
  title?: string
  cdid?: string
  unit?: string
  source?: string
  description?: string
}

export interface ONSEconomicActivityData {
  data: ONSEconomicActivityDataPoint[]
  latest: ONSEconomicActivityDataPoint | null
  metadata?: ONSEconomicActivityMetadata
  next_release?: ONSEconomicActivityNextRelease | null
}

// Indeed賃金トラッカー（UK）データの型
export interface IndeedWageTrackerUKDataPoint {
  date: string
  value: number | null
  ma3: number | null
}

export interface IndeedWageTrackerUKMetadata {
  source?: string
  url?: string
  data_start?: string
  country?: string
  country_code?: string
  unit?: string
}

export interface IndeedWageTrackerUKData {
  data: IndeedWageTrackerUKDataPoint[]
  latest: IndeedWageTrackerUKDataPoint | null
  metadata?: IndeedWageTrackerUKMetadata
}

// ONS労働生産性データの型
export interface ONSProductivityDataPoint {
  date: string
  value: number
  period: string
}

export interface ONSProductivityYoYDataPoint {
  date: string
  period: string
  value?: number
  yoy: number
  is_flash?: boolean  // 速報値フラグ
}

export interface ONSProductivityQoQDataPoint {
  date: string
  period: string
  value?: number
  qoq: number
  is_flash?: boolean  // 速報値フラグ
}

export interface ONSProductivitySeriesData {
  data: ONSProductivityDataPoint[]
  yoy: ONSProductivityYoYDataPoint[]
  qoq: ONSProductivityQoQDataPoint[]
  metadata?: {
    title?: string
    cdid?: string
    unit?: string
    release_date?: string
    next_release_ons?: string
  }
}

export interface ONSProductivityDMWOData {
  data: ONSProductivityDataPoint[]
  metadata?: {
    title?: string
    cdid?: string
    unit?: string
    release_date?: string
    next_release_ons?: string
  }
}

export interface ONSProductivityNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  label: string
}

export interface ONSProductivityMetadata {
  source?: string
  description?: string
  series?: {
    lzvb?: string
    a4ym?: string
    dmwo?: string
  }
  has_flash_estimate?: boolean  // 速報値が含まれているかどうか
}

export interface ONSProductivityData {
  lzvb: ONSProductivitySeriesData
  a4ym: ONSProductivitySeriesData
  dmwo: ONSProductivityDMWOData
  latest: ONSProductivityYoYDataPoint | null
  metadata?: ONSProductivityMetadata
  next_release?: ONSProductivityNextRelease | null
}

// ONS単位労働コストデータの型
export interface ONSUnitLabourCostsDataPoint {
  date: string
  value: number
  period: string
}

export interface ONSUnitLabourCostsSeriesData {
  data: ONSUnitLabourCostsDataPoint[]
  metadata?: {
    title?: string
    cdid?: string
    unit?: string
    release_date?: string
    next_release_ons?: string
  }
}

export interface ONSUnitLabourCostsMetadata {
  source?: string
  description?: string
  series?: {
    dmwn?: string
    dmwo?: string
  }
}

export interface ONSUnitLabourCostsNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  label: string
}

export interface ONSUnitLabourCostsData {
  yoy: ONSUnitLabourCostsSeriesData
  qoq: ONSUnitLabourCostsSeriesData
  latest: ONSUnitLabourCostsDataPoint | null
  metadata?: ONSUnitLabourCostsMetadata
  next_release?: ONSUnitLabourCostsNextRelease | null
}

// UK雇用ダッシュボードデータの型
export interface UKEmploymentDashboardData {
  ons_unemployment: ONSUnemploymentData | null
  ons_claimant_count: ONSClaimantCountData | null
  ons_wages: ONSWagesData | null
  ons_real_wages: ONSRealWagesData | null
  ons_employment: ONSEmploymentData | null
  ons_economic_activity: ONSEconomicActivityData | null
  ons_productivity: ONSProductivityData | null
  ons_unit_labour_costs: ONSUnitLabourCostsData | null
  indeed_wage_tracker: IndeedWageTrackerUKData | null
}

/**
 * イギリス雇用ダッシュボード専用フック
 * ONS失業率などを取得
 */
export function useUKEmploymentDashboard(): UseQueryResult<DashboardResponse<UKEmploymentDashboardData>, Error> {
  return useDashboardData<UKEmploymentDashboardData>('uk', 'employment')
}

// ONS CPI/CPIHデータの型
export interface ONSCPIHDataPoint {
  date: string
  value: number
}

export interface ONSCPIHSeriesData {
  data: ONSCPIHDataPoint[]
  metadata?: {
    code?: string
    name?: string
  }
}

export interface ONSCPIHMetadata {
  source?: string
  dataset?: string
  description?: string
}

export interface ONSCPIHNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  label: string
}

export interface ONSCPIHData {
  series: {
    cpi_all_yoy?: ONSCPIHSeriesData
    cpi_core_yoy?: ONSCPIHSeriesData
    cpi_all_mom?: ONSCPIHSeriesData
    cpi_core_mom?: ONSCPIHSeriesData
    cpih_all_yoy?: ONSCPIHSeriesData
    cpih_core_yoy?: ONSCPIHSeriesData
    // CPI Components (YoY)
    energy_yoy?: ONSCPIHSeriesData
    electricity_yoy?: ONSCPIHSeriesData
    food_yoy?: ONSCPIHSeriesData
    services_yoy?: ONSCPIHSeriesData
    goods_yoy?: ONSCPIHSeriesData
    rent_yoy?: ONSCPIHSeriesData
  }
  latest: ONSCPIHDataPoint | null
  metadata?: ONSCPIHMetadata
  next_release?: ONSCPIHNextRelease | null
}

// ONS PPIデータの型
export interface ONSPPIDataPoint {
  date: string
  value: number
}

export interface ONSPPISeriesData {
  data: ONSPPIDataPoint[]
  metadata?: {
    code?: string
    name?: string
  }
}

export interface ONSPPIMetadata {
  source?: string
  dataset?: string
  description?: string
}

export interface ONSPPINextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  label: string
}

export interface ONSPPIData {
  series: {
    output_yoy?: ONSPPISeriesData
    output_mom?: ONSPPISeriesData
    input_yoy?: ONSPPISeriesData
    input_mom?: ONSPPISeriesData
  }
  latest: ONSPPIDataPoint | null
  metadata?: ONSPPIMetadata
  next_release?: ONSPPINextRelease | null
}

// BRC店頭価格指数データの型
export interface BRCShopPriceDataPoint {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

export interface BRCShopPriceNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  label: string
}

export interface BRCShopPriceData {
  data: BRCShopPriceDataPoint[]
  latest: BRCShopPriceDataPoint | null
  next_release?: BRCShopPriceNextRelease | null
}

// BOEインフレ期待調査データの型
export interface BOEInflationAttitudesDataPoint {
  date: string
  value: number
}

export interface BOEInflationAttitudesSeriesMetadata {
  name: string
  name_en: string
}

export interface BOEInflationAttitudesSeries {
  data: BOEInflationAttitudesDataPoint[]
  metadata: BOEInflationAttitudesSeriesMetadata
}

export interface BOEInflationAttitudesLatest {
  date: string
  next_12_months?: number
  following_12_months?: number
  five_years?: number
}

export interface BOEInflationAttitudesNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  label: string
}

export interface BOEInflationAttitudesData {
  series: {
    next_12_months?: BOEInflationAttitudesSeries
    following_12_months?: BOEInflationAttitudesSeries
    five_years?: BOEInflationAttitudesSeries
  }
  latest: BOEInflationAttitudesLatest | null
  next_release?: BOEInflationAttitudesNextRelease | null
}

// UK物価ダッシュボードデータの型
export interface UKInflationDashboardData {
  ons_cpih: ONSCPIHData | null
  ons_ppi: ONSPPIData | null
  brc_shop_price: BRCShopPriceData | null
  boe_inflation_attitudes: BOEInflationAttitudesData | null
}

/**
 * イギリス物価ダッシュボード専用フック
 * ONS CPI/CPIH/PPIなどを取得
 */
export function useUKInflationDashboard(): UseQueryResult<DashboardResponse<UKInflationDashboardData>, Error> {
  return useDashboardData<UKInflationDashboardData>('uk', 'inflation')
}

// UK住宅価格指数データの型
export interface UKHousePriceDataPoint {
  date: string
  value: number
}

export interface UKHousePriceSeriesMetadata {
  name: string
  name_en: string
}

export interface UKHousePriceSeries {
  data: UKHousePriceDataPoint[]
  metadata: UKHousePriceSeriesMetadata
}

export interface UKHousePriceLatest {
  date: string
  all?: number
  detached?: number
  semi_detached?: number
  terraced?: number
  flat?: number
}

export interface UKHousePriceNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  label: string
}

export interface UKHousePriceData {
  series: {
    all?: UKHousePriceSeries
    detached?: UKHousePriceSeries
    semi_detached?: UKHousePriceSeries
    terraced?: UKHousePriceSeries
    flat?: UKHousePriceSeries
  }
  series_mom: {
    all?: UKHousePriceSeries
    detached?: UKHousePriceSeries
    semi_detached?: UKHousePriceSeries
    terraced?: UKHousePriceSeries
    flat?: UKHousePriceSeries
  }
  latest: UKHousePriceLatest | null
  next_release?: UKHousePriceNextRelease | null
}

// RICS住宅価格データの型
export interface RICSHousePriceDataPoint {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

export interface RICSHousePriceLatest {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

export interface RICSHousePriceNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  label: string
}

export interface RICSHousePriceData {
  data: RICSHousePriceDataPoint[]
  latest: RICSHousePriceLatest | null
  next_release?: RICSHousePriceNextRelease | null
}

// ハリファックス住宅価格指数データの型
export interface HalifaxHousePriceDataPoint {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

export interface HalifaxHousePriceLatest {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

export interface HalifaxHousePriceData {
  mom: HalifaxHousePriceDataPoint[]
  yoy: HalifaxHousePriceDataPoint[]
  latest_mom: HalifaxHousePriceLatest | null
  latest_yoy: HalifaxHousePriceLatest | null
  next_release?: string | null
}

// ライトムーブ住宅価格指数データの型
export interface RightmoveHousePriceDataPoint {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

export interface RightmoveHousePriceLatest {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

export interface RightmoveHousePriceData {
  mom: RightmoveHousePriceDataPoint[]
  yoy: RightmoveHousePriceDataPoint[]
  latest_mom: RightmoveHousePriceLatest | null
  latest_yoy: RightmoveHousePriceLatest | null
  next_release?: string | null
}

// ネーションワイド住宅価格指数データの型
export interface NationwideHPIDataPoint {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

export interface NationwideHPILatest {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

export interface NationwideHPIData {
  mom: NationwideHPIDataPoint[]
  yoy: NationwideHPIDataPoint[]
  latest_mom: NationwideHPILatest | null
  latest_yoy: NationwideHPILatest | null
  next_release?: string | null
}

// BoE Mortgage Lendingデータ型
export interface BoEMortgageLendingDataPoint {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

export interface BoEMortgageLendingLatest {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

export interface BoEMortgageLendingData {
  data: BoEMortgageLendingDataPoint[]
  latest: BoEMortgageLendingLatest | null
  next_release?: string | null
}

// BoE Mortgage Ratesデータ型
export interface BoEMortgageRatesDataPoint {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

export interface BoEMortgageRatesLatest {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

export interface BoEMortgageRatesData {
  cfmz6k6: BoEMortgageRatesDataPoint[]
  cfmz6jv: BoEMortgageRatesDataPoint[]
  iumtlmv: BoEMortgageRatesDataPoint[]
  latest_cfmz6k6: BoEMortgageRatesLatest | null
  latest_cfmz6jv: BoEMortgageRatesLatest | null
  latest_iumtlmv: BoEMortgageRatesLatest | null
  next_release?: string | null
}

// UK住宅ダッシュボードデータの型
export interface UKHousingDashboardData {
  uk_house_price: UKHousePriceData | null
  rics_house_price: RICSHousePriceData | null
  halifax_house_price: HalifaxHousePriceData | null
  rightmove_house_price: RightmoveHousePriceData | null
  nationwide_hpi: NationwideHPIData | null
  boe_mortgage_lending: BoEMortgageLendingData | null
  boe_mortgage_rates: BoEMortgageRatesData | null
}

/**
 * イギリス住宅ダッシュボード専用フック
 * UK House Price Indexなどを取得
 */
export function useUKHousingDashboard(): UseQueryResult<DashboardResponse<UKHousingDashboardData>, Error> {
  return useDashboardData<UKHousingDashboardData>('uk', 'housing')
}

// ECB GDPデータの型
export interface ECBGDPDataPoint {
  date: string
  value: number | null
}

export interface ECBGDPMetadata {
  last_updated: string
  source: string
  data_start: string
  unit_qoq: string
  unit_yoy: string
  frequency: string
}

export interface ECBGDPNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  datetime_cet: string
  time_cet: string
  label: string
}

export interface ECBGDPData {
  gdp_growth_qoq: ECBGDPDataPoint[]
  gdp_growth_yoy: ECBGDPDataPoint[]
  metadata: ECBGDPMetadata
  next_release?: ECBGDPNextRelease | null
}

// ECB GDP構成要素データ型
export interface ECBGDPComponentsDataPoint {
  date: string
  value: number
}

export interface ECBGDPComponentsMetadata {
  last_updated: string
  source: string
  data_start: string
  unit: string
  frequency: string
  components: {
    private_consumption: string
    government_consumption: string
    gross_fixed_capital: string
    changes_in_inventories: string
    net_exports: string
  }
}

export interface ECBGDPComponentsData {
  components: {
    private_consumption: ECBGDPComponentsDataPoint[]
    government_consumption: ECBGDPComponentsDataPoint[]
    gross_fixed_capital: ECBGDPComponentsDataPoint[]
    changes_in_inventories: ECBGDPComponentsDataPoint[]
    net_exports: ECBGDPComponentsDataPoint[]
  }
  metadata: ECBGDPComponentsMetadata
}

// ECB BLSデータ型
export interface ECBBLSDataPoint {
  date: string
  value: number
}

export interface ECBBLSMetadata {
  last_updated: string
  source: string
  data_start: string
  unit: string
  frequency: string
  description: {
    enterprises_current?: string
    enterprises_expected?: string
    consumer_current?: string
    consumer_expected?: string
    housing_current?: string
    housing_expected?: string
  }
}

export interface ECBBLSNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  datetime_cet: string
  time_cet: string
  label: string
}

export interface ECBBLSData {
  enterprises_current: ECBBLSDataPoint[]   // 現在の信用需要 - 企業向け融資
  enterprises_expected: ECBBLSDataPoint[]  // 予想信用需要 - 企業向け融資
  consumer_current: ECBBLSDataPoint[]      // 現在の信用需要 - 消費者信用
  consumer_expected: ECBBLSDataPoint[]     // 期待信用需要 - 消費者信用
  housing_current: ECBBLSDataPoint[]       // 現在の信用需要 - 住宅購入向け融資
  housing_expected: ECBBLSDataPoint[]      // 期待信用需要 - 住宅購入向け融資
  metadata: ECBBLSMetadata
  next_release?: ECBBLSNextRelease | null
}

// ECB鉱工業生産データ型
export interface ECBProductionDataPoint {
  date: string
  value: number
}

export interface ECBProductionMoMDataPoint {
  date: string
  value: number
  current_index: number
  previous_index: number
}

export interface ECBProductionMetadata {
  last_updated: string
  source: string
  data_start: string
  unit_index: string
  unit_mom: string
  unit_yoy: string
  frequency: string
  series_unadjusted: string
  series_wda: string
}

export interface ECBProductionNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  datetime_cet: string
  time_cet: string
  label: string
}

export interface ECBProductionData {
  production_wda: ECBProductionDataPoint[]
  mom_change: ECBProductionMoMDataPoint[]
  yoy_change: ECBProductionDataPoint[]
  metadata: ECBProductionMetadata
  next_release?: ECBProductionNextRelease | null
}

// Eurostat ESIデータ型
export interface EurostatESIDataPoint {
  date: string
  value: number
}

export interface EurostatESINextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  datetime_cet: string
  time_cet: string
  label: string
  estimate: number | null
}

export interface EurostatESIMetadata {
  source: string
  dataset: string
  indicator: string
  unit: string
  frequency: string
  seasonal_adjustment: string
  countries: {
    euro_area: string
    germany: string
    france: string
    italy: string
  }
}

export interface EurostatESIData {
  euro_area: EurostatESIDataPoint[]
  germany: EurostatESIDataPoint[]
  france: EurostatESIDataPoint[]
  italy: EurostatESIDataPoint[]
  metadata: EurostatESIMetadata
  next_release?: EurostatESINextRelease | null
}

// 欧州経済政策不確実性指数データ型
export interface EuroPolicyUncertaintyDataPoint {
  date: string
  value: number
}

export interface EuroPolicyUncertaintyMetadata {
  source: string
  series_id: string
  indicator: string
  unit: string
  frequency: string
  description: string
}

export interface EuroPolicyUncertaintyData {
  data: EuroPolicyUncertaintyDataPoint[]
  latest: EuroPolicyUncertaintyDataPoint | null
  metadata: EuroPolicyUncertaintyMetadata
}

// ECB小売売上高データ型
export interface ECBRetailTradeDataPoint {
  date: string
  value: number
}

export interface ECBRetailTradeMetadata {
  source: string
  dataflow: string
  indicator: string
  unit: string
  adjustment_mom: string
  adjustment_yoy: string
}

export interface ECBRetailTradeData {
  retail_yoy: ECBRetailTradeDataPoint[]
  retail_mom: ECBRetailTradeDataPoint[]
  metadata: ECBRetailTradeMetadata
  next_release?: { date: string; label?: string; time_jst?: string } | null
}

// ドイツ小売売上高データ型
export interface GermanyRetailSalesDataPoint {
  date: string
  value: number
}

export interface GermanyRetailSalesMetadata {
  source: string
  country: string
  table: string
  description: string
  unit: string
}

export interface GermanyRetailSalesData {
  retail_sales_yoy: GermanyRetailSalesDataPoint[]
  retail_sales_mom: GermanyRetailSalesDataPoint[]
  metadata: GermanyRetailSalesMetadata
  next_release?: { date: string; label?: string; time_jst?: string } | null
}

// ドイツGDP成長率データの型
export interface GermanyGDPGrowthData {
  gdp_growth_qoq: GermanyGDPGrowthItem[]
  gdp_growth_yoy: GermanyGDPGrowthItem[]
  metadata: GermanyGDPGrowthMetadata
  next_release?: { date: string; label?: string; time_jst?: string } | null
}

export interface GermanyGDPGrowthItem {
  date: string
  value: number
  forecast?: number | null
  previous?: number | null
  source?: string
}

export interface GermanyGDPGrowthMetadata {
  source?: string
  country?: string
  table?: string
  description?: string
  unit?: string
  adjustment?: string
}

// ドイツ鉱工業生産データの型
export interface GermanyIndustrialProductionData {
  mom: GermanyIndustrialProductionItem[]
  yoy: GermanyIndustrialProductionItem[]
  latest_mom: GermanyIndustrialProductionItem | null
  latest_yoy: GermanyIndustrialProductionItem | null
  next_release?: GermanyIndustrialProductionNextRelease | null
}

export interface GermanyIndustrialProductionNextRelease {
  date: string
  label?: string
  time_jst?: string
  datetime_jst?: string
  datetime_cet?: string
  time_cet?: string
}

export interface GermanyIndustrialProductionItem {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

// ドイツ製造業新規受注データの型
export interface GermanyFactoryOrdersData {
  mom: GermanyFactoryOrdersItem[]
  yoy: GermanyFactoryOrdersItem[]
  domestic_mom: GermanyFactoryOrdersItem[]
  domestic_yoy: GermanyFactoryOrdersItem[]
  foreign_mom: GermanyFactoryOrdersItem[]
  foreign_yoy: GermanyFactoryOrdersItem[]
  index_total: GermanyFactoryOrdersItem[]
  index_domestic: GermanyFactoryOrdersItem[]
  index_foreign: GermanyFactoryOrdersItem[]
  latest_mom: GermanyFactoryOrdersItem | null
  latest_yoy: GermanyFactoryOrdersItem | null
  next_release?: GermanyFactoryOrdersNextRelease | null
}

export interface GermanyFactoryOrdersNextRelease {
  date: string
  label?: string
  time_jst?: string
  datetime_jst?: string
  datetime_cet?: string
  time_cet?: string
}

export interface GermanyFactoryOrdersItem {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

// ユーロ圏経済ダッシュボードデータの型
export interface EurozoneEconomyData {
  ecb_gdp: ECBGDPData | null
  ecb_gdp_components: ECBGDPComponentsData | null
  ecb_bls: ECBBLSData | null
  ecb_production: ECBProductionData | null
  eurostat_esi: EurostatESIData | null
  euro_policy_uncertainty: EuroPolicyUncertaintyData | null
  eu_pmi: EUPMIData | null
  germany_gdp_growth: GermanyGDPGrowthData | null
  germany_industrial_production: GermanyIndustrialProductionData | null
  germany_factory_orders: GermanyFactoryOrdersData | null
  zew_economic_sentiment: ZEWEconomicSentimentData | null
  ifo_business_climate: IfoBusinessClimateData | null
  germany_pmi: GermanyPMIData | null
  france_pmi: FrancePMIData | null
  ecb_adjusted_loans: ECBAdjustedLoansData | null
  ecb_ciss: ECBCISSData | null
  eu_international_trade: EUInternationalTradeData | null
  eu_terms_of_trade: EUTermsOfTradeData | null
  ecb_current_account: ECBCurrentAccountData | null
  france_business_confidence: FranceBusinessConfidenceData | null
  eu_government_debt_to_gdp_ratio: EUGovernmentDebtToGdpRatioData | null
}

// EU政府債務残高対GDP比データの型
export interface EUGovernmentDebtToGdpRatioDataPoint {
  date: string
  value: number // % of GDP
  quarter?: string
}

export interface EUGovernmentDebtToGdpRatioNextRelease {
  date: string
  datetime_jst?: string
  time_jst?: string
  label?: string
}

export interface EUGovernmentDebtToGdpRatioData {
  countries: Record<string, EUGovernmentDebtToGdpRatioDataPoint[]>
  ea20: EUGovernmentDebtToGdpRatioDataPoint[]
  qoq_change?: EUGovernmentDebtToGdpRatioDataPoint[]
  latest: EUGovernmentDebtToGdpRatioDataPoint | null
  metadata: {
    title?: string
    source?: string
    dataset?: string
    unit?: string
    description?: string
    updated?: string
  }
  next_release?: EUGovernmentDebtToGdpRatioNextRelease | null
}

// フランス企業信頼感データの型
export interface FranceBusinessConfidenceData {
  data: FranceBusinessConfidenceItem[]
  latest: FranceBusinessConfidenceItem | null
  metadata: Record<string, unknown>
  next_release: FranceBusinessConfidenceNextRelease | null
}

export interface FranceBusinessConfidenceItem {
  date: string
  value: number
  forecast?: number | null
  previous?: number | null
}

export interface FranceBusinessConfidenceNextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  label?: string
}

// ECB経常収支データの型
export interface ECBCurrentAccountData {
  data: ECBCurrentAccountItem[]
  latest: ECBCurrentAccountItem | null
  metadata: Record<string, unknown>
  next_release: ECBCurrentAccountNextRelease | null
}

export interface ECBCurrentAccountItem {
  date: string
  value: number
}

export interface ECBCurrentAccountNextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  label?: string
}

// ZEW景況感指数データの型
export interface ZEWEconomicSentimentData {
  sentiment: ZEWEconomicSentimentItem[]
  situation: ZEWEconomicSentimentItem[]
  latest_sentiment: ZEWEconomicSentimentItem | null
  latest_situation: ZEWEconomicSentimentItem | null
  next_release?: ZEWEconomicSentimentNextRelease | null
}

export interface ZEWEconomicSentimentItem {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

export interface ZEWEconomicSentimentNextRelease {
  date: string
  label?: string
  time_jst?: string
  datetime_jst?: string
  datetime_cet?: string
  time_cet?: string
}

// IFO企業景況感指数データの型
export interface IfoBusinessClimateData {
  climate: IfoBusinessClimateItem[]
  current: IfoBusinessClimateItem[]
  expectations: IfoBusinessClimateItem[]
  latest_climate: IfoBusinessClimateItem | null
  latest_current: IfoBusinessClimateItem | null
  latest_expectations: IfoBusinessClimateItem | null
  next_release?: IfoBusinessClimateNextRelease | null
}

export interface IfoBusinessClimateItem {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

export interface IfoBusinessClimateNextRelease {
  date: string
  label?: string
  time_jst?: string
  datetime_jst?: string
  datetime_cet?: string
  time_cet?: string
}

// ドイツ S&P Global PMIデータの型（製造業/サービス業/総合）
export interface GermanyPMIData {
  manufacturing: GermanyPMISeriesData | null
  services: GermanyPMISeriesData | null
  composite: GermanyPMISeriesData | null
  next_release: GermanyPMINextRelease | null
}

export interface GermanyPMISeriesData {
  data: GermanyPMIItem[]
  latest: GermanyPMIItem | null
}

export interface GermanyPMIItem {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

export interface GermanyPMINextRelease {
  date: string
  datetime_utc?: string
  datetime_cet?: string
  time_cet?: string
  label?: string
  estimate?: number | null
}

// フランス HCOB PMIデータの型（製造業/サービス業/総合）
export interface FrancePMIData {
  manufacturing: FrancePMISeriesData | null
  services: FrancePMISeriesData | null
  composite: FrancePMISeriesData | null
  next_release: FrancePMINextRelease | null
}

export interface FrancePMISeriesData {
  data: FrancePMIItem[]
  latest: FrancePMIItem | null
}

export interface FrancePMIItem {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

export interface FrancePMINextRelease {
  date: string
  datetime_utc?: string
  datetime_cet?: string
  time_cet?: string
  label?: string
  estimate?: number | null
}

// ユーロ圏 HCOB PMIデータの型（製造業/サービス業/総合）
export interface EUPMIData {
  manufacturing: EUPMISeriesData | null
  services: EUPMISeriesData | null
  composite: EUPMISeriesData | null
  next_release: EUPMINextRelease | null
}

export interface EUPMISeriesData {
  data: EUPMIItem[]
  latest: EUPMIItem | null
}

export interface EUPMIItem {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

export interface EUPMINextRelease {
  date: string
  datetime_utc?: string
  datetime_cet?: string
  time_cet?: string
  label?: string
  estimate?: number | null
}

// EU国際貿易データの型
export interface EUInternationalTradeData {
  balance: EUInternationalTradeItem[]
  exports: EUInternationalTradeItem[]
  imports: EUInternationalTradeItem[]
  balance_mom: EUInternationalTradeItem[]
  balance_mom_diff: EUInternationalTradeItem[]
  balance_yoy: EUInternationalTradeItem[]
  exports_mom: EUInternationalTradeItem[]
  exports_yoy: EUInternationalTradeItem[]
  imports_mom: EUInternationalTradeItem[]
  imports_yoy: EUInternationalTradeItem[]
  latest_balance: EUInternationalTradeItem | null
  latest_exports: EUInternationalTradeItem | null
  latest_imports: EUInternationalTradeItem | null
  latest_balance_mom: EUInternationalTradeItem | null
  latest_balance_mom_diff: EUInternationalTradeItem | null
  latest_balance_yoy: EUInternationalTradeItem | null
  latest_exports_mom: EUInternationalTradeItem | null
  latest_exports_yoy: EUInternationalTradeItem | null
  latest_imports_mom: EUInternationalTradeItem | null
  latest_imports_yoy: EUInternationalTradeItem | null
  metadata: Record<string, unknown>
  next_release: EUInternationalTradeNextRelease | null
}

export interface EUInternationalTradeItem {
  date: string
  value: number
}

export interface EUInternationalTradeNextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  datetime_cet?: string
  time_cet?: string
  label?: string
}

// EU交易条件データの型
export interface EUTermsOfTradeData {
  terms_of_trade: EUTermsOfTradeItem[]
  export_uv: EUTermsOfTradeItem[]
  import_uv: EUTermsOfTradeItem[]
  latest_tot: EUTermsOfTradeItem | null
  latest_export_uv: EUTermsOfTradeItem | null
  latest_import_uv: EUTermsOfTradeItem | null
  metadata: Record<string, unknown>
  next_release: EUTermsOfTradeNextRelease | null
}

export interface EUTermsOfTradeItem {
  date: string
  value: number
}

export interface EUTermsOfTradeNextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  datetime_cet?: string
  time_cet?: string
  label?: string
}

/**
 * ユーロ圏経済ダッシュボード専用フック
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useEurozoneEconomyDashboard()
 *
 * if (data) {
 *   console.log(data.data.ecb_gdp) // ECB GDPデータ
 * }
 * ```
 */
export function useEurozoneEconomyDashboard(): UseQueryResult<DashboardResponse<EurozoneEconomyData>, Error> {
  return useDashboardData<EurozoneEconomyData>('eurozone', 'economy')
}

// ユーロ圏消費ダッシュボードデータの型
export interface EurozoneConsumerData {
  ecb_retail_trade: ECBRetailTradeData | null
  eurostat_consumer_confidence: EurostatConsumerConfidenceData | null
  germany_retail_sales: GermanyRetailSalesData | null
  germany_consumer_confidence_gfk: GermanyConsumerConfidenceGfKData | null
}

// ドイツGfK消費者信頼感指数データの型
export interface GermanyConsumerConfidenceGfKData {
  data: GermanyConsumerConfidenceGfKItem[]
  latest: GermanyConsumerConfidenceGfKItem | null
  metadata: Record<string, unknown>
  next_release: GermanyConsumerConfidenceGfKNextRelease | null
}

export interface GermanyConsumerConfidenceGfKItem {
  date: string
  value: number
  forecast?: number | null
  previous?: number | null
}

export interface GermanyConsumerConfidenceGfKNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  label: string
}

// Eurostat消費者信頼感データの型
export interface EurostatConsumerConfidenceData {
  data: EurostatConsumerConfidenceItem[]
  latest: EurostatConsumerConfidenceItem | null
  metadata: Record<string, unknown>
  next_release: EurostatConsumerConfidenceNextRelease | null
}

export interface EurostatConsumerConfidenceItem {
  date: string
  value: number
}

export interface EurostatConsumerConfidenceNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  label: string
}

/**
 * ユーロ圏消費ダッシュボード専用フック
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useEurozoneConsumerDashboard()
 *
 * if (data) {
 *   console.log(data.data.ecb_retail_trade) // ECB小売売上高データ
 * }
 * ```
 */
export function useEurozoneConsumerDashboard(): UseQueryResult<DashboardResponse<EurozoneConsumerData>, Error> {
  return useDashboardData<EurozoneConsumerData>('eurozone', 'consumer')
}

// ECB CES賃金期待データの型
export interface ECBCesWageExpectationsData {
  data: ECBCesWageExpectationsItem[]
  latest: ECBCesWageExpectationsItem | null
  next_release: { date: string; datetime_jst?: string; time_jst?: string; label?: string } | null
}

export interface ECBCesWageExpectationsItem {
  date: string
  value: number  // % change (household income expectations 12m ahead)
}

// ユーロ圏雇用ダッシュボードデータの型
export interface EurozoneEmploymentData {
  ecb_unemployment: ECBUnemploymentData | null
  ecb_employment: ECBEmploymentData | null
  ecb_labor_productivity: ECBLaborProductivityData | null
  ecb_unit_labour_cost: ECBUnitLabourCostData | null
  eurostat_wages: EurostatWagesData | null
  ecb_negotiated_wages: ECBNegotiatedWagesData | null
  indeed_euro_wage: IndeedEuroWageData | null
  germany_unemployment: GermanyUnemploymentData | null
  eurostat_job_vacancy: EurostatJobVacancyData | null
  ecb_ces_wage_expectations: ECBCesWageExpectationsData | null
}

// ECB失業率データの型
export interface ECBUnemploymentData {
  unemployment_rate: ECBUnemploymentItem[]
  metadata: Record<string, unknown>
  next_release: ECBUnemploymentNextRelease | null
}

export interface ECBUnemploymentItem {
  date: string
  value: number
}

export interface ECBUnemploymentNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  datetime_cet: string
  time_cet: string
  label: string
  estimate: number | null
}

// ECB雇用者数変化データの型
export interface ECBEmploymentData {
  employment_qoq: ECBEmploymentItem[]
  employment_yoy: ECBEmploymentItem[]
  metadata: Record<string, unknown>
  next_release: ECBEmploymentNextRelease | null
}

export interface ECBEmploymentItem {
  date: string
  value: number
}

export interface ECBEmploymentNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  datetime_cet: string
  time_cet: string
  label: string
  estimate: number | null
}

// ECB労働生産性データの型
export interface ECBLaborProductivityData {
  per_hour: ECBLaborProductivityItem[]
  per_person: ECBLaborProductivityItem[]
  per_hour_yoy: ECBLaborProductivityItem[]
  per_person_yoy: ECBLaborProductivityItem[]
  metadata: Record<string, unknown>
  next_release: ECBLaborProductivityNextRelease | null
}

export interface ECBLaborProductivityItem {
  date: string
  value: number
}

export interface ECBLaborProductivityNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  datetime_cet: string
  time_cet: string
  label: string
  estimate: number | null
}

// ECB労働コスト指数データの型
export interface ECBUnitLabourCostData {
  unit_labour_cost: ECBUnitLabourCostItem[]
  unit_labour_cost_yoy: ECBUnitLabourCostItem[]
  unit_labour_cost_qoq: ECBUnitLabourCostItem[]
  metadata: Record<string, unknown>
  next_release: ECBUnitLabourCostNextRelease | null
}

export interface ECBUnitLabourCostItem {
  date: string
  value: number
}

export interface ECBUnitLabourCostNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  datetime_cet: string
  time_cet: string
  label: string
  estimate: number | null
}

// Eurostat賃金・給与データの型
export interface EurostatWagesData {
  data: EurostatWagesItem[]
  latest: EurostatWagesItem | null
  metadata: Record<string, unknown>
  next_release: EurostatWagesNextRelease | null
}

export interface EurostatWagesItem {
  date: string
  value: number
}

export interface EurostatWagesNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  datetime_cet: string
  time_cet: string
  label: string
  estimate: number | null
}

// ECB交渉妥結賃金データの型
export interface ECBNegotiatedWagesData {
  data: ECBNegotiatedWagesItem[]
  latest: ECBNegotiatedWagesItem | null
  metadata: Record<string, unknown>
  next_release: ECBNegotiatedWagesNextRelease | null
}

export interface ECBNegotiatedWagesItem {
  date: string
  value: number
}

export interface ECBNegotiatedWagesNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  datetime_cet: string
  time_cet: string
  label: string
  estimate: number | null
}

// Indeed賃金トラッカー（ユーロ圏）データの型
export interface IndeedEuroWageData {
  germany: IndeedEuroWageItem[]
  france: IndeedEuroWageItem[]
  euro_area: IndeedEuroWageItem[]
  latest: IndeedEuroWageItem | null
  metadata: Record<string, unknown>
}

export interface IndeedEuroWageItem {
  date: string
  value: number
  ma3: number | null
}

// ドイツ失業率データの型
export interface GermanyUnemploymentData {
  unemployment_rate: GermanyUnemploymentItem[]
  metadata: Record<string, unknown>
  next_release: GermanyUnemploymentNextRelease | null
}

export interface GermanyUnemploymentItem {
  date: string
  value: number
}

export interface GermanyUnemploymentNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  datetime_cet: string
  time_cet: string
  label: string
  estimate: number | null
}

// Eurostat求人欠員率データの型
export interface EurostatJobVacancyData {
  data: EurostatJobVacancyItem[]
  latest: EurostatJobVacancyItem | null
  metadata: Record<string, unknown>
  next_release: EurostatJobVacancyNextRelease | null
}

export interface EurostatJobVacancyItem {
  date: string
  value: number
}

export interface EurostatJobVacancyNextRelease {
  date: string
  label: string
  month: number
  year: number
}

/**
 * ユーロ圏雇用ダッシュボード専用フック
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useEurozoneEmploymentDashboard()
 *
 * if (data) {
 *   console.log(data.data.ecb_unemployment) // ECB失業率データ
 * }
 * ```
 */
export function useEurozoneEmploymentDashboard(): UseQueryResult<DashboardResponse<EurozoneEmploymentData>, Error> {
  return useDashboardData<EurozoneEmploymentData>('eurozone', 'employment')
}

// ユーロ圏インフレダッシュボードデータの型
export interface EurozoneInflationData {
  ecb_hicp: ECBHICPData | null
  ecb_ppi: ECBPPIData | null
  ecb_spf: ECBSPFData | null
  ecb_spf_core: ECBSPFCoreData | null
  germany_cpi: GermanyCPIData | null
  germany_ppi: GermanyPPIData | null
  ecb_inflation_expectations: ECBInflationExpectationsData | null
  eu_import_prices: EUImportPricesData | null
  spain_hicp_cpi: SpainHICPCPIData | null
}

// ECB HICPデータの型
export interface ECBHICPData {
  annual_rates: ECBHICPAnnualRates
  monthly_changes: ECBHICPMonthlyChanges
  breakdown_annual_rates: ECBHICPBreakdownAnnualRates
  metadata: Record<string, unknown>
  next_release: ECBHICPNextRelease | null
}

export interface ECBHICPAnnualRates {
  total_hicp: ECBHICPItem[]
  core_hicp: ECBHICPItem[]
  core_excl_unprocessed_food: ECBHICPItem[]
}

export interface ECBHICPMonthlyChanges {
  total_hicp: ECBHICPItem[]
  core_hicp: ECBHICPItem[]
}

export interface ECBHICPBreakdownAnnualRates {
  goods: ECBHICPItem[]
  food: ECBHICPItem[]
  energy: ECBHICPItem[]
  services: ECBHICPItem[]
}

export interface ECBHICPItem {
  date: string
  value: number | null
}

export interface ECBHICPNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  datetime_cet: string
  time_cet: string
  label: string
  estimate: number | null
}

// ECB PPIデータの型
export interface ECBPPIData {
  annual_rates: ECBPPIRates
  monthly_changes: ECBPPIRates
  metadata: Record<string, unknown>
  next_release: ECBPPINextRelease | null
}

export interface ECBPPIRates {
  ppi: ECBPPIItem[]
}

export interface ECBPPIItem {
  date: string
  value: number | null
}

export interface ECBPPINextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  datetime_cet: string
  time_cet: string
  label: string
  estimate: number | null
}

// ECB SPFデータの型
export interface ECBSPFData {
  inflation_expectations: ECBSPFInflationExpectations
  metadata: Record<string, unknown>
  next_release: string | null
}

export interface ECBSPFInflationExpectations {
  hicp_12m: ECBSPFItem[]
  hicp_24m: ECBSPFItem[]
  hicp_lt: ECBSPFItem[]
}

export interface ECBSPFItem {
  date: string
  value: number
}

// ECB SPF Coreデータの型
export interface ECBSPFCoreData {
  inflation_expectations: ECBSPFCoreInflationExpectations
  metadata: Record<string, unknown>
  next_release: string | null
}

export interface ECBSPFCoreInflationExpectations {
  core_12m: ECBSPFCoreItem[]
  core_24m: ECBSPFCoreItem[]
  core_lt: ECBSPFCoreItem[]
}

export interface ECBSPFCoreItem {
  date: string
  value: number
}

// ドイツCPI/HICPデータの型
export interface GermanyCPIData {
  cpi_yoy: GermanyCPIItem[]
  cpi_mom: GermanyCPIItem[]
  hicp_yoy: GermanyCPIItem[]
  hicp_mom: GermanyCPIItem[]
  metadata: Record<string, unknown>
  next_release: GermanyCPINextRelease | null
}

export interface GermanyCPIItem {
  date: string
  value: number | null
  forecast: number | null
  previous: number | null
  period: string | null
  event: string | null
}

export interface GermanyCPINextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  datetime_cet: string
  time_cet: string
  label: string
  estimate: number | null
}

// ドイツPPIデータの型
export interface GermanyPPIData {
  ppi_yoy: GermanyPPIItem[]
  ppi_mom: GermanyPPIItem[]
  metadata: Record<string, unknown>
  next_release: GermanyPPINextRelease | null
}

export interface GermanyPPIItem {
  date: string
  value: number | null
}

export interface GermanyPPINextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  datetime_cet: string
  time_cet: string
  label: string
  estimate: number | null
}

// ECB Consumer Expectations Survey インフレ期待データの型
export interface ECBInflationExpectationsData {
  inflation_12m: ECBInflationExpectationsItem[]
  inflation_3y: ECBInflationExpectationsItem[]
  inflation_5y: ECBInflationExpectationsItem[]
  metadata: Record<string, unknown>
  next_release: ECBInflationExpectationsNextRelease | null
}

export interface ECBInflationExpectationsItem {
  date: string
  value: number
}

export interface ECBInflationExpectationsNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  datetime_cet: string
  time_cet: string
  label: string
  estimate: number | null
}

// EU輸入物価データの型
export interface EUImportPricesData {
  yoy: EUImportPricesItem[]
  mom: EUImportPricesItem[]
  latest_yoy: EUImportPricesItem | null
  latest_mom: EUImportPricesItem | null
  metadata: Record<string, unknown>
  next_release: EUImportPricesNextRelease | null
}

export interface EUImportPricesItem {
  date: string
  value: number
}

export interface EUImportPricesNextRelease {
  date: string
  datetime_jst: string
  time_jst: string
  label: string
}

// スペインHICP/CPIデータの型
export interface SpainHICPCPIData {
  cpi_mom: SpainHICPCPIItem[]
  cpi_yoy: SpainHICPCPIItem[]
  core_cpi_mom: SpainHICPCPIItem[]
  core_cpi_yoy: SpainHICPCPIItem[]
  hicp_mom: SpainHICPCPIItem[]
  hicp_yoy: SpainHICPCPIItem[]
  latest_cpi_yoy: SpainHICPCPIItem | null
  latest_hicp_yoy: SpainHICPCPIItem | null
  metadata: Record<string, unknown>
  next_release: SpainHICPCPINextRelease | null
}

export interface SpainHICPCPIItem {
  date: string
  value: number
}

export interface SpainHICPCPINextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  datetime_cet: string
  time_cet: string
  label: string
  estimate: number | null
}

/**
 * ユーロ圏インフレダッシュボード専用フック
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useEurozoneInflationDashboard()
 *
 * if (data) {
 *   console.log(data.data.ecb_hicp) // ECB HICPデータ
 * }
 * ```
 */
export function useEurozoneInflationDashboard(): UseQueryResult<DashboardResponse<EurozoneInflationData>, Error> {
  return useDashboardData<EurozoneInflationData>('eurozone', 'inflation')
}

// ============================================================================
// スイス金融政策ダッシュボード
// ============================================================================

// SNB政策金利データの型
export interface ChSnbRateItem {
  date: string
  value: number
  forecast?: number | null
  previous?: number | null
}

export interface ChSnbRateNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  datetime_zurich?: string
  time_zurich?: string
  label: string
  estimate?: number | null
}

export interface ChSnbRateData {
  data: ChSnbRateItem[]
  latest: ChSnbRateItem | null
  metadata: Record<string, unknown>
  next_release: ChSnbRateNextRelease | null
}

// SNBインフレ見通しリリース
export interface ChInflationForecastRelease {
  release_date: string
  observed_image: string | null
  forecast_image: string | null
  observed_url: string
  forecast_url: string
}

export interface ChInflationForecastData {
  latest: ChInflationForecastRelease | null
  metadata: Record<string, unknown>
  next_release: ChSnbRateNextRelease | null
}

// スイスCPIデータアイテム
export interface ChCPIItem {
  date: string
  cpi_yoy: number | null
  cpi_mom: number | null
  core1_yoy?: number | null
  core1_mom?: number | null
  core2_yoy?: number | null
  core2_mom?: number | null
}

// スイスCPIデータ
export interface ChCPIData {
  data: ChCPIItem[]
  latest: ChCPIItem | null
  metadata: Record<string, unknown>
  next_release: ChSnbRateNextRelease | null
}

// SNBバランスシートデータアイテム
export interface SNBBalanceSheetItem {
  date: string
  value: number
}

// SNBバランスシートデータ
export interface SNBBalanceSheetData {
  data: SNBBalanceSheetItem[]
  latest: SNBBalanceSheetItem | null
  metadata: {
    source: string
    indicator: string
    description: string
    unit: string
  }
  next_release: string | null
}

// SNB当座預金データアイテム
export interface SNBSightDepositsItem {
  date: string
  value: number
}

// SNB当座預金データ
export interface SNBSightDepositsData {
  data: SNBSightDepositsItem[]
  latest: SNBSightDepositsItem | null
  metadata: {
    source: string
    indicator: string
    description: string
    unit: string
  }
  next_release: string | null
  last_publishing_date: string | null
}

// 外貨準備データ項目
export interface ForeignCurrencyReservesItem {
  date: string
  chf: number | null
  usd: number | null
}

// 外貨準備データ
export interface ForeignCurrencyReservesData {
  data: ForeignCurrencyReservesItem[]
  latest: ForeignCurrencyReservesItem | null
  metadata: {
    source: string
    indicator: string
    description: string
    unit: string
  }
  next_release: string | null
  last_publishing_date: string | null
}

// マネタリーベースデータ項目
export interface MonetaryBaseItem {
  date: string
  value: number
}

// マネタリーベースデータ
export interface MonetaryBaseData {
  data: MonetaryBaseItem[]
  latest: MonetaryBaseItem | null
  metadata: {
    source: string
    indicator: string
    description: string
    unit: string
  }
  next_release: string | null
  last_publishing_date: string | null
}

// 貨幣総量M2データ項目
export interface MonetaryAggregateM2Item {
  date: string
  value: number | null
  yoy: number | null
}

// 貨幣総量M2データ
export interface MonetaryAggregateM2Data {
  data: MonetaryAggregateM2Item[]
  latest: MonetaryAggregateM2Item | null
  metadata: {
    source: string
    indicator: string
    description: string
    unit: string
  }
  next_release: string | null
  last_publishing_date: string | null
}

// スイス金融政策ダッシュボードデータの型
export interface SwitzerlandPolicyData {
  ch_snb_rate: ChSnbRateData | null
  ch_inflation_forecast: ChInflationForecastData | null
  ch_cpi: ChCPIData | null
  snb_balance_sheet: SNBBalanceSheetData | null
  snb_sight_deposits: SNBSightDepositsData | null
  foreign_currency_reserves: ForeignCurrencyReservesData | null
  monetary_base: MonetaryBaseData | null
  monetary_aggregate_m2: MonetaryAggregateM2Data | null
}

/**
 * スイス金融政策ダッシュボード専用フック
 * SNB政策金利などを取得
 */
export function useSwitzerlandPolicyDashboard(): UseQueryResult<DashboardResponse<SwitzerlandPolicyData>, Error> {
  return useDashboardData<SwitzerlandPolicyData>('switzerland', 'policy')
}

// スイスPPIデータ項目
export interface ChPPIItem {
  date: string
  ppi_yoy: number | null
  ppi_mom: number | null
}

// スイスPPIデータ
export interface ChPPIData {
  data: ChPPIItem[]
  latest: ChPPIItem | null
  metadata: Record<string, unknown>
  next_release: ChSnbRateNextRelease | null
}

// スイス物価ダッシュボードデータの型
export interface SwitzerlandInflationData {
  ch_cpi: ChCPIData | null
  ch_ppi: ChPPIData | null
}

/**
 * スイス物価ダッシュボード専用フック
 * CPIなどを取得
 */
export function useSwitzerlandInflationDashboard(): UseQueryResult<DashboardResponse<SwitzerlandInflationData>, Error> {
  return useDashboardData<SwitzerlandInflationData>('switzerland', 'inflation')
}

// KOF経済バロメーターデータ項目
export interface KofBarometerItem {
  date: string
  value: number | null
}

// KOF経済バロメーターデータ
export interface KofBarometerData {
  data: KofBarometerItem[]
  latest: KofBarometerItem | null
  metadata: Record<string, unknown>
  next_release: ChSnbRateNextRelease | null
}

// SECO消費者景況感データ項目
export interface CHConsumerSentimentItem {
  date: string
  value: number | null
}

// SECO消費者景況感データ
export interface CHConsumerSentimentData {
  data: CHConsumerSentimentItem[]
  latest: CHConsumerSentimentItem | null
  metadata: Record<string, unknown>
  next_release: ChSnbRateNextRelease | null
}

// スイス小売売上高データ項目
export interface CHRetailTradeItem {
  date: string
  mom: number | null
  yoy: number | null
}

// スイス小売売上高データ
export interface CHRetailTradeData {
  data: CHRetailTradeItem[]
  latest: CHRetailTradeItem | null
  metadata: Record<string, unknown>
  next_release: ChSnbRateNextRelease | null
}

// スイス消費者ダッシュボードデータの型
export interface SwitzerlandConsumerData {
  kof_economic_barometer: KofBarometerData | null
  ch_consumer_sentiment: CHConsumerSentimentData | null
  ch_households_and_npish: CHHouseholdsAndNpishData | null
  ch_retail_trade: CHRetailTradeData | null
}

/**
 * スイス消費者ダッシュボード専用フック
 * KOF経済バロメーターなどを取得
 */
export function useSwitzerlandConsumerDashboard(): UseQueryResult<DashboardResponse<SwitzerlandConsumerData>, Error> {
  return useDashboardData<SwitzerlandConsumerData>('switzerland', 'consumer')
}

// スイス失業率データ項目
export interface CHUnemploymentRateItem {
  date: string
  value: number | null
}

// スイス失業率データ
export interface CHUnemploymentRateData {
  data: CHUnemploymentRateItem[]
  latest: CHUnemploymentRateItem | null
  metadata: Record<string, unknown>
  next_release: ChSnbRateNextRelease | null
}

// スイス求人情報データ項目
export interface CHJobVacanciesItem {
  date: string
  value: number | null
}

// スイス求人情報データ
export interface CHJobVacanciesData {
  data: CHJobVacanciesItem[]
  latest: CHJobVacanciesItem | null
  metadata: Record<string, unknown>
  next_release: ChSnbRateNextRelease | null
}

// スイス名目賃金上昇率データ項目
export interface CHNominalWageGrowthItem {
  date: string
  value: number | null
  period?: string  // 元の四半期表記（例: "2024-Q3"）
}

// スイス名目賃金上昇率データ
export interface CHNominalWageGrowthData {
  data: CHNominalWageGrowthItem[]
  latest: CHNominalWageGrowthItem | null
  metadata: Record<string, unknown>
  next_release: ChSnbRateNextRelease | null
}

// スイス雇用ダッシュボードデータの型
export interface SwitzerlandEmploymentData {
  ch_unemployment_rate: CHUnemploymentRateData | null
  ch_job_vacancies: CHJobVacanciesData | null
  ch_nominal_wage_growth: CHNominalWageGrowthData | null
}

/**
 * スイス雇用ダッシュボード専用フック
 * スイス失業率などを取得
 */
export function useSwitzerlandEmploymentDashboard(): UseQueryResult<DashboardResponse<SwitzerlandEmploymentData>, Error> {
  return useDashboardData<SwitzerlandEmploymentData>('switzerland', 'employment')
}

// スイスGDP成長率データ項目
export interface CHGrowthRateItem {
  date: string
  qoq: number | null  // 前期比（季節調整 + スポーツ調整済み）
  yoy: number | null  // 前年比（調整前）
  annualized: number | null  // 年率換算
}

// スイスGDP成長率データ
export interface CHGrowthRateData {
  data: CHGrowthRateItem[]
  latest: CHGrowthRateItem | null
  metadata: Record<string, unknown>
  next_release: ChSnbRateNextRelease | null
}

// スイス鉱工業生産 月次データ項目
export interface CHIndustrialProductionMonthlyItem {
  date: string
  mom: number | null  // 前月比
  yoy: number | null  // 前年比
}

// スイス鉱工業生産 四半期データ項目
export interface CHIndustrialProductionQuarterlyItem {
  date: string
  qoq: number | null  // 前期比
  yoy: number | null  // 前年比
}

// スイス鉱工業生産データ
export interface CHIndustrialProductionData {
  monthly_data: CHIndustrialProductionMonthlyItem[]
  quarterly_data: CHIndustrialProductionQuarterlyItem[]
  latest_monthly: CHIndustrialProductionMonthlyItem | null
  latest_quarterly: CHIndustrialProductionQuarterlyItem | null
  metadata: Record<string, unknown>
  next_release: ChSnbRateNextRelease | null
}

// スイス家計消費データ項目
export interface CHHouseholdsAndNpishItem {
  date: string
  qoq: number | null  // 前期比（季節調整済み）
  yoy: number | null  // 前年比（調整前）
}

// スイス家計消費データ
export interface CHHouseholdsAndNpishData {
  data: CHHouseholdsAndNpishItem[]
  latest: CHHouseholdsAndNpishItem | null
  metadata: Record<string, unknown>
  next_release: ChSnbRateNextRelease | null
}

// スイスPMIデータ項目
export interface CHPmiItem {
  date: string
  value: number | null
  forecast: number | null
  previous: number | null
  period?: string
}

// スイスPMIデータ
export interface CHPmiData {
  manufacturing_data: CHPmiItem[]
  services_data: CHPmiItem[]
  latest_manufacturing: CHPmiItem | null
  latest_services: CHPmiItem | null
  metadata: Record<string, unknown>
  next_release: ChSnbRateNextRelease | null
}

// スイス貿易収支データ
export interface CHBalanceOfTradeDataPoint {
  date: string
  value: number
  exports: number
  imports: number
}

export interface CHBalanceOfTradeMoMChangePoint {
  date: string
  value: number
}

export interface CHBalanceOfTradeNextRelease {
  date: string
  datetime_jst?: string
  time_jst?: string
  label?: string
  estimate?: number | null
}

export interface CHBalanceOfTradeData {
  data: CHBalanceOfTradeDataPoint[]
  mom_change: CHBalanceOfTradeMoMChangePoint[]
  latest: CHBalanceOfTradeDataPoint | null
  metadata: Record<string, unknown>
  next_release?: CHBalanceOfTradeNextRelease | null
}

// スイス経常収支データ項目
export interface CHCurrentAccountItem {
  date: string
  value: number             // 経常収支（B CHF）
  qoq_change?: number       // 前期比変化額（B CHF）
}

// スイス経常収支データ
export interface CHCurrentAccountData {
  data: CHCurrentAccountItem[]
  qoq_change: { date: string; value: number }[]
  latest: CHCurrentAccountItem | null
  metadata: Record<string, unknown>
  next_release?: CHBalanceOfTradeNextRelease | null
}

// スイス経常収支対GDP比データ項目
export interface CHCurrentAccountGdpRatioItem {
  date: string
  value: number             // 経常収支対GDP比（%）
  current_account?: number  // 経常収支（M CHF）
  gdp?: number              // GDP（M CHF）
}

// スイス経常収支対GDP比データ
export interface CHCurrentAccountGdpRatioData {
  data: CHCurrentAccountGdpRatioItem[]
  latest: CHCurrentAccountGdpRatioItem | null
  metadata: Record<string, unknown>
  next_release?: CHBalanceOfTradeNextRelease | null
}

// スイス経済ダッシュボードデータの型
export interface SwitzerlandEconomyData {
  ch_growth_rate: CHGrowthRateData | null
  ch_industrial_production: CHIndustrialProductionData | null
  ch_pmi: CHPmiData | null
  ch_balance_of_trade: CHBalanceOfTradeData | null
  ch_current_account: CHCurrentAccountData | null
  ch_current_account_gdp_ratio: CHCurrentAccountGdpRatioData | null
}

/**
 * スイス経済ダッシュボード専用フック
 * GDP成長率、鉱工業生産などを取得
 */
export function useSwitzerlandEconomyDashboard(): UseQueryResult<DashboardResponse<SwitzerlandEconomyData>, Error> {
  return useDashboardData<SwitzerlandEconomyData>('switzerland', 'economy')
}

// スイス住宅ローン金利データ項目
export interface CHMortgageRatesItem {
  date: string
  variable_500k_1m: number | null  // 変動金利（50万〜100万CHF）
  variable_1m_5m: number | null    // 変動金利（100万〜500万CHF）
  fixed_500k_1m: number | null     // 固定金利（50万〜100万CHF）
  fixed_1m_5m: number | null       // 固定金利（100万〜500万CHF）
}

// スイス住宅ローン金利データ
export interface CHMortgageRatesData {
  data: CHMortgageRatesItem[]
  latest: CHMortgageRatesItem | null
  metadata: Record<string, unknown>
  next_release: string | null
}

// スイス住宅ローン残高データ項目
export interface CHMortgageBalanceItem {
  date: string
  value: number           // 十億CHF単位
  value_chf?: number      // CHF単位（元データ）
  mom?: number            // 前月比（%）
  yoy?: number            // 前年比（%）
}

// スイス住宅ローン残高データ
export interface CHMortgageBalanceData {
  data: CHMortgageBalanceItem[]
  latest: CHMortgageBalanceItem | null
  metadata: Record<string, unknown>
  next_release: string | null
}

// スイス新規住宅ローン融資額データ項目
export interface CHNewMortgageLoansItem {
  date: string
  quarter: string
  value: number  // 百万CHF単位
  qoq?: number   // 前期比（%）
  yoy?: number   // 前年比（%）
}

// スイス新規住宅ローン融資額データ
export interface CHNewMortgageLoansData {
  data: CHNewMortgageLoansItem[]
  latest: CHNewMortgageLoansItem | null
  metadata: Record<string, unknown>
  next_release: string | null
}

// スイス住宅価格指数データ項目
export interface CHHousingPricesItem {
  date: string
  quarter: string
  value: number  // 指数 (2020Q1=100)
  qoq?: number   // 前期比（%）
  yoy?: number   // 前年比（%）
}

// スイス住宅価格指数データ
export interface CHHousingPricesData {
  data: CHHousingPricesItem[]
  latest: CHHousingPricesItem | null
  metadata: Record<string, unknown>
  next_release: string | null
}

// スイス住宅ダッシュボードデータの型
export interface SwitzerlandHousingData {
  ch_mortgage_rates: CHMortgageRatesData | null
  ch_mortgage_balance: CHMortgageBalanceData | null
  ch_new_mortgage_loans: CHNewMortgageLoansData | null
  ch_housing_prices: CHHousingPricesData | null
}

/**
 * スイス住宅ダッシュボード専用フック
 * 住宅ローン金利などを取得
 */
export function useSwitzerlandHousingDashboard(): UseQueryResult<DashboardResponse<SwitzerlandHousingData>, Error> {
  return useDashboardData<SwitzerlandHousingData>('switzerland', 'housing')
}

// =============================================================================
// カナダ (Canada)
// =============================================================================

// カナダBOC政策金利データ項目
export interface CaBocRateItem {
  date: string
  value: number
}

// カナダBOC政策金利の次回発表日
export interface CaBocRateNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  datetime_toronto: string
  time_toronto: string
  label: string
  estimate?: number | null
}

// カナダBOC政策金利データ
export interface CaBocRateData {
  data: CaBocRateItem[]
  latest: CaBocRateItem | null
  metadata: Record<string, unknown>
  next_release: CaBocRateNextRelease | null
}

// BOC金融政策報告書データ項目
export interface BocMprSeriesItem {
  date: string
  value: number
}

// BOC金融政策報告書の比較項目
export interface BocMprComparisonItem {
  date: string
  latest: number | null
  previous: number | null
  diff: number | null
}

// BOC金融政策報告書の系列比較
export interface BocMprSeriesComparison {
  label: string
  data: BocMprComparisonItem[]
}

// BOC金融政策報告書レポート
export interface BocMprReport {
  period: string
  report_date: string
  report_label: string
  series: {
    gdp_qoq: BocMprSeriesItem[]
    gdp_yoy: BocMprSeriesItem[]
    cpi_yoy: BocMprSeriesItem[]
    core_yoy: BocMprSeriesItem[]
  }
}

// BOC金融政策報告書の比較データ
export interface BocMprComparison {
  latest_period: string
  previous_period: string
  series_comparison: {
    gdp_qoq: BocMprSeriesComparison
    gdp_yoy: BocMprSeriesComparison
    cpi_yoy: BocMprSeriesComparison
    core_yoy: BocMprSeriesComparison
  }
}

// BOC金融政策報告書データ
export interface BocMprData {
  latest_report: BocMprReport | null
  previous_report: BocMprReport | null
  comparison: BocMprComparison | null
  metadata: Record<string, unknown>
}

// BOCバランスシートデータ項目
export interface BocBalanceSheetItem {
  date: string
  value: number
}

// BOCバランスシートデータ
export interface BocBalanceSheetData {
  data: BocBalanceSheetItem[]
  latest: BocBalanceSheetItem | null
  metadata: Record<string, unknown>
}

// カナダ銀行バランスシート（チャータード銀行）データ
export interface CanadaBanksBalanceSheetItem {
  date: string
  value: number
}

export interface CanadaBanksBalanceSheetData {
  data: CanadaBanksBalanceSheetItem[]
  latest: CanadaBanksBalanceSheetItem | null
  metadata: Record<string, unknown>
}

// CORRA（カナダ翌日物レポ平均金利）データ項目
export interface CaCorraItem {
  date: string
  value: number
}

// CORRAデータ
export interface CaCorraData {
  data: CaCorraItem[]
  latest: CaCorraItem | null
  metadata: Record<string, unknown>
}

// 決済残高（Settlement Balances）データ項目
export interface CaSettlementBalancesItem {
  date: string
  value: number  // 百万CAD
}

// 決済残高の日次/週次データセット
export interface CaSettlementBalancesDataset {
  data: CaSettlementBalancesItem[]
  latest: CaSettlementBalancesItem | null
  metadata: Record<string, unknown>
}

// 決済残高データ（日次と週次の両方を含む）
export interface CaSettlementBalancesData {
  data: CaSettlementBalancesItem[]
  latest: CaSettlementBalancesItem | null
  metadata: Record<string, unknown>
  daily: CaSettlementBalancesDataset
  weekly: CaSettlementBalancesDataset
}

// 政府預金（Government Deposits）データ項目
export interface CaGovernmentDepositsItem {
  date: string
  value: number | null  // 百万CAD（total）
  total: number | null  // 合計
  boc: number | null    // BOC保有分
  ap: number | null     // オークション参加者保有分
}

// 政府預金データ
export interface CaGovernmentDepositsData {
  data: CaGovernmentDepositsItem[]
  latest: CaGovernmentDepositsItem | null
  metadata: Record<string, unknown>
}

// カナダ金融政策ダッシュボードデータの型
export interface CanadaPolicyData {
  ca_boc_rate: CaBocRateData | null
  boc_mpr: BocMprData | null
  boc_balance_sheet: BocBalanceSheetData | null
  canada_banks_balance_sheet: CanadaBanksBalanceSheetData | null
  ca_corra: CaCorraData | null
  ca_settlement_balances: CaSettlementBalancesData | null
  ca_government_deposits: CaGovernmentDepositsData | null
}

/**
 * カナダ金融政策ダッシュボード専用フック
 * BOC政策金利などを取得
 */
export function useCanadaPolicyDashboard(): UseQueryResult<DashboardResponse<CanadaPolicyData>, Error> {
  return useDashboardData<CanadaPolicyData>('canada', 'policy')
}

// ===== カナダ物価 =====

// カナダCPIデータ項目
export interface CaCpiItem {
  date: string
  yoy?: number
  mom?: number
  index?: number
  trim?: number
  median?: number
  common?: number
}

// カナダCPIデータ
export interface CaCpiData {
  data: CaCpiItem[]
  latest: CaCpiItem | null
  metadata: Record<string, unknown>
  next_release?: {
    date: string
    time_jst?: string
    label?: string
  } | null
}

// カナダIPPIデータ項目
export interface CaIppiItem {
  date: string
  yoy?: number
  mom?: number
  index?: number
}

// カナダIPPIデータ
export interface CaIppiData {
  data: CaIppiItem[]
  latest: CaIppiItem | null
  metadata: Record<string, unknown>
  next_release?: {
    date: string
    time_jst?: string
    label?: string
  } | null
}

// カナダインフレ期待データ項目
export interface CaInflationExpectationsItem {
  date: string
  exp_1y?: number
  exp_2y?: number
  exp_5y?: number
}

// カナダインフレ期待データ
export interface CaInflationExpectationsData {
  data: CaInflationExpectationsItem[]
  latest: CaInflationExpectationsItem | null
  metadata: Record<string, unknown>
  next_release?: {
    date: string
    time_jst?: string
    label?: string
  } | null
}

// カナダCPI サービス/家賃（粘着性CPI）データ項目
export interface CaCpiServiceRentItem {
  date: string
  all_items?: number
  ex_food_energy?: number
  services?: number
  shelter?: number
  rent?: number
}

// カナダCPI サービス/家賃データ
export interface CaCpiServiceRentData {
  data: CaCpiServiceRentItem[]
  latest: CaCpiServiceRentItem | null
  metadata: Record<string, unknown>
  next_release?: {
    date: string
    time_jst?: string
    label?: string
  } | null
}

// カナダ物価ダッシュボードデータの型
export interface CanadaInflationData {
  ca_cpi: CaCpiData | null
  ca_ippi: CaIppiData | null
  ca_inflation_expectations: CaInflationExpectationsData | null
  ca_cpi_service_rent: CaCpiServiceRentData | null
}

/**
 * カナダ物価ダッシュボード専用フック
 * CPIなどを取得
 */
export function useCanadaInflationDashboard(): UseQueryResult<DashboardResponse<CanadaInflationData>, Error> {
  return useDashboardData<CanadaInflationData>('canada', 'inflation')
}

// カナダ雇用者数データ項目
export interface CaEmploymentItem {
  date: string
  employment?: number
  fulltime?: number
  parttime?: number
  employment_change?: number
  fulltime_change?: number
  parttime_change?: number
}

// カナダ雇用者数データ
export interface CaEmploymentData {
  data: CaEmploymentItem[]
  latest: CaEmploymentItem | null
  metadata: Record<string, unknown>
  next_release?: {
    date: string
    time_jst?: string
    label?: string
  } | null
}

// カナダ失業率データ項目
export interface CaUnemploymentRateItem {
  date: string
  value: number
}

// カナダ失業率データ
export interface CaUnemploymentRateData {
  data: CaUnemploymentRateItem[]
  latest: CaUnemploymentRateItem | null
  metadata: Record<string, unknown>
  next_release?: {
    date: string
    time_jst?: string
    label?: string
  } | null
}

// カナダ労働参加率データ項目
export interface CaLaborForceParticipationRateItem {
  date: string
  value: number
}

// カナダ労働参加率データ
export interface CaLaborForceParticipationRateData {
  data: CaLaborForceParticipationRateItem[]
  latest: CaLaborForceParticipationRateItem | null
  metadata: Record<string, unknown>
  next_release?: {
    date: string
    time_jst?: string
    label?: string
  } | null
}

// カナダ平均時給データ項目
export interface CaAverageHourlyWageItem {
  date: string
  value: number
  yoy: number | null
  mom: number | null
}

// カナダ平均時給データ
export interface CaAverageHourlyWageData {
  data: CaAverageHourlyWageItem[]
  latest: CaAverageHourlyWageItem | null
  metadata: Record<string, unknown>
  next_release?: {
    date: string
    time_jst?: string
    label?: string
  } | null
}

// カナダ週間平均給与データ項目
export interface CaWeeklyAverageSalaryItem {
  date: string
  value: number
  yoy: number | null
  mom: number | null
}

// カナダ週間平均給与データ
export interface CaWeeklyAverageSalaryData {
  data: CaWeeklyAverageSalaryItem[]
  latest: CaWeeklyAverageSalaryItem | null
  metadata: Record<string, unknown>
  next_release?: {
    date: string
    time_jst?: string
    label?: string
  } | null
}

// カナダ求人率データ項目
export interface CaJobVacancyRateItem {
  date: string
  value: number
}

// カナダ求人率データ
export interface CaJobVacancyRateData {
  data: CaJobVacancyRateItem[]
  latest: CaJobVacancyRateItem | null
  metadata: Record<string, unknown>
  next_release?: {
    date: string
    time_jst?: string
    label?: string
  } | null
}

// カナダ雇用ダッシュボードデータの型
export interface CanadaEmploymentData {
  ca_employment: CaEmploymentData | null
  ca_unemployment_rate: CaUnemploymentRateData | null
  ca_labor_force_participation_rate: CaLaborForceParticipationRateData | null
  ca_average_hourly_wage: CaAverageHourlyWageData | null
  ca_weekly_average_salary: CaWeeklyAverageSalaryData | null
  ca_job_vacancy_rate: CaJobVacancyRateData | null
}

/**
 * カナダ雇用ダッシュボード専用フック
 * 雇用者数などを取得
 */
export function useCanadaEmploymentDashboard(): UseQueryResult<DashboardResponse<CanadaEmploymentData>, Error> {
  return useDashboardData<CanadaEmploymentData>('canada', 'employment')
}

// ===== カナダ経済 =====

// カナダGDP成長率データ項目
export interface CaGdpGrowthItem {
  date: string
  value: number
  qoq_simple?: number  // 前期比（非年率）
  qoq?: number         // 前期比年率
  yoy?: number         // 前年比
}

// カナダGDP成長率データ
export interface CaGdpGrowthData {
  data: CaGdpGrowthItem[]
  latest: CaGdpGrowthItem | null
  metadata: Record<string, unknown>
  next_release?: {
    date: string
    time_jst?: string
    label?: string
  } | null
}

// カナダ月次GDPデータ項目
export interface CaGdpMonthlyItem {
  date: string
  value: number
  mom?: number  // 前月比
  yoy?: number  // 前年比
}

// カナダ月次GDP FMP最新データ
export interface CaGdpMonthlyFmpLatest {
  date: string
  mom: number
  estimate?: number
  previous?: number
  is_advance: boolean
  source: string
  event?: string
  release_date?: string
}

// カナダ月次GDP速報値
export interface CaGdpMonthlyAdvanceEstimate {
  date: string
  mom: number  // 前月比（速報値）
  is_advance: boolean
  source?: string
  source_url?: string
  fetched_at?: string
  fmp_latest?: CaGdpMonthlyFmpLatest  // FMPからの最新確定値
}

// カナダ月次GDPデータ
export interface CaGdpMonthlyData {
  data: CaGdpMonthlyItem[]
  latest: CaGdpMonthlyItem | null
  advance_estimate?: CaGdpMonthlyAdvanceEstimate | null  // 速報値
  metadata: Record<string, unknown>
  next_release?: {
    date: string
    time_jst?: string
    label?: string
  } | null
}

// カナダ鉱工業生産データ項目
export interface CaIndustrialProductionItem {
  date: string
  value: number   // 絶対値（百万CAD、Chained 2017 dollars）
  mom?: number    // 前月比（%）
  yoy?: number    // 前年比（%）
}

// カナダ鉱工業生産データ
export interface CaIndustrialProductionData {
  data: CaIndustrialProductionItem[]
  latest: CaIndustrialProductionItem | null
  metadata: Record<string, unknown>
  next_release?: {
    date: string
    time_jst?: string
    label?: string
  } | null
}

// カナダ貿易収支データ項目
export interface CaTradeBalanceItem {
  date: string
  balance: number         // 貿易収支（百万CAD）
  exports?: number        // 輸出（百万CAD）
  imports?: number        // 輸入（百万CAD）
  mom?: number            // 前月比（%）
  mom_change?: number     // 前月比変化額（百万CAD）
  yoy?: number            // 前年比（%）
  yoy_change?: number     // 前年比変化額（百万CAD）
}

// カナダ貿易収支データ
export interface CaTradeBalanceData {
  data: CaTradeBalanceItem[]
  latest: CaTradeBalanceItem | null
  metadata: Record<string, unknown>
  next_release?: {
    date: string
    time_jst?: string
    label?: string
  } | null
}

// カナダ経常収支データ項目
export interface CaCurrentAccountItem {
  date: string
  value: number             // 経常収支（百万CAD）
  qoq_change?: number       // 前期比変化額（百万CAD）
}

// カナダ経常収支データ
export interface CaCurrentAccountData {
  data: CaCurrentAccountItem[]
  latest: CaCurrentAccountItem | null
  metadata: Record<string, unknown>
  next_release?: {
    date: string
    time_jst?: string
    label?: string
  } | null
}

// カナダ経常収支対GDP比データ項目
export interface CaCurrentAccountGdpRatioItem {
  date: string
  value: number             // 経常収支対GDP比（%）
  current_account?: number  // 経常収支（百万CAD）
  gdp?: number              // GDP（百万CAD）
}

// カナダ経常収支対GDP比データ
export interface CaCurrentAccountGdpRatioData {
  data: CaCurrentAccountGdpRatioItem[]
  latest: CaCurrentAccountGdpRatioItem | null
  metadata: Record<string, unknown>
  next_release?: {
    date: string
    time_jst?: string
    label?: string
  } | null
}

// カナダ対米輸出依存度データ項目
export interface CaUsExportDependenceItem {
  date: string
  value: number           // 依存度（%）
  us_export?: number      // 米国向け輸出（百万CAD）
  total_export?: number   // 総輸出（百万CAD）
  ma_3m?: number          // 3ヶ月移動平均（%）
  ma_12m?: number         // 12ヶ月移動平均（%）
}

// カナダ対米輸出依存度データ
export interface CaUsExportDependenceData {
  data: CaUsExportDependenceItem[]
  latest: CaUsExportDependenceItem | null
  metadata: Record<string, unknown>
  next_release?: {
    date: string
    time_jst?: string
    label?: string
  } | null
}

// カナダBOS（企業景況感調査）データ項目
export interface CaBosItem {
  date: string
  future_sales?: number | null       // 将来売上見通し（BO）
  investment?: number | null         // 設備投資見通し（BO）
  employment?: number | null         // 雇用見通し（BO）
  input_prices?: number | null       // 投入価格インフレ（BO）
  output_prices?: number | null      // 産出価格インフレ（BO）
  credit?: number | null             // 信用条件（BO）
}

// カナダBOS次回発表情報
export interface CaBosNextRelease {
  date: string
  datetime_jst: string
  time_jst: string
  datetime_toronto: string
  time_toronto: string
  label: string
}

// カナダBOSデータ
export interface CaBosData {
  data: CaBosItem[]
  latest: CaBosItem | null
  metadata: Record<string, unknown>
  next_release?: CaBosNextRelease | null
}

// カナダCSCE（消費者期待調査）データ項目
export interface CaCsceItem {
  date: string
  inflation_1y?: number | null       // 1年先インフレ期待
  inflation_2y?: number | null       // 2年先インフレ期待
  inflation_5y?: number | null       // 5年先インフレ期待
  wage_next_12m?: number | null      // 賃金成長期待（次の12ヶ月）
  wage_past_12m?: number | null      // 賃金成長実績（過去12ヶ月）
  prob_lose_job?: number | null      // 失業確率
  prob_leave_job?: number | null     // 自発的退職確率
  prob_find_job?: number | null      // 求職成功確率
  income_growth?: number | null      // 所得成長期待
  spending_growth?: number | null    // 支出成長期待
}

// カナダCSCE次回発表情報
export interface CaCsceNextRelease {
  date: string
  datetime_jst: string
  time_jst: string
  datetime_toronto: string
  time_toronto: string
  label: string
}

// カナダCSCEデータ
export interface CaCsceData {
  data: CaCsceItem[]
  latest: CaCsceItem | null
  metadata: Record<string, unknown>
  next_release?: CaCsceNextRelease | null
}

// カナダSLOS（貸出態度調査）データ項目
export interface CaSlosItem {
  date: string
  business?: number | null           // 企業向け貸出条件（BO）
  mortgage?: number | null           // 住宅ローン貸出条件（BO）
  non_mortgage?: number | null       // 非住宅ローン貸出条件（BO）
}

// カナダSLOS次回発表情報
export interface CaSlosNextRelease {
  date: string
  datetime_jst: string
  time_jst: string
  datetime_toronto: string
  time_toronto: string
  label: string
}

// カナダSLOSデータ
export interface CaSlosData {
  data: CaSlosItem[]
  latest: CaSlosItem | null
  metadata: Record<string, unknown>
  next_release?: CaSlosNextRelease | null
}

// カナダ Ivey PMI データ項目
export interface CaIveyPmiItem {
  date: string
  value: number
}

// カナダ Ivey PMI データ
export interface CaIveyPmiData {
  data: CaIveyPmiItem[]
  latest: CaIveyPmiItem | null
  metadata: Record<string, unknown>
  next_release?: {
    date: string
    datetime_jst?: string
    time_jst?: string
    datetime_toronto?: string
    time_toronto?: string
    label?: string
    estimate?: number | null
  } | null
}

// カナダ S&P Global PMI データ項目
export interface CaSpPmiItem {
  date: string
  value: number
}

// カナダ S&P Global PMI 系列データ
export interface CaSpPmiSeriesData {
  data: CaSpPmiItem[]
  latest: CaSpPmiItem | null
}

// カナダ S&P Global PMI 次回発表
export interface CaSpPmiNextRelease {
  date: string
  datetime_jst?: string
  time_jst?: string
  datetime_toronto?: string
  time_toronto?: string
  label?: string
  estimate?: number | null
}

// カナダ S&P Global PMI データ（3系列）
export interface CaSpPmiData {
  manufacturing: CaSpPmiSeriesData | null
  services: CaSpPmiSeriesData | null
  composite: CaSpPmiSeriesData | null
  next_release: CaSpPmiNextRelease | null
  last_updated: string | null
}

// カナダ経済ダッシュボードデータの型
export interface CanadaEconomyData {
  ca_gdp_growth: CaGdpGrowthData | null
  ca_gdp_monthly: CaGdpMonthlyData | null
  ca_industrial_production: CaIndustrialProductionData | null
  ca_trade_balance: CaTradeBalanceData | null
  ca_current_account: CaCurrentAccountData | null
  ca_current_account_gdp_ratio: CaCurrentAccountGdpRatioData | null
  ca_us_export_dependence: CaUsExportDependenceData | null
  ca_bos: CaBosData | null
  ca_csce: CaCsceData | null
  ca_slos: CaSlosData | null
  ca_ivey_pmi: CaIveyPmiData | null
  ca_sp_pmi: CaSpPmiData | null
}

/**
 * カナダ経済ダッシュボード専用フック
 * GDP成長率などを取得
 */
export function useCanadaEconomyDashboard(): UseQueryResult<DashboardResponse<CanadaEconomyData>, Error> {
  return useDashboardData<CanadaEconomyData>('canada', 'economy')
}

// ===== カナダ消費者 =====

// カナダ小売売上高データ項目
export interface CaRetailSalesItem {
  date: string
  total_value: number
  ex_auto_value: number
  ex_auto_gas_value: number
  total_mom?: number
  total_yoy?: number
  ex_auto_mom?: number
  ex_auto_yoy?: number
  ex_auto_gas_mom?: number
  ex_auto_gas_yoy?: number
}

// カナダ小売売上高速報値
export interface CaRetailSalesAdvanceEstimate {
  date: string
  total_mom: number
}

// カナダ小売売上高データ
export interface CaRetailSalesData {
  data: CaRetailSalesItem[]
  latest: CaRetailSalesItem | null
  advance_estimate?: CaRetailSalesAdvanceEstimate | null
  metadata: Record<string, unknown>
  next_release?: {
    date: string
    time_jst?: string
    label?: string
  } | null
}

// カナダ家計DSRデータ項目
export interface CaDebtServiceRatioItem {
  date: string
  value: number           // 総合DSR（%）
  mortgage?: number       // 住宅ローンDSR（%）
  non_mortgage?: number   // 非住宅ローンDSR（%）
}

// カナダ家計DSRデータ
export interface CaDebtServiceRatioData {
  data: CaDebtServiceRatioItem[]
  latest: CaDebtServiceRatioItem | null
  metadata: Record<string, unknown>
  next_release?: {
    date: string
    time_jst?: string
    label?: string
  } | null
}

// カナダ消費者ダッシュボードデータの型
export interface CanadaConsumerData {
  ca_retail_sales: CaRetailSalesData | null
}

/**
 * カナダ消費者ダッシュボード専用フック
 * 小売売上高などを取得
 */
export function useCanadaConsumerDashboard(): UseQueryResult<DashboardResponse<CanadaConsumerData>, Error> {
  return useDashboardData<CanadaConsumerData>('canada', 'consumer')
}

// ===== カナダ住宅 =====

// カナダ住宅着工件数データ項目
export interface CaHousingStartsItem {
  date: string
  value: number  // 千件
  mom?: number   // 前月比（%）
  yoy?: number   // 前年比（%）
}

// カナダ住宅着工件数次回発表情報
export interface CaHousingStartsNextRelease {
  date: string           // YYYY-MM-DD形式
  datetime_jst: string   // ISO8601形式（JST）
  time_jst: string       // HH:MM形式
  datetime_toronto: string // ISO8601形式（トロント時間）
  time_toronto: string   // HH:MM形式
  label: string          // 例: "Housing Starts (Jan)"
  estimate: number | null
}

// カナダ住宅着工件数データ
export interface CaHousingStartsData {
  data: CaHousingStartsItem[]
  latest: CaHousingStartsItem | null
  metadata: Record<string, unknown>
  next_release?: CaHousingStartsNextRelease | null
}

// カナダ建築許可データ項目
export interface CaBuildingPermitsItem {
  date: string
  value: number  // 百万カナダドル
  mom?: number   // 前月比（%）
  yoy?: number   // 前年比（%）
}

// カナダ建築許可次回発表情報
export interface CaBuildingPermitsNextRelease {
  date: string           // YYYY-MM-DD形式
  datetime_jst: string   // ISO8601形式（JST）
  time_jst: string       // HH:MM形式
  datetime_toronto: string // ISO8601形式（トロント時間）
  time_toronto: string   // HH:MM形式
  label: string          // 例: "Building Permits (Jan)"
  estimate: number | null
}

// カナダ建築許可データ
export interface CaBuildingPermitsData {
  data: CaBuildingPermitsItem[]
  latest: CaBuildingPermitsItem | null
  metadata: Record<string, unknown>
  next_release?: CaBuildingPermitsNextRelease | null
}

// カナダ新築住宅価格指数データ項目
export interface CaNewHousingPriceIndexItem {
  date: string
  mom?: number   // 前月比（%）
  yoy?: number   // 前年比（%）
}

// カナダ新築住宅価格指数次回発表情報
export interface CaNewHousingPriceIndexNextRelease {
  date: string           // YYYY-MM-DD形式
  datetime_jst: string   // ISO8601形式（JST）
  time_jst: string       // HH:MM形式
  datetime_toronto: string // ISO8601形式（トロント時間）
  time_toronto: string   // HH:MM形式
  label: string          // 例: "New Housing Price Index MoM (Dec)"
  estimate: number | null
}

// カナダ新築住宅価格指数データ
export interface CaNewHousingPriceIndexData {
  data: CaNewHousingPriceIndexItem[]
  latest: CaNewHousingPriceIndexItem | null
  metadata: Record<string, unknown>
  next_release?: CaNewHousingPriceIndexNextRelease | null
}

// カナダ住宅ダッシュボードデータの型
export interface CanadaHousingData {
  ca_housing_starts: CaHousingStartsData | null
  ca_building_permits: CaBuildingPermitsData | null
  ca_new_housing_price_index: CaNewHousingPriceIndexData | null
  ca_debt_service_ratio: CaDebtServiceRatioData | null
}

/**
 * カナダ住宅ダッシュボード専用フック
 * 住宅着工件数、建築許可などを取得
 */
export function useCanadaHousingDashboard(): UseQueryResult<DashboardResponse<CanadaHousingData>, Error> {
  return useDashboardData<CanadaHousingData>('canada', 'housing')
}

// ===== オーストラリア金融政策 =====

// RBA政策金利データ項目
export interface AuRbaRateItem {
  date: string
  value: number
}

// RBA政策金利の次回発表日
export interface AuRbaRateNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  datetime_sydney: string
  time_sydney: string
  label: string
  estimate?: number | null
}

// RBA政策金利データ
export interface AuRbaRateData {
  data: AuRbaRateItem[]
  latest: AuRbaRateItem | null
  metadata: Record<string, unknown>
  next_release: AuRbaRateNextRelease | null
}

// ASX RBA Rate Tracker サマリ
export interface AsxRateTrackerSummary {
  current_rate: number | null
  last_rate_change: number | null
  last_meeting_date: string | null
  next_meeting_date: string | null
  settlement_date: string | null
  settlement_price: number | null
  market_expectation_pct: number | null
  future_cash_rate: number | null
  future_rate_change: number | null
  expiry_month: number | null
  expiry_year: number | null
}

// ASX 確率推移データ
export interface AsxProbabilityDay {
  date: string
  prob_no_change: number
  prob_change: number
}

// ASX 確率メタ情報
export interface AsxProbabilityMeta {
  future_cash_rate: number | null
  future_rate_change: number | null
}

// ASX イールドカーブデータポイント
export interface AsxYieldCurvePoint {
  month: string
  implied_yield: number
}

// ASX イールドカーブ
export interface AsxYieldCurveData {
  settlement_date: string | null
  target_rate: number | null
  data: AsxYieldCurvePoint[]
}

// ASX RBA Rate Trackerデータ
export interface AsxRateTrackerData {
  summary: AsxRateTrackerSummary | null
  probability_history: AsxProbabilityDay[]
  probability_meta: AsxProbabilityMeta | null
  yield_curve: AsxYieldCurveData | null
}

// RBA SMP経済予測データの型
export interface RbaSmpForecastPoint {
  date: string
  value: number | null
}

export interface RbaSmpIndicatorData {
  latest: RbaSmpForecastPoint[]
  previous: RbaSmpForecastPoint[]
}

export interface RbaSmpForecastMetadata {
  latest_publication: string
  previous_publication: string
  source: string
  last_updated: string
}

export interface RbaSmpForecastData {
  indicators: {
    cash_rate: RbaSmpIndicatorData
    gdp: RbaSmpIndicatorData
    household_consumption: RbaSmpIndicatorData
    employment: RbaSmpIndicatorData
    unemployment_rate: RbaSmpIndicatorData
    cpi: RbaSmpIndicatorData
    trimmed_mean: RbaSmpIndicatorData
  }
  metadata: RbaSmpForecastMetadata
}

// ===== 住宅ローン金利（RBA F6）=====
export interface AuHousingLendingRatesItem {
  date: string
  outstanding_oo_variable: number | null   // 既存 自己居住 変動
  outstanding_oo_fixed: number | null      // 既存 自己居住 固定(≤3yr)
  outstanding_inv_variable: number | null  // 既存 投資 変動
  outstanding_inv_fixed: number | null     // 既存 投資 固定(≤3yr)
  new_oo_variable: number | null           // 新規 自己居住 変動
  new_oo_fixed: number | null              // 新規 自己居住 固定(≤3yr)
}

export interface AuHousingLendingRatesNextRelease {
  date: string
  datetime_jst?: string
  time_jst?: string
  label?: string
  estimate?: number | null
}

export interface AuHousingLendingRatesData {
  data: AuHousingLendingRatesItem[]
  latest: AuHousingLendingRatesItem | null
  metadata: Record<string, unknown>
  next_release?: AuHousingLendingRatesNextRelease | null
}

// ===== 住宅ローン延滞率（APRA）=====
export interface AuHousingLoanArrearsItem {
  date: string
  past_due_30_89: number    // 30-89日延滞率 (%)
  non_performing: number    // 不良債権率 (90日以上, %)
  total_arrears: number     // 合計延滞率 (%)
}

export interface AuHousingLoanArrearsData {
  data: AuHousingLoanArrearsItem[]
  latest: AuHousingLoanArrearsItem | null
  metadata: Record<string, unknown>
  next_release?: Record<string, unknown> | null
}

// オーストラリア金融政策ダッシュボードデータの型
export interface AustraliaPolicyData {
  au_rba_rate: AuRbaRateData | null
  au_asx_rate_tracker: AsxRateTrackerData | null
  au_monetary_policy: RbaSmpForecastData | null
}

/**
 * オーストラリア金融政策ダッシュボード専用フック
 * RBA政策金利などを取得
 */
export function useAustraliaPolicyDashboard(): UseQueryResult<DashboardResponse<AustraliaPolicyData>, Error> {
  return useDashboardData<AustraliaPolicyData>('australia', 'policy')
}

// ABS 月次CPIデータの型
export interface AuMonthlyCpiDataPoint {
  date: string
  cpi_yoy: number | null
  cpi_mom: number | null
  trimmed_mean_yoy: number | null
  trimmed_mean_mom: number | null
  weighted_median_yoy: number | null
  weighted_median_mom: number | null
}

export interface AuMonthlyCpiData {
  data: AuMonthlyCpiDataPoint[]
  latest: AuMonthlyCpiDataPoint | null
  metadata: {
    source: string
    indicator: string
    frequency: string
    unit: string
  }
  next_release: { date: string; event: string } | null
}

// AU CPIカテゴリ別データの型
export interface AuCpiCategoriesDataPoint {
  date: string
  goods_yoy: number | null
  goods_mom: number | null
  services_yoy: number | null
  services_mom: number | null
  electricity_yoy: number | null
  electricity_mom: number | null
  rents_yoy: number | null
  rents_mom: number | null
  new_dwellings_yoy: number | null
  new_dwellings_mom: number | null
  food_yoy: number | null
  food_mom: number | null
}

export interface AuCpiCategoriesData {
  data: AuCpiCategoriesDataPoint[]
  latest: AuCpiCategoriesDataPoint | null
  metadata: {
    source: string
    indicator: string
    frequency: string
    unit: string
  }
  next_release: { date: string; event: string } | null
}

// AU 四半期CPIデータの型
export interface AuQuarterlyCpiDataPoint {
  date: string
  cpi_qoq: number | null
  cpi_yoy: number | null
  cpi_sa_yoy: number | null
  trimmed_mean_yoy: number | null
  weighted_median_yoy: number | null
  trimmed_mean_qoq: number | null
  weighted_median_qoq: number | null
}

export interface AuQuarterlyCpiData {
  data: AuQuarterlyCpiDataPoint[]
  latest: AuQuarterlyCpiDataPoint | null
  metadata: {
    source: string
    indicator: string
    frequency: string
    unit: string
  }
  next_release: { date: string; event: string } | null
}

// AU 四半期PPIデータの型
export interface AuQuarterlyPpiDataPoint {
  date: string
  ppi_qoq: number | null
  ppi_yoy: number | null
}

export interface AuQuarterlyPpiData {
  data: AuQuarterlyPpiDataPoint[]
  latest: AuQuarterlyPpiDataPoint | null
  metadata: {
    source: string
    indicator: string
    frequency: string
    unit: string
  }
  next_release: { date: string; event: string } | null
}

// AU インフレ期待データの型
export interface AuInflationExpectationsDataPoint {
  date: string
  value: number | null
}

export interface AuInflationExpectationsData {
  data: AuInflationExpectationsDataPoint[]
  latest: AuInflationExpectationsDataPoint | null
  metadata: {
    source: string
    indicator: string
    frequency: string
    unit: string
  }
  next_release: { date: string; event: string } | null
}

// NAB企業調査 コスト・価格チャート（PDFスクリーンショット）の型
export interface NabCostPriceScreenshot {
  key: string
  label: string
  label_ja: string
  url: string | null
  exists: boolean
}

export interface NabCostPriceData {
  screenshots: NabCostPriceScreenshot[]
  last_updated: string | null
  next_release: { date: string; label?: string } | null
  pdf_name?: string
}

// オーストラリア物価ダッシュボードデータの型
export interface AustraliaInflationData {
  au_monthly_cpi: AuMonthlyCpiData | null
  au_cpi_categories: AuCpiCategoriesData | null
  au_quarterly_cpi: AuQuarterlyCpiData | null
  au_quarterly_ppi: AuQuarterlyPpiData | null
  au_inflation_expectations: AuInflationExpectationsData | null
  au_nab_cost_price: NabCostPriceData | null
}

// =====================================================================
// オーストラリア雇用 (Australia Employment)
// =====================================================================

export interface AuUnemploymentRateDataPoint {
  date: string
  value: number | null
}

export interface AuUnemploymentRateNextRelease {
  date: string
  datetime_jst: string
  time_jst: string
  label: string
  estimate: number | null
}

export interface AuUnemploymentRateData {
  data: AuUnemploymentRateDataPoint[]
  latest: AuUnemploymentRateDataPoint | null
  metadata: {
    source: string
    indicator: string
    frequency: string
    unit: string
  }
  next_release?: AuUnemploymentRateNextRelease | null
}

export interface AuEmployedPersonsDataPoint {
  date: string
  value: number | null
  mom_change: number | null
  yoy_change: number | null
}

export interface AuEmployedPersonsData {
  data: AuEmployedPersonsDataPoint[]
  latest: AuEmployedPersonsDataPoint | null
  metadata: {
    source: string
    indicator: string
    frequency: string
    unit: string
  }
  next_release?: AuUnemploymentRateNextRelease | null
}

export interface AuFulltimeParttimeDataPoint {
  date: string
  fulltime: number | null
  parttime: number | null
  fulltime_mom: number | null
  parttime_mom: number | null
  fulltime_yoy: number | null
  parttime_yoy: number | null
}

export interface AuFulltimeParttimeData {
  data: AuFulltimeParttimeDataPoint[]
  latest: AuFulltimeParttimeDataPoint | null
  metadata: {
    source: string
    indicator: string
    frequency: string
    unit: string
  }
  next_release?: AuUnemploymentRateNextRelease | null
}

export interface AuParticipationRateDataPoint {
  date: string
  value: number | null
}

export interface AuParticipationRateData {
  data: AuParticipationRateDataPoint[]
  latest: AuParticipationRateDataPoint | null
  metadata: {
    source: string
    indicator: string
    frequency: string
    unit: string
  }
  next_release?: AuUnemploymentRateNextRelease | null
}

export interface AuWagePriceIndexDataPoint {
  date: string
  qoq: number | null
  yoy: number | null
}

export interface AuWagePriceIndexData {
  data: AuWagePriceIndexDataPoint[]
  latest: AuWagePriceIndexDataPoint | null
  metadata: {
    source: string
    indicator: string
    frequency: string
    unit: string
  }
  next_release?: AuUnemploymentRateNextRelease | null
}

export interface AuJobVacanciesDataPoint {
  date: string
  value: number | null
}

export interface AuJobVacanciesData {
  data: AuJobVacanciesDataPoint[]
  latest: AuJobVacanciesDataPoint | null
  metadata: {
    source: string
    indicator: string
    frequency: string
    unit: string
  }
  next_release?: AuUnemploymentRateNextRelease | null
}

export interface AuAnzJobAdvertisementsDataPoint {
  date: string
  value: number | null
  mom: number | null
  yoy: number | null
}

export interface AuAnzJobAdvertisementsData {
  data: AuAnzJobAdvertisementsDataPoint[]
  latest: AuAnzJobAdvertisementsDataPoint | null
  metadata: {
    source: string
    indicator: string
    frequency: string
    unit: string
  }
  next_release?: AuUnemploymentRateNextRelease | null
}

// オーストラリア アンダー・ユーティライゼーション データ項目
export interface AuUnderutilizationItem {
  date: string
  underutilisation: number | null
  underemployment: number | null
  unemployment: number | null
}

// オーストラリア アンダー・ユーティライゼーション データ
export interface AuUnderutilizationData {
  data: AuUnderutilizationItem[]
  latest: AuUnderutilizationItem | null
  metadata: Record<string, unknown>
  next_release?: AuUnemploymentRateNextRelease | null
}

export interface AustraliaEmploymentData {
  au_unemployment_rate: AuUnemploymentRateData | null
  au_employed_persons: AuEmployedPersonsData | null
  au_fulltime_parttime: AuFulltimeParttimeData | null
  au_participation_rate: AuParticipationRateData | null
  au_wage_price_index: AuWagePriceIndexData | null
  au_job_vacancies: AuJobVacanciesData | null
  au_anz_job_advertisements: AuAnzJobAdvertisementsData | null
  au_underutilization: AuUnderutilizationData | null
}

/**
 * オーストラリア物価ダッシュボード専用フック
 * ABS月次CPIなどを取得
 */
export function useAustraliaInflationDashboard(): UseQueryResult<DashboardResponse<AustraliaInflationData>, Error> {
  return useDashboardData<AustraliaInflationData>('australia', 'inflation')
}

/**
 * オーストラリア雇用ダッシュボード専用フック
 * ABS失業率などを取得
 */
export function useAustraliaEmploymentDashboard(): UseQueryResult<DashboardResponse<AustraliaEmploymentData>, Error> {
  return useDashboardData<AustraliaEmploymentData>('australia', 'employment')
}

// オーストラリア消費データの型
export interface AuHouseholdSpendingDataPoint {
  date: string
  mom: number | null
  yoy: number | null
}

export interface AuHouseholdSpendingData {
  data: AuHouseholdSpendingDataPoint[]
  latest: AuHouseholdSpendingDataPoint | null
  metadata: {
    source: string
    indicator: string
    frequency: string
    unit: string
  }
  next_release?: AuUnemploymentRateNextRelease | null
}

export interface AuWestpacConsumerConfidenceDataPoint {
  date: string
  value: number | null
  change: number | null
}

export interface AuWestpacConsumerConfidenceData {
  data: AuWestpacConsumerConfidenceDataPoint[]
  latest: AuWestpacConsumerConfidenceDataPoint | null
  metadata: {
    source: string
    indicator: string
    frequency: string
    unit: string
  }
  next_release?: AuUnemploymentRateNextRelease | null
}

export interface AuNabBusinessConfidenceDataPoint {
  date: string
  value: number | null
  mom: number | null
}

export interface AuNabBusinessConfidenceData {
  data: AuNabBusinessConfidenceDataPoint[]
  latest: AuNabBusinessConfidenceDataPoint | null
  metadata: {
    source: string
    indicator: string
    frequency: string
    unit: string
  }
  next_release?: AuUnemploymentRateNextRelease | null
}

export interface AuConsumerSpendingDataPoint {
  date: string
  qoq: number | null
  yoy: number | null
}

export interface AuConsumerSpendingData {
  data: AuConsumerSpendingDataPoint[]
  latest: AuConsumerSpendingDataPoint | null
  metadata: {
    source: string
    indicator: string
    frequency: string
    unit: string
  }
  next_release?: AuUnemploymentRateNextRelease | null
}

export interface AuHouseholdSavingRatioDataPoint {
  date: string
  value: number | null
  qoq: number | null
  yoy: number | null
}

export interface AuHouseholdSavingRatioData {
  data: AuHouseholdSavingRatioDataPoint[]
  latest: AuHouseholdSavingRatioDataPoint | null
  metadata: {
    source: string
    indicator: string
    frequency: string
    unit: string
  }
  next_release?: AuUnemploymentRateNextRelease | null
}

export interface AuDisposablePersonalIncomeDataPoint {
  date: string
  qoq: number | null
  yoy: number | null
}

export interface AuDisposablePersonalIncomeData {
  data: AuDisposablePersonalIncomeDataPoint[]
  latest: AuDisposablePersonalIncomeDataPoint | null
  metadata: {
    source: string
    indicator: string
    frequency: string
    unit: string
  }
  next_release?: AuUnemploymentRateNextRelease | null
}

export interface AustraliaConsumerData {
  au_household_spending: AuHouseholdSpendingData | null
  au_westpac_consumer_confidence: AuWestpacConsumerConfidenceData | null
  au_nab_business_confidence: AuNabBusinessConfidenceData | null
  au_consumer_spending: AuConsumerSpendingData | null
  au_household_saving_ratio: AuHouseholdSavingRatioData | null
  au_disposable_personal_income: AuDisposablePersonalIncomeData | null
}

/**
 * オーストラリア消費ダッシュボード専用フック
 * ABS家計支出などを取得
 */
export function useAustraliaConsumerDashboard(): UseQueryResult<DashboardResponse<AustraliaConsumerData>, Error> {
  return useDashboardData<AustraliaConsumerData>('australia', 'consumer')
}

// =====================================================================
// オーストラリア経済 (Australia Economy)
// =====================================================================

export interface AuGdpGrowthRateDataPoint {
  date: string
  qoq: number | null
  yoy: number | null
}

export interface AuGdpGrowthRateData {
  data: AuGdpGrowthRateDataPoint[]
  latest: AuGdpGrowthRateDataPoint | null
  metadata: {
    source: string
    indicator: string
    frequency: string
    unit: string
  }
  next_release?: AuUnemploymentRateNextRelease | null
}

export interface AuGdpPriceRelatedDataPoint {
  date: string
  deflator_qoq: number | null
  deflator_yoy: number | null
  net_exports_contribution: number | null
  exports_contribution: number | null
  imports_contribution: number | null
  gfcf_qoq: number | null
  gfcf_yoy: number | null
  gfcf_level: number | null
  consumption_qoq: number | null
  consumption_yoy: number | null
  consumption_level: number | null
}

export interface AuGdpPriceRelatedData {
  data: AuGdpPriceRelatedDataPoint[]
  latest: AuGdpPriceRelatedDataPoint | null
  metadata: {
    source: string
    indicator: string
    frequency: string
    unit: string
  }
  next_release?: AuUnemploymentRateNextRelease | null
}

export interface AuPrivateNewCapitalExpenditureDataPoint {
  date: string
  value: number | null
  qoq: number | null
  yoy: number | null
}

export interface AuPrivateNewCapitalExpenditureData {
  data: AuPrivateNewCapitalExpenditureDataPoint[]
  latest: AuPrivateNewCapitalExpenditureDataPoint | null
  metadata: {
    source: string
    indicator: string
    frequency: string
    unit: string
  }
  next_release?: AuUnemploymentRateNextRelease | null
}

// === 国際貿易 ===
export interface AuInternationalTradeItem {
  date: string
  value: number
}

export interface AuInternationalTradeNextRelease {
  date: string
  datetime_jst: string
  time_jst: string
  label: string
  estimate: number | null
}

export interface AuInternationalTradeData {
  balance: AuInternationalTradeItem[]
  exports: AuInternationalTradeItem[]
  imports: AuInternationalTradeItem[]
  balance_mom_diff: AuInternationalTradeItem[]
  exports_mom: AuInternationalTradeItem[]
  exports_yoy: AuInternationalTradeItem[]
  imports_mom: AuInternationalTradeItem[]
  imports_yoy: AuInternationalTradeItem[]
  latest_balance: AuInternationalTradeItem | null
  latest_exports: AuInternationalTradeItem | null
  latest_imports: AuInternationalTradeItem | null
  metadata: Record<string, unknown>
  next_release: AuInternationalTradeNextRelease | null
}

// === 経常収支 ===
export interface AuCurrentAccountItem {
  date: string
  value: number
}

export interface AuCurrentAccountNextRelease {
  date: string
  datetime_jst: string
  time_jst: string
  label: string
  estimate: number | null
}

export interface AuCurrentAccountData {
  data: AuCurrentAccountItem[]
  qoq_diff: AuCurrentAccountItem[]
  yoy_diff: AuCurrentAccountItem[]
  latest: AuCurrentAccountItem | null
  metadata: Record<string, unknown>
  next_release: AuCurrentAccountNextRelease | null
}

// === 経常収支対GDP比 ===
export interface AuCurrentAccountGdpRatioItem {
  date: string
  value: number
  current_account?: number
  gdp?: number
}

export interface AuCurrentAccountGdpRatioData {
  data: AuCurrentAccountGdpRatioItem[]
  latest: AuCurrentAccountGdpRatioItem | null
  metadata: Record<string, unknown>
  next_release?: AuCurrentAccountNextRelease | null
}

// オーストラリア S&P Global PMI データ項目
export interface AuPmiItem {
  date: string
  value: number
}

// オーストラリア S&P Global PMI 系列データ
export interface AuPmiSeriesData {
  data: AuPmiItem[]
  latest: AuPmiItem | null
}

// オーストラリア S&P Global PMI 次回発表
export interface AuPmiNextRelease {
  date: string
  datetime_jst?: string
  time_jst?: string
  label?: string
  estimate?: number | null
}

// オーストラリア S&P Global PMI データ（3系列）
export interface AuPmiData {
  manufacturing: AuPmiSeriesData | null
  services: AuPmiSeriesData | null
  composite: AuPmiSeriesData | null
  next_release: AuPmiNextRelease | null
  last_updated: string | null
}

// オーストラリア 交易条件データ項目
export interface AuTermsOfTradeItem {
  date: string
  value: number | null
  qoq: number | null
  yoy: number | null
}

// オーストラリア 交易条件データ
export interface AuTermsOfTradeData {
  data: AuTermsOfTradeItem[]
  latest: AuTermsOfTradeItem | null
  metadata: Record<string, unknown>
  next_release?: AuCurrentAccountNextRelease | null
}

export interface AustraliaEconomyData {
  au_gdp_growth_rate: AuGdpGrowthRateData | null
  au_gdp_price_related: AuGdpPriceRelatedData | null
  au_private_new_capital_expenditure: AuPrivateNewCapitalExpenditureData | null
  au_international_trade: AuInternationalTradeData | null
  au_current_account: AuCurrentAccountData | null
  au_current_account_gdp_ratio: AuCurrentAccountGdpRatioData | null
  au_pmi: AuPmiData | null
  au_terms_of_trade: AuTermsOfTradeData | null
}

/**
 * オーストラリア経済ダッシュボード専用フック
 * GDP成長率などを取得
 */
export function useAustraliaEconomyDashboard(): UseQueryResult<DashboardResponse<AustraliaEconomyData>, Error> {
  return useDashboardData<AustraliaEconomyData>('australia', 'economy')
}

// ===== オーストラリア住宅 =====

export interface AuCotalityHomePricesDailyPoint {
  date: string
  value: number | null
}

export interface AuCotalityHomePricesMonthlyPoint {
  date: string
  value: number | null
  mom: number | null
}

export interface AuCotalityHomePricesData {
  data: AuCotalityHomePricesDailyPoint[]
  monthly_data: AuCotalityHomePricesMonthlyPoint[]
  latest: AuCotalityHomePricesDailyPoint | null
  metadata: {
    source: string
    indicator: string
    frequency: string
    unit: string
  }
  next_release?: null
}

// === 建築許可件数 ===
export interface AuNumberOfBuildingPermitsItem {
  date: string
  value: number | null
  mom: number | null
  yoy: number | null
}

export interface AuNumberOfBuildingPermitsNextRelease {
  date: string
  datetime_jst: string
  time_jst: string
  label: string
  estimate: number | null
}

export interface AuNumberOfBuildingPermitsData {
  data: AuNumberOfBuildingPermitsItem[]
  latest: AuNumberOfBuildingPermitsItem | null
  metadata: {
    source: string
    indicator: string
    frequency: string
    unit: string
    series_id: string
  }
  next_release?: AuNumberOfBuildingPermitsNextRelease | null
}

export interface AustraliaHousingData {
  au_cotality_home_prices: AuCotalityHomePricesData | null
  au_number_of_building_permits: AuNumberOfBuildingPermitsData | null
  au_housing_lending_rates: AuHousingLendingRatesData | null
  au_housing_loan_arrears: AuHousingLoanArrearsData | null
}

/**
 * オーストラリア住宅ダッシュボード専用フック
 * Cotality住宅価格指数などを取得
 */
export function useAustraliaHousingDashboard(): UseQueryResult<DashboardResponse<AustraliaHousingData>, Error> {
  return useDashboardData<AustraliaHousingData>('australia', 'housing')
}

// ===== ニュージーランド =====

// RBNZ政策金利（OCR）データの型
export interface NzRbnzRateItem {
  date: string
  value: number
}

export interface NzRbnzRateNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  datetime_auckland: string
  time_auckland: string
  label: string
  estimate: number | null
}

export interface NzRbnzRateData {
  data: NzRbnzRateItem[]
  latest: NzRbnzRateItem | null
  metadata: Record<string, unknown>
  next_release?: NzRbnzRateNextRelease | null
}

// RBNZ MPS経済見通しデータの型
export interface NzMpsForecastPoint {
  date: string
  value: number | null
}

export interface NzMpsSimpleIndicator {
  latest: NzMpsForecastPoint[]
  previous: NzMpsForecastPoint[]
  name_jp: string
  name_en: string
  unit: string
}

export interface NzMpsMultiSeriesIndicator {
  series: Record<string, NzMpsForecastPoint[]>
  series_config: { key: string; name: string }[]
  name_jp: string
  name_en: string
  unit: string
}

export interface NzMpsMultiLatestPreviousIndicator {
  series: Record<string, { latest: NzMpsForecastPoint[]; previous: NzMpsForecastPoint[] }>
  series_config: { key: string; name: string }[]
  name_jp: string
  name_en: string
  unit: string
}

export interface NzMpsForecastMetadata {
  source: string
  indicator: string
  latest_publication: string
  previous_publication: string
  filename: string
  last_updated: string
}

export interface NzMpsForecastData {
  indicators: {
    ocr: NzMpsSimpleIndicator
    gdp_qoq: NzMpsSimpleIndicator
    cpi_headline: NzMpsMultiSeriesIndicator
    inflation_components: NzMpsMultiLatestPreviousIndicator
    wage_inflation: NzMpsSimpleIndicator
    output_gap: NzMpsSimpleIndicator
    unemployment_rate: NzMpsSimpleIndicator
    neutral_ocr: NzMpsMultiSeriesIndicator
  }
  metadata: NzMpsForecastMetadata
}

// RBNZ中央銀行バランスシートデータの型
export interface NzBalanceSheetItem {
  date: string
  value: number
}

export interface NzBalanceSheetNextRelease {
  date: string
  label: string
  estimated: boolean
}

export interface NzBalanceSheetData {
  data: NzBalanceSheetItem[]
  latest: NzBalanceSheetItem | null
  metadata: Record<string, unknown>
  next_release?: NzBalanceSheetNextRelease | null
}

// NZ銀行バランスシートデータの型
export interface NzBankBalanceSheetItem {
  date: string
  value: number
}

export interface NzBankBalanceSheetNextRelease {
  date: string
  label: string
  estimated: boolean
}

export interface NzBankBalanceSheetData {
  data: NzBankBalanceSheetItem[]
  latest: NzBankBalanceSheetItem | null
  metadata: Record<string, unknown>
  next_release?: NzBankBalanceSheetNextRelease | null
}

// ニュージーランド金融政策ダッシュボードデータの型
// =============================================================================
// 中国（China）
// =============================================================================

export interface CnLprItem {
  date: string
  value: number | null
  forecast: number | null
  previous: number | null
}

export interface CnLprData {
  data: CnLprItem[]
  latest: CnLprItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string; label?: string; time_jst?: string } | null
}

export interface ChReverseRepoItem {
  date: string
  value: number | null
  bid_amount: number | null
  win_amount: number | null
}

export interface ChReverseRepoData {
  data: ChReverseRepoItem[]
  latest: ChReverseRepoItem | null
  metadata: Record<string, unknown>
}

export interface ChRrrItem {
  date: string
  value: number | null
}

export interface ChRrrData {
  data: ChRrrItem[]
  latest: ChRrrItem | null
  metadata: Record<string, unknown>
}

export interface ChCbsItem {
  date: string
  value: number | null
}

export interface ChCbsNextRelease {
  date: string   // YYYY-MM-DD
  label: string  // e.g. "Central Bank Balance Sheet (Mar)"
}

export interface ChCbsData {
  data: ChCbsItem[]
  latest: ChCbsItem | null
  metadata: Record<string, unknown>
  next_release?: ChCbsNextRelease | null
}

export interface ChM1M2Item {
  date: string
  m2: number | null
  m1: number | null
  m2_yoy: number | null
  m1_yoy: number | null
}

export interface ChM1M2NextRelease {
  date: string   // YYYY-MM-DD
  label: string  // e.g. "M1/M2 Money Supply (Mar)"
}

export interface ChM1M2Data {
  data: ChM1M2Item[]
  latest: ChM1M2Item | null
  metadata: Record<string, unknown>
  next_release?: ChM1M2NextRelease | null
}

export interface CnAggregateFinancingItem {
  date: string
  flow: number | null   // 100億元単位（月次フロー）
  stock: number | null  // 兆元単位（月末残高）
  yoy: number | null    // 残高前年比（%）
}

export interface CnAggregateFinancingNextRelease {
  date: string
  datetime_jst?: string
  time_jst?: string
  label?: string
  estimate?: number | null
}

export interface CnAggregateFinancingData {
  data: CnAggregateFinancingItem[]
  latest: CnAggregateFinancingItem | null
  metadata: Record<string, unknown>
  next_release?: CnAggregateFinancingNextRelease | null
}

export interface CnNewRmbLoansItem {
  date: string
  stock: number | null   // 亿元（全項貸款残高）
  flow: number | null    // 亿元（月次新増人民元貸出）
  stock_yoy: number | null // 残高前年比（%）
}

export interface CnNewRmbLoansNextRelease {
  date: string
  datetime_jst?: string
  time_jst?: string
  label?: string
  estimate?: number | null
}

export interface CnNewRmbLoansData {
  data: CnNewRmbLoansItem[]
  latest: CnNewRmbLoansItem | null
  metadata: Record<string, unknown>
  next_release?: CnNewRmbLoansNextRelease | null
}

export interface CnForexReservesItem {
  date: string
  value: number | null   // 亿美元（Foreign currency reserves）
  yoy: number | null     // 前年比（%）
}

export interface CnForexReservesNextRelease {
  date: string
  datetime_jst?: string
  time_jst?: string
  label?: string
  estimate?: number | null
}

export interface CnForexReservesData {
  data: CnForexReservesItem[]
  latest: CnForexReservesItem | null
  metadata: Record<string, unknown>
  next_release?: CnForexReservesNextRelease | null
}

export interface ChinaPolicyData {
  cn_lpr_1y: CnLprData | null
  cn_lpr_5y: CnLprData | null
  ch_reverse_repo_rate: ChReverseRepoData | null
  china_reserve_requirement_ratio_for_large_banks: ChRrrData | null
  ch_central_bank_balance_sheet: ChCbsData | null
  ch_m1_m2: ChM1M2Data | null
  cn_aggregate_financing_to_the_real_economy: CnAggregateFinancingData | null
  cn_new_rmb_loans: CnNewRmbLoansData | null
  cn_foreign_exchange_reserves: CnForexReservesData | null
  cn_local_bonds: CnLocalBondsData | null
  cn_overseas_investor_flow: CnOverseasInvestorFlowData | null
  cn_capital_flows: CnCapitalFlowsData | null
}

export interface CnCapitalFlowsItem {
  date: string
  net_total: number | null
  net_current: number | null
  net_goods: number | null
  net_services: number | null
  net_capital: number | null
  net_securities: number | null
  net_other: number | null
}

export interface CnCapitalFlowsData {
  data: CnCapitalFlowsItem[]
  latest: CnCapitalFlowsItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string; [key: string]: unknown } | null
}

/**
 * 中国金融政策ダッシュボード専用フック
 * LPR（ローンプライムレート）などを取得
 */
export function useChinaPolicyDashboard(): UseQueryResult<DashboardResponse<ChinaPolicyData>, Error> {
  return useDashboardData<ChinaPolicyData>('china', 'policy')
}

export interface NewZealandPolicyData {
  nz_rbnz_rate: NzRbnzRateData | null
  nz_economic_forecast: NzMpsForecastData | null
  nz_central_bank_balance_sheet: NzBalanceSheetData | null
  nz_bank_balance_sheet: NzBankBalanceSheetData | null
}

/**
 * ニュージーランド金融政策ダッシュボード専用フック
 * RBNZ政策金利などを取得
 */
export function useNewZealandPolicyDashboard(): UseQueryResult<DashboardResponse<NewZealandPolicyData>, Error> {
  return useDashboardData<NewZealandPolicyData>('newzealand', 'policy')
}

// NZ CPI（消費者物価指数）データの型
export interface NzCpiItem {
  date: string
  all_qoq: number | null
  all_yoy: number | null
  tradable_qoq: number | null
  tradable_yoy: number | null
  non_tradable_qoq: number | null
  non_tradable_yoy: number | null
}

export interface NzCpiData {
  data: NzCpiItem[]
  latest: NzCpiItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string; label?: string; time_jst?: string } | null
}

// NZ CPI項目別データの型
export interface NzCpiItemItem {
  date: string
  food_yoy: number | null
  rentals_yoy: number | null
  purchase_housing_yoy: number | null
  electricity_yoy: number | null
  gas_yoy: number | null
}

export interface NzCpiItemData {
  data: NzCpiItemItem[]
  latest: NzCpiItemItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string; label?: string; time_jst?: string } | null
}

// NZ インフレ期待データの型
export interface NzInflationExpectationsItem {
  date: string
  one_year: number | null
  two_year: number | null
  five_year: number | null
  ten_year: number | null
}

export interface NzInflationExpectationsData {
  data: NzInflationExpectationsItem[]
  latest: NzInflationExpectationsItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string; label?: string; time_jst?: string } | null
}

// NZ PPI（生産者物価指数）データの型
export interface NzPpiItem {
  date: string
  output_index: number | null
  output_qoq: number | null
  output_yoy: number | null
  input_index: number | null
  input_qoq: number | null
  input_yoy: number | null
}

export interface NzPpiData {
  data: NzPpiItem[]
  latest: NzPpiItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string; label?: string; time_jst?: string } | null
}

// NZ ANZ企業景況感物価関連（PDFスクリーンショット）
export interface NzAnzBusinessOutlookPriceData {
  page2_exists: boolean
  last_updated: string | null
  pdf_date: string | null
  next_release: { date: string; label?: string; time_jst?: string } | null
}

// ニュージーランド物価ダッシュボードデータの型
export interface NewZealandInflationData {
  nz_cpi: NzCpiData | null
  nz_cpi_item: NzCpiItemData | null
  nz_ppi: NzPpiData | null
  nz_inflation_expectations: NzInflationExpectationsData | null
  nz_anz_business_outlook_price: NzAnzBusinessOutlookPriceData | null
}

/**
 * ニュージーランド物価ダッシュボード専用フック
 * PPI等を取得
 */
export function useNewZealandInflationDashboard(): UseQueryResult<DashboardResponse<NewZealandInflationData>, Error> {
  return useDashboardData<NewZealandInflationData>('newzealand', 'inflation')
}

// NZ 雇用者数データの型
export interface NzNumberOfEmployeesItem {
  date: string
  total: number | null
  fulltime: number | null
  parttime: number | null
  total_qoq: number | null
  fulltime_qoq: number | null
  parttime_qoq: number | null
  total_yoy: number | null
  fulltime_yoy: number | null
  parttime_yoy: number | null
}

export interface NzNumberOfEmployeesData {
  data: NzNumberOfEmployeesItem[]
  latest: NzNumberOfEmployeesItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string; label?: string; time_jst?: string } | null
}

// NZ 失業率データの型
export interface NzUnemploymentRateItem {
  date: string
  value: number | null
}

export interface NzUnemploymentRateData {
  data: NzUnemploymentRateItem[]
  latest: NzUnemploymentRateItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string; label?: string; time_jst?: string } | null
}

// NZ 賃金データの型
export interface NzWagesItem {
  date: string
  wage_index: number | null
  wage_index_qoq: number | null
  wage_index_yoy: number | null
  hourly_earnings: number | null
  hourly_earnings_qoq: number | null
  hourly_earnings_yoy: number | null
}

export interface NzWagesData {
  data: NzWagesItem[]
  latest: NzWagesItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string; label?: string; time_jst?: string } | null
}

// NZ 労働参加率データの型
export interface NzLabourForceParticipationItem {
  date: string
  value: number | null
}

export interface NzLabourForceParticipationData {
  data: NzLabourForceParticipationItem[]
  latest: NzLabourForceParticipationItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string; label?: string; time_jst?: string } | null
}

export interface NzLaborCostIndexItem {
  date: string
  value: number | null
  qoq: number | null
  yoy: number | null
}

export interface NzLaborCostIndexData {
  data: NzLaborCostIndexItem[]
  latest: NzLaborCostIndexItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string; label?: string; time_jst?: string } | null
}

// ニュージーランド雇用ダッシュボードデータの型
export interface NewZealandEmploymentData {
  nz_number_of_employees: NzNumberOfEmployeesData | null
  nz_unemployment_rate: NzUnemploymentRateData | null
  nz_wages: NzWagesData | null
  nz_labour_force_participation: NzLabourForceParticipationData | null
  nz_labor_cost_index: NzLaborCostIndexData | null
}

/**
 * ニュージーランド雇用ダッシュボード専用フック
 * 雇用者数・失業率等を取得
 */
export function useNewZealandEmploymentDashboard(): UseQueryResult<DashboardResponse<NewZealandEmploymentData>, Error> {
  return useDashboardData<NewZealandEmploymentData>('newzealand', 'employment')
}

// =============================================================================
// ニュージーランド消費
// =============================================================================

export interface NzRetailSalesItem {
  date: string
  total_qoq: number | null
  core_qoq: number | null
  total_yoy: number | null
  core_yoy: number | null
}

export interface NzRetailSalesData {
  data: NzRetailSalesItem[]
  latest: NzRetailSalesItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string; label?: string; time_jst?: string } | null
}

export interface NzAnzBusinessOutlookSurveyItem {
  date: string
  value: number | null
}

export interface NzAnzBusinessOutlookSurveyData {
  data: NzAnzBusinessOutlookSurveyItem[]
  latest: NzAnzBusinessOutlookSurveyItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string; label?: string; time_jst?: string } | null
}

export interface NzNzierBusinessConditionsIndexItem {
  date: string
  value: number | null
}

export interface NzNzierBusinessConditionsIndexData {
  data: NzNzierBusinessConditionsIndexItem[]
  latest: NzNzierBusinessConditionsIndexItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string; label?: string; time_jst?: string } | null
}

// ニュージーランド消費ダッシュボードデータの型
export interface NewZealandConsumerData {
  nz_retail_sales: NzRetailSalesData | null
  nz_anz_business_outlook_survey: NzAnzBusinessOutlookSurveyData | null
  nz_nzier_business_conditions_index: NzNzierBusinessConditionsIndexData | null
}

/**
 * ニュージーランド消費ダッシュボード専用フック
 * 小売売上高等を取得
 */
export function useNewZealandConsumerDashboard(): UseQueryResult<DashboardResponse<NewZealandConsumerData>, Error> {
  return useDashboardData<NewZealandConsumerData>('newzealand', 'consumer')
}

// =============================================================================
// ニュージーランド経済
// =============================================================================

export interface NzGdpGrowthRateItem {
  date: string
  qoq: number | null
  yoy: number | null
}

export interface NzGdpGrowthRateData {
  data: NzGdpGrowthRateItem[]
  latest: NzGdpGrowthRateItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string; label?: string } | null
}

export interface NzGdpItemItem {
  date: string
  hce_qoq: number | null
  gfcf_qoq: number | null
  exports_qoq: number | null
  imports_qoq: number | null
  gdp_expenditure_qoq: number | null
  net_exports_qoq: number | null
  hce_yoy: number | null
  gfcf_yoy: number | null
  exports_yoy: number | null
  imports_yoy: number | null
  gdp_expenditure_yoy: number | null
  net_exports_yoy: number | null
  inventories: number | null
  inventories_diff: number | null
  inventories_yoy_diff: number | null
  net_exports: number | null
}

export interface NzGdpItemData {
  data: NzGdpItemItem[]
  latest: NzGdpItemItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string; label?: string } | null
}

export interface NzCapacityUtilizationItem {
  date: string
  value: number | null
}

export interface NzCapacityUtilizationData {
  data: NzCapacityUtilizationItem[]
  latest: NzCapacityUtilizationItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string; label?: string; time_jst?: string } | null
}

export interface NzPmiItem {
  date: string
  value: number | null
}

export interface NzPmiData {
  data: NzPmiItem[]
  latest: NzPmiItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string; label?: string; time_jst?: string } | null
}

export interface NzGlobalDairyTradeItem {
  date: string
  value: number | null
}

export interface NzGlobalDairyTradeData {
  data: NzGlobalDairyTradeItem[]
  latest: NzGlobalDairyTradeItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string; label?: string; time_jst?: string } | null
}

export interface NzTermsOfTradeItem {
  date: string
  terms_of_trade_qoq: number | null
  export_price_qoq: number | null
  import_price_qoq: number | null
  terms_of_trade_yoy: number | null
  export_price_yoy: number | null
  import_price_yoy: number | null
}

export interface NzTermsOfTradeData {
  data: NzTermsOfTradeItem[]
  latest: NzTermsOfTradeItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string; label?: string; time_jst?: string } | null
}

export interface NzTradeBalanceItem {
  date: string
  exports: number | null
  imports: number | null
  balance: number | null
}

export interface NzTradeBalanceData {
  data: NzTradeBalanceItem[]
  latest: NzTradeBalanceItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string; label?: string; time_jst?: string } | null
}

export interface NzCurrentAccountBalanceItem {
  date: string
  value: number | null
  qoq_change: number | null
}

export interface NzCurrentAccountBalanceData {
  data: NzCurrentAccountBalanceItem[]
  latest: NzCurrentAccountBalanceItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string; label?: string; time_jst?: string } | null
}

export interface NzCurrentAccountGdpRatioItem {
  date: string
  ratio: number | null
  ca_value: number | null
  gdp_value: number | null
}

export interface NzCurrentAccountGdpRatioData {
  data: NzCurrentAccountGdpRatioItem[]
  latest: NzCurrentAccountGdpRatioItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string; label?: string; time_jst?: string } | null
}

// ニュージーランド経済ダッシュボードデータの型
export interface NewZealandEconomyData {
  nz_gdp_growth_rate: NzGdpGrowthRateData | null
  nz_gdp_item: NzGdpItemData | null
  nz_capacity_utilization: NzCapacityUtilizationData | null
  nz_pmi: NzPmiData | null
  nz_psi: NzPmiData | null
  nz_pci: NzPmiData | null
  nz_global_dairy_trade: NzGlobalDairyTradeData | null
  nz_terms_of_trade: NzTermsOfTradeData | null
  nz_trade_balance: NzTradeBalanceData | null
  nz_current_account_balance: NzCurrentAccountBalanceData | null
  nz_current_account_gdp_ratio: NzCurrentAccountGdpRatioData | null
}

/**
 * ニュージーランド経済ダッシュボード専用フック
 * GDP成長率等を取得
 */
export function useNewZealandEconomyDashboard(): UseQueryResult<DashboardResponse<NewZealandEconomyData>, Error> {
  return useDashboardData<NewZealandEconomyData>('newzealand', 'economy')
}

// ============================================================================
// 中国住宅
// ============================================================================

export interface CnCommercialResidentialSalesItem {
  date: string
  floor_started_yoy?: number | null
  sales_yoy?: number | null
  floor_sold_yoy?: number | null
}

export interface CnCommercialResidentialSalesNextRelease {
  date: string
  datetime_jst: string
  time_jst: string
  label: string
}

export interface CnCommercialResidentialSalesData {
  data: CnCommercialResidentialSalesItem[]
  latest: CnCommercialResidentialSalesItem | null
  metadata: Record<string, unknown>
  next_release?: CnCommercialResidentialSalesNextRelease | null
}

export interface CnHousePriceIndexItem {
  date: string
  value: number | null
  forecast?: number | null
  previous?: number | null
}

export interface CnHousePriceIndexNextRelease {
  date: string
  datetime_jst: string
  time_jst: string
  label: string
  estimate?: number | null
}

export interface CnHousePriceIndexData {
  data: CnHousePriceIndexItem[]
  latest: CnHousePriceIndexItem | null
  metadata?: Record<string, unknown>
  next_release?: CnHousePriceIndexNextRelease | null
}

export interface ChinaHousingData {
  cn_commercial_residential_sales: CnCommercialResidentialSalesData | null
  cn_house_price_index: CnHousePriceIndexData | null
}

/**
 * 中国住宅ダッシュボード専用フック
 */
export function useChinaHousingDashboard(): UseQueryResult<DashboardResponse<ChinaHousingData>, Error> {
  return useDashboardData<ChinaHousingData>('china', 'housing')
}

// =============================================================================
// 中国インフレーション
// =============================================================================

export interface CnPpiItem {
  date: string
  yoy: number | null
  mom: number | null
}

export interface CnPpiNextRelease {
  date: string
  datetime_jst: string
  time_jst: string
  label: string
  estimate?: number | null
}

export interface CnPpiData {
  data: CnPpiItem[]
  latest: CnPpiItem | null
  metadata?: Record<string, unknown>
  next_release?: CnPpiNextRelease | null
}

export interface CnCpiItem {
  date: string
  yoy: number | null
  mom: number | null
  food_yoy: number | null
  food_mom: number | null
  nonfood_yoy: number | null
  nonfood_mom: number | null
  core_yoy: number | null
  core_mom: number | null
}

export interface CnCpiNextRelease {
  date: string
  datetime_jst: string
  time_jst: string
  label: string
  estimate?: number | null
}

export interface CnCpiData {
  data: CnCpiItem[]
  latest: CnCpiItem | null
  metadata?: Record<string, unknown>
  next_release?: CnCpiNextRelease | null
}

export interface CnExportPricesItem {
  date: string
  index: number | null
  yoy: number | null
  mom: number | null
}

export interface CnExportPricesData {
  data: CnExportPricesItem[]
  latest: CnExportPricesItem | null
  metadata?: Record<string, unknown>
  next_release?: null
}

export interface ChinaInflationData {
  cn_cpi: CnCpiData | null
  cn_ppi: CnPpiData | null
  cn_export_prices: CnExportPricesData | null
}

/**
 * 中国インフレーションダッシュボード専用フック
 */
export function useChinaInflationDashboard(): UseQueryResult<DashboardResponse<ChinaInflationData>, Error> {
  return useDashboardData<ChinaInflationData>('china', 'inflation')
}

// --- 中国雇用 ---
export interface CnUnemploymentRateItem {
  date: string
  total: number | null
  youth: number | null
}

export interface CnUnemploymentRateNextRelease {
  date: string
  datetime_jst: string
  time_jst: string
  label: string
  estimate?: number | null
}

export interface CnUnemploymentRateData {
  data: CnUnemploymentRateItem[]
  latest: CnUnemploymentRateItem | null
  metadata?: Record<string, unknown>
  next_release?: CnUnemploymentRateNextRelease | null
}

// --- 中国消費 ---

export interface CnRetailSalesItem {
  date: string
  yoy: number | null
}

export interface CnRetailSalesNextRelease {
  date: string
  datetime_jst: string
  time_jst: string
  label: string
  estimate?: number | null
}

export interface CnRetailSalesData {
  data: CnRetailSalesItem[]
  latest: CnRetailSalesItem | null
  metadata?: Record<string, unknown>
  next_release?: CnRetailSalesNextRelease | null
}

export interface ChinaConsumerData {
  cn_retail_sales: CnRetailSalesData | null
}

/**
 * 中国消費ダッシュボード専用フック
 */
export function useChinaConsumerDashboard(): UseQueryResult<DashboardResponse<ChinaConsumerData>, Error> {
  return useDashboardData<ChinaConsumerData>('china', 'consumer')
}

export interface ChinaEmploymentData {
  cn_unemployment_rate: CnUnemploymentRateData | null
}

/**
 * 中国雇用ダッシュボード専用フック
 */
export function useChinaEmploymentDashboard(): UseQueryResult<DashboardResponse<ChinaEmploymentData>, Error> {
  return useDashboardData<ChinaEmploymentData>('china', 'employment')
}

// ---------------------------------------------------------------------------
// 中国経済（China Economy）
// ---------------------------------------------------------------------------

export interface CnGdpGrowthRateItem {
  date: string
  yoy: number | null
  qoq: number | null
}

export interface CnGdpGrowthRateNextRelease {
  date: string
  datetime_jst: string
  time_jst: string
  label: string
  estimate: number | null
}

export interface CnGdpGrowthRateData {
  data: CnGdpGrowthRateItem[]
  latest: CnGdpGrowthRateItem | null
  metadata: Record<string, unknown>
  next_release?: CnGdpGrowthRateNextRelease | null
}

export interface CnIndustrialProductionItem {
  date: string
  yoy: number | null
}

export interface CnIndustrialProductionNextRelease {
  date: string
  datetime_jst: string
  time_jst: string
  label: string
  estimate: number | null
}

export interface CnIndustrialProductionData {
  data: CnIndustrialProductionItem[]
  latest: CnIndustrialProductionItem | null
  metadata: Record<string, unknown>
  next_release?: CnIndustrialProductionNextRelease | null
}

export interface CnFixedAssetInvestmentItem {
  date: string
  ytd: number | null
}

export interface CnFixedAssetInvestmentNextRelease {
  date: string
  datetime_jst: string
  time_jst: string
  label: string
  estimate: number | null
}

export interface CnFixedAssetInvestmentData {
  data: CnFixedAssetInvestmentItem[]
  latest: CnFixedAssetInvestmentItem | null
  metadata: Record<string, unknown>
  next_release?: CnFixedAssetInvestmentNextRelease | null
}

export interface CnBeijingPm25DailyItem {
  date: string
  pm25: number
}

export interface CnBeijingPm25MonthlyItem {
  date: string
  pm25_avg: number
}

export interface CnBeijingPm25Ma30Item {
  date: string
  pm25_ma30: number
}

export interface CnBeijingPm25Data {
  daily: CnBeijingPm25DailyItem[]
  monthly: CnBeijingPm25MonthlyItem[]
  ma30: CnBeijingPm25Ma30Item[]
  latest: CnBeijingPm25DailyItem | null
  latest_monthly: CnBeijingPm25MonthlyItem | null
  metadata: Record<string, unknown>
}

// --- PMI（購買担当者景況指数）---
export interface CnPmiHeadlineItem {
  date: string
  manufacturing: number | null
  non_manufacturing: number | null
  composite: number | null
}

export interface CnPmiMfgSubItem {
  date: string
  production: number | null
  new_orders: number | null
  new_export_orders: number | null
  in_hand_orders: number | null
  employment: number | null
  raw_material_price: number | null
  producer_prices: number | null
  supplier_delivery: number | null
}

export interface CnPmiNmfSubItem {
  date: string
  services: number | null
  construction: number | null
  new_orders: number | null
  export_new_orders: number | null
  in_hand_orders: number | null
  sale_price: number | null
  input_price: number | null
  supplier_delivery: number | null
  employment: number | null
}

export interface CnPmiNextRelease {
  date: string
  datetime_jst?: string
  time_jst?: string
  label?: string
  estimate?: number | null
}

export interface CnPmiData {
  headline: {
    data: CnPmiHeadlineItem[]
    latest: CnPmiHeadlineItem | null
  } | null
  manufacturing_sub: {
    data: CnPmiMfgSubItem[]
    latest: CnPmiMfgSubItem | null
  } | null
  non_manufacturing_sub: {
    data: CnPmiNmfSubItem[]
    latest: CnPmiNmfSubItem | null
  } | null
  metadata: Record<string, unknown>
  next_release?: CnPmiNextRelease | null
}

// --- Caixin PMI（財新PMI）---
export interface CnCaixinPmiItem {
  date: string
  value: number | null
  forecast: number | null
  previous: number | null
}

export interface CnCaixinPmiNextRelease {
  date: string
  datetime_jst?: string
  time_jst?: string
  label?: string
  estimate?: number | null
}

export interface CnCaixinPmiData {
  manufacturing: {
    data: CnCaixinPmiItem[]
    latest: CnCaixinPmiItem | null
  } | null
  services: {
    data: CnCaixinPmiItem[]
    latest: CnCaixinPmiItem | null
  } | null
  next_release_manufacturing?: CnCaixinPmiNextRelease | null
  next_release_services?: CnCaixinPmiNextRelease | null
  metadata: Record<string, unknown>
}

// 中国貿易収支
export interface CnTradeBalanceItem {
  date: string
  value: number
}

export interface CnTradeBalanceNextRelease {
  date: string
  datetime_jst?: string
  time_jst?: string
  label?: string
  estimate?: number | null
}

export interface CnTradeBalanceData {
  balance: CnTradeBalanceItem[]
  exports: CnTradeBalanceItem[]
  imports: CnTradeBalanceItem[]
  balance_yoy: CnTradeBalanceItem[]
  exports_yoy: CnTradeBalanceItem[]
  imports_yoy: CnTradeBalanceItem[]
  balance_mom_diff: CnTradeBalanceItem[]
  exports_mom_diff: CnTradeBalanceItem[]
  imports_mom_diff: CnTradeBalanceItem[]
  latest_balance: CnTradeBalanceItem | null
  latest_exports: CnTradeBalanceItem | null
  latest_imports: CnTradeBalanceItem | null
  metadata: Record<string, unknown>
  next_release?: CnTradeBalanceNextRelease | null
}

// 中国 集積回路生産 (Integrated Circuit Manufacturing)
export interface CnIntegratedCircuitManufacturingItem {
  date: string
  raw_value: number | null
  yoy: number | null
  mom: number | null
}

export interface CnIntegratedCircuitManufacturingData {
  data: CnIntegratedCircuitManufacturingItem[]
  latest: CnIntegratedCircuitManufacturingItem | null
  metadata: Record<string, unknown>
  next_release?: null
}

// 中国 電気機器在庫 (Electronics Stock)
export interface CnElectronicsStockItem {
  date: string
  yoy: number | null
}

export interface CnElectronicsStockSoxItem {
  date: string
  sox_yoy: number | null
}

export interface CnElectronicsStockData {
  data: CnElectronicsStockItem[]
  sox_data: CnElectronicsStockSoxItem[]
  latest: CnElectronicsStockItem | null
  metadata: Record<string, unknown>
  next_release?: null
}

export interface ChinaEconomyData {
  cn_gdp_growth_rate: CnGdpGrowthRateData | null
  cn_industrial_production: CnIndustrialProductionData | null
  cn_fixed_asset_investment: CnFixedAssetInvestmentData | null
  cn_beijing_pm25: CnBeijingPm25Data | null
  cn_pmi: CnPmiData | null
  cn_caixin_pmi: CnCaixinPmiData | null
  cn_trade_balance: CnTradeBalanceData | null
  cn_current_account: CnCurrentAccountData | null
  cn_current_account_gdp_ratio: CnCurrentAccountGdpRatioData | null
  cn_land_sales_income: CnLandSalesIncomeData | null
  cn_integrated_circuit_manufacturing: CnIntegratedCircuitManufacturingData | null
  cn_electronics_stock: CnElectronicsStockData | null
}

// 中国 経常収支 (Current Account)
export interface CnCurrentAccountItem {
  date: string
  value: number
}

export interface CnCurrentAccountNextRelease {
  date: string
  datetime_jst?: string
  time_jst?: string
  label?: string
  estimate?: number | null
}

export interface CnCurrentAccountData {
  data: CnCurrentAccountItem[]
  qoq_diff: CnCurrentAccountItem[]
  yoy_diff: CnCurrentAccountItem[]
  latest: CnCurrentAccountItem | null
  metadata: Record<string, unknown>
  next_release?: CnCurrentAccountNextRelease | null
}

// 中国 経常収支対GDP比 (Current Account to GDP Ratio)
export interface CnCurrentAccountGdpRatioItem {
  date: string
  value: number
  current_account?: number
  gdp?: number
}

export interface CnCurrentAccountGdpRatioData {
  data: CnCurrentAccountGdpRatioItem[]
  latest: CnCurrentAccountGdpRatioItem | null
  metadata: Record<string, unknown>
  next_release?: CnCurrentAccountNextRelease | null
}

// 中国 土地売却収入 (Land Sales Income)
export interface CnLandSalesIncomeItem {
  date: string
  value: number
  yoy: number | null
  mom: number | null
  monthly_increment: number | null
}

export interface CnLandSalesIncomeData {
  data: CnLandSalesIncomeItem[]
  latest: CnLandSalesIncomeItem | null
  metadata: Record<string, unknown>
  next_release?: null
}

// 中国 地方政府債券 (Local Government Bonds)
export interface CnLocalBondsItem {
  date: string
  new_ratio: number | null
  special_ratio: number | null
  headroom: number | null
  cost: number | null
}

export interface CnLocalBondsData {
  data: CnLocalBondsItem[]
  latest: CnLocalBondsItem | null
  metadata: Record<string, unknown>
  next_release?: null
}

// 中国 海外投資家フロー (Overseas Investor Flow)
export interface CnOverseasInvestorFlowItem {
  date: string
  shch: number | null       // Shanghai Clearing House (RMB billion)
  ccdc: number | null       // China Central Depository & Clearing (RMB billion)
  total: number | null      // 合計 (RMB billion)
}

export interface CnOverseasInvestorFlowData {
  data: CnOverseasInvestorFlowItem[]
  latest: CnOverseasInvestorFlowItem | null
  metadata: Record<string, unknown>
  next_release?: null
}

/**
 * 中国経済ダッシュボード専用フック
 */
export function useChinaEconomyDashboard(): UseQueryResult<DashboardResponse<ChinaEconomyData>, Error> {
  return useDashboardData<ChinaEconomyData>('china', 'economy')
}

// ============================================================================
// グローバル経済
// ============================================================================

export interface GlobalManufacturingPmiItem {
  date: string
  value: number | null
}

export interface GlobalManufacturingPmiData {
  data: GlobalManufacturingPmiItem[]
  latest: GlobalManufacturingPmiItem | null
  metadata: Record<string, unknown>
  next_release?: null
}

export interface GlobalEpuItem {
  date: string
  value: number | null
}

export interface GlobalEpuData {
  data: GlobalEpuItem[]
  latest: GlobalEpuItem | null
  metadata: Record<string, unknown>
  next_release?: null
}

// WSTS 半導体売上高
export interface SemiconductorSalesItem {
  date: string
  worldwide: number | null
  americas: number | null
  europe: number | null
  japan: number | null
  asia_pacific: number | null
}

export interface SemiconductorSalesData {
  data: SemiconductorSalesItem[]
  yoy_data: SemiconductorSalesItem[]
  mma_data: SemiconductorSalesItem[]
  mma_yoy_data: SemiconductorSalesItem[]
  latest: SemiconductorSalesItem | null
  metadata: Record<string, unknown>
  next_release?: null
}

// 台湾PMI先行き（電子工学業）
export interface TaiwanPmiOutlookItem {
  date: string
  value: number | null
}

export interface TaiwanPmiOutlookData {
  data: TaiwanPmiOutlookItem[]
  latest: TaiwanPmiOutlookItem | null
  metadata: Record<string, unknown>
  next_release?: null
}

// 台湾製造業PMI（S&P Global）
export interface TaiwanManufacturingPmiItem {
  date: string
  value: number | null
  forecast: number | null
  previous: number | null
}

export interface TaiwanManufacturingPmiNextRelease {
  date: string
  datetime_jst: string
  time_jst: string
  label: string
  estimate: number | null
}

export interface TaiwanManufacturingPmiData {
  data: TaiwanManufacturingPmiItem[]
  latest: TaiwanManufacturingPmiItem | null
  metadata: Record<string, unknown>
  next_release?: TaiwanManufacturingPmiNextRelease | null
}

// 韓国輸出（前年比）
export interface SouthKoreanExportsItem {
  date: string
  value: number | null
  forecast: number | null
  previous: number | null
}

export interface SouthKoreanExportsNextRelease {
  date: string
  datetime_jst: string
  time_jst: string
  label: string
  estimate: number | null
}

export interface SouthKoreanExportsData {
  data: SouthKoreanExportsItem[]
  latest: SouthKoreanExportsItem | null
  metadata: Record<string, unknown>
  next_release?: SouthKoreanExportsNextRelease | null
}

// 韓国半導体輸出
export interface KrSemiconductorExportsItem {
  date: string
  value: number | null    // Billion USD
  yoy: number | null      // YoY%
  mom: number | null       // MoM%
}

export interface KrSemiconductorExportsNextRelease {
  date: string
  datetime_jst: string
  time_jst: string
  label: string
  estimate: number | null
}

export interface KrSemiconductorExportsData {
  data: KrSemiconductorExportsItem[]
  latest: KrSemiconductorExportsItem | null
  metadata: Record<string, unknown>
  next_release?: KrSemiconductorExportsNextRelease | null
}

// 台湾輸出受注（前年比）
export interface TaiwanExportOrdersItem {
  date: string
  value: number | null
  forecast: number | null
  previous: number | null
}

export interface TaiwanExportOrdersNextRelease {
  date: string
  datetime_jst: string
  time_jst: string
  label: string
  estimate: number | null
}

export interface TaiwanExportOrdersData {
  data: TaiwanExportOrdersItem[]
  latest: TaiwanExportOrdersItem | null
  metadata: Record<string, unknown>
  next_release?: TaiwanExportOrdersNextRelease | null
}

// 台湾電気機器輸出
export interface TaiwanElectricalEquipmentExportsItem {
  date: string
  value: number | null  // YoY%
  mom: number | null     // MoM%
  raw_value: number | null  // 百萬美元
}

export interface TaiwanElectricalEquipmentExportsData {
  data: TaiwanElectricalEquipmentExportsItem[]
  latest: TaiwanElectricalEquipmentExportsItem | null
  metadata: Record<string, unknown>
  next_release?: null
}

// 中国・上海コンテナ運賃指数
export interface ChinaShanghaiContainerFreightIndexItem {
  date: string
  scfi: number | null
  ccfi: number | null
}
export interface ChinaShanghaiContainerFreightIndexData {
  data: ChinaShanghaiContainerFreightIndexItem[]
  latest: ChinaShanghaiContainerFreightIndexItem | null
  metadata: Record<string, unknown>
  next_release?: null
}

// OECD CLI（景気先行指数）
export interface OecdCliItem {
  date: string
  g20: number | null
  g7: number | null
  a5m: number | null
  usa: number | null
  jpn: number | null
  chn: number | null
  deu: number | null
  gbr: number | null
  kor: number | null
  aus: number | null
  can: number | null
}
export interface OecdCliData {
  data: OecdCliItem[]
  latest: OecdCliItem | null
  metadata: Record<string, unknown>
  next_release?: { date: string } | null
}

// グローバル経済ダッシュボードデータの型
export interface GlobalEconomyData {
  jpmorgan_global_manufacturing_pmi: GlobalManufacturingPmiData | null
  economic_surprise_index_screenshot_url: string | null
  komtrax_screenshot_url: string | null
  global_epu: GlobalEpuData | null
  semiconductor_sales: SemiconductorSalesData | null
  taiwan_pmi_outlook: TaiwanPmiOutlookData | null
  taiwan_manufacturing_pmi: TaiwanManufacturingPmiData | null
  south_korean_exports: SouthKoreanExportsData | null
  kr_semiconductor_exports: KrSemiconductorExportsData | null
  taiwan_export_orders: TaiwanExportOrdersData | null
  taiwan_electrical_equipment_exports: TaiwanElectricalEquipmentExportsData | null
  china_shanghai_container_freight_index: ChinaShanghaiContainerFreightIndexData | null
  oecd_cli: OecdCliData | null
}

/**
 * グローバル経済ダッシュボード専用フック
 */
export function useGlobalEconomyDashboard(): UseQueryResult<DashboardResponse<GlobalEconomyData>, Error> {
  return useDashboardData<GlobalEconomyData>('global', 'economy')
}
