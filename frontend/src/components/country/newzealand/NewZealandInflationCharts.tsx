import { Spin, Alert, Button } from 'antd'
import { useNewZealandInflationDashboard } from '../../../hooks/useDashboardData'
import NzCpiChart from './inflation/NzCpiChart'
import NzCpiItemChart from './inflation/NzCpiItemChart'
import NzPpiChart from './inflation/NzPpiChart'
import NzInflationExpectationsChart from './inflation/NzInflationExpectationsChart'
import NzAnzBusinessSentimentPriceChart from './inflation/NzAnzBusinessSentimentPriceChart'

/**
 * ニュージーランド物価チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function NewZealandInflationCharts() {
  const { data, isLoading, error, refetch } = useNewZealandInflationDashboard()

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
      {/* CPI */}
      <NzCpiChart
        data={dashboardData?.nz_cpi ?? null}
      />

      {/* CPI 項目別 */}
      <NzCpiItemChart
        data={dashboardData?.nz_cpi_item ?? null}
      />

      {/* PPI */}
      <NzPpiChart
        data={dashboardData?.nz_ppi ?? null}
      />

      {/* インフレ期待 */}
      <NzInflationExpectationsChart
        data={dashboardData?.nz_inflation_expectations ?? null}
      />

      {/* ANZ企業景況感物価関連 */}
      <NzAnzBusinessSentimentPriceChart
        data={dashboardData?.nz_anz_business_outlook_price ?? null}
      />
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
