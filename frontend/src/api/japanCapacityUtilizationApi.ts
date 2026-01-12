/**
 * Japan Capacity Utilization API
 * 製造工業稼働率指数データの取得
 *
 * データソース: 経済産業省 (METI)
 * URL: https://www.meti.go.jp/statistics/tyo/iip/xls/b2020_ngsm1j.xlsx
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface JapanCapacityUtilizationDataPoint {
  date: string
  item_name: string
  category: string
  value: number | null
}

export interface JapanCapacityUtilizationResponse {
  data: JapanCapacityUtilizationDataPoint[]
  latest: JapanCapacityUtilizationDataPoint | null
  cached: boolean
  source: string
  last_updated: string | null
  error?: string
}

/**
 * 稼働率指数データを取得
 */
export async function fetchJapanCapacityUtilizationData(
  forceRefresh = false
): Promise<JapanCapacityUtilizationResponse> {
  try {
    const url = new URL(`${API_BASE_URL}/api/japan/capacity-utilization`)
    if (forceRefresh) {
      url.searchParams.set('force_refresh', 'true')
    }

    const response = await fetch(url.toString())
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Error fetching Japan Capacity Utilization data:', error)
    return {
      data: [],
      latest: null,
      cached: false,
      source: 'error',
      last_updated: null,
      error: error instanceof Error ? error.message : 'Unknown error',
    }
  }
}

/**
 * 日付フォーマット（YYYY-MM-DD → YYYY年MM月）
 */
export function formatCapacityDate(dateStr: string | undefined): string {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}年${parseInt(month)}月`
}
