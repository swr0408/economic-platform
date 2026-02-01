import { Spin, Alert, Button } from 'antd'
import { useSwitzerlandPolicyDashboard } from '../../../hooks/useDashboardData'
import ChSnbRateChart from './monetary_policy/ChSnbRateChart'
import ChInflationForecastChart from './monetary_policy/ChInflationForecastChart'
import ChCPIChart from './inflation/ChCPIChart'
import SNBBalanceSheetChart from './monetary_policy/SNBBalanceSheetChart'
import SNBSightDepositsChart from './monetary_policy/SNBSightDepositsChart'
import ForeignCurrencyReservesChart from './monetary_policy/ForeignCurrencyReservesChart'
import MonetaryBaseChart from './monetary_policy/MonetaryBaseChart'
import MonetaryAggregateM2Chart from './monetary_policy/MonetaryAggregateM2Chart'

/**
 * スイス金融政策チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function SwitzerlandPolicyCharts() {
  const { data, isLoading, error, refetch } = useSwitzerlandPolicyDashboard()

  // ローディング状態
  if (isLoading) {
    return <PolicyChartsSkeleton />
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
      {/* SNB Policy Rate Chart */}
      <div id="policy-rate">
        <ChSnbRateChart
          data={dashboardData?.ch_snb_rate ?? null}
        />
      </div>

      {/* SNB Inflation Forecast Chart */}
      <div id="inflation-forecast">
        <ChInflationForecastChart
          data={dashboardData?.ch_inflation_forecast ?? null}
        />
      </div>

      {/* SNB Balance Sheet Chart */}
      <div id="balance-sheet">
        <SNBBalanceSheetChart
          data={dashboardData?.snb_balance_sheet ?? null}
        />
      </div>

      {/* SNB Sight Deposits Chart */}
      <div id="sight-deposits">
        <SNBSightDepositsChart
          data={dashboardData?.snb_sight_deposits ?? null}
        />
      </div>

      {/* Foreign Currency Reserves Chart */}
      <div id="foreign-currency-reserves">
        <ForeignCurrencyReservesChart
          data={dashboardData?.foreign_currency_reserves ?? null}
        />
      </div>

      {/* Monetary Base Chart */}
      <div id="monetary-base">
        <MonetaryBaseChart
          data={dashboardData?.monetary_base ?? null}
        />
      </div>

      {/* Monetary Aggregate M2 Chart */}
      <div id="monetary-aggregate-m2">
        <MonetaryAggregateM2Chart
          data={dashboardData?.monetary_aggregate_m2 ?? null}
        />
      </div>
    </div>
  )
}

/**
 * スケルトンローダー
 * データ取得中に表示される骨組み
 */
function PolicyChartsSkeleton() {
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
        <div style={{ marginTop: 16, color: '#666' }}>金融政策データを読み込み中...</div>
      </div>
    </div>
  )
}
