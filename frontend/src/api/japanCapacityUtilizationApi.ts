/**
 * Japan Capacity Utilization API
 * 製造工業稼働率指数データの取得
 *
 * データソース: 経済産業省 (METI)
 * URL: https://www.meti.go.jp/statistics/tyo/iip/xls/b2020_ngsm1j.xlsx
 */

// 本番は Caddy で同一オリジン配信のため相対パス（''）を既定とする。
// プロジェクト全体の規約に合わせ VITE_API_BASE_URL を使用する
// （旧 VITE_API_URL || 'http://localhost:8000' は .env 未設定の本番ビルドで
//  localhost:8000 を絶対参照してしまい取得失敗→チャート非表示になっていた）。
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

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
    // API_BASE_URL は同一オリジン配信のため通常 ''（相対）。new URL() は絶対URLが
    // 必須なので、base に window.location.origin を渡す（API_BASE_URL が絶対指定の
    // 場合は第1引数が絶対URLになり base は無視される）。
    const url = new URL(`${API_BASE_URL}/api/japan/capacity-utilization`, window.location.origin)
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
