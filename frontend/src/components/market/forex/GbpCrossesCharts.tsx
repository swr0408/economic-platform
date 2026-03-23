import { Alert } from 'antd'
import MarketPriceChart from '../MarketPriceChart'
import { useMarketBatchData } from '../../../hooks/useMarketData'
import LoadingChart from '../../common/LoadingChart'
import LazyChart from '../../common/LazyChart'

const SYMBOL_IDS = ['gbpaud', 'gbpnzd', 'gbpcad', 'gbpchf']

const COLORS: Record<string, string> = {
  gbpaud: '#f59e0b',
  gbpnzd: '#06b6d4',
  gbpcad: '#ef4444',
  gbpchf: '#f97316',
}

export default function GbpCrossesCharts() {
  const { data, isLoading, error } = useMarketBatchData(SYMBOL_IDS)

  if (isLoading) return <LoadingChart title="ポンドクロスデータ読み込み中..." />
  if (error) return <Alert type="error" message="データの取得に失敗しました" showIcon />

  return (
    <div className="country-chart-stack">
      <LazyChart id="gbpaud"><MarketPriceChart title="GBP/AUD" symbolData={data?.gbpaud} color={COLORS.gbpaud} decimals={4} /></LazyChart>
      <LazyChart id="gbpnzd"><MarketPriceChart title="GBP/NZD" symbolData={data?.gbpnzd} color={COLORS.gbpnzd} decimals={4} /></LazyChart>
      <LazyChart id="gbpcad"><MarketPriceChart title="GBP/CAD" symbolData={data?.gbpcad} color={COLORS.gbpcad} decimals={4} /></LazyChart>
      <LazyChart id="gbpchf"><MarketPriceChart title="GBP/CHF" symbolData={data?.gbpchf} color={COLORS.gbpchf} decimals={4} /></LazyChart>
    </div>
  )
}
