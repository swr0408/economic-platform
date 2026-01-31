import { Spin, Alert, Button } from 'antd'
import { useSwitzerlandPolicyDashboard } from '../../../hooks/useDashboardData'
import ChSnbRateChart from './monetary_policy/ChSnbRateChart'
import ChInflationForecastChart from './monetary_policy/ChInflationForecastChart'
import ChCPIChart from './inflation/ChCPIChart'
import SNBBalanceSheetChart from './monetary_policy/SNBBalanceSheetChart'

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
