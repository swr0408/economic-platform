import { Spin, Alert, Button } from 'antd'
import { useEurozoneInflationDashboard } from '../../../hooks/useDashboardData'
import ECBHICPChart from './inflation/ECBHICPChart'
import ECBHICPBreakdownChart from './inflation/ECBHICPBreakdownChart'
import ECBPPIChart from './inflation/ECBPPIChart'
import ECBSPFChart from './inflation/ECBSPFChart'
import ECBSPFCoreChart from './inflation/ECBSPFCoreChart'
import ECBInflationExpectationsChart from './inflation/ECBInflationExpectationsChart'
import GermanyCPIChart from './inflation/GermanyCPIChart'
import GermanyPPIChart from './inflation/GermanyPPIChart'
import SpainHICPCPIChart from './inflation/SpainHICPCPIChart'
import EUImportPricesChart from './inflation/EUImportPricesChart'

/**
 * ユーロ圏インフレチャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function EurozoneInflationCharts() {
  const { data, isLoading, error, refetch } = useEurozoneInflationDashboard()

  if (error) {
    return (
      <Alert
        message="データ読み込みエラー"
        description={
          <div>
            <p>インフレデータの取得に失敗しました。</p>
            <Button onClick={() => refetch()} style={{ marginTop: 8 }}>
              再試行
            </Button>
          </div>
        }
        type="error"
        showIcon
      />
    )
  }

  if (isLoading || !data) {
    return <SkeletonLoader />
  }

  const dashboardData = data?.data

  return (
    <div className="country-chart-stack">
      {/* ECB HICP Chart */}
      <div id="ecb-hicp">
        <ECBHICPChart
          data={dashboardData?.ecb_hicp ?? null}
        />
      </div>

      {/* ECB HICP Breakdown Chart */}
      <div id="ecb-hicp-breakdown">
        <ECBHICPBreakdownChart
          data={dashboardData?.ecb_hicp ?? null}
        />
      </div>

      {/* ECB PPI Chart */}
      <div id="ecb-ppi">
        <ECBPPIChart
          data={dashboardData?.ecb_ppi ?? null}
        />
      </div>

      {/* ECB Inflation Expectations (CES) Chart */}
      <div id="ecb-inflation-expectations">
        <ECBInflationExpectationsChart
          data={dashboardData?.ecb_inflation_expectations ?? null}
        />
      </div>

      {/* ECB SPF Chart */}
      <div id="ecb-spf">
        <ECBSPFChart
          data={dashboardData?.ecb_spf ?? null}
        />
      </div>

      {/* ECB SPF Core Chart */}
      <div id="ecb-spf-core">
        <ECBSPFCoreChart
          data={dashboardData?.ecb_spf_core ?? null}
        />
      </div>

      {/* Germany CPI Chart */}
      <div id="germany-cpi">
        <GermanyCPIChart
          data={dashboardData?.germany_cpi ?? null}
        />
      </div>

      {/* Germany PPI Chart */}
      <div id="germany-ppi">
        <GermanyPPIChart
          data={dashboardData?.germany_ppi ?? null}
        />
      </div>

      {/* Spain HICP/CPI Chart */}
      <div id="spain-hicp-cpi">
        <SpainHICPCPIChart
          data={dashboardData?.spain_hicp_cpi ?? null}
        />
      </div>

      {/* EU Import Prices Chart */}
      <div id="eu-import-prices">
        <EUImportPricesChart
          data={dashboardData?.eu_import_prices ?? null}
        />
      </div>
    </div>
  )
}

/**
 * スケルトンローダー
 * データ取得中に表示される骨組み
 */
function SkeletonLoader() {
  return (
    <div className="country-chart-stack">
      <div
        style={{
          height: 300,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'rgba(0, 0, 0, 0.02)',
          borderRadius: 12,
        }}
      >
        <Spin size="large" />
        <div style={{ marginTop: 16, color: '#666' }}>インフレデータを読み込み中...</div>
      </div>
    </div>
  )
}
