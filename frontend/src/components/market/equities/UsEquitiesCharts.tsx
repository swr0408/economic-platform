import { Alert } from 'antd'
import MarketPriceChart from '../MarketPriceChart'
import FearGreedChart from './FearGreedChart'
import NaaimChart from './NaaimChart'
import GexDixChart from './GexDixChart'
import CboePcrChart from './CboePcrChart'
import Sp500ValuationChart from './Sp500ValuationChart'
import Nasdaq100ValuationChart from './Nasdaq100ValuationChart'
import GrowthValueRatioChart from './GrowthValueRatioChart'
import Russell2000Russell1000Chart from './Russell2000Russell1000Chart'
import FinancialStressIndexChart from './FinancialStressIndexChart'
import CmdiChart from './CmdiChart'
import UsInterestRateSpreadChart from './UsInterestRateSpreadChart'
import Sp500StockPortionChart from './Sp500StockPortionChart'
import VixTermStructureChart from './VixTermStructureChart'
import HistoricalVolatilityChart from './HistoricalVolatilityChart'
import VixCrossRatioChart from './VixCrossRatioChart'
import SectorRatioChart from './SectorRatioChart'
import SqAnalysisChart from './SqAnalysisChart'
import CftcPositioningChart from '../cot/CftcPositioningChart'
import { useMarketBatchData } from '../../../hooks/useMarketData'
import LoadingChart from '../../common/LoadingChart'
import LazyChart from '../../common/LazyChart'

const SYMBOL_IDS = ['sox']

export default function UsEquitiesCharts() {
  const { data, isLoading, error } = useMarketBatchData(SYMBOL_IDS)

  if (isLoading) return <LoadingChart title="米国株データ読み込み中..." />
  if (error) return <Alert type="error" message="データの取得に失敗しました" showIcon />

  return (
    <div className="country-chart-stack">
      <LazyChart id="vix-term-structure"><VixTermStructureChart /></LazyChart>
      <LazyChart id="historical-volatility"><HistoricalVolatilityChart /></LazyChart>
      <LazyChart id="vix-cross-ratio"><VixCrossRatioChart /></LazyChart>
      <LazyChart id="sector-ratio"><SectorRatioChart /></LazyChart>
      <LazyChart id="sox"><MarketPriceChart title="SOX（半導体指数）" symbolData={data?.sox} color="#f59e0b" decimals={0} /></LazyChart>
      <LazyChart id="fear-greed"><FearGreedChart /></LazyChart>
      <LazyChart id="naaim"><NaaimChart /></LazyChart>
      <LazyChart id="gex-dix"><GexDixChart /></LazyChart>
      <LazyChart id="cboe-pcr"><CboePcrChart /></LazyChart>
      <LazyChart id="sp500-valuation"><Sp500ValuationChart /></LazyChart>
      <LazyChart id="nasdaq100-valuation"><Nasdaq100ValuationChart /></LazyChart>
      <LazyChart id="growth-value-ratio"><GrowthValueRatioChart /></LazyChart>
      <LazyChart id="russell2000-russell1000"><Russell2000Russell1000Chart /></LazyChart>
      <LazyChart id="financial-stress-index"><FinancialStressIndexChart /></LazyChart>
      <LazyChart id="cmdi"><CmdiChart /></LazyChart>
      <LazyChart id="us-interest-rate-spread"><UsInterestRateSpreadChart /></LazyChart>
      <LazyChart id="sp500-stock-portion"><Sp500StockPortionChart /></LazyChart>
      <LazyChart id="cot-sp500"><CftcPositioningChart asset="sp500" assetLabel="S&P 500" reportType="tff" compareId="cftc_sp500" /></LazyChart>
      <LazyChart id="cot-dow"><CftcPositioningChart asset="dow" assetLabel="ダウ平均" reportType="tff" compareId="cftc_dow" /></LazyChart>
      <LazyChart id="cot-nasdaq100"><CftcPositioningChart asset="nasdaq100" assetLabel="ナスダック100" reportType="tff" compareId="cftc_nasdaq100" /></LazyChart>
      <LazyChart id="cot-russell2000"><CftcPositioningChart asset="russell2000" assetLabel="ラッセル2000" reportType="tff" compareId="cftc_russell2000" /></LazyChart>
      <LazyChart id="cot-vix"><CftcPositioningChart asset="vix" assetLabel="VIX" reportType="tff" compareId="cftc_vix" /></LazyChart>
      <LazyChart id="sq-analysis"><SqAnalysisChart /></LazyChart>
    </div>
  )
}
