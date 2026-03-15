import { Alert, Typography } from 'antd'
import MarketPriceChart from '../MarketPriceChart'
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
import UsNaturalGasStorageChart from './UsNaturalGasStorageChart'
import UsNaturalGasTradeChart from './UsNaturalGasTradeChart'
import LngExportsByRegionChart from './LngExportsByRegionChart'
import SteoNaturalGasChart from './SteoNaturalGasChart'
import EuNaturalGasStorageChart from './EuNaturalGasStorageChart'
import EuNaturalGasProductionChart from './EuNaturalGasProductionChart'
import NoaaHddCddChart from './NoaaHddCddChart'
import RoniChart from './RoniChart'
import OpecMomrChart from './OpecMomrChart'
import IeaOilMarketReportChart from './IeaOilMarketReportChart'
import CrackSpreadChart from './CrackSpreadChart'
import CftcPositioningChart from '../cot/CftcPositioningChart'
import { useMarketBatchData } from '../../../hooks/useMarketData'
import LoadingChart from '../../common/LoadingChart'

const { Title } = Typography

const SYMBOL_IDS = ['crude_oil', 'brent_oil', 'natural_gas']

const COLORS = {
  crude_oil: '#3b82f6',
  brent_oil: '#06b6d4',
  natural_gas: '#f59e0b',
}

export default function EnergyCharts() {
  const { data, isLoading, error } = useMarketBatchData(SYMBOL_IDS)

  if (isLoading) return <LoadingChart title="エネルギーデータ読み込み中..." />
  if (error) return <Alert type="error" message="データの取得に失敗しました" showIcon />

  return (
    <div className="country-chart-stack">
      {/* 原油 */}
      <div id="crude-oil">
        <Title level={4} style={{ color: '#f1f5f9', marginBottom: 16 }}>原油</Title>
      </div>
      <div id="wti"><MarketPriceChart title="WTI原油" symbolData={data?.crude_oil} color={COLORS.crude_oil} unit=" USD/bbl" /></div>
      <div id="brent"><MarketPriceChart title="ブレント原油" symbolData={data?.brent_oil} color={COLORS.brent_oil} unit=" USD/bbl" /></div>
      <div id="api-weekly-crude-oil-inventories"><ApiWeeklyCrudeOilInventoriesChart /></div>
      <div id="weekly-crude-oil-inventories"><WeeklyCrudeOilInventoriesChart /></div>
      <div id="cushing-inventory"><CushingInventoryChart /></div>
      <div id="distillate-fuel-inventories"><DistillateFuelInventoriesChart /></div>
      <div id="gasoline-refinery"><UsGasolineRefineryChart /></div>
      <div id="adjustments"><AdjustmentsChart /></div>
      <div id="shale-oil-production"><UsShaleOilProductionChart /></div>
      <div id="crude-oil-net-demand"><CrudeOilNetDemandChart /></div>
      <div id="crack-spread"><CrackSpreadChart /></div>
      <div id="short-term-energy-outlook"><ShortTermEnergyOutlookChart /></div>
      <div id="opec-momr"><OpecMomrChart /></div>
      <div id="iea-oil-market-report"><IeaOilMarketReportChart /></div>
      <div id="rig-count"><NorthAmericaRigCountChart /></div>
      <div id="cot-crude-oil"><CftcPositioningChart asset="crude_oil" assetLabel="原油（WTI）" reportType="disagg" compareId="cftc_crude_oil" /></div>
      <div id="cot-brent"><CftcPositioningChart asset="brent" assetLabel="ブレント原油" reportType="disagg" compareId="cftc_brent" /></div>

      {/* 天然ガス */}
      <div id="natural-gas">
        <Title level={4} style={{ color: '#f1f5f9', marginTop: 32, marginBottom: 16 }}>天然ガス</Title>
      </div>
      <div id="natural-gas-chart"><MarketPriceChart title="天然ガス (Henry Hub)" symbolData={data?.natural_gas} color={COLORS.natural_gas} unit=" USD/MMBtu" /></div>
      <div id="natural-gas-storage"><UsNaturalGasStorageChart /></div>
      <div id="natural-gas-trade"><UsNaturalGasTradeChart /></div>
      <div id="lng-exports-by-region"><LngExportsByRegionChart /></div>
      <div id="steo-natural-gas"><SteoNaturalGasChart /></div>
      <div id="noaa-hdd-cdd"><NoaaHddCddChart /></div>
      <div id="eu-natural-gas-storage"><EuNaturalGasStorageChart /></div>
      <div id="eu-natural-gas-production"><EuNaturalGasProductionChart /></div>
      <div id="roni"><RoniChart /></div>
      <div id="cot-natural-gas"><CftcPositioningChart asset="natural_gas" assetLabel="天然ガス" reportType="disagg" compareId="cftc_natural_gas" /></div>
    </div>
  )
}
