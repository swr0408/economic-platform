import { Alert } from 'antd'
import MarketPriceChart from '../MarketPriceChart'
import { useMarketBatchData } from '../../../hooks/useMarketData'
import LoadingChart from '../../common/LoadingChart'
import LazyChart from '../../common/LazyChart'

const SYMBOL_IDS = ['audnzd', 'audcad', 'audchf', 'nzdcad', 'nzdchf', 'cadchf']

const COLORS: Record<string, string> = {
  audnzd: '#06b6d4',
  audcad: '#ef4444',
  audchf: '#f97316',
  nzdcad: '#ef4444',
  nzdchf: '#f97316',
  cadchf: '#64748b',
}

export default function OtherCrossesCharts() {
  const { data, isLoading, error } = useMarketBatchData(SYMBOL_IDS)

  if (isLoading) return <LoadingChart title="その他クロスデータ読み込み中..." />
  if (error) return <Alert type="error" message="データの取得に失敗しました" showIcon />

  return (
    <div className="country-chart-stack">
      <LazyChart id="audnzd"><MarketPriceChart title="AUD/NZD" symbolData={data?.audnzd} color={COLORS.audnzd} decimals={4} /></LazyChart>
      <LazyChart id="audcad"><MarketPriceChart title="AUD/CAD" symbolData={data?.audcad} color={COLORS.audcad} decimals={4} /></LazyChart>
      <LazyChart id="audchf"><MarketPriceChart title="AUD/CHF" symbolData={data?.audchf} color={COLORS.audchf} decimals={4} /></LazyChart>
      <LazyChart id="nzdcad"><MarketPriceChart title="NZD/CAD" symbolData={data?.nzdcad} color={COLORS.nzdcad} decimals={4} /></LazyChart>
      <LazyChart id="nzdchf"><MarketPriceChart title="NZD/CHF" symbolData={data?.nzdchf} color={COLORS.nzdchf} decimals={4} /></LazyChart>
      <LazyChart id="cadchf"><MarketPriceChart title="CAD/CHF" symbolData={data?.cadchf} color={COLORS.cadchf} decimals={4} /></LazyChart>
    </div>
  )
}
