import { Spin, Alert, Button } from 'antd'
import { useSwitzerlandHousingDashboard } from '../../../hooks/useDashboardData'
import CHMortgageRatesChart from './housing/CHMortgageRatesChart'
import CHMortgageBalanceChart from './housing/CHMortgageBalanceChart'
import CHNewMortgageLoansChart from './housing/CHNewMortgageLoansChart'
import CHHousingPricesChart from './housing/CHHousingPricesChart'

/**
 * スイス住宅チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function SwitzerlandHousingCharts() {
  const { data, isLoading, error, refetch } = useSwitzerlandHousingDashboard()

  // ローディング状態
  if (isLoading) {
    return <HousingChartsSkeleton />
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
      {/* CH Mortgage Rates Chart */}
      <div id="ch-mortgage-rates">
        <CHMortgageRatesChart
          data={dashboardData?.ch_mortgage_rates ?? null}
        />
      </div>

      {/* CH Mortgage Balance Chart */}
      <div id="ch-mortgage-balance">
        <CHMortgageBalanceChart
          data={dashboardData?.ch_mortgage_balance ?? null}
        />
      </div>

      {/* CH New Mortgage Loans Chart */}
      <div id="ch-new-mortgage-loans">
        <CHNewMortgageLoansChart
          data={dashboardData?.ch_new_mortgage_loans ?? null}
        />
      </div>

      {/* CH Housing Prices Chart */}
      <div id="ch-housing-prices">
        <CHHousingPricesChart
          data={dashboardData?.ch_housing_prices ?? null}
        />
      </div>
    </div>
  )
}

/**
 * スケルトンローダー
 * データ取得中に表示される骨組み
 */
function HousingChartsSkeleton() {
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
        <div style={{ marginTop: 16, color: '#666' }}>住宅データを読み込み中...</div>
      </div>
    </div>
  )
}
