import { Spin, Alert, Button } from 'antd'
import { useChinaConsumerDashboard } from '../../../hooks/useDashboardData'
import CnRetailSalesChart from './consumer/CnRetailSalesChart'

/**
 * 中国消費チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function ChinaConsumerCharts() {
  const { data, isLoading, error, refetch } = useChinaConsumerDashboard()

  if (isLoading) {
    return <ConsumerChartsSkeleton />
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
      <CnRetailSalesChart
        data={dashboardData?.cn_retail_sales ?? null}
      />
    </div>
  )
}

function ConsumerChartsSkeleton() {
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
        <div style={{ marginTop: 16, color: '#666' }}>消費データを読み込み中...</div>
      </div>
    </div>
  )
}
