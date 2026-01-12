/**
 * Eurozone HCOB PMI API
 * ユーロ圏PMI（製造業/サービス業/総合）API
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export interface EurozonePMIDataPoint {
  date: string // YYYY-MM-DD format
  value: number | null
  forecast: number | null
  previous: number | null
}

export interface EurozonePMITypeData {
  data: EurozonePMIDataPoint[]
  latest: EurozonePMIDataPoint | null
}

export interface EurozonePMIResponse {
  manufacturing: EurozonePMITypeData | null
  services: EurozonePMITypeData | null
  composite: EurozonePMITypeData | null
  next_release: {
    date: string
    datetime_utc: string
    datetime_cet: string
    time_cet: string
    label: string
    estimate?: number | null
  } | null
  cached: boolean
  source: string
  last_updated: string
  error?: string
}

/**
 * Fetch Eurozone HCOB PMI data
 */
export async function fetchEurozonePMIData(forceRefresh = false): Promise<EurozonePMIResponse> {
  const url = new URL(`${API_BASE_URL}/api/eurozone/pmi`)
  if (forceRefresh) {
    url.searchParams.append('refresh', 'true')
  }

  const response = await fetch(url.toString())

  if (!response.ok) {
    throw new Error(`Failed to fetch Eurozone PMI data: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Force refresh Eurozone PMI data
 */
export async function refreshEurozonePMIData(): Promise<EurozonePMIResponse> {
  const url = new URL(`${API_BASE_URL}/api/eurozone/pmi/refresh`)

  const response = await fetch(url.toString(), {
    method: 'POST',
  })

  if (!response.ok) {
    throw new Error(`Failed to refresh Eurozone PMI data: ${response.statusText}`)
  }

  return response.json()
}
