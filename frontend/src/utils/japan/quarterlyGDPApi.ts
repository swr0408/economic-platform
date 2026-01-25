/**
 * API utility for fetching Japan Quarterly GDP Growth Rate
 *
 * データソース: e-Stat（内閣府）
 * 更新: 四半期毎（速報・改定値）
 */

export interface QuarterlyGDPDataPoint {
  date: string  // "2024-Q1"
  value: number  // Growth rate %
}

export interface QuarterlyGDPData {
  data: QuarterlyGDPDataPoint[]
  latest: QuarterlyGDPDataPoint | null
  next_release: string | null
  cached: boolean
  source: string
  last_updated: string
  error?: string
}

/**
 * Fetch Quarterly GDP Growth Rate (QoQ) data - 前期比（非年率）
 */
export async function fetchQuarterlyGDPQoQ(forceRefresh = false): Promise<QuarterlyGDPData> {
  try {
    const url = forceRefresh
      ? '/api/japan/quarterly-gdp?force_refresh=true'
      : '/api/japan/quarterly-gdp'

    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`Failed to fetch GDP QoQ: ${response.statusText}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Error fetching GDP QoQ:', error)
    throw error
  }
}

/**
 * Fetch Quarterly GDP Growth Rate (QoQ Annualized) data - 前期比年率
 */
export async function fetchQuarterlyGDPQoQAnnualized(forceRefresh = false): Promise<QuarterlyGDPData> {
  try {
    const url = forceRefresh
      ? '/api/japan/quarterly-gdp/annualized?force_refresh=true'
      : '/api/japan/quarterly-gdp/annualized'

    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`Failed to fetch GDP QoQ Annualized: ${response.statusText}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Error fetching GDP QoQ Annualized:', error)
    throw error
  }
}

/**
 * Fetch Quarterly GDP Growth Rate (YoY) data - 前年比
 */
export async function fetchQuarterlyGDPYoY(forceRefresh = false): Promise<QuarterlyGDPData> {
  try {
    const url = forceRefresh
      ? '/api/japan/quarterly-gdp/yoy?force_refresh=true'
      : '/api/japan/quarterly-gdp/yoy'

    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`Failed to fetch GDP YoY: ${response.statusText}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Error fetching GDP YoY:', error)
    throw error
  }
}

/**
 * Format quarter date for display
 * "2024-Q1" -> "2024 Q1"
 */
export function formatQuarterLabel(dateStr: string): string {
  try {
    const [year, quarter] = dateStr.split('-')
    return `${year} ${quarter}`
  } catch {
    return dateStr
  }
}

/**
 * Format value with % suffix
 */
export function formatGDPValue(value: number | null): string {
  if (value === null || value === undefined) return '-'
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
}

/**
 * Parse quarter date string to Date object
 * "2024-Q1" -> Date(2024, 0, 1)
 */
export function parseQuarterDate(dateStr: string): Date | null {
  try {
    const [year, quarter] = dateStr.split('-')
    const quarterNum = parseInt(quarter.replace('Q', ''))

    if (!year || !quarterNum || quarterNum < 1 || quarterNum > 4) {
      return null
    }

    // Convert quarter to month (Q1 = Jan, Q2 = Apr, Q3 = Jul, Q4 = Oct)
    const month = (quarterNum - 1) * 3
    return new Date(parseInt(year), month, 1)
  } catch {
    return null
  }
}
