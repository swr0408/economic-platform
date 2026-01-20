import { Spin, Alert, Button } from 'antd'
import { useUKConsumerDashboard } from '../../../hooks/useDashboardData'
import ONSRetailSalesChart from './consumer/ONSRetailSalesChart'
import BRCRetailSalesChart from './consumer/BRCRetailSalesChart'
import GfKConsumerConfidenceChart from './consumer/GfKConsumerConfidenceChart'

/**
 * イギリス消費チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function UKConsumerCharts() {
  const { data, isLoading, error, refetch } = useUKConsumerDashboard()

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
      {/* ONS Retail Sales Chart */}
      <div id="uk-retail-sales">
        <ONSRetailSalesChart
          data={dashboardData?.ons_retail_sales ?? null}
        />
      </div>

      {/* BRC Retail Sales Chart */}
      <div id="uk-brc-retail-sales">
        <BRCRetailSalesChart
          data={dashboardData?.brc_retail_sales ?? null}
        />
      </div>

      {/* GfK Consumer Confidence Chart */}
      <div id="uk-gfk-consumer-confidence">
        <GfKConsumerConfidenceChart
          data={dashboardData?.gfk_consumer_confidence ?? null}
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
