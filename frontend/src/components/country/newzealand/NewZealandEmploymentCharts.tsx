import { Spin, Alert, Button } from 'antd'
import { useNewZealandEmploymentDashboard } from '../../../hooks/useDashboardData'
import NzNumberOfEmployeesChart from './employment/NzNumberOfEmployeesChart'
import NzUnemploymentRateChart from './employment/NzUnemploymentRateChart'
import NzWagesChart from './employment/NzWagesChart'
import NzLabourForceParticipationChart from './employment/NzLabourForceParticipationChart'
import NzLaborCostIndexChart from './employment/NzLaborCostIndexChart'

/**
 * ニュージーランド雇用チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function NewZealandEmploymentCharts() {
  const { data, isLoading, error, refetch } = useNewZealandEmploymentDashboard()

  // ローディング状態
  if (isLoading) {
    return <EmploymentChartsSkeleton />
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
      {/* 失業率 */}
      <NzUnemploymentRateChart
        data={dashboardData?.nz_unemployment_rate ?? null}
      />
      {/* 雇用者数 */}
      <NzNumberOfEmployeesChart
        data={dashboardData?.nz_number_of_employees ?? null}
      />
      {/* 労働コスト指数 */}
      <NzLaborCostIndexChart
        data={dashboardData?.nz_labor_cost_index ?? null}
      />
      {/* 賃金 */}
      <NzWagesChart
        data={dashboardData?.nz_wages ?? null}
      />
      {/* 労働参加率 */}
      <NzLabourForceParticipationChart
        data={dashboardData?.nz_labour_force_participation ?? null}
      />
    </div>
  )
}

/**
 * スケルトンローダー
 * データ取得中に表示される骨組み
 */
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
