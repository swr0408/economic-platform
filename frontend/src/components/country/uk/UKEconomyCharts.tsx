/**
 * イギリス経済指標チャート群コンポーネント
 *
 * UK経済カテゴリのダッシュボードページで使用
 * ONS GDP、ONS GVA（月間GDP）、ONS Production Industries（鉱工業生産）などの経済指標を表示
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
import { Spin, Alert, Button } from 'antd'
import { useUKEconomyDashboard } from '../../../hooks/useDashboardData'
import ONSGDPChart from './economy/ONSGDPChart'
import ONSGVAChart from './economy/ONSGVAChart'
import ONSProductionChart from './economy/ONSProductionChart'
import CBIIndustrialTrendsChart from './economy/CBIIndustrialTrendsChart'
import UKPMIChart from './economy/UKPMIChart'
import UKTradeBalanceChart from './economy/UKTradeBalanceChart'
import UKCurrentAccountChart from './economy/UKCurrentAccountChart'
import UKCurrentAccountGdpRatioChart from './economy/UKCurrentAccountGdpRatioChart'

export default function UKEconomyCharts() {
  const { data, isLoading, error, refetch } = useUKEconomyDashboard()

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
      {/* ONS GDP成長率 */}
      <div id="ons-gdp">
        <ONSGDPChart data={dashboardData?.ons_gdp ?? null} />
      </div>

      {/* ONS GVA（月間GDP） */}
      <div id="ons-gva">
        <ONSGVAChart data={dashboardData?.ons_gva ?? null} />
      </div>

      {/* UK PMI */}
      <div id="uk-pmi">
        <UKPMIChart data={dashboardData?.uk_pmi ?? null} />
      </div>

      {/* ONS Production Industries（鉱工業生産） */}
      <div id="ons-production">
        <ONSProductionChart data={dashboardData?.ons_production ?? null} />
      </div>

      {/* CBI製造業受注指数 */}
      <div id="cbi-industrial-trends">
        <CBIIndustrialTrendsChart data={dashboardData?.cbi_industrial_trends ?? null} />
      </div>

      {/* UK貿易収支 */}
      <div id="uk-trade-balance">
        <UKTradeBalanceChart data={dashboardData?.uk_trade_balance ?? null} />
      </div>

      {/* UK経常収支 */}
      <div id="uk-current-account">
        <UKCurrentAccountChart data={dashboardData?.uk_current_account ?? null} />
      </div>

      {/* UK経常収支対GDP比 */}
      <div id="uk-current-account-gdp-ratio">
        <UKCurrentAccountGdpRatioChart data={dashboardData?.uk_current_account ?? null} />
      </div>
    </div>
  )
}

/**
 * ローディングスケルトン
 */
function EconomyChartsSkeleton() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
      <Spin size="large" tip="データを読み込んでいます..." />
    </div>
  )
}
