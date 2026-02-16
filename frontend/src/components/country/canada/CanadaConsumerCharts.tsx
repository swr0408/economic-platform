import { Spin, Alert, Button } from 'antd'
import { useCanadaConsumerDashboard } from '../../../hooks/useDashboardData'
import CanadaRetailSalesChart from './consumer/CanadaRetailSalesChart'

/**
 * カナダ消費者チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function CanadaConsumerCharts() {
  const { data, isLoading, error, refetch } = useCanadaConsumerDashboard()

  // ローディング状態
  if (isLoading) {
    return <ConsumerChartsSkeleton />
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
      {/* Retail Sales Chart */}
      <div id="retail-sales">
        <CanadaRetailSalesChart
          data={dashboardData?.ca_retail_sales ?? null}
        />
      </div>
    </div>
  )
}

/**
 * スケルトンローダー
 * データ取得中に表示される骨組み
 */
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
        <div style={{ marginTop: 16, color: '#666' }}>消費者データを読み込み中...</div>
      </div>
    </div>
  )
}
