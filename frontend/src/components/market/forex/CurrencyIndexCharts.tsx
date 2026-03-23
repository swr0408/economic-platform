import CftcPositioningChart from '../cot/CftcPositioningChart'
import LazyChart from '../../common/LazyChart'

export default function CurrencyIndexCharts() {
  return (
    <div className="country-chart-stack">
      <LazyChart id="cot-usd-index"><CftcPositioningChart asset="usd_index" assetLabel="ドルインデックス" reportType="tff" compareId="cftc_usd_index" handbookId="cot-usd-index" /></LazyChart>
    </div>
  )
}
