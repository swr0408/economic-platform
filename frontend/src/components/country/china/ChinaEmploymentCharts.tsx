import { Spin, Alert, Button } from 'antd'
import { useChinaEmploymentDashboard } from '../../../hooks/useDashboardData'
import CnUnemploymentRateChart from './employment/CnUnemploymentRateChart'

/**
 * 中国雇用チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function ChinaEmploymentCharts() {
  const { data, isLoading, error, refetch } = useChinaEmploymentDashboard()

  if (isLoading) {
    return <EmploymentChartsSkeleton />
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
      {/* 失業率 */}
      <CnUnemploymentRateChart
        data={dashboardData?.cn_unemployment_rate ?? null}
      />
    </div>
  )
}

function EmploymentChartsSkeleton() {
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
        <div style={{ marginTop: 16, color: '#666' }}>雇用データを読み込み中...</div>
      </div>
    </div>
  )
}
