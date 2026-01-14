/**
 * API utility for Japan CPI (Consumer Price Index) data
 * 全国消費者物価指数 & 東京都区部消費者物価指数
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export interface CPIDataPoint {
  date: string // YYYY-MM-01 format
  index: number | null // 指数
  yoy: number | null // 前年同月比 (%)
  mom: number | null // 前月比 (%)
  core_index: number | null // コア指数
  core_yoy: number | null // コア前年同月比 (%)
  core_mom: number | null // コア前月比 (%)
  core_core_index: number | null // コアコア指数
  core_core_yoy: number | null // コアコア前年同月比 (%)
  core_core_mom: number | null // コアコア前月比 (%)
}

export interface NextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  label?: string
}

export interface CPIResponse {
  data: CPIDataPoint[]
  latest?: CPIDataPoint
  next_release?: NextRelease | null
  last_updated?: string
  source?: string
  cached?: boolean
  error?: string
}

/**
 * Fetch Japan National CPI data (全国消費者物価指数)
 * @param force_refresh - Force refresh data from source
 */
export async function fetchNationalCPIData(force_refresh: boolean = false): Promise<CPIResponse> {
  try {
    const params = new URLSearchParams()
    if (force_refresh) {
      params.append('force_refresh', 'true')
    }

    const url = `${API_BASE_URL}/api/japan/national-cpi${params.toString() ? `?${params.toString()}` : ''}`
    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data: CPIResponse = await response.json()
    return data
  } catch (error) {
    console.error('Error fetching national CPI data:', error)
    return {
      data: [],
      error: error instanceof Error ? error.message : 'Unknown error',
    }
  }
}

/**
 * Fetch Japan Tokyo CPI data (東京都区部消費者物価指数)
 * @param force_refresh - Force refresh data from source
 */
export async function fetchTokyoCPIData(force_refresh: boolean = false): Promise<CPIResponse> {
  try {
    const params = new URLSearchParams()
    if (force_refresh) {
      params.append('force_refresh', 'true')
    }

    const url = `${API_BASE_URL}/api/japan/tokyo-cpi${params.toString() ? `?${params.toString()}` : ''}`
    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data: CPIResponse = await response.json()
    return data
  } catch (error) {
    console.error('Error fetching Tokyo CPI data:', error)
    return {
      data: [],
      error: error instanceof Error ? error.message : 'Unknown error',
    }
  }
}

/**
 * Force refresh National CPI data
 */
export async function refreshNationalCPIData(): Promise<CPIResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/japan/national-cpi/refresh`, {
      method: 'POST',
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data: CPIResponse = await response.json()
    return data
  } catch (error) {
    console.error('Error refreshing national CPI data:', error)
    return {
      data: [],
      error: error instanceof Error ? error.message : 'Unknown error',
    }
  }
}

/**
 * Force refresh Tokyo CPI data
 */
export async function refreshTokyoCPIData(): Promise<CPIResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/japan/tokyo-cpi/refresh`, {
      method: 'POST',
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data: CPIResponse = await response.json()
    return data
  } catch (error) {
    console.error('Error refreshing Tokyo CPI data:', error)
    return {
      data: [],
      error: error instanceof Error ? error.message : 'Unknown error',
    }
  }
}

// =============================================================================
// CPI 10大費目カテゴリ関連
// =============================================================================

export interface CPICategoryData {
  index: number | null
  yoy: number | null
  contribution: number | null
}

export interface CPICategory {
  code: string
  name: string
  current: CPICategoryData
  previous: CPICategoryData
}

export interface CPICategoriesData {
  current_month: string
  previous_month: string
  categories: CPICategory[]
}

export interface CPICategoriesResponse {
  data: CPICategoriesData
  next_release?: NextRelease | null
  last_updated?: string
  source?: string
  cached?: boolean
  error?: string
}

/**
 * Fetch Japan CPI 10 major categories data (10大費目)
 * @param force_refresh - Force refresh data from source
 */
export async function fetchCPICategoriesData(force_refresh: boolean = false): Promise<CPICategoriesResponse> {
  try {
    const params = new URLSearchParams()
    if (force_refresh) {
      params.append('force_refresh', 'true')
    }

    const url = `${API_BASE_URL}/api/japan/cpi-categories${params.toString() ? `?${params.toString()}` : ''}`
    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data: CPICategoriesResponse = await response.json()
    return data
  } catch (error) {
    console.error('Error fetching CPI categories data:', error)
    return {
      data: { current_month: '', previous_month: '', categories: [] },
      error: error instanceof Error ? error.message : 'Unknown error',
    }
  }
}

/**
 * Format category date for display (YYYY年MM月)
 * @param dateStr - Date string in YYYY-MM-DD format
 */
export function formatCategoryDate(dateStr: string): string {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    const year = date.getFullYear()
    const month = date.getMonth() + 1
    return `${year}年${month.toString().padStart(2, '0')}月`
  } catch {
    return dateStr
  }
}
