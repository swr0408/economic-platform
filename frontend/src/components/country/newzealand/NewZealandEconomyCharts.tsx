import { Spin, Alert, Button } from 'antd'
import { useNewZealandEconomyDashboard } from '../../../hooks/useDashboardData'
import NzGdpGrowthRateChart from './economy/NzGdpGrowthRateChart'
import NzGdpItemChart from './economy/NzGdpItemChart'
import NzCapacityUtilizationChart from './economy/NzCapacityUtilizationChart'
import NzPmiChart from './economy/NzPmiChart'
import NzGlobalDairyTradeChart from './economy/NzGlobalDairyTradeChart'
import NzTermsOfTradeChart from './economy/NzTermsOfTradeChart'
import NzTradeBalanceChart from './economy/NzTradeBalanceChart'
import NzCurrentAccountBalanceChart from './economy/NzCurrentAccountBalanceChart'
import NzCurrentAccountGdpRatioChart from './economy/NzCurrentAccountGdpRatioChart'

/**
 * ニュージーランド経済チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function NewZealandEconomyCharts() {
  const { data, isLoading, error, refetch } = useNewZealandEconomyDashboard()

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
      {/* GDP成長率 */}
      <NzGdpGrowthRateChart
        data={dashboardData?.nz_gdp_growth_rate ?? null}
      />

      {/* GDP項目 */}
      <NzGdpItemChart
        data={dashboardData?.nz_gdp_item ?? null}
      />

      {/* 設備稼働率 */}
      <NzCapacityUtilizationChart
        data={dashboardData?.nz_capacity_utilization ?? null}
      />

      {/* PMI / PSI / PCI */}
      <NzPmiChart
        pmi={dashboardData?.nz_pmi ?? null}
        psi={dashboardData?.nz_psi ?? null}
        pci={dashboardData?.nz_pci ?? null}
      />

      {/* 乳製品価格（GDT） */}
      <NzGlobalDairyTradeChart
        data={dashboardData?.nz_global_dairy_trade ?? null}
      />

      {/* 交易条件 */}
      <NzTermsOfTradeChart
        data={dashboardData?.nz_terms_of_trade ?? null}
      />

      {/* 貿易収支 */}
      <NzTradeBalanceChart
        data={dashboardData?.nz_trade_balance ?? null}
      />

      {/* 経常収支 */}
      <NzCurrentAccountBalanceChart
        data={dashboardData?.nz_current_account_balance ?? null}
      />

      {/* 経常収支対GDP比 */}
      <NzCurrentAccountGdpRatioChart
        data={dashboardData?.nz_current_account_gdp_ratio ?? null}
      />
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
