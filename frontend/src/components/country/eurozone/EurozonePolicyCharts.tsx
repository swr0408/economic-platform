import { Spin, Alert, Button } from 'antd'
import { useEurozonePolicyDashboard } from '../../../hooks/useDashboardData'
import RestrictedSection from '../../common/RestrictedSection'
import ECBRatesChart from './monetary_policy/ECBRatesChart'
import EurexOISChart from './monetary_policy/EurexOISChart'
import ECBRateCutsExpectationChart from './monetary_policy/ECBRateCutsExpectationChart'
import ECBMacroProjectionsChart from './monetary_policy/ECBMacroProjectionsChart'
import ECBM3Chart from './monetary_policy/ECBM3Chart'
import BankInterestRatesChart from './monetary_policy/BankInterestRatesChart'
import ECBBalanceSheetChart from './monetary_policy/ECBBalanceSheetChart'

/**
 * ユーロ圏金融政策チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function EurozonePolicyCharts() {
  const { data, isLoading, error, refetch } = useEurozonePolicyDashboard()

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
      {/* ECB政策枠組み（ハンドブックのみ） */}
      <div id="ecb-policy-framework" />

      {/* ECB Rates Chart */}
      <div id="ecb-rates">
        <ECBRatesChart
          data={dashboardData?.ecb_rates ?? null}
        />
      </div>

      {/* Eurex OIS Chart */}
      <div id="eurex-ois">
        <EurexOISChart
          data={dashboardData?.eurex_ois ?? null}
        />
      </div>

      {/* ECB Rate Cuts Expectation Chart (special) */}
      <RestrictedSection visibility="special">
        <div id="ecb-rate-cuts">
          <ECBRateCutsExpectationChart />
        </div>
      </RestrictedSection>

      {/* ECB Macro Projections Chart */}
      <div id="ecb-macro-projections">
        <ECBMacroProjectionsChart
          data={dashboardData?.ecb_macro_projections ?? null}
        />
      </div>

      {/* ECB M3 Money Supply Chart */}
      <div id="ecb-m3">
        <ECBM3Chart
          data={dashboardData?.ecb_m3 ?? null}
        />
      </div>

      {/* Bank Interest Rates Chart */}
      <div id="ecb-bank-interest-rates">
        <BankInterestRatesChart
          data={dashboardData?.ecb_bank_interest_rates ?? null}
        />
      </div>

      {/* ECB Balance Sheet Chart */}
      <div id="ecb-balance-sheet">
        <ECBBalanceSheetChart
          data={dashboardData?.ecb_balance_sheet ?? null}
        />
      </div>

      {/* 伊独スプレッド（ハンドブックのみ） */}
      <div id="btp-bund-spread" />
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
