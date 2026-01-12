/**
 * Japan IIP Forecast API Client
 * 鉱工業生産予測指数データの取得
 *
 * データソース: 経済産業省 (METI)
 * Excel URL: https://www.meti.go.jp/statistics/tyo/iip/xls/b2020_ygzosm1je.xlsx
 * PDF URL: https://www.meti.go.jp/statistics/tyo/iip/result/pdf/reference/rev_forecast.pdf
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface JapanIIPForecastDataPoint {
  item_name: string
  this_month: number | null
  next_month: number | null
}

export interface RevisionTable {
  columns: string[]
  rows: (string | number | null)[][]
}

export interface JapanIIPForecastResponse {
  data: JapanIIPForecastDataPoint[]
  forecast_month: string | null
  next_month: string | null
  revision_table: RevisionTable | null
  cached: boolean
  source: string
  last_updated: string | null
  pdf_reference: string
  error?: string
}

/**
 * IIP予測指数データを取得
 */
export async function fetchJapanIIPForecastData(
  forceRefresh = false
): Promise<JapanIIPForecastResponse> {
  try {
    const url = new URL(`${API_BASE_URL}/api/japan/iip-forecast`)
    if (forceRefresh) {
      url.searchParams.set('force_refresh', 'true')
    }

    const response = await fetch(url.toString())
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Error fetching Japan IIP Forecast data:', error)
    return {
      data: [],
      forecast_month: null,
      next_month: null,
      revision_table: null,
      cached: false,
      source: 'error',
      last_updated: null,
      pdf_reference: '',
      error: error instanceof Error ? error.message : 'Unknown error',
    }
  }
}

/**
 * テーブル表示用にデータをフォーマット
 */
export function formatJapanIIPForecastDataForTable(
  data: JapanIIPForecastDataPoint[]
): Array<JapanIIPForecastDataPoint & { key: string }> {
  return data.map((item, index) => ({
    ...item,
    key: `${item.item_name}-${index}`,
  }))
}

/**
 * 日付フォーマット（YYYY-MM-DD → YYYY年MM月）
 */
export function formatForecastMonth(dateStr: string | null): string {
  if (!dateStr) return ''

  const parts = dateStr.split('-')
  if (parts.length < 2) return dateStr

  const year = parts[0]
  const month = parseInt(parts[1], 10)

  return `${year}年${month}月`
}
