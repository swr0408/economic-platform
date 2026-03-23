import { Alert } from 'antd'
import MarketPriceChart from '../MarketPriceChart'
import { useMarketBatchData } from '../../../hooks/useMarketData'
import LoadingChart from '../../common/LoadingChart'
import LazyChart from '../../common/LazyChart'

const SYMBOL_IDS = ['dax', 'ftse100', 'cac40', 'eurostoxx50']

const COLORS: Record<string, string> = {
  dax: '#3b82f6',
  ftse100: '#10b981',
  cac40: '#8b5cf6',
  eurostoxx50: '#f59e0b',
}

export default function EuEquitiesCharts() {
  const { data, isLoading, error } = useMarketBatchData(SYMBOL_IDS)

  if (isLoading) return <LoadingChart title="欧州株データ読み込み中..." />
  if (error) return <Alert type="error" message="データの取得に失敗しました" showIcon />

  return (
    <div className="country-chart-stack">
      <LazyChart id="dax"><MarketPriceChart title="DAX" symbolData={data?.dax} color={COLORS.dax} decimals={0} /></LazyChart>
      <LazyChart id="ftse100"><MarketPriceChart title="FTSE 100" symbolData={data?.ftse100} color={COLORS.ftse100} decimals={0} /></LazyChart>
      <LazyChart id="cac40"><MarketPriceChart title="CAC 40" symbolData={data?.cac40} color={COLORS.cac40} decimals={0} /></LazyChart>
      <LazyChart id="eurostoxx50"><MarketPriceChart title="EURO STOXX 50" symbolData={data?.eurostoxx50} color={COLORS.eurostoxx50} decimals={0} /></LazyChart>
    </div>
  )
}
