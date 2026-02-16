import { Spin, Alert, Button } from 'antd'
import { useCanadaPolicyDashboard } from '../../../hooks/useDashboardData'
import CaBocRateChart from './monetary_policy/CaBocRateChart'
import BocRateCutsExpectationChart from './monetary_policy/BocRateCutsExpectationChart'
import BocMonetaryPolicyReportChart from './monetary_policy/BocMonetaryPolicyReportChart'
import BocBalanceSheetChart from './monetary_policy/BocBalanceSheetChart'
import CanadaBanksBalanceSheetChart from './monetary_policy/CanadaBanksBalanceSheetChart'
import CaCorraChart from './monetary_policy/CaCorraChart'
import CaSettlementBalancesChart from './monetary_policy/CaSettlementBalancesChart'
import CaGovernmentDepositsChart from './monetary_policy/CaGovernmentDepositsChart'

/**
 * カナダ金融政策チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function CanadaPolicyCharts() {
  const { data, isLoading, error, refetch } = useCanadaPolicyDashboard()

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
      {/* BOC Policy Rate Chart */}
      <div id="policy-rate">
        <CaBocRateChart
          data={dashboardData?.ca_boc_rate ?? null}
        />
      </div>

      {/* BOC Rate Cuts Expectation Chart */}
      <div id="boc-rate-cuts">
        <BocRateCutsExpectationChart />
      </div>

      {/* BOC Monetary Policy Report Chart */}
      <div id="boc-mpr">
        <BocMonetaryPolicyReportChart
          data={dashboardData?.boc_mpr ?? null}
        />
      </div>

      {/* BOC Balance Sheet Chart */}
      <div id="boc-balance-sheet">
        <BocBalanceSheetChart
          data={dashboardData?.boc_balance_sheet ?? null}
        />
      </div>

      {/* Canada Banks Balance Sheet Chart (Chartered Banks) */}
      <div id="canada-banks-balance-sheet">
        <CanadaBanksBalanceSheetChart
          data={dashboardData?.canada_banks_balance_sheet ?? null}
        />
      </div>

      {/* CORRA Chart */}
      <div id="ca-corra">
        <CaCorraChart
          data={dashboardData?.ca_corra ?? null}
        />
      </div>

      {/* Settlement Balances Chart */}
      <div id="ca-settlement-balances">
        <CaSettlementBalancesChart
          data={dashboardData?.ca_settlement_balances ?? null}
        />
      </div>

      {/* Government Deposits Chart (TGA相当) */}
      <div id="ca-government-deposits">
        <CaGovernmentDepositsChart
          data={dashboardData?.ca_government_deposits ?? null}
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
