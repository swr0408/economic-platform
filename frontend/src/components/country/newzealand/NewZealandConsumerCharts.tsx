import { Spin, Alert, Button } from 'antd'
import { useNewZealandConsumerDashboard } from '../../../hooks/useDashboardData'
import NzRetailSalesChart from './consumer/NzRetailSalesChart'
import NzAnzBusinessOutlookSurveyChart from './consumer/NzAnzBusinessOutlookSurveyChart'
import NzNzierBusinessConditionsIndexChart from './consumer/NzNzierBusinessConditionsIndexChart'

/**
 * ニュージーランド消費チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function NewZealandConsumerCharts() {
  const { data, isLoading, error, refetch } = useNewZealandConsumerDashboard()

  // ローディング状態
  if (isLoading) {
    return <ConsumerChartsSkeleton />
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
      {/* 小売売上高 */}
      <NzRetailSalesChart
        data={dashboardData?.nz_retail_sales ?? null}
      />
      
      {/* ANZ企業景況感指数 */}
      <NzAnzBusinessOutlookSurveyChart
        data={dashboardData?.nz_anz_business_outlook_survey ?? null}
      />

      {/* NZIER企業景況指数 */}
      <NzNzierBusinessConditionsIndexChart
        data={dashboardData?.nz_nzier_business_conditions_index ?? null}
      />

    </div>
  )
}

/**
 * スケルトンローダー
 * データ取得中に表示される骨組み
 */
function ConsumerChartsSkeleton() {
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
        <div style={{ marginTop: 16, color: '#666' }}>消費データを読み込み中...</div>
      </div>
    </div>
  )
}
