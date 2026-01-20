/**
 * BRC Commentary API
 * Fetches BRC Retail Sales Monitor commentary from the backend
 */

export interface BRCCommentaryItem {
  en: string
  ja: string
  speaker?: string
}

export interface BRCCommentaryData {
  commentaries: BRCCommentaryItem[] | null
  data_year: number | null
  data_month: number | null
  url: string | null
  last_updated: string
  error?: string
}

/**
 * Fetch BRC commentary (cached if available)
 */
export async function fetchBRCCommentary(): Promise<BRCCommentaryData> {
  const response = await fetch('/api/uk/brc-commentary')

  if (!response.ok) {
    throw new Error(`Failed to fetch BRC commentary: ${response.statusText}`)
  }

  return await response.json()
}

/**
 * Force refresh BRC commentary (bypass cache)
 */
export async function refreshBRCCommentary(): Promise<BRCCommentaryData> {
  const response = await fetch('/api/uk/brc-commentary/refresh', {
    method: 'POST'
  })

  if (!response.ok) {
    throw new Error(`Failed to refresh BRC commentary: ${response.statusText}`)
  }

  return await response.json()
}
