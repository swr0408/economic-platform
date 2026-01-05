/**
 * USA 金融政策関連データのAPI utilities
 */
import { fetchJson, fetchBlob, logApiMeta, type ApiMeta } from '../apiUtils'

// ========================================
// NY Fed Term Premium 関連
// ========================================

export interface TermPremiumData {
  date: string
  yield_10y: number | null      // 10年債利回り
  term_premium: number | null   // ACMタームプレミアム
  expected_rate: number | null  // 期待短期金利
}

export interface TermPremiumResponse {
  data: TermPremiumData[]
  meta: ApiMeta & {
    count: number
    series: string[]
  }
}

/**
 * NY Fed ACM タームプレミアム関連データを取得（複数シリーズ）
 */
export const fetchTermPremium = async (): Promise<TermPremiumData[]> => {
  const result = await fetchJson<TermPremiumResponse>('/api/nyfed/term-premium')

  logApiMeta('Term Premium API', {
    cached: result.meta.cached,
    source: result.meta.source,
    response_time_ms: result.meta.response_time_ms,
    count: result.meta.count,
    series: result.meta.series
  })

  return result.data
}

/**
 * NY Fed ACM タームプレミアムデータを取得（メタ情報付き）
 */
export const fetchTermPremiumWithMeta = async (): Promise<TermPremiumResponse> => {
  return fetchJson<TermPremiumResponse>('/api/nyfed/term-premium')
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
  meta: ApiMeta & {
    meeting_count: number
    data_source: string
  }
}

/**
 * CME FedWatch 確率テーブルデータを取得
 */
export const fetchFedWatchProbabilities = async (): Promise<FedWatchResponse> => {
  const result = await fetchJson<FedWatchResponse>('/api/fedwatch/probabilities')

  logApiMeta('FedWatch API', {
    cached: result.meta.cached,
    source: result.meta.source,
    response_time_ms: result.meta.response_time_ms,
    meeting_count: result.meta.meeting_count
  })

  return result
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
  const result = await fetchJson<FOMCSEPDatesResponse>(
    `/api/fomc-projections/sep-dates?count=${count}`
  )
  return result.dates
}

/**
 * FOMC Projections Figure 2画像を取得
 */
export const fetchFOMCProjectionsFigure2 = async (date: string): Promise<string> => {
  return fetchBlob(`/api/fomc-projections/figure2/${date}`)
}

/**
 * 最新のFOMC Projections Figure 2画像を取得
 */
export const fetchLatestFOMCProjectionsFigure2 = async (): Promise<string> => {
  return fetchBlob('/api/fomc-projections/latest')
}

/**
 * 最新のFOMC Economic Projections Table 1画像を取得
 */
export const fetchLatestFOMCTable1 = async (): Promise<string> => {
  return fetchBlob('/api/fomc-projections/table1/latest')
}
