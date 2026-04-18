import { Spin, Alert, Button } from 'antd'
import { useChinaPolicyDashboard } from '../../../hooks/useDashboardData'
import CnLprChart from './policy/CnLprChart'
import ChReverseRepoRateChart from './policy/ChReverseRepoRateChart'
import ChRrrChart from './policy/ChRrrChart'
import ChCentralBankBalanceSheetChart from './policy/ChCentralBankBalanceSheetChart'
import CnFixingRepoRateChart from './policy/CnFixingRepoRateChart'
import CnShiborChart from './policy/CnShiborChart'
import ChM1M2Chart from './policy/ChM1M2Chart'
import CnAggregateFinancingChart from './policy/CnAggregateFinancingChart'
import CnNewRmbLoansChart from './policy/CnNewRmbLoansChart'
import CnForeignExchangeReservesChart from './policy/CnForeignExchangeReservesChart'
import CnCentralParityChart from './policy/CnCentralParityChart'
import CnCreditImpulseChart from './policy/CnCreditImpulseChart'
import CnLocalBondsChart from './policy/CnLocalBondsChart'
import CnGovernmentBondIssuanceChart from './policy/CnGovernmentBondIssuanceChart'
import CnOverseasInvestorFlowChart from './policy/CnOverseasInvestorFlowChart'
import CnCapitalFlowsChart from './policy/CnCapitalFlowsChart'

/**
 * 中国金融政策チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function ChinaPolicyCharts() {
  const { data, isLoading, error, refetch } = useChinaPolicyDashboard()

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
      {/* 逆回購金利（7日物） */}
      <ChReverseRepoRateChart
        data={dashboardData?.ch_reverse_repo_rate ?? null}
      />

      {/* ローンプライムレート (1Y + 5Y) */}
      <CnLprChart
        lpr1y={dashboardData?.cn_lpr_1y ?? null}
        lpr5y={dashboardData?.cn_lpr_5y ?? null}
      />

      {/* 預金準備率（大型金融機関） */}
      <ChRrrChart
        data={dashboardData?.china_reserve_requirement_ratio_for_large_banks ?? null}
      />

      {/* 中銀バランスシート（総資産） */}
      <ChCentralBankBalanceSheetChart
        data={dashboardData?.ch_central_bank_balance_sheet ?? null}
      />

      {/* Fixing Repo Rate (FR / FDR) */}
      <CnFixingRepoRateChart />

      {/* Central Parity Rate（基準値・Fixing） */}
      <CnCentralParityChart />

      {/* SHIBOR（上海銀行間取引金利） */}
      <CnShiborChart />

      {/* M1/M2（貨幣供応量） */}
      <ChM1M2Chart
        data={dashboardData?.ch_m1_m2 ?? null}
      />

      {/* 社会融資総量 */}
      <CnAggregateFinancingChart
        data={dashboardData?.cn_aggregate_financing_to_the_real_economy ?? null}
      />

      {/* 新規人民元貸出 */}
      <CnNewRmbLoansChart
        data={dashboardData?.cn_new_rmb_loans ?? null}
      />

      {/* 外貨準備 */}
      <CnForeignExchangeReservesChart
        data={dashboardData?.cn_foreign_exchange_reserves ?? null}
      />

      {/* クレジットインパルス */}
      <CnCreditImpulseChart />

      {/* 国債発行（Government Bond Issuance） */}
      <CnGovernmentBondIssuanceChart />

      {/* 資本フロー */}
      <CnCapitalFlowsChart
        data={dashboardData?.cn_capital_flows ?? null}
      />

      {/* 海外投資家フロー */}
      <CnOverseasInvestorFlowChart
        data={dashboardData?.cn_overseas_investor_flow ?? null}
      />

      {/* 地方政府債券 */}
      <CnLocalBondsChart
        data={dashboardData?.cn_local_bonds ?? null}
      />
    </div>
  )
}

/**
 * スケルトンローダー
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
