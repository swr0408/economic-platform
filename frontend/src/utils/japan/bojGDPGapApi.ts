/**
 * 日銀 GDPギャップ API
 * 日銀GDPギャップデータをバックエンドから取得
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export interface BOJGDPGapDataPoint {
  date: string  // YYYY-QX format (e.g., "2024-Q1")
  value: number  // GDP gap in percentage
}

export interface NextRelease {
  date: string
  datetime_jst?: string
  label?: string
}

export interface BOJGDPGapResponse {
  data: BOJGDPGapDataPoint[]
  latest: BOJGDPGapDataPoint | null
  next_release: NextRelease | null
  cached: boolean
  source: string
  last_updated: string | null
  error?: string
}

export async function fetchBOJGDPGapData(forceRefresh = false): Promise<BOJGDPGapResponse> {
  try {
    const params = new URLSearchParams()
    if (forceRefresh) {
      params.append('force_refresh', 'true')
    }

    const url = `${API_BASE_URL}/api/japan/boj-gdp-gap${params.toString() ? `?${params.toString()}` : ''}`
    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Error fetching BOJ GDP Gap data:', error)
    return {
      data: [],
      latest: null,
      next_release: null,
      cached: false,
      source: 'error',
      last_updated: null,
      error: error instanceof Error ? error.message : 'Unknown error',
    }
  }
}

/**
 * Format quarter date for display
 * @param dateStr - Date string in YYYY-QX format (e.g., "2024-Q1")
 * @returns Formatted date string (e.g., "2024年Q1")
 */
export function formatQuarterDate(dateStr: string): string {
  try {
    const [year, quarter] = dateStr.split('-')
    return `${year}/${quarter}`
  } catch {
    return dateStr
  }
}

/**
 * Parse quarter date string to Date object
 * @param dateStr - Date string in YYYY-QX format
 * @returns Date object or null if invalid
 */
export function parseQuarterDate(dateStr: string): Date | null {
  try {
    const [year, quarter] = dateStr.split('-')
    const quarterNum = parseInt(quarter.replace('Q', ''))

    if (!year || !quarterNum || quarterNum < 1 || quarterNum > 4) {
      return null
    }

    // Convert quarter to month (Q1 = Jan, Q2 = Apr, Q3 = Jul, Q4 = Oct)
    const month = (quarterNum - 1) * 3
    return new Date(parseInt(year), month, 1)
  } catch {
    return null
  }
}
