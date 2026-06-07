import { Spin, Alert, Button } from 'antd'
import { useChinaInflationDashboard } from '../../../hooks/useDashboardData'
import CnCpiChart from './inflation/CnCpiChart'
import CnPpiChart from './inflation/CnPpiChart'
import CnExportPricesChart from './inflation/CnExportPricesChart'

/**
 * 中国インフレーションチャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function ChinaInflationCharts() {
  const { data, isLoading, error, refetch } = useChinaInflationDashboard()

  if (isLoading) {
    return <InflationChartsSkeleton />
  }

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
      {/* CPI */}
      <CnCpiChart
        data={dashboardData?.cn_cpi ?? null}
      />
      {/* PPI */}
      <CnPpiChart
        data={dashboardData?.cn_ppi ?? null}
      />
      {/* 輸出物価指数 */}
      <CnExportPricesChart
        data={dashboardData?.cn_export_prices ?? null}
      />
    </div>
  )
}

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
