import Sp500HeatmapChart from './Sp500HeatmapChart'
import Nasdaq100HeatmapChart from './Nasdaq100HeatmapChart'
import DowHeatmapChart from './DowHeatmapChart'
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
import LazyChart from '../../common/LazyChart'

export default function UsEquitiesCharts() {
  return (
    <div className="country-chart-stack">
      <LazyChart id="us-interest-rate-spread"><UsInterestRateSpreadChart /></LazyChart>
      <LazyChart id="fear-greed"><FearGreedChart /></LazyChart>
      <LazyChart id="gex-dix"><GexDixChart /></LazyChart>
      <LazyChart id="cboe-pcr"><CboePcrChart /></LazyChart>
      <LazyChart id="naaim"><NaaimChart /></LazyChart>
      <LazyChart id="sp500-stock-portion"><Sp500StockPortionChart /></LazyChart>
      <LazyChart id="sp500-heatmap"><Sp500HeatmapChart /></LazyChart>
      <LazyChart id="nasdaq100-heatmap"><Nasdaq100HeatmapChart /></LazyChart>
      <LazyChart id="dow-heatmap"><DowHeatmapChart /></LazyChart>
      <LazyChart id="vix-term-structure"><VixTermStructureChart /></LazyChart>
      <LazyChart id="historical-volatility"><HistoricalVolatilityChart /></LazyChart>
      <LazyChart id="sector-ratio"><SectorRatioChart /></LazyChart>
      <LazyChart id="vix-cross-ratio"><VixCrossRatioChart /></LazyChart>
      <LazyChart id="sp500-valuation"><Sp500ValuationChart /></LazyChart>
      <LazyChart id="nasdaq100-valuation"><Nasdaq100ValuationChart /></LazyChart>
      <LazyChart id="growth-value-ratio"><GrowthValueRatioChart /></LazyChart>
      <LazyChart id="russell2000-russell1000"><Russell2000Russell1000Chart /></LazyChart>
      <LazyChart id="financial-stress-index"><FinancialStressIndexChart /></LazyChart>
      <LazyChart id="cmdi"><CmdiChart /></LazyChart>
      <LazyChart id="cot-sp500"><CftcPositioningChart asset="sp500" assetLabel="S&P 500" reportType="tff" compareId="cftc_sp500" /></LazyChart>
      <LazyChart id="cot-nasdaq100"><CftcPositioningChart asset="nasdaq100" assetLabel="ナスダック100" reportType="tff" compareId="cftc_nasdaq100" /></LazyChart>
      <LazyChart id="cot-dow"><CftcPositioningChart asset="dow" assetLabel="ダウ平均" reportType="tff" compareId="cftc_dow" /></LazyChart>
      <LazyChart id="cot-russell2000"><CftcPositioningChart asset="russell2000" assetLabel="ラッセル2000" reportType="tff" compareId="cftc_russell2000" /></LazyChart>
      <LazyChart id="cot-vix"><CftcPositioningChart asset="vix" assetLabel="VIX" reportType="tff" compareId="cftc_vix" /></LazyChart>
      <LazyChart id="sq-analysis"><SqAnalysisChart /></LazyChart>
    </div>
  )
}
