import { Spin, Alert, Button } from 'antd'
import { useSwitzerlandInflationDashboard } from '../../../hooks/useDashboardData'
import ChCPIChart from './inflation/ChCPIChart'
import ChPPIChart from './inflation/ChPPIChart'

/**
 * スイス物価チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function SwitzerlandInflationCharts() {
  const { data, isLoading, error, refetch } = useSwitzerlandInflationDashboard()

  // ローディング状態
  if (isLoading) {
    return <InflationChartsSkeleton />
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
      {/* CPI Chart */}
      <div id="cpi">
        <ChCPIChart
          data={dashboardData?.ch_cpi ?? null}
        />
      </div>

      {/* PPI Chart */}
      <div id="ppi">
        <ChPPIChart
          data={dashboardData?.ch_ppi ?? null}
        />
      </div>
    </div>
  )
}

/**
 * スケルトンローダー
 * データ取得中に表示される骨組み
 */
function InflationChartsSkeleton() {
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
        <div style={{ marginTop: 16, color: '#666' }}>物価データを読み込み中...</div>
      </div>
    </div>
  )
}
