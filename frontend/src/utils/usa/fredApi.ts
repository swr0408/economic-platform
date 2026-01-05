/**
 * FRED (Federal Reserve Economic Data) API utilities
 * KWタームプレミアム（THREEFYTP10）取得用
 */
import { fetchJson, logApiMeta, type ApiMeta } from '../apiUtils'

export interface FREDSeriesData {
  date: string
  value: number
}

interface FREDSeriesResponse {
  series_id: string
  data: FREDSeriesData[]
  meta: ApiMeta & {
    count: number
  }
}

/**
 * KWモデル タームプレミアム（THREEFYTP10）を取得
 */
export const fetchKWTermPremium = async (): Promise<FREDSeriesData[]> => {
  const result = await fetchJson<FREDSeriesResponse>('/api/fred/kw-term-premium')

  logApiMeta('FRED KW Term Premium API', {
    cached: result.meta.cached,
    source: result.meta.source,
    response_time_ms: result.meta.response_time_ms,
    count: result.meta.count
  })

  return result.data
}
