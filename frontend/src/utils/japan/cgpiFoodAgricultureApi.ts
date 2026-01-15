/**
 * 企業物価指数：飲食料品・農林水産物 API クライアント
 */

import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

export interface CGPIFoodAgricultureDataPoint {
  date: string
  food_yoy: number | null
  agriculture_yoy: number | null
}

export interface CGPIFoodAgricultureResponse {
  data: CGPIFoodAgricultureDataPoint[]
  latest: CGPIFoodAgricultureDataPoint | null
  next_release: {
    date: string
    datetime_jst: string
    label: string
  } | null
  cached: boolean
  source: string
  last_updated: string | null
  error?: string
}

export async function fetchCGPIFoodAgricultureData(
  forceRefresh = false
): Promise<CGPIFoodAgricultureResponse> {
  try {
    const response = await axios.get<CGPIFoodAgricultureResponse>(
      `${API_BASE}/api/japan/cgpi-food-agriculture`,
      {
        params: { force_refresh: forceRefresh },
      }
    )
    return response.data
  } catch (error) {
    console.error('Error fetching CGPI Food/Agriculture data:', error)
    return {
      data: [],
      latest: null,
      next_release: null,
      cached: false,
      source: 'error',
      last_updated: null,
      error: 'データの取得に失敗しました',
    }
  }
}
