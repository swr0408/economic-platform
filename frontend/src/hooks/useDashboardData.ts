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
