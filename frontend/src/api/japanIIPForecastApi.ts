/**
 * Japan IIP Forecast API Client
 * 鉱工業生産予測指数データの取得
 *
 * データソース: 経済産業省 (METI)
 * Excel URL: https://www.meti.go.jp/statistics/tyo/iip/xls/b2020_ygzosm1je.xlsx
 * PDF URL: https://www.meti.go.jp/statistics/tyo/iip/result/pdf/reference/rev_forecast.pdf
 */

// 本番は Caddy で同一オリジン配信のため相対パス（''）を既定とする。
// プロジェクト全体の規約に合わせ VITE_API_BASE_URL を使用する
// （旧 VITE_API_URL || 'http://localhost:8000' は .env 未設定の本番ビルドで
//  localhost:8000 を絶対参照してしまい取得失敗→チャート非表示になっていた）。
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

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
    // API_BASE_URL は同一オリジン配信のため通常 ''（相対）。new URL() は絶対URLが
    // 必須なので、base に window.location.origin を渡す（API_BASE_URL が絶対指定の
    // 場合は第1引数が絶対URLになり base は無視される）。
    const url = new URL(`${API_BASE_URL}/api/japan/iip-forecast`, window.location.origin)
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
