/**
 * 工作機械受注 API
 *
 * データソース: 日本工作機械工業会 (JMTBA)
 * 更新: 月次
 */

export interface MachineToolOrdersDataPoint {
  date: string  // "2024-01-01"
  value: number | null  // YoY growth rate %
  forecast?: number | null
  previous?: number | null
}

export interface NextReleaseInfo {
  date?: string
  datetime_utc?: string
  datetime_jst?: string
  time_jst?: string
  label?: string
  estimate?: number | null
}

export interface MachineToolOrdersData {
  data: MachineToolOrdersDataPoint[]
  latest: MachineToolOrdersDataPoint | null
  next_release: NextReleaseInfo | string | null
  cached: boolean
  source: string
  last_updated: string
  error?: string
}

/**
 * Fetch Machine Tool Orders data
 */
export async function fetchMachineToolOrders(forceRefresh = false): Promise<MachineToolOrdersData> {
  try {
    const url = forceRefresh
      ? '/api/japan/machine-tool-orders?force_refresh=true'
      : '/api/japan/machine-tool-orders'

    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`Failed to fetch machine tool orders: ${response.statusText}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Error fetching machine tool orders:', error)
    throw error
  }
}
