/**
 * Japan S&P Global PMI API
 * 日本PMI（製造業/サービス業/総合）API
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export interface JapanPMIDataPoint {
  date: string // YYYY-MM-DD format
  value: number | null
  forecast: number | null
  previous: number | null
}

export interface JapanPMITypeData {
  data: JapanPMIDataPoint[]
  latest: JapanPMIDataPoint | null
}

export interface JapanPMIResponse {
  manufacturing: JapanPMITypeData | null
  services: JapanPMITypeData | null
  composite: JapanPMITypeData | null
  next_release: {
    date: string
    datetime_utc: string
    datetime_jst: string
    time_jst: string
    label: string
    estimate?: number | null
  } | null
  cached: boolean
  source: string
  last_updated: string
  error?: string
}

/**
 * Fetch Japan S&P Global PMI data
 */
export async function fetchJapanPMIData(forceRefresh = false): Promise<JapanPMIResponse> {
  const url = new URL(`${API_BASE_URL}/api/japan/pmi`)
  if (forceRefresh) {
    url.searchParams.append('force_refresh', 'true')
  }

  const response = await fetch(url.toString())

  if (!response.ok) {
    throw new Error(`Failed to fetch Japan PMI data: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Force refresh Japan PMI data
 */
export async function refreshJapanPMIData(): Promise<JapanPMIResponse> {
  const url = new URL(`${API_BASE_URL}/api/japan/pmi/refresh`)

  const response = await fetch(url.toString(), {
    method: 'POST',
  })

  if (!response.ok) {
    throw new Error(`Failed to refresh Japan PMI data: ${response.statusText}`)
  }

  return response.json()
}
