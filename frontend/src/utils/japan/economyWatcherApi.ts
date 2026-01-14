/**
 * Economy Watcher Survey API
 * 景気ウォッチャー調査API
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export interface NextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  label?: string
}

export interface EconomyWatcherDataPoint {
  date: string // YYYY-MM-01 format
  total: number | null // Total DI (合計)
  household: number | null // Household-related DI (家計動向関連)
  corporate: number | null // Corporate-related DI (企業動向関連)
  employment: number | null // Employment-related DI (雇用関連)
}

export interface EconomyWatcherResponse {
  data: EconomyWatcherDataPoint[]
  latest?: EconomyWatcherDataPoint
  last_updated: string
  source: string
  indicator?: string
  cached?: boolean
  error?: string
}

export interface EconomyWatcherFullResponse {
  current: {
    data: EconomyWatcherDataPoint[]
    latest?: EconomyWatcherDataPoint
  }
  outlook: {
    data: EconomyWatcherDataPoint[]
    latest?: EconomyWatcherDataPoint
  }
  next_release?: NextRelease | null
  last_updated: string
  source: string
  cached?: boolean
  error?: string
}

/**
 * Fetch Economy Watcher Survey full data (both current and outlook)
 */
export async function fetchEconomyWatcherData(forceRefresh = false): Promise<EconomyWatcherFullResponse> {
  const url = new URL(`${API_BASE_URL}/api/japan/economy-watcher`)
  if (forceRefresh) {
    url.searchParams.append('force_refresh', 'true')
  }

  const response = await fetch(url.toString())

  if (!response.ok) {
    throw new Error(`Failed to fetch Economy Watcher data: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Fetch Economy Watcher Survey current conditions data (現状判断)
 */
export async function fetchEconomyWatcherCurrentData(forceRefresh = false): Promise<EconomyWatcherResponse> {
  const url = new URL(`${API_BASE_URL}/api/japan/economy-watcher/current`)
  if (forceRefresh) {
    url.searchParams.append('force_refresh', 'true')
  }

  const response = await fetch(url.toString())

  if (!response.ok) {
    throw new Error(`Failed to fetch Economy Watcher current data: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Fetch Economy Watcher Survey outlook data (先行き判断)
 */
export async function fetchEconomyWatcherOutlookData(forceRefresh = false): Promise<EconomyWatcherResponse> {
  const url = new URL(`${API_BASE_URL}/api/japan/economy-watcher/outlook`)
  if (forceRefresh) {
    url.searchParams.append('force_refresh', 'true')
  }

  const response = await fetch(url.toString())

  if (!response.ok) {
    throw new Error(`Failed to fetch Economy Watcher outlook data: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Force refresh Economy Watcher data
 */
export async function refreshEconomyWatcherData(): Promise<EconomyWatcherFullResponse> {
  const url = new URL(`${API_BASE_URL}/api/japan/economy-watcher/refresh`)

  const response = await fetch(url.toString(), {
    method: 'POST',
  })

  if (!response.ok) {
    throw new Error(`Failed to refresh Economy Watcher data: ${response.statusText}`)
  }

  return response.json()
}
