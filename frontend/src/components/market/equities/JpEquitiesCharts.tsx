import Nikkei225ValuationChart from './Nikkei225ValuationChart'
import TopixValuationChart from './TopixValuationChart'
import NikkeiRegressionChart from './NikkeiRegressionChart'
import ElectronicComponentsBalanceChart from './ElectronicComponentsBalanceChart'
import JpxPcrChart from './JpxPcrChart'
import ChinaM2NikkeiYoyChart from './ChinaM2NikkeiYoyChart'
import NikkeiDoubleInverseChart from './NikkeiDoubleInverseChart'
import JpxInvestorTradingChart from './JpxInvestorTradingChart'
import MofSecuritiesTradingChart from './MofSecuritiesTradingChart'
import AdvanceDeclineRatioChart from './AdvanceDeclineRatioChart'
import NtMagnificationChart from './NtMagnificationChart'
import CftcPositioningChart from '../cot/CftcPositioningChart'
import LazyChart from '../../common/LazyChart'

export default function JpEquitiesCharts() {
  return (
    <div className="country-chart-stack">
      <LazyChart id="nikkei225-valuation"><Nikkei225ValuationChart /></LazyChart>
      <LazyChart id="topix-valuation"><TopixValuationChart /></LazyChart>
      <LazyChart id="nikkei-regression"><NikkeiRegressionChart /></LazyChart>
      <LazyChart id="electronic-components-balance"><ElectronicComponentsBalanceChart /></LazyChart>
      <LazyChart id="jpx-pcr"><JpxPcrChart /></LazyChart>
      <LazyChart id="china-m2-nikkei-yoy"><ChinaM2NikkeiYoyChart /></LazyChart>
      <LazyChart id="nikkei-double-inverse"><NikkeiDoubleInverseChart /></LazyChart>
      <LazyChart id="jpx-investor-trading"><JpxInvestorTradingChart /></LazyChart>
      <LazyChart id="mof-securities-trading"><MofSecuritiesTradingChart /></LazyChart>
      <LazyChart id="advance-decline-ratio"><AdvanceDeclineRatioChart /></LazyChart>
      <LazyChart id="nt-magnification"><NtMagnificationChart /></LazyChart>
      <LazyChart id="cot-nikkei225"><CftcPositioningChart asset="nikkei225" assetLabel="日経225" reportType="tff" compareId="cftc_nikkei225" /></LazyChart>
    </div>
  )
}
