import { Spin, Alert, Button } from 'antd'
import { useJapanPolicyDashboard } from '../../../hooks/useDashboardData'
import BOJPolicyRateChart from './monetary_policy/BOJPolicyRateChart'
import OISCurveChart from './monetary_policy/OISCurveChart'
import BOJMeetingExpectationsTable from './monetary_policy/BOJMeetingExpectationsTable'
import BOJOutlookReport from './monetary_policy/BOJOutlookReport'
import BEIChart from './monetary_policy/BEIChart'

/**
 * 日本金融政策チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function JapanPolicyCharts() {
  const { data, isLoading, error, refetch } = useJapanPolicyDashboard()

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
      {/* BOJ Policy Rate Chart */}
      <div id="boj-policy-rate">
        <BOJPolicyRateChart
          data={dashboardData?.boj_policy_rate ?? null}
        />
      </div>

      {/* JSCC OIS Curve Chart */}
      <div id="ois-curve">
        <OISCurveChart />
      </div>

      {/* BOJ Meeting Expectations Table */}
      <div id="boj-meeting-expectations">
        <BOJMeetingExpectationsTable />
      </div>

      {/* BOJ Outlook Report */}
      <div id="boj-outlook">
        <BOJOutlookReport />
      </div>

      {/* 10年物価連動国債BEI */}
      <div id="bei">
        <BEIChart />
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
