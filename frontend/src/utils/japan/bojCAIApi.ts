/**
 * BOJ Consumption Activity Index (CAI) API
 * 消費活動指数API
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export interface BOJCAIDataPoint {
  date: string
  nominal_cai: number | null
  real_cai: number | null
}

export interface BOJCAIResponse {
  data: BOJCAIDataPoint[]
  latest?: BOJCAIDataPoint
  last_updated: string
  source: string
  indicator?: string
  cached?: boolean
  error?: string
}

/**
 * Fetch BOJ CAI data
 */
export async function fetchBOJCAIData(forceRefresh = false): Promise<BOJCAIResponse> {
  const url = new URL(`${API_BASE_URL}/api/japan/boj-cai`)
  if (forceRefresh) {
    url.searchParams.append('force_refresh', 'true')
  }

  const response = await fetch(url.toString())

  if (!response.ok) {
    throw new Error(`Failed to fetch BOJ CAI data: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Fetch BOJ CAI chart data
 */
export async function fetchBOJCAIChartData(forceRefresh = false): Promise<BOJCAIResponse> {
  const url = new URL(`${API_BASE_URL}/api/japan/boj-cai/chart`)
  if (forceRefresh) {
    url.searchParams.append('force_refresh', 'true')
  }

  const response = await fetch(url.toString())

  if (!response.ok) {
    throw new Error(`Failed to fetch BOJ CAI chart data: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Force refresh BOJ CAI data
 */
export async function refreshBOJCAIData(): Promise<BOJCAIResponse> {
  const url = new URL(`${API_BASE_URL}/api/japan/boj-cai/refresh`)

  const response = await fetch(url.toString(), {
    method: 'POST',
  })

  if (!response.ok) {
    throw new Error(`Failed to refresh BOJ CAI data: ${response.statusText}`)
  }

  return response.json()
}
