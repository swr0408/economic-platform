import { Spin, Alert, Button } from 'antd'
import { useUSAPolicyDashboard } from '../../../hooks/useDashboardData'
import PolicyRateChart from './monetary_policy/PolicyRateChart'
import TermPremiumChart from './monetary_policy/TermPremiumChart'
import CMEFedWatchChart from './monetary_policy/CMEFedWatchChart'
import FOMCProjectionsChart from './monetary_policy/FOMCProjectionsChart'
import FOMCTable1Chart from './monetary_policy/FOMCTable1Chart'
import FRBTotalAssetsChart from './monetary_policy/FRBTotalAssetsChart'
import ReserveBalancesChart from './monetary_policy/ReserveBalancesChart'
import TGAChart from './monetary_policy/TGAChart'
import OASChart from './monetary_policy/OASChart'
import SOFRVolatilityChart from './monetary_policy/SOFRVolatilityChart'
import ONRRPChart from './monetary_policy/ONRRPChart'
import FederalBudgetChart from './monetary_policy/FederalBudgetChart'
import CBOProjectionsChart from './monetary_policy/CBOProjectionsChart'
import CRELoanDelinquencyChart from './monetary_policy/CRELoanDelinquencyChart'
import QuarterlyRefundingChart from './monetary_policy/QuarterlyRefundingChart'
import RestrictedSection from '../../common/RestrictedSection'
import FedRateCutsExpectationChart from './monetary_policy/FedRateCutsExpectationChart'

/**
 * 米国金融政策チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 * これにより7-8リクエスト → 1リクエストに削減し、ページ読み込みを高速化
 */
export default function USAPolicyCharts() {
  const { data, isLoading, error, refetch } = useUSAPolicyDashboard()

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
      {/* Federal Funds Target Rate Chart */}
      <div id="policy-rate">
        <PolicyRateChart
          data={dashboardData?.policy_rate ?? null}
          nextFomc={dashboardData?.next_fomc ?? null}
        />
      </div>

      {/* Fed Rate Cuts Expectation Chart (special) */}
      <RestrictedSection visibility="special">
        <div id="fed-rate-cuts">
          <FedRateCutsExpectationChart />
        </div>
      </RestrictedSection>

      {/* CME FedWatch Tool */}
      <div id="fed-watch">
        <CMEFedWatchChart
          screenshotUrl={dashboardData?.fedwatch_screenshot_url ?? null}
          lastUpdated={data?.last_updated}
          cached={data?.cached}
        />
      </div>

      {/* ACM Term Premium Chart */}
      <div id="term-premium">
        <TermPremiumChart
          data={dashboardData?.term_premium ?? null}
          kwData={dashboardData?.kw_term_premium ?? null}
        />
      </div>

      {/* SOFR Volatility Chart */}
      <div id="sofr-volatility">
        <SOFRVolatilityChart data={dashboardData?.sofr_volatility ?? null} />
      </div>

      {/* FOMC Dot Plot */}
      <div id="dot-plot">
        <FOMCProjectionsChart sepDates={dashboardData?.sep_dates ?? null} />
      </div>

      {/* FOMC Economic Projections Table 1 */}
      <div id="fomc-projections">
        <FOMCTable1Chart sepDates={dashboardData?.sep_dates ?? null} />
      </div>

      {/* FRB Total Assets Chart */}
      <div id="frb-total-assets">
        <FRBTotalAssetsChart data={dashboardData?.frb_total_assets ?? null} />
      </div>

      {/* Reserve Balances Chart */}
      <div id="reserve-balances">
        <ReserveBalancesChart data={dashboardData?.reserve_balances ?? null} />
      </div>

      {/* TGA Chart */}
      <div id="tga">
        <TGAChart data={dashboardData?.tga ?? null} />
      </div>

      {/* ON RRP Chart */}
      <div id="on-rrp">
        <ONRRPChart data={dashboardData?.on_rrp ?? null} />
      </div>

      {/* OAS Chart */}
      <div id="oas">
        <OASChart data={dashboardData?.oas ?? null} />
      </div>

      {/* Federal Budget Balance Chart */}
      <div id="federal-budget">
        <FederalBudgetChart data={dashboardData?.federal_budget ?? null} />
      </div>

      {/* CBO Budget Projections Chart */}
      <div id="cbo-projections">
        <CBOProjectionsChart data={dashboardData?.cbo_projections ?? null} />
      </div>

      {/* CRE Loan Delinquency Rate Chart */}
      <div id="cre-loan-delinquency">
        <CRELoanDelinquencyChart data={dashboardData?.cre_loan_delinquency ?? null} />
      </div>

      {/* Treasury Quarterly Refunding */}
      <div id="quarterly-refunding">
        <QuarterlyRefundingChart />
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
