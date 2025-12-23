import { Spin, Alert, Button } from 'antd'
import { useUSAConsumerDashboard } from '../../../hooks/useDashboardData'
import RetailSalesChart from './consumer/RetailSalesChart'

/**
 * 米国消費チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function USAConsumerCharts() {
  const { data, isLoading, error, refetch } = useUSAConsumerDashboard()

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

      {/* 小売売上高チャート */}
      <div id="retail-sales">
        <RetailSalesChart
          data={dashboardData?.retail_sales ?? null}
          controlData={dashboardData?.retail_control ?? null}
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
        <div style={{ marginTop: 16, color: '#666' }}>消費データを読み込み中...</div>
      </div>
    </div>
  )
}
