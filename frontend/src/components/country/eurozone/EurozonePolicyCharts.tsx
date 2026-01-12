import { Spin, Alert, Button } from 'antd'
import { useEurozonePolicyDashboard } from '../../../hooks/useDashboardData'
import ECBRatesChart from './monetary_policy/ECBRatesChart'
import EurexOISChart from './monetary_policy/EurexOISChart'
import ECBRateCutsExpectationChart from './monetary_policy/ECBRateCutsExpectationChart'
import ECBMacroProjectionsChart from './monetary_policy/ECBMacroProjectionsChart'

/**
 * ユーロ圏金融政策チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function EurozonePolicyCharts() {
  const { data, isLoading, error, refetch } = useEurozonePolicyDashboard()

  // ローディング状態
  if (isLoading) {
    return <PolicyChartsSkeleton />
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
      {/* ECB Rates Chart */}
      <div id="ecb-rates">
        <ECBRatesChart
          data={dashboardData?.ecb_rates ?? null}
        />
      </div>

      {/* Eurex OIS Chart */}
      <div id="eurex-ois">
        <EurexOISChart
          data={dashboardData?.eurex_ois ?? null}
        />
      </div>

      {/* ECB Rate Cuts Expectation Chart */}
      <div id="ecb-rate-cuts">
        <ECBRateCutsExpectationChart />
      </div>

      {/* ECB Macro Projections Chart */}
      <div id="ecb-macro-projections">
        <ECBMacroProjectionsChart
          data={dashboardData?.ecb_macro_projections ?? null}
        />
      </div>
    </div>
  )
}

/**
 * スケルトンローダー
 * データ取得中に表示される骨組み
 */
function PolicyChartsSkeleton() {
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
        <div style={{ marginTop: 16, color: '#666' }}>金融政策データを読み込み中...</div>
      </div>
    </div>
  )
}
