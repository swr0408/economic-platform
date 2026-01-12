/**
 * ECB預金ファシリティ金利API
 *
 * ECB金利データを取得するためのAPIクライアント
 */
import { fetchJson, logApiMeta, type ApiMeta } from '../apiUtils'

// 型定義
export interface ECBRateItem {
  date: string
  value: number
  forecast: number | null
  previous: number | null
}

export interface ECBRateNextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  datetime_cet?: string
  time_cet?: string
  label: string
  estimate?: number | null
}

export interface ECBRatesResponse {
  data: ECBRateItem[]
  latest: ECBRateItem | null
  next_release: ECBRateNextRelease | null
  meta: ApiMeta & {
    count: number
  }
}

/**
 * ECB金利データを取得
 */
export async function fetchECBRatesData(refresh: boolean = false): Promise<ECBRatesResponse> {
  const url = refresh ? '/api/eurozone/ecb-rates?refresh=true' : '/api/eurozone/ecb-rates'
  const result = await fetchJson<ECBRatesResponse>(url)

  logApiMeta('ECB Rates', {
    cached: result.meta.cached,
    source: result.meta.source,
    response_time_ms: result.meta.response_time_ms,
    count: result.meta.count
  })

  return result
}

/**
 * キャッシュステータスを取得
 */
export async function fetchECBRatesCacheStatus(): Promise<{
  indicator: string
  source: string
  cache_key: string
  exists: boolean
  last_updated: string | null
  data_count: number
  latest: ECBRateItem | null
  next_release: ECBRateNextRelease | null
  file_cache_exists: boolean
}> {
  return fetchJson('/api/eurozone/ecb-rates/cache/status')
}

/**
 * キャッシュを無効化
 */
export async function invalidateECBRatesCache(): Promise<{
  success: boolean
  message: string
}> {
  const response = await fetch('/api/eurozone/ecb-rates/cache/invalidate', {
    method: 'POST'
  })
  return response.json()
}
