import { Alert } from 'antd'
import MarketPriceChart from '../MarketPriceChart'
import CftcPositioningChart from '../cot/CftcPositioningChart'
import { useMarketBatchData } from '../../../hooks/useMarketData'
import LoadingChart from '../../common/LoadingChart'
import LazyChart from '../../common/LazyChart'

const SYMBOL_IDS = ['eurgbp', 'euraud', 'eurnzd', 'eurcad', 'eurchf']

const COLORS: Record<string, string> = {
  eurgbp: '#3b82f6',
  euraud: '#f59e0b',
  eurnzd: '#06b6d4',
  eurcad: '#ef4444',
  eurchf: '#f97316',
}

export default function EurCrossesCharts() {
  const { data, isLoading, error } = useMarketBatchData(SYMBOL_IDS)

  if (isLoading) return <LoadingChart title="ユーロクロスデータ読み込み中..." />
  if (error) return <Alert type="error" message="データの取得に失敗しました" showIcon />

  return (
    <div className="country-chart-stack">
      <LazyChart id="eurgbp"><MarketPriceChart title="EUR/GBP" symbolData={data?.eurgbp} color={COLORS.eurgbp} decimals={4} /></LazyChart>
      <LazyChart id="cot-eurgbp"><CftcPositioningChart asset="eurgbp" assetLabel="ユーロ/ポンド" reportType="tff" compareId="cftc_eurgbp" handbookId="cot-eurgbp" /></LazyChart>
      <LazyChart id="euraud"><MarketPriceChart title="EUR/AUD" symbolData={data?.euraud} color={COLORS.euraud} decimals={4} /></LazyChart>
      <LazyChart id="eurnzd"><MarketPriceChart title="EUR/NZD" symbolData={data?.eurnzd} color={COLORS.eurnzd} decimals={4} /></LazyChart>
      <LazyChart id="eurcad"><MarketPriceChart title="EUR/CAD" symbolData={data?.eurcad} color={COLORS.eurcad} decimals={4} /></LazyChart>
      <LazyChart id="eurchf"><MarketPriceChart title="EUR/CHF" symbolData={data?.eurchf} color={COLORS.eurchf} decimals={4} /></LazyChart>
    </div>
  )
}
