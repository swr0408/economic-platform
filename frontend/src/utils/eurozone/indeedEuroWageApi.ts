/**
 * Indeed Euro Wage Growth API
 *
 * Indeed GitHubからユーロ圏の賃金成長データを取得
 * - ドイツ (DE)
 * - フランス (FR)
 * - ユーロ圏 (EA)
 *
 * データソース:
 * - Indeed Hiring Lab GitHub Repository
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// =============================================================================
// 型定義
// =============================================================================

export interface IndeedEuroWageDataPoint {
  date: string
  value: number
  ma3: number | null // 3-month moving average
}

export interface IndeedEuroWageMetadata {
  source: string
  url: string
  data_start: string
  countries: {
    germany: string
    france: string
    euro_area: string
  }
}

export interface IndeedEuroWageResponse {
  germany: IndeedEuroWageDataPoint[]
  france: IndeedEuroWageDataPoint[]
  euro_area: IndeedEuroWageDataPoint[]
  latest: IndeedEuroWageDataPoint | null
  metadata: IndeedEuroWageMetadata
  cached: boolean
  source: string
  last_updated: string
}

// =============================================================================
// API関数
// =============================================================================

/**
 * Indeed賃金成長データを取得（ドイツ、フランス、ユーロ圏）
 */
export const fetchIndeedEuroWage = async (
  forceRefresh = false
): Promise<IndeedEuroWageResponse> => {
  const params = new URLSearchParams()
  if (forceRefresh) {
    params.append('force_refresh', 'true')
  }

  const url = `${API_BASE_URL}/api/eurozone/indeed-wage${params.toString() ? `?${params}` : ''}`
  const response = await fetch(url)

  if (!response.ok) {
    throw new Error('Failed to fetch Indeed Euro Wage data')
  }

  return response.json()
}

// =============================================================================
// フォーマッター
// =============================================================================

/**
 * 日付を表示用にフォーマット（YYYY-MM-DD -> YYYY/MM）
 */
export const formatIndeedDate = (dateStr: string): string => {
  const date = new Date(dateStr)
  return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}`
}

/**
 * 日付を日本語表記に変換（YYYY-MM-DD -> YYYY年M月）
 */
export const formatIndeedDateJP = (dateStr: string): string => {
  const date = new Date(dateStr)
  return `${date.getFullYear()}/${date.getMonth() + 1}`
}

/**
 * パーセント値をフォーマット
 */
export const formatPercentValue = (value: number): string => {
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`
}
