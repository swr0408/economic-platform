import CftcPositioningChart from '../cot/CftcPositioningChart'
import LazyChart from '../../common/LazyChart'

export default function JpyCrossesCharts() {
  return (
    <div className="country-chart-stack">
      <LazyChart id="cot-eurjpy"><CftcPositioningChart asset="eurjpy" assetLabel="ユーロ/円" reportType="tff" compareId="cftc_eurjpy" /></LazyChart>
    </div>
  )
}
