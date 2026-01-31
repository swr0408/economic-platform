import { Spin, Alert, Button } from 'antd'
import { useSwitzerlandConsumerDashboard } from '../../../hooks/useDashboardData'
import KofBarometerChart from './consumer/KofBarometerChart'
import CHConsumerSentimentChart from './consumer/CHConsumerSentimentChart'

/**
 * スイス消費者チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function SwitzerlandConsumerCharts() {
  const { data, isLoading, error, refetch } = useSwitzerlandConsumerDashboard()

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
      {/* KOF Economic Barometer Chart */}
      <div id="kof-barometer">
        <KofBarometerChart
          data={dashboardData?.kof_economic_barometer ?? null}
        />
      </div>

      {/* SECO Consumer Sentiment Chart */}
      <div id="ch-consumer-sentiment">
        <CHConsumerSentimentChart
          data={dashboardData?.ch_consumer_sentiment ?? null}
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
