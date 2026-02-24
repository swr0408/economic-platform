import { Spin, Alert, Button } from 'antd'
import { useAustraliaConsumerDashboard } from '../../../hooks/useDashboardData'
import AuHouseholdSpendingChart from './consumer/AuHouseholdSpendingChart'
import AuWestpacConsumerConfidenceChart from './consumer/AuWestpacConsumerConfidenceChart'
import AuNabConfidenceIndexChart from './consumer/AuNabConfidenceIndexChart'
import AuConsumerSpendingChart from './consumer/AuConsumerSpendingChart'
import AuHouseholdSavingRatioChart from './consumer/AuHouseholdSavingRatioChart'
import AuDisposablePersonalIncomeChart from './consumer/AuDisposablePersonalIncomeChart'

/**
 * オーストラリア消費チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function AustraliaConsumerCharts() {
  const { data, isLoading, error, refetch } = useAustraliaConsumerDashboard()

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
      {/* AU Household Spending */}
      <div id="household-spending">
        <AuHouseholdSpendingChart
          data={dashboardData?.au_household_spending ?? null}
        />
      </div>

      {/* AU Westpac Consumer Confidence */}
      <div id="consumer-confidence">
        <AuWestpacConsumerConfidenceChart
          data={dashboardData?.au_westpac_consumer_confidence ?? null}
        />
      </div>

      {/* AU NAB Business Confidence */}
      <div id="nab-business-confidence">
        <AuNabConfidenceIndexChart
          data={dashboardData?.au_nab_business_confidence ?? null}
        />
      </div>

      {/* AU Consumer Spending */}
      <div id="consumer-spending">
        <AuConsumerSpendingChart
          data={dashboardData?.au_consumer_spending ?? null}
        />
      </div>

      {/* AU Household Saving Ratio */}
      <div id="household-saving-ratio">
        <AuHouseholdSavingRatioChart
          data={dashboardData?.au_household_saving_ratio ?? null}
        />
      </div>

      {/* AU Disposable Personal Income */}
      <div id="disposable-personal-income">
        <AuDisposablePersonalIncomeChart
          data={dashboardData?.au_disposable_personal_income ?? null}
        />
      </div>
    </div>
  )
}

/**
 * スケルトンローダー
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
