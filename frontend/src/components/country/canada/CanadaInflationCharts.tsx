import { Spin, Alert, Button } from 'antd'
import { useCanadaInflationDashboard } from '../../../hooks/useDashboardData'
import CaCpiChart from './inflation/CaCpiChart'
import CaIppiChart from './inflation/CaIppiChart'
import CaInflationExpectationsChart from './inflation/CaInflationExpectationsChart'
import CaCpiServiceRentChart from './inflation/CaCpiServiceRentChart'

/**
 * カナダ物価チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function CanadaInflationCharts() {
  const { data, isLoading, error, refetch } = useCanadaInflationDashboard()

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
      {/* CPI Chart */}
      <div id="ca-cpi">
        <CaCpiChart
          data={dashboardData?.ca_cpi ?? null}
        />
      </div>

      {/* CPI Service / Rent Chart */}
      <div id="ca-cpi-service-rent">
        <CaCpiServiceRentChart
          data={dashboardData?.ca_cpi_service_rent ?? null}
        />
      </div>

      {/* IPPI Chart */}
      <div id="ca-ippi">
        <CaIppiChart
          data={dashboardData?.ca_ippi ?? null}
        />
      </div>

      {/* Inflation Expectations Chart */}
      <div id="ca-inflation-expectations">
        <CaInflationExpectationsChart
          data={dashboardData?.ca_inflation_expectations ?? null}
        />
      </div>
    </div>
  )
}

/**
 * スケルトンローダー
 * データ取得中に表示される骨組み
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
