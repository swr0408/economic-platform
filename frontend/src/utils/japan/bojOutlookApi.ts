/**
 * API utility for fetching BOJ Outlook Report
 *
 * データソース: 日本銀行
 * URL: https://www.boj.or.jp/mopo/outlook/gor{YYMM}a.pdf
 * 発表月: 1月、4月、7月、10月（年4回）
 */

export interface BOJOutlookData {
  report_date: string | null  // "2025-07-01"
  yymm: string | null  // "2507"
  pdf_url: string | null
  forecasts_image: string | null  // Path to forecasts table image
  risks_image: string | null  // Path to risks chart image
  last_updated: string
  cached?: boolean
  error?: string
}

/**
 * Fetch BOJ Outlook Report data from backend
 */
export async function fetchBOJOutlook(forceRefresh = false): Promise<BOJOutlookData> {
  try {
    const url = forceRefresh
      ? '/api/japan/boj-outlook?force_refresh=true'
      : '/api/japan/boj-outlook'

    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`Failed to fetch BOJ outlook: ${response.statusText}`)
    }

    const data: BOJOutlookData = await response.json()
    return data
  } catch (error) {
    console.error('Error fetching BOJ outlook:', error)
    throw error
  }
}

/**
 * Get BOJ Outlook image URL
 * @param imageType 'forecasts' or 'risks'
 */
export function getOutlookImageUrl(imageType: 'forecasts' | 'risks'): string {
  return `/api/japan/boj-outlook/image/${imageType}`
}

/**
 * Format report date for display
 */
export function formatReportDate(dateStr: string | null): string {
  if (!dateStr) return '-'

  try {
    const date = new Date(dateStr)
    const year = date.getFullYear()
    const month = date.getMonth() + 1

    // Map month to Japanese display (1月, 4月, 7月, 10月)
    return `${year}/${month}`
  } catch {
    return dateStr
  }
}
