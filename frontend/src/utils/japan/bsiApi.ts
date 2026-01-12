/**
 * API utility for fetching Japan BSI (Business Survey Index) data
 * 法人企業景気予測調査
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export type SheetName = 'ref1' | 'ref2' | 'ref3' | 'ref4'
export type PeriodType = 'actual' | 'forecast1' | 'forecast2'

export interface BSIDataPoint {
  date: string
  year: number
  quarter: string
  large_all_industries: number | null
  large_manufacturing: number | null
  large_non_manufacturing: number | null
  medium_all_industries: number | null
  small_all_industries: number | null
}

export interface BSIResponse {
  data: BSIDataPoint[]
  last_updated: string
  cached: boolean
  source: string
  description?: string
}

export interface BSIChartData {
  chart_data: {
    dates: string[]
    large_all_industries: (number | null)[]
    large_manufacturing: (number | null)[]
    large_non_manufacturing: (number | null)[]
    medium_all_industries: (number | null)[]
    small_all_industries: (number | null)[]
  }
  metadata: {
    title: string
    source: string
    series: Array<{
      key: string
      name: string
      color: string
    }>
  }
  last_updated: string
  cached: boolean
  source: string
}

export interface BSIComprehensiveResponse {
  data: BSIDataPoint[]
  sheet_name: string
  sheet_title: string
  sheet_description: string
  period_type: string
  last_updated: string
  cached: boolean
  source: string
}

export interface BSIComprehensiveChartData {
  chart_data: {
    dates: string[]
    large_all_industries: (number | null)[]
    large_manufacturing: (number | null)[]
    large_non_manufacturing: (number | null)[]
    medium_all_industries: (number | null)[]
    small_all_industries: (number | null)[]
  }
  sheet_name: string
  sheet_title: string
  sheet_description: string
  period_type: string
  period_label: string
  metadata: {
    title: string
    source: string
    series: Array<{
      key: string
      name: string
      color: string
    }>
  }
  last_updated: string
  cached: boolean
  source: string
}

export interface SheetInfo {
  sheets: Array<{
    name: string
    title: string
    description: string
  }>
  period_types: Array<{
    name: string
    label: string
  }>
}

/**
 * Fetch raw BSI data
 */
export async function fetchBSIData(forceRefresh: boolean = false): Promise<BSIResponse> {
  const url = `${API_BASE_URL}/api/japan/bsi?force_refresh=${forceRefresh}`
  const response = await fetch(url)

  if (!response.ok) {
    throw new Error(`Failed to fetch BSI data: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Fetch BSI data formatted for chart display
 */
export async function fetchBSIChartData(forceRefresh: boolean = false): Promise<BSIChartData> {
  const url = `${API_BASE_URL}/api/japan/bsi/chart?force_refresh=${forceRefresh}`
  const response = await fetch(url)

  if (!response.ok) {
    throw new Error(`Failed to fetch BSI chart data: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Fetch available sheet information
 */
export async function fetchBSISheetInfo(): Promise<SheetInfo> {
  const url = `${API_BASE_URL}/api/japan/bsi/sheets`
  const response = await fetch(url)

  if (!response.ok) {
    throw new Error(`Failed to fetch BSI sheet info: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Fetch comprehensive BSI data for specific sheet and period type
 */
export async function fetchBSIComprehensive(
  sheetName: SheetName,
  periodType: PeriodType,
  forceRefresh: boolean = false
): Promise<BSIComprehensiveResponse> {
  const params = new URLSearchParams()
  if (forceRefresh) {
    params.append('force_refresh', 'true')
  }

  const url = `${API_BASE_URL}/api/japan/bsi/${sheetName}/${periodType}?${params.toString()}`
  const response = await fetch(url)

  if (!response.ok) {
    throw new Error(`Failed to fetch BSI data: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Fetch comprehensive BSI data formatted for chart display
 */
export async function fetchBSIComprehensiveChart(
  sheetName: SheetName,
  periodType: PeriodType,
  forceRefresh: boolean = false
): Promise<BSIComprehensiveChartData> {
  const params = new URLSearchParams()
  if (forceRefresh) {
    params.append('force_refresh', 'true')
  }

  const url = `${API_BASE_URL}/api/japan/bsi/${sheetName}/${periodType}/chart?${params.toString()}`
  const response = await fetch(url)

  if (!response.ok) {
    throw new Error(`Failed to fetch BSI chart data: ${response.statusText}`)
  }

  return response.json()
}

// Helper function to get period type display name
export function getPeriodTypeDisplayName(periodType: PeriodType): string {
  const periodNames: Record<PeriodType, string> = {
    actual: '実績（当期）',
    forecast1: '見通し（翌期）',
    forecast2: '見通し（翌々期）',
  }
  return periodNames[periodType]
}

// Helper function to get sheet display name
export function getSheetDisplayName(sheetName: SheetName): string {
  const sheetNames: Record<SheetName, string> = {
    ref1: '貴社の景況',
    ref2: '国内の景況',
    ref3: '設備投資',
    ref4: '雇用',
  }
  return sheetNames[sheetName]
}

// Format quarter date for display
export function formatQuarterDate(dateStr: string): string {
  if (!dateStr) return ''

  try {
    const date = new Date(dateStr)
    const year = date.getFullYear()
    const month = date.getMonth() + 1
    const quarter = Math.ceil(month / 3)
    return `${year}年Q${quarter}`
  } catch {
    return dateStr
  }
}
