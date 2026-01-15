/**
 * Japan POS-UVPI API
 * 日本POS-UVPI（消費者購買単価指数）API
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export interface PosUvpiDataPoint {
  date: string
  chg_uvpi_total: number
}

export interface NextRelease {
  date: string
  datetime_jst?: string
  label?: string
}

export interface PosUvpiResponse {
  data: PosUvpiDataPoint[]
  latest: PosUvpiDataPoint | null
  next_release: NextRelease | null
  cached: boolean
  source: string
  last_updated: string | null
  error?: string
}

export async function fetchPosUvpiData(forceRefresh = false): Promise<PosUvpiResponse> {
  try {
    const params = new URLSearchParams()
    if (forceRefresh) {
      params.append('force_refresh', 'true')
    }

    const url = `${API_BASE_URL}/api/japan/pos-uvpi${params.toString() ? `?${params.toString()}` : ''}`
    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Error fetching POS-UVPI data:', error)
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
