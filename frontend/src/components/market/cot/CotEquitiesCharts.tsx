import CftcPositioningChart from './CftcPositioningChart'
import LazyChart from '../../common/LazyChart'

export default function CotEquitiesCharts() {
  return (
    <div className="country-chart-stack">
      <LazyChart id="cot-sp500"><CftcPositioningChart asset="sp500" assetLabel="S&P 500" reportType="tff" compareId="cftc_sp500" /></LazyChart>
      <LazyChart id="cot-dow"><CftcPositioningChart asset="dow" assetLabel="ダウ平均" reportType="tff" compareId="cftc_dow" /></LazyChart>
      <LazyChart id="cot-nasdaq100"><CftcPositioningChart asset="nasdaq100" assetLabel="ナスダック100" reportType="tff" compareId="cftc_nasdaq100" /></LazyChart>
      <LazyChart id="cot-russell2000"><CftcPositioningChart asset="russell2000" assetLabel="ラッセル2000" reportType="tff" compareId="cftc_russell2000" /></LazyChart>
      <LazyChart id="cot-nikkei225"><CftcPositioningChart asset="nikkei225" assetLabel="日経225" reportType="tff" compareId="cftc_nikkei225" /></LazyChart>
      <LazyChart id="cot-vix"><CftcPositioningChart asset="vix" assetLabel="VIX" reportType="tff" compareId="cftc_vix" /></LazyChart>
    </div>
  )
}
