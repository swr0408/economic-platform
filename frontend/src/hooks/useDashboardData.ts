/**
 * ダッシュボードデータ取得フック
 * 国・カテゴリ別のバッチAPIを呼び出し、React Queryでキャッシュ管理
 */
import { useQuery, UseQueryResult } from '@tanstack/react-query'

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

// 米国経済データの型
export interface USAEconomyData {
  gdp_growth_rate: GDPGrowthItem[] | null
  gdp_contributions: GDPContributionsData | null
  gdp_components_growth: GDPComponentsGrowthItem[] | null
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

// 潜在成長率データの型
export interface PotentialGDPData {
  real: PotentialGDPItem[]
  nominal: PotentialGDPItem[]
}

export interface PotentialGDPItem {
  date: string
  value: number
}

// 銀行貸し出し態度データの型
export interface BankLendingData {
  data: BankLendingItem[]
  latest: BankLendingItem | null
  next_release: BankLendingNextRelease | null
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
  mom: number | null      // 前月比
  yoy: number | null      // 前年比
  ex_transport_mom: number | null  // 輸送除外の前月比
  ex_transport_yoy: number | null  // 輸送除外の前年比
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
  image_url: string | null    // スクリーンショットURL
  latest: OpenTableLatest | null
  last_updated: string | null
  source: string | null
}

export interface OpenTableLatest {
  date: string
  description: string
}

// 米国消費データの型
export interface USAConsumerData {
  retail_sales: RetailSalesData | null
  retail_control: RetailControlData | null
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

/**
 * ダッシュボードデータを取得するAPI関数
 */
async function fetchDashboardData<T>(
  country: string,
  category: string
): Promise<DashboardResponse<T>> {
  const response = await fetch(`/api/${country}/${category}/dashboard`)

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
  const response = await fetch(`/api/${country}/${category}/dashboard/light`)

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
  const response = await fetch(`/api/${country}/${category}/dashboard/heavy`)

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

// 米国雇用ダッシュボードデータの型
export interface USAEmploymentData {
  unemployment_rate: UnemploymentRateData | null
  unemployment_by_reason: UnemploymentByReasonData | null
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
// Zillow家賃指数、ケースシラー住宅価格指数、家賃CPIの前年比
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

// 日本金融政策ダッシュボードデータの型
export interface JapanPolicyData {
  boj_policy_rate: BOJPolicyRateData | null
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

// ユーロ圏金融政策ダッシュボードデータの型
export interface EurozonePolicyData {
  ecb_rates: ECBRatesData | null
  eurex_ois: EurexOISData | null
  ecb_macro_projections: ECBMacroProjectionsData | null
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

export interface ECBGDPData {
  gdp_growth_qoq: ECBGDPDataPoint[]
  gdp_growth_yoy: ECBGDPDataPoint[]
  metadata: ECBGDPMetadata
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
    enterprises: string
    households: string
  }
}

export interface ECBBLSData {
  enterprises: ECBBLSDataPoint[]
  households: ECBBLSDataPoint[]
  metadata: ECBBLSMetadata
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

export interface ECBProductionData {
  production_wda: ECBProductionDataPoint[]
  mom_change: ECBProductionMoMDataPoint[]
  yoy_change: ECBProductionDataPoint[]
  metadata: ECBProductionMetadata
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
  next_release?: string | null
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
