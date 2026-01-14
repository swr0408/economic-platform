import { Spin, Alert, Button } from 'antd'
import { useJapanConsumerDashboard } from '../../../hooks/useDashboardData'
import ConsumerSentimentChart from './consumer/ConsumerSentimentChart'
import BOJCAIChart from './consumer/BOJCAIChart'
import EconomyWatcherChart from './consumer/EconomyWatcherChart'
import ConsumptionExpenditureChart from './consumer/ConsumptionExpenditureChart'
import RetailSalesChart from './consumer/RetailSalesChart'

/**
 * 日本消費チャート群
 *
 * バッチAPIで消費支出データを一括取得し、各チャートコンポーネントにpropsで渡す
 * その他の指標は個別APIで取得
 */
export default function JapanConsumerCharts() {
  const { data, isLoading, error, refetch } = useJapanConsumerDashboard()

  // エラー状態（ダッシュボードAPI全体のエラー）
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

      {/* 消費動向調査（消費者態度指数） */}
      <div id="consumer-sentiment">
        <ConsumerSentimentChart />
      </div>

      {/* 消費活動指数（旅行収支調整前） */}
      <div id="boj-cai">
        <BOJCAIChart />
      </div>

      {/* 景気ウォッチャー調査（現状判断DI・先行き判断DI タブ切り替え） */}
      <div id="economy-watcher">
        <EconomyWatcherChart />
      </div>
      
      {/* 実質消費支出（家計調査） */}
      <div id="consumption-expenditure">
        <ConsumptionExpenditureChart
          data={isLoading ? null : (dashboardData?.consumption_expenditure ?? null)}
        />
      </div>

      {/* 小売業販売額（商業動態統計） */}
      <div id="retail-sales">
        <RetailSalesChart
          data={isLoading ? null : (dashboardData?.retail_sales ?? null)}
        />
      </div>
    </div>
  )
}

/**
 * スケルトンローダー
 * データ取得中に表示される骨組み
 */
export function ConsumerChartsSkeleton() {
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
        <div style={{ marginTop: 16, color: '#666' }}>消費指標データを読み込み中...</div>
      </div>
    </div>
  )
}
