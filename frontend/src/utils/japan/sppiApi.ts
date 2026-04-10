/**
 * API utility for Japan SPPI (Services Producer Price Index) data
 * 企業向けサービス価格指数
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export interface SPPIDataPoint {
  date: string // YYYY-MM-01 format
  index: number | null // 指数
  yoy: number | null // 前年同月比 (%)
}

export interface NextRelease {
  date: string
  datetime_jst?: string
  label?: string
}

export interface SPPIResponse {
  data: SPPIDataPoint[]
  latest?: SPPIDataPoint | null
  next_release?: NextRelease | null
  last_updated?: string
  source?: string
  cached?: boolean
  error?: string
}

/**
 * Fetch Japan SPPI data (企業向けサービス価格指数)
 * @param force_refresh - Force refresh data from source
 */
export async function fetchSPPIData(force_refresh: boolean = false): Promise<SPPIResponse> {
  try {
    const params = new URLSearchParams()
    if (force_refresh) {
      params.append('force_refresh', 'true')
    }

    const url = `${API_BASE_URL}/api/japan/sppi${params.toString() ? `?${params.toString()}` : ''}`
    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data: SPPIResponse = await response.json()
    return data
  } catch (error) {
    console.error('Error fetching SPPI data:', error)
    return {
      data: [],
      error: error instanceof Error ? error.message : 'Unknown error',
    }
  }
}

/**
 * Force refresh SPPI data
 */
export async function refreshSPPIData(): Promise<SPPIResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/japan/sppi/refresh`, {
      method: 'POST',
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data: SPPIResponse = await response.json()
    return data
  } catch (error) {
    console.error('Error refreshing SPPI data:', error)
    return {
      data: [],
      error: error instanceof Error ? error.message : 'Unknown error',
    }
  }
}
