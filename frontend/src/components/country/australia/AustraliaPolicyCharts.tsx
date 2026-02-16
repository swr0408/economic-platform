import { Spin, Alert, Button } from 'antd'
import { useAustraliaPolicyDashboard } from '../../../hooks/useDashboardData'
import RbaInterestRateChart from './monetary_policy/RbaInterestRateChart'
import AsxRateTrackerChart from './monetary_policy/AsxRateTrackerChart'
import RbaOisChart from './monetary_policy/RbaOisChart'
import RbaExpectationsChart from './monetary_policy/RbaExpectationsChart'
import RbaMonetaryPolicyChart from './monetary_policy/RbaMonetaryPolicyChart'

/**
 * オーストラリア金融政策チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function AustraliaPolicyCharts() {
  const { data, isLoading, error, refetch } = useAustraliaPolicyDashboard()

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
      {/* RBA Policy Rate Chart */}
      <div id="policy-rate">
        <RbaInterestRateChart
          data={dashboardData?.au_rba_rate ?? null}
        />
      </div>

      {/* ASX RBA Rate Tracker */}
      <div id="asx-rate-tracker">
        <AsxRateTrackerChart
          data={dashboardData?.au_asx_rate_tracker ?? null}
        />
      </div>

      {/* RBA SMP 経済予測 */}
      <div id="rba-monetary-policy">
        <RbaMonetaryPolicyChart
          data={dashboardData?.au_monetary_policy ?? null}
        />
      </div>

      {/* RBA OIS */}
      <div id="rba-ois">
        <RbaOisChart />
      </div>

      {/* RBA 利上げ・利下げ期待 */}
      <div id="rba-expectations">
        <RbaExpectationsChart />
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
