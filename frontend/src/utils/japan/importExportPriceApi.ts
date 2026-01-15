/**
 * Japan Import/Export Price Index API
 * 日本輸入・輸出物価指数 API
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export interface ImportExportPriceDataPoint {
  date: string
  export_yen_yoy: number | null
  import_yen_yoy: number | null
  import_contract_yoy: number | null
}

export interface NextRelease {
  date: string
  datetime_jst?: string
  label?: string
}

export interface ImportExportPriceResponse {
  data: ImportExportPriceDataPoint[]
  latest: ImportExportPriceDataPoint | null
  next_release: NextRelease | null
  cached: boolean
  source: string
  last_updated: string | null
  error?: string
}

export async function fetchImportExportPriceData(
  forceRefresh = false
): Promise<ImportExportPriceResponse> {
  try {
    const params = new URLSearchParams()
    if (forceRefresh) {
      params.append('force_refresh', 'true')
    }

    const url = `${API_BASE_URL}/api/japan/import-export-price${params.toString() ? `?${params.toString()}` : ''}`
    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Error fetching import/export price data:', error)
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
