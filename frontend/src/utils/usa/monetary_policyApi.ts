/**
 * USA 金融政策関連データのAPI utilities
 */

export interface TermPremiumData {
  date: string
  yield_10y: number | null      // 10年債利回り
  term_premium: number | null   // ACMタームプレミアム
  expected_rate: number | null  // 期待短期金利
}

export interface TermPremiumResponse {
  data: TermPremiumData[]
  meta: {
    cached: boolean
    source: string
    last_updated: string | null
    response_time_ms: number
    count: number
    series: string[]
  }
}

/**
 * NY Fed ACM タームプレミアム関連データを取得（複数シリーズ）
 */
export const fetchTermPremium = async (): Promise<TermPremiumData[]> => {
  try {
    const response = await fetch('/api/nyfed/term-premium')
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const result: TermPremiumResponse = await response.json()

    // メタ情報をコンソールに出力（開発時のデバッグ用）
    if (import.meta.env.DEV) {
      console.log('Term Premium API:', {
        cached: result.meta.cached,
        source: result.meta.source,
        response_time_ms: result.meta.response_time_ms,
        count: result.meta.count,
        series: result.meta.series
      })
    }

    return result.data
  } catch (error) {
    console.error('Error fetching NY Fed Term Premium:', error)
    throw error
  }
}

/**
 * NY Fed ACM タームプレミアムデータを取得（メタ情報付き）
 */
export const fetchTermPremiumWithMeta = async (): Promise<TermPremiumResponse> => {
  try {
    const response = await fetch('/api/nyfed/term-premium')
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    return await response.json()
  } catch (error) {
    console.error('Error fetching NY Fed Term Premium:', error)
    throw error
  }
}

// ========================================
// CME FedWatch Tool 関連
// ========================================

/** FOMC会合データ（金利レベル別確率） */
export interface FedWatchMeeting {
  date: string                              // 会合日 (YYYY/MM/DD形式)
  probabilities: Record<string, number>     // { "275-300": 0.00, "300-325": 57.60, ... }
}

/** FedWatch APIレスポンス */
export interface FedWatchResponse {
  meetings: FedWatchMeeting[]     // FOMC会合リスト
  rate_levels: string[]           // 金利レベル（列ヘッダー）["275-300", "300-325", ...]
  current_rate: string            // 現在の政策金利
  meta: {
    cached: boolean
    source: string
    last_updated: string | null
    response_time_ms: number
    meeting_count: number
    data_source: string
  }
}

/**
 * CME FedWatch 確率テーブルデータを取得
 */
export const fetchFedWatchProbabilities = async (): Promise<FedWatchResponse> => {
  try {
    const response = await fetch('/api/fedwatch/probabilities')
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const result: FedWatchResponse = await response.json()

    if (import.meta.env.DEV) {
      console.log('FedWatch API:', {
        cached: result.meta.cached,
        source: result.meta.source,
        response_time_ms: result.meta.response_time_ms,
        meeting_count: result.meta.meeting_count
      })
    }

    return result
  } catch (error) {
    console.error('Error fetching FedWatch probabilities:', error)
    throw error
  }
}

// ========================================
// FOMC Projections (Dot Plot) 関連
// ========================================

export interface FOMCSEPDate {
  date: string   // YYYYMMDD形式
  label: string  // 表示用ラベル（例: "2025年12月18日"）
}

export interface FOMCSEPDatesResponse {
  dates: FOMCSEPDate[]
  count: number
}

/**
 * FOMC SEP発表日を取得（自動計算）
 */
export const fetchFOMCSEPDates = async (count: number = 4): Promise<FOMCSEPDate[]> => {
  try {
    const response = await fetch(`/api/fomc-projections/sep-dates?count=${count}`)
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const result: FOMCSEPDatesResponse = await response.json()
    return result.dates
  } catch (error) {
    console.error('Error fetching FOMC SEP dates:', error)
    throw error
  }
}

/**
 * FOMC Projections Figure 2画像を取得
 */
export const fetchFOMCProjectionsFigure2 = async (date: string): Promise<string> => {
  try {
    const response = await fetch(`/api/fomc-projections/figure2/${date}`)
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const blob = await response.blob()
    return URL.createObjectURL(blob)
  } catch (error) {
    console.error('Error fetching FOMC Projections Figure 2:', error)
    throw error
  }
}

/**
 * 最新のFOMC Projections Figure 2画像を取得
 */
export const fetchLatestFOMCProjectionsFigure2 = async (): Promise<string> => {
  try {
    const response = await fetch('/api/fomc-projections/latest')
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const blob = await response.blob()
    return URL.createObjectURL(blob)
  } catch (error) {
    console.error('Error fetching latest FOMC Projections Figure 2:', error)
    throw error
  }
}

/**
 * 最新のFOMC Economic Projections Table 1画像を取得
 */
export const fetchLatestFOMCTable1 = async (): Promise<string> => {
  try {
    const response = await fetch('/api/fomc-projections/table1/latest')
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const blob = await response.blob()
    return URL.createObjectURL(blob)
  } catch (error) {
    console.error('Error fetching latest FOMC Economic Projections Table 1:', error)
    throw error
  }
}
