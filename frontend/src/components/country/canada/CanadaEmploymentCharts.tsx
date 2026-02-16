import { Spin, Alert, Button } from 'antd'
import { useCanadaEmploymentDashboard } from '../../../hooks/useDashboardData'
import CaEmploymentChart from './employment/CaEmploymentChart'
import CaFulltimeParttimeChart from './employment/CaFulltimeParttimeChart'
import CaUnemploymentRateChart from './employment/CaUnemploymentRateChart'
import CaLaborForceParticipationRateChart from './employment/CaLaborForceParticipationRateChart'
import CaAverageHourlyWageChart from './employment/CaAverageHourlyWageChart'
import CaWeeklyAverageSalaryChart from './employment/CaWeeklyAverageSalaryChart'
import CaJobVacancyRateChart from './employment/CaJobVacancyRateChart'

/**
 * カナダ雇用チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function CanadaEmploymentCharts() {
  const { data, isLoading, error, refetch } = useCanadaEmploymentDashboard()

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
      {/* 失業率チャート */}
      <div id="ca-unemployment-rate">
        <CaUnemploymentRateChart
          data={dashboardData?.ca_unemployment_rate ?? null}
        />
      </div>

      {/* 雇用者数チャート */}
      <div id="ca-employment">
        <CaEmploymentChart
          data={dashboardData?.ca_employment ?? null}
        />
      </div>

      {/* フルタイム・パートタイム雇用チャート */}
      <div id="ca-fulltime-parttime">
        <CaFulltimeParttimeChart
          data={dashboardData?.ca_employment ?? null}
        />
      </div>

      {/* 労働参加率チャート */}
      <div id="ca-labor-force-participation-rate">
        <CaLaborForceParticipationRateChart
          data={dashboardData?.ca_labor_force_participation_rate ?? null}
        />
      </div>

      {/* 平均時給チャート */}
      <div id="ca-average-hourly-wage">
        <CaAverageHourlyWageChart
          data={dashboardData?.ca_average_hourly_wage ?? null}
        />
      </div>

      {/* 週間平均給与チャート */}
      <div id="ca-weekly-average-salary">
        <CaWeeklyAverageSalaryChart
          data={dashboardData?.ca_weekly_average_salary ?? null}
        />
      </div>

      {/* 求人率チャート */}
      <div id="ca-job-vacancy-rate">
        <CaJobVacancyRateChart
          data={dashboardData?.ca_job_vacancy_rate ?? null}
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
