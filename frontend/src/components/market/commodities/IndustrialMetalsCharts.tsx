import LmeCopperStockChart from './LmeCopperStockChart'
import ComexCopperStockChart from './ComexCopperStockChart'
import ShfeCopperStockChart from './ShfeCopperStockChart'
import CopperToGoldRatioChart from './CopperToGoldRatioChart'
import CftcPositioningChart from '../cot/CftcPositioningChart'
import LazyChart from '../../common/LazyChart'

export default function IndustrialMetalsCharts() {
  return (
    <div className="country-chart-stack">
      <LazyChart id="copper-to-gold-ratio"><CopperToGoldRatioChart /></LazyChart>
      <LazyChart id="lme-copper-stock"><LmeCopperStockChart /></LazyChart>
      <LazyChart id="comex-copper-stock"><ComexCopperStockChart /></LazyChart>
      <LazyChart id="shfe-copper-stock"><ShfeCopperStockChart /></LazyChart>
      <LazyChart id="cot-copper"><CftcPositioningChart asset="copper" assetLabel="銅（カッパー）" reportType="disagg" compareId="cftc_copper" handbookId="cot-copper" /></LazyChart>
    </div>
  )
}
