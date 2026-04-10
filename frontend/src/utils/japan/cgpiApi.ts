/**
 * API utility for Japan CGPI (Corporate Goods Price Index) data
 * 企業物価指数
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export interface CGPIDataPoint {
  date: string // YYYY-MM-01 format
  index: number | null // 指数
  yoy: number | null // 前年同月比 (%)
  mom: number | null // 前月比 (%)
}

export interface NextRelease {
  date: string
  datetime_jst?: string
  label?: string
}

export interface CGPIResponse {
  data: CGPIDataPoint[]
  latest?: CGPIDataPoint | null
  next_release?: NextRelease | null
  last_updated?: string
  source?: string
  cached?: boolean
  error?: string
}

/**
 * Fetch Japan CGPI data (企業物価指数)
 * @param force_refresh - Force refresh data from source
 */
export async function fetchCGPIData(force_refresh: boolean = false): Promise<CGPIResponse> {
  try {
    const params = new URLSearchParams()
    if (force_refresh) {
      params.append('force_refresh', 'true')
    }

    const url = `${API_BASE_URL}/api/japan/cgpi${params.toString() ? `?${params.toString()}` : ''}`
    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data: CGPIResponse = await response.json()
    return data
  } catch (error) {
    console.error('Error fetching CGPI data:', error)
    return {
      data: [],
      error: error instanceof Error ? error.message : 'Unknown error',
    }
  }
}

/**
 * Force refresh CGPI data
 */
export async function refreshCGPIData(): Promise<CGPIResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/japan/cgpi/refresh`, {
      method: 'POST',
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data: CGPIResponse = await response.json()
    return data
  } catch (error) {
    console.error('Error refreshing CGPI data:', error)
    return {
      data: [],
      error: error instanceof Error ? error.message : 'Unknown error',
    }
  }
}
