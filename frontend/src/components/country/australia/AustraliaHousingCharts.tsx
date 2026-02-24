import { Spin, Alert, Button } from 'antd'
import { useAustraliaHousingDashboard } from '../../../hooks/useDashboardData'
import AuCotalityHomePricesChart from './housing/AuCotalityHomePricesChart'
import AuNumberOfBuildingPermitsChart from './housing/AuNumberOfBuildingPermitsChart'

/**
 * オーストラリア住宅チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function AustraliaHousingCharts() {
  const { data, isLoading, error, refetch } = useAustraliaHousingDashboard()

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
      {/* Cotality Home Prices */}
      <div id="cotality-home-prices">
        <AuCotalityHomePricesChart
          data={dashboardData?.au_cotality_home_prices ?? null}
        />
      </div>

      {/* Building Permits */}
      <div id="building-permits">
        <AuNumberOfBuildingPermitsChart
          data={dashboardData?.au_number_of_building_permits ?? null}
        />
      </div>
    </div>
  )
}

/**
 * スケルトンローダー
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
