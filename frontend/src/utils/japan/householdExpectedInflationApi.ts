/**
 * 日銀 家計予想物価上昇率 API（生活意識に関するアンケート調査）
 * 家計の物価予想・実感データをバックエンドから取得
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export interface HouseholdExpectedInflationDataPoint {
  date: string // YYYY-MM-01 形式（調査実施年月）
  current_mean: number | null   // 現在の物価実感（前年比）平均値 %
  current_median: number | null // 現在の物価実感（前年比）中央値 %
  exp1y_mean: number | null     // 1年後の物価予想 平均値 %
  exp1y_median: number | null   // 1年後の物価予想 中央値 %
  exp5y_mean: number | null     // 5年後の物価予想 平均値 %
  exp5y_median: number | null   // 5年後の物価予想 中央値 %
}

export interface NextRelease {
  date: string
  datetime_jst?: string
  label?: string
}

export interface HouseholdExpectedInflationResponse {
  data: HouseholdExpectedInflationDataPoint[]
  latest: HouseholdExpectedInflationDataPoint | null
  next_release: NextRelease | null
  cached: boolean
  source: string
  last_updated: string | null
  error?: string
}

export async function fetchHouseholdExpectedInflationData(
  forceRefresh = false
): Promise<HouseholdExpectedInflationResponse> {
  try {
    const params = new URLSearchParams()
    if (forceRefresh) {
      params.append('force_refresh', 'true')
    }

    const url = `${API_BASE_URL}/api/japan/household-expected-inflation${params.toString() ? `?${params.toString()}` : ''}`
    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Error fetching Household Expected Inflation data:', error)
    return {
      data: [],
      latest: null,
      next_release: null,
      cached: false,
      source: 'error',
      last_updated: null,
      error: error instanceof Error ? error.message : 'Unknown error',
    }
  }
}

/**
 * 調査年月（YYYY-MM-01）を表示用にフォーマット
 * @returns 例: "2026年3月"
 */
export function formatSurveyMonth(dateStr: string): string {
  try {
    const [year, month] = dateStr.split('-')
    return `${year}年${parseInt(month, 10)}月`
  } catch {
    return dateStr
  }
}

/** X軸ラベル用の短縮フォーマット 例: "2026/03" */
export function formatSurveyMonthShort(dateStr: string): string {
  try {
    const [year, month] = dateStr.split('-')
    return `${year}/${month}`
  } catch {
    return dateStr
  }
}

/** YYYY-MM-01 を Date に変換（期間フィルタ用） */
export function parseSurveyMonth(dateStr: string): Date | null {
  try {
    const [year, month] = dateStr.split('-').map((v) => parseInt(v, 10))
    if (!year || !month) return null
    return new Date(year, month - 1, 1)
  } catch {
    return null
  }
}
