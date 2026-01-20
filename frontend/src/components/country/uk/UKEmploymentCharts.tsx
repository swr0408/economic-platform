import { Spin, Alert, Button } from 'antd'
import { useUKEmploymentDashboard } from '../../../hooks/useDashboardData'
import ONSUnemploymentChart from './employment/ONSUnemploymentChart'
import ONSClaimantCountChart from './employment/ONSClaimantCountChart'
import ONSEmploymentChart from './employment/ONSEmploymentChart'
import ONSWagesChart from './employment/ONSWagesChart'
import ONSRealWagesChart from './employment/ONSRealWagesChart'
import ONSEconomicActivityChart from './employment/ONSEconomicActivityChart'
import ONSProductivityChart from './employment/ONSProductivityChart'
import ONSUnitLabourCostsChart from './employment/ONSUnitLabourCostsChart'
import IndeedWageTrackerChart from './employment/IndeedWageTrackerChart'

/**
 * イギリス雇用チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function UKEmploymentCharts() {
  const { data, isLoading, error, refetch } = useUKEmploymentDashboard()

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
      {/* ONS Unemployment Rate Chart */}
      <div id="uk-unemployment">
        <ONSUnemploymentChart
          data={dashboardData?.ons_unemployment ?? null}
        />
      </div>

      {/* ONS Claimant Count Chart */}
      <div id="uk-claimant-count">
        <ONSClaimantCountChart
          data={dashboardData?.ons_claimant_count ?? null}
        />
      </div>

      {/* ONS Wages Chart */}
      <div id="uk-wages">
        <ONSWagesChart
          data={dashboardData?.ons_wages ?? null}
        />
      </div>

      {/* ONS Real Wages Chart */}
      <div id="uk-real-wages">
        <ONSRealWagesChart
          data={dashboardData?.ons_real_wages ?? null}
        />
      </div>

      {/* ONS Employment Chart */}
      <div id="uk-employment">
        <ONSEmploymentChart
          data={dashboardData?.ons_employment ?? null}
        />
      </div>

      {/* ONS Economic Activity Chart */}
      <div id="uk-economic-activity">
        <ONSEconomicActivityChart
          data={dashboardData?.ons_economic_activity ?? null}
        />
      </div>

      {/* ONS Productivity Chart */}
      <div id="uk-productivity">
        <ONSProductivityChart
          data={dashboardData?.ons_productivity ?? null}
        />
      </div>

      {/* ONS Unit Labour Costs Chart */}
      <div id="uk-unit-labour-costs">
        <ONSUnitLabourCostsChart
          data={dashboardData?.ons_unit_labour_costs ?? null}
        />
      </div>

      {/* Indeed Wage Tracker Chart */}
      <div id="uk-indeed-wage-tracker">
        <IndeedWageTrackerChart
          data={dashboardData?.indeed_wage_tracker ?? null}
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
