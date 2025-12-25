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

// CB消費者信頼感指数データの型（Investing.com）
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

// コントロールグループデータの型（Investing.comから取得）
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
    staleTime: options?.staleTime ?? 5 * 60 * 1000, // 5分
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
    staleTime: 5 * 60 * 1000,
    refetchOnMount: false,
  })

  // 重い指標を取得（軽量指標取得後に開始）
  const heavyQuery = useQuery({
    queryKey: ['dashboard', 'usa', 'economy', 'heavy'],
    queryFn: () => fetchDashboardHeavyData<Partial<USAEconomyData>>('usa', 'economy'),
    staleTime: 5 * 60 * 1000,
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

// 米国雇用ダッシュボードデータの型
export interface USAEmploymentData {
  unemployment_rate: UnemploymentRateData | null
  unemployment_by_reason: UnemploymentByReasonData | null
  cb_jobs_labor: CBJobsLaborData | null
  nonfarm_payrolls: NonfarmPayrollsData | null
  fullpart_time_employment: FullPartTimeEmploymentData | null
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
