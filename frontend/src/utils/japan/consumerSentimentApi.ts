/**
 * API utility for Japan Consumer Sentiment data (消費動向調査 - 消費者態度指数)
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export interface ConsumerSentimentDataPoint {
  date: string // YYYY-MM-01 format
  cci: number | null // Consumer Confidence Index (消費者態度指数)
  livelihood: number | null // Overall livelihood (暮らし向き)
  income: number | null // Income growth (収入の増え方)
  employment: number | null // Employment environment (雇用環境)
  durable_goods: number | null // Willingness to buy durable goods (耐久消費財の買い時判断)
}

export interface NextRelease {
  date: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  label?: string
}

export interface ConsumerSentimentResponse {
  data: ConsumerSentimentDataPoint[]
  latest?: ConsumerSentimentDataPoint
  next_release?: NextRelease | null
  last_updated?: string
  source?: string
  cached?: boolean
  error?: string
}

export interface ConsumerSentimentChartResponse {
  data: ConsumerSentimentDataPoint[]
  metadata: {
    title: string
    source: string
    unit: string
    series: Array<{
      key: string
      name: string
      color: string
    }>
  }
  last_updated?: string
  cached?: boolean
  source?: string
  error?: string
}

/**
 * Fetch Japan consumer sentiment data
 * @param force_refresh - Force refresh data from source
 */
export async function fetchConsumerSentimentData(force_refresh: boolean = false): Promise<ConsumerSentimentResponse> {
  try {
    const params = new URLSearchParams()
    if (force_refresh) {
      params.append('force_refresh', 'true')
    }

    const url = `${API_BASE_URL}/api/japan/consumer-sentiment${params.toString() ? `?${params.toString()}` : ''}`
    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data: ConsumerSentimentResponse = await response.json()
    return data
  } catch (error) {
    console.error('Error fetching consumer sentiment data:', error)
    return {
      data: [],
      error: error instanceof Error ? error.message : 'Unknown error',
    }
  }
}

/**
 * Fetch Japan consumer sentiment data formatted for chart
 * @param force_refresh - Force refresh data from source
 */
export async function fetchConsumerSentimentChartData(
  force_refresh: boolean = false
): Promise<ConsumerSentimentChartResponse> {
  try {
    const params = new URLSearchParams()
    if (force_refresh) {
      params.append('force_refresh', 'true')
    }

    const url = `${API_BASE_URL}/api/japan/consumer-sentiment/chart${params.toString() ? `?${params.toString()}` : ''}`
    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data: ConsumerSentimentChartResponse = await response.json()
    return data
  } catch (error) {
    console.error('Error fetching consumer sentiment chart data:', error)
    return {
      data: [],
      metadata: {
        title: '消費動向調査（消費者態度指数）',
        source: '内閣府経済社会総合研究所',
        unit: 'ポイント',
        series: [],
      },
      error: error instanceof Error ? error.message : 'Unknown error',
    }
  }
}

/**
 * Force refresh consumer sentiment data
 */
export async function refreshConsumerSentimentData(): Promise<ConsumerSentimentResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/japan/consumer-sentiment/refresh`, {
      method: 'POST',
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data: ConsumerSentimentResponse = await response.json()
    return data
  } catch (error) {
    console.error('Error refreshing consumer sentiment data:', error)
    return {
      data: [],
      error: error instanceof Error ? error.message : 'Unknown error',
    }
  }
}
