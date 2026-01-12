import { Spin, Alert, Button } from 'antd'
import { useEurozoneConsumerDashboard } from '../../../hooks/useDashboardData'
import ECBRetailTradeChart from './consumer/ECBRetailTradeChart'
import EurostatConsumerConfidenceChart from './consumer/EurostatConsumerConfidenceChart'

/**
 * ユーロ圏消費チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function EurozoneConsumerCharts() {
  const { data, isLoading, error, refetch } = useEurozoneConsumerDashboard()

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
      {/* Eurostat Consumer Confidence Chart */}

      {/* ECB Retail Trade Chart */}
      <div id="ecb-retail-trade">
        <ECBRetailTradeChart
          data={dashboardData?.ecb_retail_trade ?? null}
        />
        
      </div>
      <div id="eurostat-consumer-confidence">
        <EurostatConsumerConfidenceChart
          data={dashboardData?.eurostat_consumer_confidence ?? null}
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
