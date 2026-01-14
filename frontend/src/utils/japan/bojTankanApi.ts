/**
 * BOJ Tankan API Client
 * 日銀短観 大企業業況判断DI
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export interface NextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  label?: string
}

export interface BOJTankanDataPoint {
  date: string
  large_manufacturing_current: number | null
  large_manufacturing_outlook: number | null
  large_non_manufacturing_current: number | null
  large_non_manufacturing_outlook: number | null
}

export interface BOJTankanResponse {
  data: BOJTankanDataPoint[]
  last_updated: string
  excel_url?: string
  cached: boolean
  source: string
  next_release?: NextRelease | null
  error?: string
}

export interface BOJTankanSeriesInfo {
  key: string
  name: string
  color: string
}

export interface BOJTankanChartMetadata {
  title: string
  unit: string
  series: BOJTankanSeriesInfo[]
}

export interface BOJTankanChartResponse {
  data: BOJTankanDataPoint[]
  metadata: BOJTankanChartMetadata
  last_updated: string
  cached: boolean
  source: string
  next_release?: NextRelease | null
  error?: string
}

/**
 * Fetch BOJ Tankan DI data
 */
export const fetchBOJTankanData = async (
  forceRefresh: boolean = false
): Promise<BOJTankanResponse> => {
  try {
    const url = new URL(`${API_BASE_URL}/api/japan/boj-tankan`)
    if (forceRefresh) {
      url.searchParams.append('force_refresh', 'true')
    }

    const response = await fetch(url.toString())

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Failed to fetch BOJ Tankan data:', error)
    throw error
  }
}

/**
 * Fetch BOJ Tankan data formatted for chart display
 */
export const fetchBOJTankanChartData = async (
  forceRefresh: boolean = false
): Promise<BOJTankanChartResponse> => {
  try {
    const url = new URL(`${API_BASE_URL}/api/japan/boj-tankan/chart`)
    if (forceRefresh) {
      url.searchParams.append('force_refresh', 'true')
    }

    const response = await fetch(url.toString())

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Failed to fetch BOJ Tankan chart data:', error)
    throw error
  }
}

/**
 * Format quarter date for display (YYYY-MM to YYYY年Q四半期)
 */
export const formatQuarterDate = (dateStr: string): string => {
  if (!dateStr) return ''

  const parts = dateStr.split('-')
  if (parts.length < 2) return dateStr

  const year = parts[0]
  const month = parseInt(parts[1], 10)

  // Determine quarter
  let quarter: number
  if (month <= 3) {
    quarter = 1
  } else if (month <= 6) {
    quarter = 2
  } else if (month <= 9) {
    quarter = 3
  } else {
    quarter = 4
  }

  return `${year}年Q${quarter}`
}

/**
 * Format table data with keys
 */
export const formatBOJTankanDataForTable = (
  data: BOJTankanDataPoint[]
): Array<BOJTankanDataPoint & { key: string }> => {
  return data.map((item, index) => ({
    ...item,
    key: `${item.date}-${index}`
  }))
}
