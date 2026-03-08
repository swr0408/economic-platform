import { useQuery } from '@tanstack/react-query'
import axios from 'axios'

export interface MarketOHLC {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume?: number
}

export interface MarketSymbolData {
  data: MarketOHLC[]
  latest: {
    date: string
    close: number
    open?: number
    high?: number
    low?: number
  } | null
  symbol: {
    id: string
    name: string
    name_en: string
    category: string
    sub_category?: string
  } | null
  cached: boolean
  source: string
  last_updated: string | null
}

interface MarketDashboardResponse {
  data: Record<string, MarketSymbolData>
  cached: boolean
  response_time_ms: number
}

/**
 * 複数銘柄のデータを一括取得
 */
export function useMarketBatchData(symbolIds: string[]) {
  return useQuery({
    queryKey: ['market', 'batch', symbolIds.sort().join(',')],
    queryFn: async () => {
      if (symbolIds.length === 0) return {}
      const { data } = await axios.get<MarketDashboardResponse>(
        `/api/market/dashboard?symbols=${symbolIds.join(',')}`
      )
      return data.data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
    enabled: symbolIds.length > 0,
  })
}

// ---------------------------------------------------------------------------
// TSMC Revenue
// ---------------------------------------------------------------------------

export interface TsmcRevenueItem {
  date: string
  revenue: number
  yoy: number | null
  mom: number | null
}

export interface TsmcRevenueQuarterlyItem {
  date: string
  quarter_label: string
  revenue: number
  yoy: number | null
  qoq: number | null
  months_count: number
}

export interface TsmcRevenueNextRelease {
  date: string
  label: string
}

export interface TsmcRevenueData {
  data: TsmcRevenueItem[]
  quarterly: TsmcRevenueQuarterlyItem[]
  latest: TsmcRevenueItem | null
  latest_quarterly: TsmcRevenueQuarterlyItem | null
  metadata: Record<string, unknown>
  next_release?: TsmcRevenueNextRelease | null
  cached: boolean
  source: string
  last_updated: string | null
}

/**
 * TSMC月次売上高データを取得
 */
export function useTsmcRevenueData() {
  return useQuery({
    queryKey: ['market', 'tsmc', 'revenue'],
    queryFn: async () => {
      const { data } = await axios.get<TsmcRevenueData>('/api/market/tsmc/revenue')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

/**
 * 単一銘柄のデータを取得
 */
export function useMarketSymbolData(symbolId: string) {
  return useQuery({
    queryKey: ['market', 'symbol', symbolId],
    queryFn: async () => {
      const { data } = await axios.get<MarketSymbolData>(
        `/api/market/${symbolId}/daily`
      )
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
    enabled: !!symbolId,
  })
}
