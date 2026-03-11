import { Alert, Typography } from 'antd'
import MarketPriceChart from '../MarketPriceChart'
import WeeklyCrudeOilInventoriesChart from './WeeklyCrudeOilInventoriesChart'
import CushingInventoryChart from './CushingInventoryChart'
import DistillateFuelInventoriesChart from './DistillateFuelInventoriesChart'
import UsGasolineRefineryChart from './UsGasolineRefineryChart'
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
      <div id="weekly-crude-oil-inventories"><WeeklyCrudeOilInventoriesChart /></div>
      <div id="cushing-inventory"><CushingInventoryChart /></div>
      <div id="distillate-fuel-inventories"><DistillateFuelInventoriesChart /></div>
      <div id="gasoline-refinery"><UsGasolineRefineryChart /></div>

      {/* 天然ガス */}
      <div id="natural-gas">
        <Title level={4} style={{ color: '#f1f5f9', marginTop: 32, marginBottom: 16 }}>天然ガス</Title>
      </div>
      <div id="natural-gas-chart"><MarketPriceChart title="天然ガス (Henry Hub)" symbolData={data?.natural_gas} color={COLORS.natural_gas} unit=" USD/MMBtu" /></div>
    </div>
  )
}
