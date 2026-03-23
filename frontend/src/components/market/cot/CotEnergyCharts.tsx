import CftcPositioningChart from './CftcPositioningChart'
import LazyChart from '../../common/LazyChart'

export default function CotEnergyCharts() {
  return (
    <div className="country-chart-stack">
      <LazyChart id="cot-crude-oil"><CftcPositioningChart asset="crude_oil" assetLabel="原油（WTI）" reportType="disagg" compareId="cftc_crude_oil" handbookId="cot-crude-oil" /></LazyChart>
      <LazyChart id="cot-brent"><CftcPositioningChart asset="brent" assetLabel="ブレント原油" reportType="disagg" compareId="cftc_brent" /></LazyChart>
      <LazyChart id="cot-natural-gas"><CftcPositioningChart asset="natural_gas" assetLabel="天然ガス" reportType="disagg" compareId="cftc_natural_gas" /></LazyChart>
    </div>
  )
}
