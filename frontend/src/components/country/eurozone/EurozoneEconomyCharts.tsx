import { Spin, Alert, Button } from 'antd'
import { useEurozoneEconomyDashboard } from '../../../hooks/useDashboardData'
import EuroGDPChart from './economy/EuroGDPChart'
import EuroGDPComponentsChart from './economy/EuroGDPComponentsChart'
import ECBBLSChart from './economy/ECBBLSChart'
import ECBProductionChart from './economy/ECBProductionChart'
import EurostatESIChart from './economy/EurostatESIChart'
import EuroPolicyUncertaintyChart from './economy/EuroPolicyUncertaintyChart'
import EurozonePMIChart from './economy/EurozonePMIChart'

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

      {/* ECB BLS Chart */}
      <div id="ecb-bls">
        <ECBBLSChart
          data={dashboardData?.ecb_bls ?? null}
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

      {/* HCOB PMI Chart */}
      <div id="pmi">
        <EurozonePMIChart
          data={dashboardData?.eu_pmi ?? null}
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
