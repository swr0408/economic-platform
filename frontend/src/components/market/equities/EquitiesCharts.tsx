import { Alert, Typography } from 'antd'
import MarketPriceChart from '../MarketPriceChart'
import TsmcRevenueChart from './TsmcRevenueChart'
import FearGreedChart from './FearGreedChart'
import NaaimChart from './NaaimChart'
import GexDixChart from './GexDixChart'
import CboePcrChart from './CboePcrChart'
import NikkeiRegressionChart from './NikkeiRegressionChart'
import ElectronicComponentsBalanceChart from './ElectronicComponentsBalanceChart'
import JpxPcrChart from './JpxPcrChart'
import ChinaM2NikkeiYoyChart from './ChinaM2NikkeiYoyChart'
import NikkeiDoubleInverseChart from './NikkeiDoubleInverseChart'
import JpxInvestorTradingChart from './JpxInvestorTradingChart'
import { useMarketBatchData } from '../../../hooks/useMarketData'
import LoadingChart from '../../common/LoadingChart'

const { Title } = Typography

const SYMBOL_IDS = [
  'sp500', 'nasdaq100', 'nasdaq', 'dow', 'russell2000', 'vix', 'sox',
  'nikkei225', 'topix', 'nikkei_usd',
  'dax', 'ftse100', 'cac40', 'eurostoxx50',
  'twii', 'tsmc',
]

const COLORS = {
  sp500: '#3b82f6',
  nasdaq100: '#8b5cf6',
  nasdaq: '#a78bfa',
  dow: '#06b6d4',
  russell2000: '#14b8a6',
  vix: '#ef4444',
  sox: '#f59e0b',
  nikkei225: '#ef4444',
  topix: '#f97316',
  nikkei_usd: '#06b6d4',
  dax: '#3b82f6',
  ftse100: '#10b981',
  cac40: '#8b5cf6',
  eurostoxx50: '#f59e0b',
  twii: '#3b82f6',
  tsmc: '#10b981',
}

export default function EquitiesCharts() {
  const { data, isLoading, error } = useMarketBatchData(SYMBOL_IDS)

  if (isLoading) return <LoadingChart title="株式市場データ読み込み中..." />
  if (error) return <Alert type="error" message="データの取得に失敗しました" showIcon />

  return (
    <div className="country-chart-stack">
      {/* 米国株 */}
      <div id="us-equities">
        <Title level={4} style={{ color: '#f1f5f9', marginBottom: 16 }}>米国株</Title>
      </div>
      <div id="sp500"><MarketPriceChart title="S&P 500" symbolData={data?.sp500} color={COLORS.sp500} decimals={0} /></div>
      <div id="nasdaq100"><MarketPriceChart title="ナスダック100" symbolData={data?.nasdaq100} color={COLORS.nasdaq100} decimals={0} /></div>
      <div id="nasdaq"><MarketPriceChart title="ナスダック総合" symbolData={data?.nasdaq} color={COLORS.nasdaq} decimals={0} /></div>
      <div id="dow"><MarketPriceChart title="ダウ平均" symbolData={data?.dow} color={COLORS.dow} decimals={0} /></div>
      <div id="russell2000"><MarketPriceChart title="ラッセル2000" symbolData={data?.russell2000} color={COLORS.russell2000} decimals={0} /></div>
      <div id="vix"><MarketPriceChart title="VIX（恐怖指数）" symbolData={data?.vix} color={COLORS.vix} /></div>
      <div id="sox"><MarketPriceChart title="SOX（半導体指数）" symbolData={data?.sox} color={COLORS.sox} decimals={0} /></div>
      <div id="fear-greed"><FearGreedChart /></div>
      <div id="naaim"><NaaimChart /></div>
      <div id="gex-dix"><GexDixChart /></div>
      <div id="cboe-pcr"><CboePcrChart /></div>

      {/* 日本株 */}
      <div id="jp-equities">
        <Title level={4} style={{ color: '#f1f5f9', marginTop: 32, marginBottom: 16 }}>日本株</Title>
      </div>
      <div id="nikkei225"><MarketPriceChart title="日経平均" symbolData={data?.nikkei225} color={COLORS.nikkei225} decimals={0} /></div>
      <div id="topix"><MarketPriceChart title="TOPIX" symbolData={data?.topix} color={COLORS.topix} decimals={0} /></div>
      <div id="nikkei-usd"><MarketPriceChart title="日経平均（ドル建て）" symbolData={data?.nikkei_usd} color={COLORS.nikkei_usd} decimals={0} /></div>
      <div id="nikkei-regression"><NikkeiRegressionChart /></div>
      <div id="electronic-components-balance"><ElectronicComponentsBalanceChart /></div>
      <div id="jpx-pcr"><JpxPcrChart /></div>
      <div id="china-m2-nikkei-yoy"><ChinaM2NikkeiYoyChart /></div>
      <div id="nikkei-double-inverse"><NikkeiDoubleInverseChart /></div>
      <div id="jpx-investor-trading"><JpxInvestorTradingChart /></div>

      {/* 欧州株 */}
      <div id="eu-equities">
        <Title level={4} style={{ color: '#f1f5f9', marginTop: 32, marginBottom: 16 }}>欧州株</Title>
      </div>
      <div id="dax"><MarketPriceChart title="DAX" symbolData={data?.dax} color={COLORS.dax} decimals={0} /></div>
      <div id="ftse100"><MarketPriceChart title="FTSE 100" symbolData={data?.ftse100} color={COLORS.ftse100} decimals={0} /></div>
      <div id="cac40"><MarketPriceChart title="CAC 40" symbolData={data?.cac40} color={COLORS.cac40} decimals={0} /></div>
      <div id="eurostoxx50"><MarketPriceChart title="EURO STOXX 50" symbolData={data?.eurostoxx50} color={COLORS.eurostoxx50} decimals={0} /></div>

      {/* 台湾/半導体 */}
      <div id="tw-semiconductor">
        <Title level={4} style={{ color: '#f1f5f9', marginTop: 32, marginBottom: 16 }}>台湾/半導体</Title>
      </div>
      <div id="twii"><MarketPriceChart title="台湾加権指数" symbolData={data?.twii} color={COLORS.twii} decimals={0} /></div>
      <div id="tsmc"><MarketPriceChart title="TSMC (ADR)" symbolData={data?.tsmc} color={COLORS.tsmc} /></div>
      <div id="tsmc-revenue"><TsmcRevenueChart /></div>
    </div>
  )
}
