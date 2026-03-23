import { Alert } from 'antd'
import MarketPriceChart from '../MarketPriceChart'
import CftcPositioningChart from '../cot/CftcPositioningChart'
import { useMarketBatchData } from '../../../hooks/useMarketData'
import LoadingChart from '../../common/LoadingChart'
import LazyChart from '../../common/LazyChart'

const SYMBOL_IDS = ['eurjpy', 'gbpjpy', 'audjpy', 'nzdjpy', 'cadjpy', 'chfjpy']

const COLORS: Record<string, string> = {
  eurjpy: '#10b981',
  gbpjpy: '#8b5cf6',
  audjpy: '#f59e0b',
  nzdjpy: '#06b6d4',
  cadjpy: '#ef4444',
  chfjpy: '#f97316',
}

export default function JpyCrossesCharts() {
  const { data, isLoading, error } = useMarketBatchData(SYMBOL_IDS)

  if (isLoading) return <LoadingChart title="クロス円データ読み込み中..." />
  if (error) return <Alert type="error" message="データの取得に失敗しました" showIcon />

  return (
    <div className="country-chart-stack">
      <LazyChart id="eurjpy"><MarketPriceChart title="EUR/JPY" symbolData={data?.eurjpy} color={COLORS.eurjpy} decimals={3} /></LazyChart>
      <LazyChart id="cot-eurjpy"><CftcPositioningChart asset="eurjpy" assetLabel="ユーロ/円" reportType="tff" compareId="cftc_eurjpy" /></LazyChart>
      <LazyChart id="gbpjpy"><MarketPriceChart title="GBP/JPY" symbolData={data?.gbpjpy} color={COLORS.gbpjpy} decimals={3} /></LazyChart>
      <LazyChart id="audjpy"><MarketPriceChart title="AUD/JPY" symbolData={data?.audjpy} color={COLORS.audjpy} decimals={3} /></LazyChart>
      <LazyChart id="nzdjpy"><MarketPriceChart title="NZD/JPY" symbolData={data?.nzdjpy} color={COLORS.nzdjpy} decimals={3} /></LazyChart>
      <LazyChart id="cadjpy"><MarketPriceChart title="CAD/JPY" symbolData={data?.cadjpy} color={COLORS.cadjpy} decimals={3} /></LazyChart>
      <LazyChart id="chfjpy"><MarketPriceChart title="CHF/JPY" symbolData={data?.chfjpy} color={COLORS.chfjpy} decimals={3} /></LazyChart>
    </div>
  )
}
