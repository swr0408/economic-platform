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
  next_gdp_release: NextGDPRelease | null
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
