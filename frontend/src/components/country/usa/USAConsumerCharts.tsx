import { Spin, Alert, Button } from 'antd'
import { useUSAConsumerDashboard } from '../../../hooks/useDashboardData'
import RetailSalesChart from './consumer/RetailSalesChart'
import CartsChart from './consumer/CartsChart'
import AffinitySpendChart from './consumer/AffinitySpendChart'
import VisaSpendingChart from './consumer/VisaSpendingChart'
import TotalVehicleSalesChart from './consumer/TotalVehicleSalesChart'
import RedbookChart from './consumer/RedbookChart'
import ConsumerCreditChart from './consumer/ConsumerCreditChart'

/**
 * 米国消費チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function USAConsumerCharts() {
  const { data, isLoading, error, refetch } = useUSAConsumerDashboard()

  // ローディング状態
  if (isLoading) {
    return <ConsumerChartsSkeleton />
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

      {/* 小売売上高チャート */}
      <div id="retail-sales">
        <RetailSalesChart
          data={dashboardData?.retail_sales ?? null}
          controlData={dashboardData?.retail_control ?? null}
        />
      </div>

      {/* シカゴ連銀小売指数（CARTS）チャート */}
      <div id="carts">
        <CartsChart data={dashboardData?.carts ?? null} />
      </div>

      {/* Affinityカード支出チャート */}
      <div id="affinity-spend">
        <AffinitySpendChart data={dashboardData?.affinity_spend ?? null} />
      </div>

      {/* Visa支出モメンタム指数チャート */}
      <div id="visa-spending">
        <VisaSpendingChart data={dashboardData?.visa_spending ?? null} />
      </div>

      {/* 自動車販売台数チャート */}
      <div id="total-vehicle-sales">
        <TotalVehicleSalesChart data={dashboardData?.total_vehicle_sales ?? null} />
      </div>

      {/* Redbook小売売上高指数チャート */}
      <div id="redbook">
        <RedbookChart data={dashboardData?.redbook ?? null} />
      </div>

      {/* クレジットカードローン残高チャート */}
      <div id="consumer-credit">
        <ConsumerCreditChart data={dashboardData?.consumer_credit ?? null} />
      </div>

    </div>
  )
}

/**
 * スケルトンローダー
 * データ取得中に表示される骨組み
 */
function ConsumerChartsSkeleton() {
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
        <div style={{ marginTop: 16, color: '#666' }}>消費データを読み込み中...</div>
      </div>
    </div>
  )
}
