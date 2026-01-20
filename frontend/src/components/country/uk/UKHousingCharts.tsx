import { Spin, Alert, Button } from 'antd'
import { useUKHousingDashboard } from '../../../hooks/useDashboardData'
import UKHousePriceChart from './housing/UKHousePriceChart'
import RICSHousePriceChart from './housing/RICSHousePriceChart'

/**
 * イギリス住宅チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function UKHousingCharts() {
  const { data, isLoading, error, refetch } = useUKHousingDashboard()

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
      {/* UK House Price Index Chart */}
      <div id="uk-house-price">
        <UKHousePriceChart
          data={dashboardData?.uk_house_price ?? null}
        />
      </div>

      {/* RICS House Price Balance Chart */}
      <div id="rics-house-price">
        <RICSHousePriceChart
          data={dashboardData?.rics_house_price ?? null}
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
