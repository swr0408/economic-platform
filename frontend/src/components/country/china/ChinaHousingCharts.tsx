import { Spin, Alert, Button } from 'antd'
import { useChinaHousingDashboard } from '../../../hooks/useDashboardData'
import CnCommercialResidentialSalesChart from './housing/CnCommercialResidentialSalesChart'
import CnHousePriceIndexChart from './housing/CnHousePriceIndexChart'

/**
 * 中国住宅チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function ChinaHousingCharts() {
  const { data, isLoading, error, refetch } = useChinaHousingDashboard()

  if (isLoading) {
    return <HousingChartsSkeleton />
  }

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
      {/* 住宅価格指数 */}
      <CnHousePriceIndexChart
        data={dashboardData?.cn_house_price_index ?? null}
      />
      {/* 商業住宅販売 */}
      <CnCommercialResidentialSalesChart
        data={dashboardData?.cn_commercial_residential_sales ?? null}
      />
    </div>
  )
}

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
