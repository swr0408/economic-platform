import { Spin } from 'antd'
import QuarterlyGDPChart from './economy/QuarterlyGDPChart'
import GDPComponentsChart from './economy/GDPComponentsChart'
import GDPDeflatorChart from './economy/GDPDeflatorChart'
import PotentialGrowthChart from './economy/PotentialGrowthChart'
import BOJPotentialGrowthChart from './economy/BOJPotentialGrowthChart'
import BOJLendingChart from './economy/BOJLendingChart'
import CapitalInvestmentChart from './economy/CapitalInvestmentChart'
import JapanIIPChart from './economy/JapanIIPChart'
import JapanIIPForecastTable from './economy/JapanIIPForecastTable'
import CapacityUtilizationChart from './economy/CapacityUtilizationChart'
import TertiaryIndustryIndexChart from './economy/TertiaryIndustryIndexChart'
import MachineryOrdersChart from './economy/MachineryOrdersChart'
import MachineryOrdersForecastTable from './economy/MachineryOrdersForecastTable'
import MachineToolOrdersChart from './economy/MachineToolOrdersChart'
import BOJTankanUnifiedTable from './economy/BOJTankanUnifiedTable'
import BSIUnifiedChart from './economy/BSIUnifiedChart'
import JapanPMIChart from './economy/JapanPMIChart'
import JapanCurrentAccountChart from './economy/JapanCurrentAccountChart'
import JapanCurrentAccountGdpRatioChart from './economy/JapanCurrentAccountGdpRatioChart'
import JapanBalanceOfTradeChart from './economy/JapanBalanceOfTradeChart'
import { useJapanEconomyDashboard } from '../../../hooks/useDashboardData'

/**
 * 日本経済チャート群
 *
 * 経済指標関連のチャートを表示
 * ダッシュボードAPIからデータを取得し、各チャートコンポーネントにpropsで渡す
 */
export default function JapanEconomyCharts() {
  const { data } = useJapanEconomyDashboard()
  const dashboardData = data?.data

  return (
    <div className="country-chart-stack">
      {/* Quarterly GDP Growth Rate Chart */}
      <div id="quarterly-gdp">
        <QuarterlyGDPChart />
      </div>

      {/* GDP Components Chart */}
      <div id="gdp-components">
        <GDPComponentsChart />
      </div>

      {/* GDP Deflator Chart */}
      <div id="gdp-deflator">
        <GDPDeflatorChart />
      </div>

      {/* Potential Growth Rate Chart */}
      <div id="potential-growth">
        <PotentialGrowthChart />
      </div>

      {/* BOJ Potential Growth Rate Chart */}
      <div id="boj-potential-growth">
        <BOJPotentialGrowthChart />
      </div>

      {/* BOJ Lending Trends Chart */}
      <div id="boj-lending">
        <BOJLendingChart />
      </div>

      {/* Capital Investment Chart */}
      <div id="capital-investment">
        <CapitalInvestmentChart />
      </div>

      {/* Industrial Production Index Chart */}
      <div id="iip">
        <JapanIIPChart />
      </div>

      {/* IIP Forecast Table */}
      <div id="iip-forecast">
        <JapanIIPForecastTable />
      </div>

      {/* Capacity Utilization Chart */}
      <div id="capacity-utilization">
        <CapacityUtilizationChart />
      </div>

      {/* Tertiary Industry Activity Index Chart */}
      <div id="tertiary-industry-index">
        <TertiaryIndustryIndexChart />
      </div>

      {/* Machinery Orders Chart */}
      <div id="machinery-orders">
        <MachineryOrdersChart />
      </div>

      {/* Machinery Orders Forecast Table */}
      <div id="machinery-orders-forecast">
        <MachineryOrdersForecastTable />
      </div>

      {/* Machine Tool Orders Chart */}
      <div id="machine-tool-orders">
        <MachineToolOrdersChart />
      </div>

      {/* BOJ Tankan Unified Table */}
      <div id="boj-tankan">
        <BOJTankanUnifiedTable />
      </div>

      {/* BSI 法人企業景気予測調査 */}
      <div id="bsi">
        <BSIUnifiedChart />
      </div>

      {/* S&P Global PMI（日本） */}
      <div id="pmi">
        <JapanPMIChart />
      </div>

      {/* 経常収支 */}
      <div id="current-account">
        <JapanCurrentAccountChart data={dashboardData?.current_account ?? null} />
      </div>

      {/* 経常収支対GDP比 */}
      <div id="current-account-gdp-ratio">
        <JapanCurrentAccountGdpRatioChart data={dashboardData?.current_account_gdp_ratio ?? null} />
      </div>

      {/* 貿易収支 */}
      <div id="balance-of-trade">
        <JapanBalanceOfTradeChart data={dashboardData?.balance_of_trade ?? null} />
      </div>
    </div>
  )
}

/**
 * スケルトンローダー
 * データ取得中に表示される骨組み
 */
export function EconomyChartsSkeleton() {
  return (
    <div className="country-chart-stack">
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: 400,
          background: '#fafafa',
          borderRadius: 12,
        }}
      >
        <Spin size="large" />
        <div style={{ marginTop: 16, color: '#666' }}>経済指標データを読み込み中...</div>
      </div>
    </div>
  )
}
