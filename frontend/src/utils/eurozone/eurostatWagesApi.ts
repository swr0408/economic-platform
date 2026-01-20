/**
 * Eurostat 賃金・給与API
 *
 * ユーロ圏の賃金・給与データを取得するためのAPIクライアント
 */
import { fetchJson, logApiMeta } from '../apiUtils'

// 型定義
export interface EurostatWagesDataPoint {
  date: string
  value: number
}

export interface EurostatWagesMetadata {
  source: string
  dataset: string
  area: string
  unit: string
  frequency: string
  adjustment: string
  sector: string
  description: string
}

export interface EurostatWagesNextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  datetime_cet?: string
  time_cet?: string
  label?: string
  estimate?: number | null
}

export interface EurostatWagesResponse {
  data: EurostatWagesDataPoint[]
  latest: EurostatWagesDataPoint | null
  metadata: EurostatWagesMetadata
  next_release: EurostatWagesNextRelease | null
  cached: boolean
  source: string
  last_updated: string
  error?: string
}

/**
 * 四半期日付をフォーマット（2024-Q1 → 2024 Q1）
 */
export const formatWagesDate = (dateStr: string): string => {
  return dateStr.includes('-Q') ? dateStr.replace('-', ' ') : dateStr
}

/**
 * 四半期日付を日本語フォーマット（2024-Q1 → 2024年1-3月期）
 */
export const formatWagesDateJP = (dateStr: string): string => {
  const match = dateStr.match(/^(\d{4})-Q(\d)$/)
  if (!match) return dateStr

  const year = match[1]
  const quarter = parseInt(match[2])
  const quarterNames = ['1-3月期', '4-6月期', '7-9月期', '10-12月期']

  return `${year}/${quarterNames[quarter - 1]}`
}

/**
 * Eurostat 賃金・給与データを取得
 */
export async function fetchEurostatWagesData(forceRefresh: boolean = false): Promise<EurostatWagesResponse> {
  const url = forceRefresh
    ? '/api/eurozone/wages?force_refresh=true'
    : '/api/eurozone/wages'

  const result = await fetchJson<EurostatWagesResponse>(url)

  logApiMeta('Eurostat Wages', {
    cached: result.cached,
    source: result.source,
    data_count: result.data?.length || 0,
  })

  return result
}
