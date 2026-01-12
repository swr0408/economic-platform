/**
 * Eurex Three-Month Euro STR Futures OIS API utility
 * Fetches Eurex OIS curve data from backend
 */
import { fetchJson, logApiMeta } from '../apiUtils'

export interface EurexOISChartData {
  labels: string[]
  values: number[]
  contracts: string[]
  settle_values: number[]
  previous_values: (number | null)[]
  last_updated: string
  source: string
  current_date: string | null
  previous_date: string | null
}

export interface EurexOISResponse {
  current: {
    date: string | null
    data: EurexOISDataPoint[]
  }
  previous?: {
    date: string | null
    data: EurexOISDataPoint[]
  }
  last_updated: string
  source: string
  cached?: boolean
}

export interface EurexOISDataPoint {
  date: string
  sort_date: string
  contract: string
  settle: number
  implied_rate: number
}

/**
 * Fetch Eurex OIS chart data
 */
export async function fetchEurexOISChartData(refresh: boolean = false): Promise<EurexOISChartData> {
  const url = refresh ? '/api/eurozone/eurex-ois/chart?refresh=true' : '/api/eurozone/eurex-ois/chart'
  const result = await fetchJson<EurexOISChartData>(url)

  logApiMeta('Eurex OIS', {
    cached: false,
    source: result.source,
    response_time_ms: 0,
    count: result.labels?.length || 0
  })

  return result
}

/**
 * Fetch raw Eurex OIS data
 */
export async function fetchEurexOISData(refresh: boolean = false): Promise<EurexOISResponse> {
  const url = refresh ? '/api/eurozone/eurex-ois?refresh=true' : '/api/eurozone/eurex-ois'
  return fetchJson<EurexOISResponse>(url)
}

/**
 * Format date for display (YYYY/MM)
 */
export function formatEurexDate(dateStr: string): string {
  try {
    const [year, month] = dateStr.split('-')
    return `${year}/${month}`
  } catch {
    return dateStr
  }
}
