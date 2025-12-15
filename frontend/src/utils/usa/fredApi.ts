/**
 * FRED (Federal Reserve Economic Data) API utilities
 * KWタームプレミアム（THREEFYTP10）取得用
 */

export interface FREDSeriesData {
  date: string
  value: number
}

interface FREDSeriesResponse {
  series_id: string
  data: FREDSeriesData[]
  meta: {
    cached: boolean
    source: string
    last_updated: string | null
    response_time_ms: number
    count: number
  }
}

/**
 * KWモデル タームプレミアム（THREEFYTP10）を取得
 */
export const fetchKWTermPremium = async (): Promise<FREDSeriesData[]> => {
  try {
    const response = await fetch('/api/fred/kw-term-premium')
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const result: FREDSeriesResponse = await response.json()

    if (import.meta.env.DEV) {
      console.log('FRED KW Term Premium API:', {
        cached: result.meta.cached,
        source: result.meta.source,
        response_time_ms: result.meta.response_time_ms,
        count: result.meta.count
      })
    }

    return result.data
  } catch (error) {
    console.error('Error fetching FRED KW Term Premium:', error)
    throw error
  }
}
