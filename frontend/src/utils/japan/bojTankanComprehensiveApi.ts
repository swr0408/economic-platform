/**
 * API utility for BOJ Tankan Comprehensive Data
 * 日銀短観 包括的データ（設備投資、生産・営業用設備、雇用人員、仕入価格、販売価格）
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export type DataType = 'capital_investment' | 'production_facilities' | 'employment' | 'purchase_price' | 'selling_price'

export interface BOJTankanComprehensiveDataPoint {
  date: string
  // Capital investment specific fields
  large_manufacturing?: number | null
  large_manufacturing_revision?: number | null
  large_non_manufacturing?: number | null
  large_non_manufacturing_revision?: number | null
  // DI type fields (production_facilities, employment, purchase_price, selling_price)
  all_industries_current?: number | null
  all_industries_forecast?: number | null
  large_manufacturing_current?: number | null
  large_manufacturing_forecast?: number | null
}

export interface SeriesMetadata {
  key: string
  name: string
  color: string
}

export interface BOJTankanComprehensiveTableResponse {
  table_data: BOJTankanComprehensiveDataPoint[]
  metadata: {
    title: string
    source: string
    source_url: string
    last_updated: string
    data_type: DataType
    series: SeriesMetadata[]
  }
  cached: boolean
  source: string
}

export interface DataTypeInfo {
  key: DataType
  name: string
  unit: string
}

export interface DataTypesResponse {
  data_types: DataTypeInfo[]
}

/**
 * Fetch BOJ Tankan comprehensive table data
 */
export const fetchBOJTankanComprehensiveTable = async (
  dataType: DataType,
  forceRefresh: boolean = false
): Promise<BOJTankanComprehensiveTableResponse> => {
  try {
    const url = new URL(`${API_BASE_URL}/api/japan/boj-tankan/comprehensive/table/${dataType}`)
    if (forceRefresh) {
      url.searchParams.append('force_refresh', 'true')
    }

    const response = await fetch(url.toString())

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    console.error(`Failed to fetch BOJ Tankan ${dataType} data:`, error)
    throw error
  }
}

/**
 * Fetch available data types
 */
export const fetchBOJTankanDataTypes = async (): Promise<DataTypesResponse> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/japan/boj-tankan/comprehensive/types`)

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Failed to fetch BOJ Tankan data types:', error)
    throw error
  }
}

/**
 * Get display name for data type
 */
export const getDataTypeDisplayName = (dataType: DataType): string => {
  const names: Record<DataType, string> = {
    capital_investment: '設備投資額',
    production_facilities: '生産・営業用設備判断指数（DI）',
    employment: '雇用人員判断指数（DI）',
    purchase_price: '仕入価格判断指数（DI）',
    selling_price: '販売価格判断指数（DI）'
  }
  return names[dataType]
}

/**
 * Format date for display (YYYY-MM-DD to YYYY年Q四半期)
 */
export const formatQuarterDate = (dateStr: string): string => {
  if (!dateStr) return ''

  const parts = dateStr.split('-')
  if (parts.length < 2) return dateStr

  const year = parts[0]
  const month = parseInt(parts[1], 10)

  // Determine quarter
  let quarter: number
  if (month <= 3) {
    quarter = 1
  } else if (month <= 6) {
    quarter = 2
  } else if (month <= 9) {
    quarter = 3
  } else {
    quarter = 4
  }

  return `${year}/Q${quarter}`
}

/**
 * Format fiscal year date for display
 */
export const formatFiscalYearDate = (dateStr: string): string => {
  if (!dateStr) return ''

  const parts = dateStr.split('-')
  if (parts.length < 2) return dateStr

  const year = parseInt(parts[0], 10)
  const month = parseInt(parts[1], 10)

  // For fiscal year ending in March, the fiscal year is the previous calendar year
  if (month === 3) {
    return `FY${year - 1}`
  }

  return `FY${year}`
}
