import CftcPositioningChart from '../cot/CftcPositioningChart'
import LazyChart from '../../common/LazyChart'

export default function EurCrossesCharts() {
  return (
    <div className="country-chart-stack">
      <LazyChart id="cot-eurgbp"><CftcPositioningChart asset="eurgbp" assetLabel="ユーロ/ポンド" reportType="tff" compareId="cftc_eurgbp" handbookId="cot-eurgbp" /></LazyChart>
    </div>
  )
}
