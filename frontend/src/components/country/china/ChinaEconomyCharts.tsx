import { Spin, Alert, Button } from 'antd'
import { useChinaEconomyDashboard } from '../../../hooks/useDashboardData'
import CnGdpGrowthRateChart from './economy/CnGdpGrowthRateChart'
import CnIndustrialProductionChart from './economy/CnIndustrialProductionChart'
import CnFixedAssetInvestmentChart from './economy/CnFixedAssetInvestmentChart'
import CnPmiHeadlineChart from './economy/CnPmiHeadlineChart'
import CnPmiManufacturingSubChart from './economy/CnPmiManufacturingSubChart'
import CnPmiNonManufacturingSubChart from './economy/CnPmiNonManufacturingSubChart'
import CnLiKeqiangIndexChart from './economy/CnLiKeqiangIndexChart'
import CnBeijingPm25Chart from './economy/CnBeijingPm25Chart'
import CnCaixinPmiChart from './economy/CnCaixinPmiChart'
import CnTradeBalanceChart from './economy/CnTradeBalanceChart'
import CnCurrentAccountChart from './economy/CnCurrentAccountChart'
import CnCurrentAccountGdpRatioChart from './economy/CnCurrentAccountGdpRatioChart'
import CnLandSalesIncomeChart from './economy/CnLandSalesIncomeChart'
import CnBaiduMigrationChart from './economy/CnBaiduMigrationChart'
import CnIntegratedCircuitManufacturingChart from './economy/CnIntegratedCircuitManufacturingChart'
import CnElectronicsStockChart from './economy/CnElectronicsStockChart'

/**
 * 中国経済チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function ChinaEconomyCharts() {
  const { data, isLoading, error, refetch } = useChinaEconomyDashboard()

  if (isLoading) {
    return <EconomyChartsSkeleton />
  }

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
      <CnGdpGrowthRateChart
        data={dashboardData?.cn_gdp_growth_rate ?? null}
      />
      {/* NBS PMI ヘッドライン */}
      <CnPmiHeadlineChart
        data={dashboardData?.cn_pmi ?? null}
      />
      {/* 製造業PMIサブインデックス */}
      <CnPmiManufacturingSubChart
        data={dashboardData?.cn_pmi ?? null}
      />
      {/* 非製造業PMIサブインデックス */}
      <CnPmiNonManufacturingSubChart
        data={dashboardData?.cn_pmi ?? null}
      />
      {/* Caixin PMI */}
      <CnCaixinPmiChart
        data={dashboardData?.cn_caixin_pmi ?? null}
      />
      {/* 貿易収支 */}
      <CnTradeBalanceChart
        data={dashboardData?.cn_trade_balance ?? null}
      />
      {/* 経常収支 */}
      <CnCurrentAccountChart
        data={dashboardData?.cn_current_account ?? null}
      />
      {/* 経常収支対GDP比 */}
      <CnCurrentAccountGdpRatioChart
        data={dashboardData?.cn_current_account_gdp_ratio ?? null}
      />
      {/* 土地売却収入 */}
      <CnLandSalesIncomeChart
        data={dashboardData?.cn_land_sales_income ?? null}
      />
      {/* 集積回路生産 */}
      <CnIntegratedCircuitManufacturingChart
        data={dashboardData?.cn_integrated_circuit_manufacturing ?? null}
      />
      {/* 電気機器在庫 */}
      <CnElectronicsStockChart
        data={dashboardData?.cn_electronics_stock ?? null}
      />
      {/* 鉱工業生産 */}
      <CnIndustrialProductionChart
        data={dashboardData?.cn_industrial_production ?? null}
      />
      {/* 固定資産投資 */}
      <CnFixedAssetInvestmentChart
        data={dashboardData?.cn_fixed_asset_investment ?? null}
      />
      {/* 李克強指数（スクリーンショット） */}
      <CnLiKeqiangIndexChart />
      {/* 北京PM2.5濃度 */}
      <CnBeijingPm25Chart
        data={dashboardData?.cn_beijing_pm25 ?? null}
      />
      {/* 人流総量（百度迁徙スクリーンショット） */}
      <CnBaiduMigrationChart />
    </div>
  )
}

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
