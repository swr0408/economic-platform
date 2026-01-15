/**
 * ECB交渉妥結賃金 API クライアント
 *
 * ECB Data APIから交渉妥結賃金データを取得
 * - Negotiated Wage Rates (前年比)
 *
 * 発表スケジュール:
 * - 四半期ごと（不定期）
 * - 発表時刻: 18:00-18:10 CET
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// =============================================================================
// 型定義
// =============================================================================

export interface ECBNegotiatedWagesItem {
  date: string
  value: number
}

export interface ECBNegotiatedWagesMetadata {
  source: string
  dataflow: string
  area: string
  unit: string
  frequency: string
  adjustment: string
  description: string
}

export interface ECBNegotiatedWagesNextRelease {
  date: string
  datetime_utc: string
  datetime_jst: string
  time_jst: string
  datetime_cet: string
  time_cet: string
  label: string
  estimate: number | null
}

export interface ECBNegotiatedWagesResponse {
  data: ECBNegotiatedWagesItem[]
  latest: ECBNegotiatedWagesItem | null
  metadata: ECBNegotiatedWagesMetadata
  next_release: ECBNegotiatedWagesNextRelease | null
  cached: boolean
  source: string
  last_updated: string
}

// =============================================================================
// API関数
// =============================================================================

/**
 * ECB交渉妥結賃金データを取得
 */
export const fetchECBNegotiatedWages = async (
  forceRefresh = false
): Promise<ECBNegotiatedWagesResponse> => {
  const params = new URLSearchParams()
  if (forceRefresh) {
    params.append('force_refresh', 'true')
  }

  const url = `${API_BASE_URL}/api/eurozone/negotiated-wages${params.toString() ? `?${params}` : ''}`
  const response = await fetch(url)

  if (!response.ok) {
    throw new Error('Failed to fetch ECB Negotiated Wages data')
  }

  return response.json()
}

// =============================================================================
// フォーマッター
// =============================================================================

/**
 * 四半期形式の日付を表示用にフォーマット（2025-Q1 -> 2025 Q1）
 */
export const formatQuarterDate = (dateStr: string): string => {
  return dateStr.replace('-', ' ')
}

/**
 * 四半期形式の日付を日本語表記に変換（2025-Q1 -> 2025年1-3月期）
 */
export const formatQuarterDateJP = (dateStr: string): string => {
  const match = dateStr.match(/^(\d{4})-Q([1-4])$/)
  if (match) {
    const year = match[1]
    const quarter = parseInt(match[2], 10)
    const quarterNames = ['1-3月期', '4-6月期', '7-9月期', '10-12月期']
    return `${year}年${quarterNames[quarter - 1]}`
  }
  return dateStr
}

/**
 * パーセント値をフォーマット
 */
export const formatPercentValue = (value: number): string => {
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
}
