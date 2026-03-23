import CftcPositioningChart from './CftcPositioningChart'
import LazyChart from '../../common/LazyChart'

export default function CotBondsCharts() {
  return (
    <div className="country-chart-stack">
      <LazyChart id="cot-us02y"><CftcPositioningChart asset="us02y" assetLabel="米国2年債" reportType="tff" compareId="cftc_us02y" /></LazyChart>
      <LazyChart id="cot-us10y"><CftcPositioningChart asset="us10y" assetLabel="米国10年債" reportType="tff" compareId="cftc_us10y" /></LazyChart>
      <LazyChart id="cot-us30y"><CftcPositioningChart asset="us30y" assetLabel="米国30年債" reportType="tff" compareId="cftc_us30y" /></LazyChart>
    </div>
  )
}
