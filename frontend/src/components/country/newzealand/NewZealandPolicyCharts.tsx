import { Spin, Alert, Button } from 'antd'
import { useNewZealandPolicyDashboard } from '../../../hooks/useDashboardData'
import NzInterestRateChart from './monetary_policy/NzInterestRateChart'
import NzEconomicForecastChart from './monetary_policy/NzEconomicForecastChart'
import NzCentralBankBalanceSheetChart from './monetary_policy/NzCentralBankBalanceSheetChart'
import NzBankBalanceSheetChart from './monetary_policy/NzBankBalanceSheetChart'

/**
 * ニュージーランド金融政策チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function NewZealandPolicyCharts() {
  const { data, isLoading, error, refetch } = useNewZealandPolicyDashboard()

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
      {/* RBNZ政策金利（OCR） */}
      <div id="policy-rate">
        <NzInterestRateChart
          data={dashboardData?.nz_rbnz_rate ?? null}
        />
      </div>

      {/* RBNZ MPS経済見通し */}
      <NzEconomicForecastChart
        data={dashboardData?.nz_economic_forecast ?? null}
      />

      {/* RBNZ中央銀行バランスシート */}
      <NzCentralBankBalanceSheetChart
        data={dashboardData?.nz_central_bank_balance_sheet ?? null}
      />

      {/* 銀行バランスシート（S10） */}
      <NzBankBalanceSheetChart
        data={dashboardData?.nz_bank_balance_sheet ?? null}
      />
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
