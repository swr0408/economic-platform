import { Spin, Alert, Button } from 'antd'
import { useCanadaHousingDashboard } from '../../../hooks/useDashboardData'
import CanadaHousingStartsChart from './housing/CanadaHousingStartsChart'
import CanadaBuildingPermitsChart from './housing/CanadaBuildingPermitsChart'
import CanadaNewHousingPriceIndexChart from './housing/CanadaNewHousingPriceIndexChart'
import CanadaDebtServiceRatioChart from './housing/CanadaDebtServiceRatioChart'

/**
 * カナダ住宅チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function CanadaHousingCharts() {
  const { data, isLoading, error, refetch } = useCanadaHousingDashboard()

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
      {/* Housing Starts Chart */}
      <div id="housing-starts">
        <CanadaHousingStartsChart
          data={dashboardData?.ca_housing_starts ?? null}
        />
      </div>

      {/* Building Permits Chart */}
      <div id="building-permits">
        <CanadaBuildingPermitsChart
          data={dashboardData?.ca_building_permits ?? null}
        />
      </div>

      {/* New Housing Price Index Chart */}
      <div id="new-housing-price-index">
        <CanadaNewHousingPriceIndexChart
          data={dashboardData?.ca_new_housing_price_index ?? null}
        />
      </div>

      {/* Debt Service Ratio Chart */}
      <div id="debt-service-ratio">
        <CanadaDebtServiceRatioChart
          data={dashboardData?.ca_debt_service_ratio ?? null}
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
