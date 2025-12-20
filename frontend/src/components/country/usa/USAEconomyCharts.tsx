import { Spin, Alert, Button } from 'antd'
import { useUSAEconomyDashboard } from '../../../hooks/useDashboardData'
import GDPGrowthChart from './economy/GDPGrowthChart'
import GDPContributionsChart from './economy/GDPContributionsChart'
import GDPComponentsGrowthChart from './economy/GDPComponentsGrowthChart'
import PotentialGDPChart from './economy/PotentialGDPChart'
import BankLendingChart from './economy/BankLendingChart'
import FCIChart from './economy/FCIChart'
import NFCIChart from './economy/NFCIChart'
import GDPNowChart from './economy/GDPNowChart'
import ISMManufacturingChart from './economy/ISMManufacturingChart'
import ISMComponentsChart from './economy/ISMComponentsChart'
import OrderInventoryBalanceChart from './economy/OrderInventoryBalanceChart'

/**
 * 米国経済チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function USAEconomyCharts() {
  const { data, isLoading, error, refetch } = useUSAEconomyDashboard()

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

      {/* GDP成長率チャート */}
      <div id="gdp-growth">
        <GDPGrowthChart
          data={dashboardData?.gdp_growth_rate ?? null}
          nextRelease={dashboardData?.next_gdp_release ?? null}
        />
      </div>

      {/* GDP項目別成長率チャート */}
      <div id="gdp-components-growth">
        <GDPComponentsGrowthChart
          data={dashboardData?.gdp_components_growth ?? null}
        />
      </div>

      {/* GDP寄与度チャート */}
      <div id="gdp-contributions">
        <GDPContributionsChart
          data={dashboardData?.gdp_contributions ?? null}
        />
      </div>

      {/* 潜在成長率チャート */}
      <div id="potential-gdp">
        <PotentialGDPChart
          data={dashboardData?.potential_gdp ?? null}
        />
      </div>

      {/* 銀行貸し出し態度チャート */}
      <div id="bank-lending">
        <BankLendingChart
          data={dashboardData?.bank_lending ?? null}
        />
      </div>

      {/* FCI-G（金融情勢指数）チャート */}
      <div id="fci">
        <FCIChart
          data={dashboardData?.fci ?? null}
        />
      </div>

      {/* シカゴ連銀金融環境指数（NFCI）チャート */}
      <div id="nfci">
        <NFCIChart
          data={dashboardData?.nfci ?? null}
        />
      </div>

      {/* GDPNow（リアルタイムGDP予測）チャート */}
      <div id="gdpnow">
        <GDPNowChart
          data={dashboardData?.gdpnow ?? null}
        />
      </div>

      {/* ISM製造業景況指数チャート */}
      <div id="ism-manufacturing">
        <ISMManufacturingChart
          data={dashboardData?.ism_manufacturing ?? null}
        />
      </div>

      {/* ISM製造業サブインデックスチャート */}
      <div id="ism-components">
        <ISMComponentsChart
          data={dashboardData?.ism_components ?? null}
        />
      </div>

      {/* ISM製造業受注在庫バランスチャート */}
      <div id="order-inventory-balance">
        <OrderInventoryBalanceChart
          data={dashboardData?.ism_components ?? null}
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
