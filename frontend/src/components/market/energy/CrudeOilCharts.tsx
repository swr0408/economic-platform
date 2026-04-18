import WeeklyCrudeOilInventoriesChart from './WeeklyCrudeOilInventoriesChart'
import ApiWeeklyCrudeOilInventoriesChart from './ApiWeeklyCrudeOilInventoriesChart'
import CushingInventoryChart from './CushingInventoryChart'
import DistillateFuelInventoriesChart from './DistillateFuelInventoriesChart'
import AdjustmentsChart from './AdjustmentsChart'
import UsShaleOilProductionChart from './UsShaleOilProductionChart'
import NorthAmericaRigCountChart from './NorthAmericaRigCountChart'
import CrudeOilNetDemandChart from './CrudeOilNetDemandChart'
import ShortTermEnergyOutlookChart from './ShortTermEnergyOutlookChart'
import UsGasolineRefineryChart from './UsGasolineRefineryChart'
import OpecMomrChart from './OpecMomrChart'
import IeaOilMarketReportChart from './IeaOilMarketReportChart'
import CrackSpreadChart from './CrackSpreadChart'
import CftcPositioningChart from '../cot/CftcPositioningChart'
import LazyChart from '../../common/LazyChart'

export default function CrudeOilCharts() {
  return (
    <div className="country-chart-stack">
      <LazyChart id="crack-spread"><CrackSpreadChart /></LazyChart>
      <LazyChart id="api-weekly-crude-oil-inventories"><ApiWeeklyCrudeOilInventoriesChart /></LazyChart>
      <LazyChart id="weekly-crude-oil-inventories"><WeeklyCrudeOilInventoriesChart /></LazyChart>
      <LazyChart id="cushing-inventory"><CushingInventoryChart /></LazyChart>
      <LazyChart id="distillate-fuel-inventories"><DistillateFuelInventoriesChart /></LazyChart>
      <LazyChart id="gasoline-refinery"><UsGasolineRefineryChart /></LazyChart>
      <LazyChart id="adjustments"><AdjustmentsChart /></LazyChart>
      <LazyChart id="shale-oil-production"><UsShaleOilProductionChart /></LazyChart>
      <LazyChart id="crude-oil-net-demand"><CrudeOilNetDemandChart /></LazyChart>
      <LazyChart id="short-term-energy-outlook"><ShortTermEnergyOutlookChart /></LazyChart>
      <LazyChart id="opec-momr"><OpecMomrChart /></LazyChart>
      <LazyChart id="iea-oil-market-report"><IeaOilMarketReportChart /></LazyChart>
      <LazyChart id="rig-count"><NorthAmericaRigCountChart /></LazyChart>
      <LazyChart id="cot-crude-oil"><CftcPositioningChart asset="crude_oil" assetLabel="原油（WTI）" reportType="disagg" compareId="cftc_crude_oil" handbookId="cot-crude-oil" /></LazyChart>
      <LazyChart id="cot-brent"><CftcPositioningChart asset="brent" assetLabel="ブレント原油" reportType="disagg" compareId="cftc_brent" /></LazyChart>
    </div>
  )
}
