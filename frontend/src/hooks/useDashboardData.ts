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
