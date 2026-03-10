import { Alert, Typography } from 'antd'
import MarketPriceChart from '../MarketPriceChart'
import GoldEtfHoldingsChart from './GoldEtfHoldingsChart'
import GoldPremiumChart from './GoldPremiumChart'
import WgcGoldEtfChart from './WgcGoldEtfChart'
import { useMarketBatchData } from '../../../hooks/useMarketData'
import LoadingChart from '../../common/LoadingChart'

const { Title } = Typography

const SYMBOL_IDS = [
  'gold', 'gold_jpy', 'silver', 'platinum',
  'copper', 'aluminum',
]

const COLORS = {
  gold: '#f59e0b',
  gold_jpy: '#fbbf24',
  silver: '#94a3b8',
  platinum: '#a78bfa',
  copper: '#f97316',
  aluminum: '#64748b',
}

export default function CommoditiesCharts() {
  const { data, isLoading, error } = useMarketBatchData(SYMBOL_IDS)

  if (isLoading) return <LoadingChart title="コモディティデータ読み込み中..." />
  if (error) return <Alert type="error" message="データの取得に失敗しました" showIcon />

  return (
    <div className="country-chart-stack">
      {/* 貴金属 */}
      <div id="precious-metals">
        <Title level={4} style={{ color: '#f1f5f9', marginBottom: 16 }}>貴金属</Title>
      </div>
      <div id="gold"><MarketPriceChart title="金（ドル建て）" symbolData={data?.gold} color={COLORS.gold} unit=" USD/oz" /></div>
      <div id="gold-jpy"><MarketPriceChart title="金（円建て）" symbolData={data?.gold_jpy} color={COLORS.gold_jpy} decimals={0} unit=" 円/oz" /></div>
      <div id="gold-etf-holdings"><GoldEtfHoldingsChart /></div>
      <div id="gold-premium"><GoldPremiumChart /></div>
      <div id="wgc-gold-etf"><WgcGoldEtfChart /></div>
      <div id="silver"><MarketPriceChart title="銀" symbolData={data?.silver} color={COLORS.silver} unit=" USD/oz" /></div>
      <div id="platinum"><MarketPriceChart title="プラチナ" symbolData={data?.platinum} color={COLORS.platinum} unit=" USD/oz" /></div>

      {/* 工業用金属 */}
      <div id="industrial-metals">
        <Title level={4} style={{ color: '#f1f5f9', marginTop: 32, marginBottom: 16 }}>工業用金属</Title>
      </div>
      <div id="copper"><MarketPriceChart title="銅" symbolData={data?.copper} color={COLORS.copper} unit=" USD/lb" /></div>
      <div id="aluminum"><MarketPriceChart title="アルミニウム" symbolData={data?.aluminum} color={COLORS.aluminum} /></div>
    </div>
  )
}
