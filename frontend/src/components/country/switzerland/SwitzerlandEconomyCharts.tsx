import { Spin, Alert, Button } from 'antd'
import { useSwitzerlandEconomyDashboard } from '../../../hooks/useDashboardData'
import CHGrowthRateChart from './economy/CHGrowthRateChart'
import CHIndustrialProductionChart from './economy/CHIndustrialProductionChart'
import CHHouseholdsAndNpishChart from './economy/CHHouseholdsAndNpishChart'
import ChPmiChart from './economy/ChPmiChart'
import CHBalanceOfTradeChart from './economy/CHBalanceOfTradeChart'
import ChCurrentAccountChart from './economy/ChCurrentAccountChart'
import ChCurrentAccountGdpRatioChart from './economy/ChCurrentAccountGdpRatioChart'

/**
 * スイス経済チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function SwitzerlandEconomyCharts() {
  const { data, isLoading, error, refetch } = useSwitzerlandEconomyDashboard()

  // ローディング状態
  if (isLoading) {
    return <EconomyChartsSkeleton />
  }

  // エラー状態
  if (error) {
    return (
      <Alert
        type="error"
        message="データの取得に失敗しました"
        description={error.message}
        action={
          <Button size="small" onClick={() => refetch()}>
            再試行
          </Button>
        }
        style={{ marginBottom: 24 }}
      />
    )
  }

  const dashboardData = data?.data

  return (
    <div className="country-chart-stack">
      {/* GDP Growth Rate Chart */}
      <div id="ch-growth-rate">
        <CHGrowthRateChart
          data={dashboardData?.ch_growth_rate ?? null}
        />
      </div>

      {/* Households and NPISH Chart */}
      <div id="ch-households-and-npish">
        <CHHouseholdsAndNpishChart
          data={dashboardData?.ch_households_and_npish ?? null}
        />
      </div>

      {/* Industrial Production Chart */}
      <div id="ch-industrial-production">
        <CHIndustrialProductionChart
          data={dashboardData?.ch_industrial_production ?? null}
        />
      </div>

      {/* PMI Chart */}
      <div id="ch-pmi">
        <ChPmiChart
          data={dashboardData?.ch_pmi ?? null}
        />
      </div>

      {/* 貿易収支 */}
      <div id="ch-balance-of-trade">
        <CHBalanceOfTradeChart
          data={dashboardData?.ch_balance_of_trade ?? null}
        />
      </div>

      {/* 経常収支 */}
      <div id="ch-current-account">
        <ChCurrentAccountChart
          data={dashboardData?.ch_current_account ?? null}
        />
      </div>

      {/* 経常収支対GDP比 */}
      <div id="ch-current-account-gdp-ratio">
        <ChCurrentAccountGdpRatioChart
          data={dashboardData?.ch_current_account_gdp_ratio ?? null}
        />
      </div>
    </div>
  )
}

/**
 * スケルトンローダー
 * データ取得中に表示される骨組み
 */
function EconomyChartsSkeleton() {
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
        <div style={{ marginTop: 16, color: '#666' }}>経済データを読み込み中...</div>
      </div>
    </div>
  )
}
