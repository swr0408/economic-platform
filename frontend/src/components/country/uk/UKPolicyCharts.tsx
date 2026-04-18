import { Spin, Alert, Button } from 'antd'
import { useUKPolicyDashboard } from '../../../hooks/useDashboardData'
import BOEBankRateChart from './monetary_policy/BOEBankRateChart'
import SONIAChart from './monetary_policy/SONIAChart'
import BOEMPCVotingChart from './monetary_policy/BOEMPCVotingChart'
import BOEOISCurveChart from './monetary_policy/BOEOISCurveChart'
import BOEEconomicOutlookSection from './monetary_policy/BOEEconomicOutlookSection'
import BOEDMPSurveySection from './monetary_policy/BOEDMPSurveySection'
import UKPublicSectorNetBorrowingChart from './monetary_policy/UKPublicSectorNetBorrowingChart'
import UkQtChart from './monetary_policy/UkQtChart'
import RestrictedSection from '../../common/RestrictedSection'
import BOERateCutsExpectationChart from './monetary_policy/BOERateCutsExpectationChart'

/**
 * イギリス金融政策チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function UKPolicyCharts() {
  const { data, isLoading, error, refetch } = useUKPolicyDashboard()

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
      {/* BOE Bank Rate Chart */}
      <div id="boe-bank-rate">
        <BOEBankRateChart
          data={dashboardData?.boe_bank_rate ?? null}
        />
      </div>

      {/* BOE Rate Cuts Expectation Chart (special) */}
      <RestrictedSection visibility="special">
        <div id="boe-rate-cuts">
          <BOERateCutsExpectationChart />
        </div>
      </RestrictedSection>

      {/* SONIA Chart */}
      <div id="sonia">
        <SONIAChart />
      </div>

      {/* BOE MPC Voting Chart */}
      <div id="boe-mpc-voting">
        <BOEMPCVotingChart
          data={dashboardData?.boe_mpc_voting ?? null}
        />
      </div>

      {/* BOE OIS Curve Chart */}
      <div id="boe-ois-curve">
        <BOEOISCurveChart
          data={dashboardData?.boe_ois_curve ?? null}
        />
      </div>

      {/* BOE Economic Outlook Section */}
      <div id="boe-economic-outlook">
        <BOEEconomicOutlookSection
          marketExpectationsData={dashboardData?.boe_market_expectations ?? null}
          cpiProjectionsData={dashboardData?.boe_cpi_projections ?? null}
          gdpForecastData={dashboardData?.boe_gdp_forecast ?? null}
          unemploymentForecastData={dashboardData?.boe_unemployment_forecast ?? null}
          servicesInflationData={dashboardData?.boe_services_inflation ?? null}
          wageGrowthData={dashboardData?.boe_wage_growth ?? null}
          averageWeeklyEarningsData={dashboardData?.boe_average_weekly_earnings ?? null}
          unitWageCostsData={dashboardData?.boe_unit_wage_costs ?? null}
          inflationExpectationsData={dashboardData?.boe_inflation_expectations ?? null}
          isLoading={isLoading}
        />
      </div>

      {/* BOE DMP Survey Section */}
      <div id="boe-dmp-survey">
        <BOEDMPSurveySection
          data={dashboardData?.boe_dmp_survey ?? null}
          isLoading={isLoading}
        />
      </div>

      {/* UK Public Sector Net Borrowing Chart */}
      <div id="uk-public-sector-net-borrowing">
        <UKPublicSectorNetBorrowingChart
          data={dashboardData?.uk_public_sector_net_borrowing ?? null}
        />
      </div>

      {/* UK QT (APF Gilt Holdings) Chart */}
      <div id="uk-qt">
        <UkQtChart
          data={dashboardData?.uk_qt ?? null}
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
