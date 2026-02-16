import { Spin, Alert, Button } from 'antd'
import { useCanadaEconomyDashboard } from '../../../hooks/useDashboardData'
import CanadaGdpGrowthChart from './economy/CanadaGdpGrowthChart'
import CanadaGdpMonthlyChart from './economy/CanadaGdpMonthlyChart'
import CanadaIndustrialProductionChart from './economy/CanadaIndustrialProductionChart'
import CanadaTradeBalanceChart from './economy/CanadaTradeBalanceChart'
import CanadaCurrentAccountChart from './economy/CanadaCurrentAccountChart'
import CanadaCurrentAccountGdpRatioChart from './economy/CanadaCurrentAccountGdpRatioChart'
import CaUsExportDependenceChart from './economy/CaUsExportDependenceChart'
import CanadaBusinessOutlookSurveyChart from './economy/CanadaBusinessOutlookSurveyChart'
import CanadianSurveyOfConsumerExpectationsChart from './economy/CanadianSurveyOfConsumerExpectationsChart'
import CanadaSeniorLoanOfficerSurveyChart from './economy/CanadaSeniorLoanOfficerSurveyChart'
import IveyPmiChart from './economy/IveyPmiChart'
import CaSpPmiChart from './economy/CaSpPmiChart'

/**
 * カナダ経済チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function CanadaEconomyCharts() {
  const { data, isLoading, error, refetch } = useCanadaEconomyDashboard()

  // ローディング状態
  if (isLoading) {
    return <EconomyChartsSkeleton />
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
      {/* GDP Growth Rate Chart (Quarterly) */}
      <div id="gdp-growth">
        <CanadaGdpGrowthChart
          data={dashboardData?.ca_gdp_growth ?? null}
        />
      </div>

      {/* Monthly GDP Chart */}
      <div id="gdp-monthly">
        <CanadaGdpMonthlyChart
          data={dashboardData?.ca_gdp_monthly ?? null}
        />
      </div>

      {/* Industrial Production Chart */}
      <div id="industrial-production">
        <CanadaIndustrialProductionChart
          data={dashboardData?.ca_industrial_production ?? null}
        />
      </div>

      {/* Trade Balance Chart */}
      <div id="trade-balance">
        <CanadaTradeBalanceChart
          data={dashboardData?.ca_trade_balance ?? null}
        />
      </div>

      {/* Current Account Chart */}
      <div id="current-account">
        <CanadaCurrentAccountChart
          data={dashboardData?.ca_current_account ?? null}
        />
      </div>

      {/* Current Account to GDP Ratio Chart */}
      <div id="current-account-gdp-ratio">
        <CanadaCurrentAccountGdpRatioChart
          data={dashboardData?.ca_current_account_gdp_ratio ?? null}
        />
      </div>

      {/* US Export Dependence Chart */}
      <div id="us-export-dependence">
        <CaUsExportDependenceChart
          data={dashboardData?.ca_us_export_dependence ?? null}
        />
      </div>

      {/* Business Outlook Survey Chart */}
      <div id="bos">
        <CanadaBusinessOutlookSurveyChart
          data={dashboardData?.ca_bos ?? null}
        />
      </div>

      {/* Canadian Survey of Consumer Expectations Chart */}
      <div id="csce">
        <CanadianSurveyOfConsumerExpectationsChart
          data={dashboardData?.ca_csce ?? null}
        />
      </div>

      {/* Senior Loan Officer Survey Chart */}
      <div id="slos">
        <CanadaSeniorLoanOfficerSurveyChart
          data={dashboardData?.ca_slos ?? null}
        />
      </div>

      {/* Ivey PMI Chart */}
      <div id="ivey-pmi">
        <IveyPmiChart
          data={dashboardData?.ca_ivey_pmi ?? null}
        />
      </div>

      {/* S&P Global PMI Chart */}
      <div id="sp-pmi">
        <CaSpPmiChart
          data={dashboardData?.ca_sp_pmi ?? null}
        />
      </div>
    </div>
  )
}

/**
 * スケルトンローダー
 * データ取得中に表示される骨組み
 */
function EconomyChartsSkeleton() {
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
        <div style={{ marginTop: 16, color: '#666' }}>経済データを読み込み中...</div>
      </div>
    </div>
  )
}
