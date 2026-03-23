import CftcPositioningChart from './CftcPositioningChart'
import LazyChart from '../../common/LazyChart'

export default function CotCommoditiesCharts() {
  return (
    <div className="country-chart-stack">
      <LazyChart id="cot-gold"><CftcPositioningChart asset="gold" assetLabel="金（ゴールド）" reportType="disagg" compareId="cftc_gold" handbookId="cot-gold" /></LazyChart>
      <LazyChart id="cot-silver"><CftcPositioningChart asset="silver" assetLabel="銀（シルバー）" reportType="disagg" compareId="cftc_silver" handbookId="cot-silver" /></LazyChart>
      <LazyChart id="cot-copper"><CftcPositioningChart asset="copper" assetLabel="銅（カッパー）" reportType="disagg" compareId="cftc_copper" /></LazyChart>
    </div>
  )
}
