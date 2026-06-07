/**
 * ロイター短観 API クライアント
 * 製造業 (FMP + DB + 手動CSV) / 非製造業 (手動CSV)
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export interface ReutersTankanDataPoint {
  date: string
  value: number | null
  forecast: number | null
  previous: number | null
}

export interface ReutersTankanSeriesData {
  data: ReutersTankanDataPoint[]
  latest: ReutersTankanDataPoint | null
}

export interface ReutersTankanNextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  label?: string
  estimate?: number | null
}

export interface ReutersTankanResponse {
  manufacturing: ReutersTankanSeriesData | null
  non_manufacturing: ReutersTankanSeriesData | null
  next_release: ReutersTankanNextRelease | null
  cached: boolean
  source: string
  last_updated: string
  error?: string
}

export async function fetchReutersTankanData(forceRefresh = false): Promise<ReutersTankanResponse> {
  const params = new URLSearchParams()
  if (forceRefresh) {
    params.append('force_refresh', 'true')
  }
  const qs = params.toString() ? `?${params.toString()}` : ''

  const response = await fetch(`${API_BASE_URL}/api/japan/reuters-tankan${qs}`)

  if (!response.ok) {
    throw new Error(`Failed to fetch Reuters Tankan data: ${response.statusText}`)
  }

  return response.json()
}
