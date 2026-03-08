import { Alert } from 'antd'
import MarketPriceChart from '../MarketPriceChart'
import { useMarketBatchData } from '../../../hooks/useMarketData'
import LoadingChart from '../../common/LoadingChart'

const SYMBOL_IDS = [
  'usdjpy', 'eurusd', 'gbpusd', 'audusd', 'nzdusd', 'usdcad', 'usdchf',
  'eurjpy', 'gbpjpy', 'audjpy', 'nzdjpy', 'cadjpy', 'chfjpy',
  'eurgbp', 'euraud', 'eurnzd', 'eurcad', 'eurchf',
  'gbpaud', 'gbpnzd', 'gbpcad', 'gbpchf',
  'audnzd', 'audcad', 'audchf', 'nzdcad', 'nzdchf', 'cadchf',
  'dxy',
]

const COLORS: Record<string, string> = {
  usdjpy: '#3b82f6',
  eurusd: '#10b981',
  gbpusd: '#8b5cf6',
  audusd: '#f59e0b',
  nzdusd: '#06b6d4',
  usdcad: '#ef4444',
  usdchf: '#f97316',
  eurjpy: '#10b981',
  gbpjpy: '#8b5cf6',
  audjpy: '#f59e0b',
  nzdjpy: '#06b6d4',
  cadjpy: '#ef4444',
  chfjpy: '#f97316',
  eurgbp: '#3b82f6',
  euraud: '#f59e0b',
  eurnzd: '#06b6d4',
  eurcad: '#ef4444',
  eurchf: '#f97316',
  gbpaud: '#f59e0b',
  gbpnzd: '#06b6d4',
  gbpcad: '#ef4444',
  gbpchf: '#f97316',
  audnzd: '#06b6d4',
  audcad: '#ef4444',
  audchf: '#f97316',
  nzdcad: '#ef4444',
  nzdchf: '#f97316',
  cadchf: '#64748b',
  dxy: '#3b82f6',
}

export default function ForexCharts() {
  const { data, isLoading, error } = useMarketBatchData(SYMBOL_IDS)

  if (isLoading) return <LoadingChart title="為替データ読み込み中..." />
  if (error) return <Alert type="error" message="データの取得に失敗しました" showIcon />

  return (
    <div className="country-chart-stack">
      <div id="usdjpy"><MarketPriceChart title="USD/JPY" symbolData={data?.usdjpy} color={COLORS.usdjpy} decimals={3} /></div>
      <div id="eurusd"><MarketPriceChart title="EUR/USD" symbolData={data?.eurusd} color={COLORS.eurusd} decimals={4} /></div>
      <div id="gbpusd"><MarketPriceChart title="GBP/USD" symbolData={data?.gbpusd} color={COLORS.gbpusd} decimals={4} /></div>
      <div id="audusd"><MarketPriceChart title="AUD/USD" symbolData={data?.audusd} color={COLORS.audusd} decimals={4} /></div>
      <div id="nzdusd"><MarketPriceChart title="NZD/USD" symbolData={data?.nzdusd} color={COLORS.nzdusd} decimals={4} /></div>
      <div id="usdcad"><MarketPriceChart title="USD/CAD" symbolData={data?.usdcad} color={COLORS.usdcad} decimals={4} /></div>
      <div id="usdchf"><MarketPriceChart title="USD/CHF" symbolData={data?.usdchf} color={COLORS.usdchf} decimals={4} /></div>
      <div id="eurjpy"><MarketPriceChart title="EUR/JPY" symbolData={data?.eurjpy} color={COLORS.eurjpy} decimals={3} /></div>
      <div id="gbpjpy"><MarketPriceChart title="GBP/JPY" symbolData={data?.gbpjpy} color={COLORS.gbpjpy} decimals={3} /></div>
      <div id="audjpy"><MarketPriceChart title="AUD/JPY" symbolData={data?.audjpy} color={COLORS.audjpy} decimals={3} /></div>
      <div id="nzdjpy"><MarketPriceChart title="NZD/JPY" symbolData={data?.nzdjpy} color={COLORS.nzdjpy} decimals={3} /></div>
      <div id="cadjpy"><MarketPriceChart title="CAD/JPY" symbolData={data?.cadjpy} color={COLORS.cadjpy} decimals={3} /></div>
      <div id="chfjpy"><MarketPriceChart title="CHF/JPY" symbolData={data?.chfjpy} color={COLORS.chfjpy} decimals={3} /></div>
      <div id="eurgbp"><MarketPriceChart title="EUR/GBP" symbolData={data?.eurgbp} color={COLORS.eurgbp} decimals={4} /></div>
      <div id="euraud"><MarketPriceChart title="EUR/AUD" symbolData={data?.euraud} color={COLORS.euraud} decimals={4} /></div>
      <div id="eurnzd"><MarketPriceChart title="EUR/NZD" symbolData={data?.eurnzd} color={COLORS.eurnzd} decimals={4} /></div>
      <div id="eurcad"><MarketPriceChart title="EUR/CAD" symbolData={data?.eurcad} color={COLORS.eurcad} decimals={4} /></div>
      <div id="eurchf"><MarketPriceChart title="EUR/CHF" symbolData={data?.eurchf} color={COLORS.eurchf} decimals={4} /></div>
      <div id="gbpaud"><MarketPriceChart title="GBP/AUD" symbolData={data?.gbpaud} color={COLORS.gbpaud} decimals={4} /></div>
      <div id="gbpnzd"><MarketPriceChart title="GBP/NZD" symbolData={data?.gbpnzd} color={COLORS.gbpnzd} decimals={4} /></div>
      <div id="gbpcad"><MarketPriceChart title="GBP/CAD" symbolData={data?.gbpcad} color={COLORS.gbpcad} decimals={4} /></div>
      <div id="gbpchf"><MarketPriceChart title="GBP/CHF" symbolData={data?.gbpchf} color={COLORS.gbpchf} decimals={4} /></div>
      <div id="audnzd"><MarketPriceChart title="AUD/NZD" symbolData={data?.audnzd} color={COLORS.audnzd} decimals={4} /></div>
      <div id="audcad"><MarketPriceChart title="AUD/CAD" symbolData={data?.audcad} color={COLORS.audcad} decimals={4} /></div>
      <div id="audchf"><MarketPriceChart title="AUD/CHF" symbolData={data?.audchf} color={COLORS.audchf} decimals={4} /></div>
      <div id="nzdcad"><MarketPriceChart title="NZD/CAD" symbolData={data?.nzdcad} color={COLORS.nzdcad} decimals={4} /></div>
      <div id="nzdchf"><MarketPriceChart title="NZD/CHF" symbolData={data?.nzdchf} color={COLORS.nzdchf} decimals={4} /></div>
      <div id="cadchf"><MarketPriceChart title="CAD/CHF" symbolData={data?.cadchf} color={COLORS.cadchf} decimals={4} /></div>
      <div id="dxy"><MarketPriceChart title="ドルインデックス (DXY)" symbolData={data?.dxy} color={COLORS.dxy} decimals={3} /></div>
    </div>
  )
}
