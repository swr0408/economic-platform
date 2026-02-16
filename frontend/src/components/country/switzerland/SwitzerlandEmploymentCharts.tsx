import { Spin, Alert, Button } from 'antd'
import { useSwitzerlandEmploymentDashboard } from '../../../hooks/useDashboardData'
import CHUnemploymentRateChart from './employment/CHUnemploymentRateChart'
import ChJobVacanciesChart from './employment/ChJobVacanciesChart'
import ChNominalWageGrowthChart from './employment/ChNominalWageGrowthChart'

/**
 * スイス雇用チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function SwitzerlandEmploymentCharts() {
  const { data, isLoading, error, refetch } = useSwitzerlandEmploymentDashboard()

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
      {/* CH Unemployment Rate Chart */}
      <div id="ch-unemployment-rate">
        <CHUnemploymentRateChart
          data={dashboardData?.ch_unemployment_rate ?? null}
        />
      </div>

      {/* CH Job Vacancies Chart */}
      <div id="ch-job-vacancies">
        <ChJobVacanciesChart
          data={dashboardData?.ch_job_vacancies ?? null}
        />
      </div>

      {/* CH Nominal Wage Growth Chart */}
      <div id="ch-nominal-wage-growth">
        <ChNominalWageGrowthChart
          data={dashboardData?.ch_nominal_wage_growth ?? null}
        />
      </div>
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
