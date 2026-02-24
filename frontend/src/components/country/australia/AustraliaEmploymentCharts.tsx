import { Spin, Alert, Button } from 'antd'
import { useAustraliaEmploymentDashboard } from '../../../hooks/useDashboardData'
import AuEmployedPersonsChart from './employment/AuEmployedPersonsChart'
import AuFulltimeParttimeChart from './employment/AuFulltimeParttimeChart'
import AuUnemploymentRateChart from './employment/AuUnemploymentRateChart'
import AuParticipationRateChart from './employment/AuParticipationRateChart'
import AuWagePriceIndexChart from './employment/AuWagePriceIndexChart'
import AuJobVacanciesChart from './employment/AuJobVacanciesChart'
import AuAnzJobAdvertisementsChart from './employment/AuAnzJobAdvertisementsChart'
import AuUnderutilizationChart from './employment/AuUnderutilizationChart'

/**
 * オーストラリア雇用チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function AustraliaEmploymentCharts() {
  const { data, isLoading, error, refetch } = useAustraliaEmploymentDashboard()

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
      {/* AU Employed Persons */}
      <div id="employment-change">
        <AuEmployedPersonsChart
          data={dashboardData?.au_employed_persons ?? null}
        />
      </div>

      {/* AU Full-time/Part-time */}
      <div id="fulltime-parttime">
        <AuFulltimeParttimeChart
          data={dashboardData?.au_fulltime_parttime ?? null}
        />
      </div>

      {/* AU Unemployment Rate */}
      <div id="unemployment">
        <AuUnemploymentRateChart
          data={dashboardData?.au_unemployment_rate ?? null}
        />
      </div>

      {/* AU Participation Rate */}
      <div id="participation-rate">
        <AuParticipationRateChart
          data={dashboardData?.au_participation_rate ?? null}
        />
      </div>

      {/* AU Wage Price Index */}
      <div id="wage-price-index">
        <AuWagePriceIndexChart
          data={dashboardData?.au_wage_price_index ?? null}
        />
      </div>

      {/* AU Job Vacancies */}
      <div id="job-vacancies">
        <AuJobVacanciesChart
          data={dashboardData?.au_job_vacancies ?? null}
        />
      </div>

      {/* AU ANZ Job Advertisements */}
      <div id="anz-job-advertisements">
        <AuAnzJobAdvertisementsChart
          data={dashboardData?.au_anz_job_advertisements ?? null}
        />
      </div>

      {/* AU Underutilization */}
      <div id="underutilization">
        <AuUnderutilizationChart
          data={dashboardData?.au_underutilization ?? null}
        />
      </div>
    </div>
  )
}

/**
 * スケルトンローダー
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
