import { Spin, Alert, Button } from 'antd'
import { useEurozoneEconomyDashboard } from '../../../hooks/useDashboardData'
import EuroGDPChart from './economy/EuroGDPChart'
import EuroGDPComponentsChart from './economy/EuroGDPComponentsChart'
import GermanyGDPGrowthChart from './economy/GermanyGDPGrowthChart'
import GermanyIndustrialProductionChart from './economy/GermanyIndustrialProductionChart'
import GermanyFactoryOrdersChart from './economy/GermanyFactoryOrdersChart'
import ZEWEconomicSentimentChart from './economy/ZEWEconomicSentimentChart'
import IfoBusinessClimateChart from './economy/IfoBusinessClimateChart'
import ECBBLSChart from './economy/ECBBLSChart'
import ECBProductionChart from './economy/ECBProductionChart'
import EurostatESIChart from './economy/EurostatESIChart'
import EuroPolicyUncertaintyChart from './economy/EuroPolicyUncertaintyChart'
import EurozonePMIChart from './economy/EurozonePMIChart'
import GermanyPMIChart from './economy/GermanyPMIChart'
import FrancePMIChart from './economy/FrancePMIChart'
import FranceBusinessConfidenceChart from './economy/FranceBusinessConfidenceChart'
import AdjustedLoansChart from './economy/AdjustedLoansChart'
import CISSChart from './economy/CISSChart'
import EUInternationalTradeChart from './economy/EUInternationalTradeChart'
import EUTermsOfTradeChart from './economy/EUTermsOfTradeChart'
import ECBCurrentAccountChart from './economy/ECBCurrentAccountChart'
import EuGovernmentDebtToGdpRatioChart from './economy/EuGovernmentDebtToGdpRatioChart'

/**
 * ユーロ圏経済チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function EurozoneEconomyCharts() {
  const { data, isLoading, error, refetch } = useEurozoneEconomyDashboard()

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
      {/* ECB GDP Chart */}
      <div id="ecb-gdp">
        <EuroGDPChart
          data={dashboardData?.ecb_gdp ?? null}
        />
      </div>

      {/* ECB GDP Components Chart */}
      <div id="ecb-gdp-components">
        <EuroGDPComponentsChart
          data={dashboardData?.ecb_gdp_components ?? null}
        />
      </div>

      {/* HCOB PMI Chart */}
      <div id="pmi">
        <EurozonePMIChart
          data={dashboardData?.eu_pmi ?? null}
        />
      </div>

      {/* ECB BLS Chart */}
      <div id="ecb-bls">
        <ECBBLSChart
          data={dashboardData?.ecb_bls ?? null}
        />
      </div>

      {/* ECB Adjusted Loans Chart */}
      <div id="ecb-adjusted-loans">
        <AdjustedLoansChart
          data={dashboardData?.ecb_adjusted_loans ?? null}
        />
      </div>

      {/* CISS Chart */}
      <div id="ecb-ciss">
        <CISSChart
          data={dashboardData?.ecb_ciss ?? null}
        />
      </div>
      
      {/* ECB Production Chart */}
      <div id="ecb-production">
        <ECBProductionChart
          data={dashboardData?.ecb_production ?? null}
        />
      </div>

      {/* Euro Policy Uncertainty Chart */}
      <div id="euro-policy-uncertainty">
        <EuroPolicyUncertaintyChart
          data={dashboardData?.euro_policy_uncertainty ?? null}
        />
      </div>

      {/* Eurostat ESI Chart */}
      <div id="eurostat-esi">
        <EurostatESIChart
          data={dashboardData?.eurostat_esi ?? null}
        />
      </div>

      {/* Germany GDP Growth Chart */}
      <div id="germany-gdp-growth">
        <GermanyGDPGrowthChart
          data={dashboardData?.germany_gdp_growth ?? null}
        />
      </div>

      {/* Germany S&P Global PMI Chart */}
      <div id="germany-pmi">
        <GermanyPMIChart
          data={dashboardData?.germany_pmi ?? null}
        />
      </div>

      {/* Germany Industrial Production Chart */}
      <div id="germany-industrial-production">
        <GermanyIndustrialProductionChart
          data={dashboardData?.germany_industrial_production ?? null}
        />
      </div>

      {/* Germany Factory Orders Chart */}
      <div id="germany-factory-orders">
        <GermanyFactoryOrdersChart
          data={dashboardData?.germany_factory_orders ?? null}
        />
      </div>

      {/* ZEW Economic Sentiment Chart */}
      <div id="zew-economic-sentiment">
        <ZEWEconomicSentimentChart
          data={dashboardData?.zew_economic_sentiment ?? null}
        />
      </div>

      {/* IFO Business Climate Chart */}
      <div id="ifo-business-climate">
        <IfoBusinessClimateChart
          data={dashboardData?.ifo_business_climate ?? null}
        />
      </div>

      {/* France HCOB PMI Chart */}
      <div id="france-pmi">
        <FrancePMIChart
          data={dashboardData?.france_pmi ?? null}
        />
      </div>

      {/* France Business Confidence Chart */}
      <div id="france-business-confidence">
        <FranceBusinessConfidenceChart
          data={dashboardData?.france_business_confidence ?? null}
        />
      </div>

      {/* EU International Trade Chart */}
      <div id="eu-international-trade">
        <EUInternationalTradeChart
          data={dashboardData?.eu_international_trade ?? null}
        />
      </div>

      {/* EU Terms of Trade Chart */}
      <div id="eu-terms-of-trade">
        <EUTermsOfTradeChart
          data={dashboardData?.eu_terms_of_trade ?? null}
        />
      </div>

      {/* ECB Current Account Chart */}
      <div id="ecb-current-account">
        <ECBCurrentAccountChart
          data={dashboardData?.ecb_current_account ?? null}
        />
      </div>

      {/* EU政府債務残高対GDP比 */}
      <div id="eu-government-debt-to-gdp-ratio">
        <EuGovernmentDebtToGdpRatioChart
          data={dashboardData?.eu_government_debt_to_gdp_ratio ?? null}
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
