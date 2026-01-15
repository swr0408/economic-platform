import { Spin, Alert, Button } from 'antd'
import { useEurozoneEmploymentDashboard } from '../../../hooks/useDashboardData'
import ECBUnemploymentChart from './employment/ECBUnemploymentChart'
import ECBEmploymentChart from './employment/ECBEmploymentChart'
import ECBLaborProductivityChart from './employment/ECBLaborProductivityChart'
import ECBUnitLabourCostChart from './employment/ECBUnitLabourCostChart'
import EurostatWagesChart from './employment/EurostatWagesChart'
import ECBNegotiatedWagesChart from './employment/ECBNegotiatedWagesChart'
import IndeedEuroWageChart from './employment/IndeedEuroWageChart'
import GermanyUnemploymentChart from './employment/GermanyUnemploymentChart'

/**
 * ユーロ圏雇用チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function EurozoneEmploymentCharts() {
  const { data, isLoading, error, refetch } = useEurozoneEmploymentDashboard()

  if (error) {
    return (
      <Alert
        message="データ読み込みエラー"
        description={
          <div>
            <p>雇用データの取得に失敗しました。</p>
            <Button onClick={() => refetch()} style={{ marginTop: 8 }}>
              再試行
            </Button>
          </div>
        }
        type="error"
        showIcon
      />
    )
  }

  if (isLoading || !data) {
    return <SkeletonLoader />
  }

  const dashboardData = data?.data

  return (
    <div className="country-chart-stack">
      {/* ECB Unemployment Chart */}
      <div id="ecb-unemployment">
        <ECBUnemploymentChart
          data={dashboardData?.ecb_unemployment ?? null}
        />
      </div>

      {/* ECB Employment Chart */}
      <div id="ecb-employment">
        <ECBEmploymentChart
          data={dashboardData?.ecb_employment ?? null}
        />
      </div>

      {/* ECB Labor Productivity Chart */}
      <div id="ecb-labor-productivity">
        <ECBLaborProductivityChart
          data={dashboardData?.ecb_labor_productivity ?? null}
        />
      </div>

      {/* ECB Unit Labour Cost Chart */}
      <div id="ecb-unit-labour-cost">
        <ECBUnitLabourCostChart
          data={dashboardData?.ecb_unit_labour_cost ?? null}
        />
      </div>

      {/* Eurostat Wages Chart */}
      <div id="eurostat-wages">
        <EurostatWagesChart
          data={dashboardData?.eurostat_wages ?? null}
        />
      </div>

      {/* ECB Negotiated Wages Chart */}
      <div id="ecb-negotiated-wages">
        <ECBNegotiatedWagesChart
          data={dashboardData?.ecb_negotiated_wages ?? null}
        />
      </div>

      {/* Indeed Euro Wage Chart */}
      <div id="indeed-euro-wage">
        <IndeedEuroWageChart
          data={dashboardData?.indeed_euro_wage ?? null}
        />
      </div>

      {/* Germany Unemployment Chart */}
      <div id="germany-unemployment">
        <GermanyUnemploymentChart
          data={dashboardData?.germany_unemployment ?? null}
        />
      </div>
    </div>
  )
}

/**
 * スケルトンローダー
 * データ取得中に表示される骨組み
 */
function SkeletonLoader() {
  return (
    <div className="country-chart-stack">
      <div
        style={{
          height: 300,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'rgba(0, 0, 0, 0.02)',
          borderRadius: 12,
        }}
      >
        <Spin size="large" />
        <div style={{ marginTop: 16, color: '#666' }}>雇用データを読み込み中...</div>
      </div>
    </div>
  )
}
