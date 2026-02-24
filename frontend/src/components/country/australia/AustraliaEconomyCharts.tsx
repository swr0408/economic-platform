import { Spin, Alert, Button } from 'antd'
import { useAustraliaEconomyDashboard } from '../../../hooks/useDashboardData'
import AuGdpGrowthRateChart from './economy/AuGdpGrowthRateChart'
import AuGdpPriceRelatedChart from './economy/AuGdpPriceRelatedChart'
import AuPrivateNewCapitalExpenditureChart from './economy/AuPrivateNewCapitalExpenditureChart'
import AuInternationalTradeChart from './economy/AuInternationalTradeChart'
import AuCurrentAccountChart from './economy/AuCurrentAccountChart'
import AuCurrentAccountGdpRatioChart from './economy/AuCurrentAccountGdpRatioChart'
import AuPmiChart from './economy/AuPmiChart'
import AuTermsOfTradeChart from './economy/AuTermsOfTradeChart'

/**
 * オーストラリア経済チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function AustraliaEconomyCharts() {
  const { data, isLoading, error, refetch } = useAustraliaEconomyDashboard()

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
      {/* AU GDP Growth Rate */}
      <div id="gdp">
        <AuGdpGrowthRateChart
          data={dashboardData?.au_gdp_growth_rate ?? null}
        />
      </div>

      {/* AU GDP Price & Expenditure Related */}
      <div id="gdp-price-related">
        <AuGdpPriceRelatedChart
          data={dashboardData?.au_gdp_price_related ?? null}
        />
      </div>

      {/* AU Private New Capital Expenditure */}
      <div id="private-capex">
        <AuPrivateNewCapitalExpenditureChart
          data={dashboardData?.au_private_new_capital_expenditure ?? null}
        />
      </div>

      {/* AU International Trade */}
      <div id="trade-balance">
        <AuInternationalTradeChart
          data={dashboardData?.au_international_trade ?? null}
        />
      </div>

      {/* AU Current Account */}
      <div id="current-account">
        <AuCurrentAccountChart
          data={dashboardData?.au_current_account ?? null}
        />
      </div>

      {/* AU Current Account GDP Ratio */}
      <div id="current-account-gdp-ratio">
        <AuCurrentAccountGdpRatioChart
          data={dashboardData?.au_current_account_gdp_ratio ?? null}
        />
      </div>

      {/* AU S&P Global PMI */}
      <div id="pmi">
        <AuPmiChart
          data={dashboardData?.au_pmi ?? null}
        />
      </div>

      {/* AU Terms of Trade */}
      <div id="terms-of-trade">
        <AuTermsOfTradeChart
          data={dashboardData?.au_terms_of_trade ?? null}
        />
      </div>
    </div>
  )
}

/**
 * スケルトンローダー
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
