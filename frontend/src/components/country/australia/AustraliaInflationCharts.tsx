import { Spin, Alert, Button } from 'antd'
import { useAustraliaInflationDashboard } from '../../../hooks/useDashboardData'
import AuMonthlyCpiChart from './inflation/AuMonthlyCpiChart'
import AuCpiCategoriesChart from './inflation/AuCpiCategoriesChart'
import AuQuarterlyCpiChart from './inflation/AuQuarterlyCpiChart'
import AuQuarterlyPpiChart from './inflation/AuQuarterlyPpiChart'
import AuInflationExpectationsChart from './inflation/AuInflationExpectationsChart'
import AuNabBusinessConfidenceIndexCostPriceChart from './inflation/AuNabBusinessConfidenceIndexCostPriceChart'

/**
 * オーストラリア物価チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function AustraliaInflationCharts() {
  const { data, isLoading, error, refetch } = useAustraliaInflationDashboard()

  // ローディング状態
  if (isLoading) {
    return <InflationChartsSkeleton />
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
      {/* AU Monthly CPI */}
      <div id="cpi">
        <AuMonthlyCpiChart
          data={dashboardData?.au_monthly_cpi ?? null}
        />
      </div>

      {/* AU CPI Categories */}
      <div id="cpi-categories">
        <AuCpiCategoriesChart
          data={dashboardData?.au_cpi_categories ?? null}
        />
      </div>

      {/* AU Quarterly CPI */}
      <div id="quarterly-cpi">
        <AuQuarterlyCpiChart
          data={dashboardData?.au_quarterly_cpi ?? null}
        />
      </div>

      {/* AU Quarterly PPI */}
      <div id="ppi">
        <AuQuarterlyPpiChart
          data={dashboardData?.au_quarterly_ppi ?? null}
        />
      </div>

      {/* AU Inflation Expectations */}
      <div id="inflation-expectations">
        <AuInflationExpectationsChart
          data={dashboardData?.au_inflation_expectations ?? null}
        />
      </div>

      {/* NAB企業調査（コスト・価格） */}
      <div id="nab-cost-price">
        <AuNabBusinessConfidenceIndexCostPriceChart
          data={dashboardData?.au_nab_cost_price ?? null}
        />
      </div>
    </div>
  )
}

/**
 * スケルトンローダー
 */
function InflationChartsSkeleton() {
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
        <div style={{ marginTop: 16, color: '#666' }}>物価データを読み込み中...</div>
      </div>
    </div>
  )
}
