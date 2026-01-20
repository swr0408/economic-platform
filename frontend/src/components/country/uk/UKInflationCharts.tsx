import { Spin, Alert, Button } from 'antd'
import { useUKInflationDashboard } from '../../../hooks/useDashboardData'
import ONSCPIHChart from './inflation/ONSCPIHChart'
import ONSCPIComponentsChart from './inflation/ONSCPIComponentsChart'
import ONSPPIChart from './inflation/ONSPPIChart'
import BRCShopPriceChart from './inflation/BRCShopPriceChart'
import BOEInflationAttitudesChart from './inflation/BOEInflationAttitudesChart'

/**
 * イギリス物価チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function UKInflationCharts() {
  const { data, isLoading, error, refetch } = useUKInflationDashboard()

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
      {/* ONS CPI/CPIH Chart */}
      <div id="uk-cpih">
        <ONSCPIHChart
          data={dashboardData?.ons_cpih ?? null}
        />
      </div>

      {/* ONS CPI Components Chart */}
      <div id="uk-cpi-components">
        <ONSCPIComponentsChart
          data={dashboardData?.ons_cpih ?? null}
        />
      </div>

      {/* ONS PPI Chart */}
      <div id="uk-ppi">
        <ONSPPIChart
          data={dashboardData?.ons_ppi ?? null}
        />
      </div>

      {/* BRC Shop Price Index Chart */}
      <div id="uk-brc-shop-price">
        <BRCShopPriceChart
          data={dashboardData?.brc_shop_price ?? null}
        />
      </div>

      {/* BOE Inflation Attitudes Survey Chart */}
      <div id="uk-boe-inflation-attitudes">
        <BOEInflationAttitudesChart
          data={dashboardData?.boe_inflation_attitudes ?? null}
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
