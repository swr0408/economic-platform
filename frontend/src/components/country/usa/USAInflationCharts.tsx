/**
 * 米国物価チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 * DashboardContainerを使用してローディング・エラー処理を共通化
 */
import { useUSAInflationDashboard } from '../../../hooks/useDashboardData'
import { DashboardContainer, ChartWrapper } from './common/DashboardContainer'

// チャートコンポーネント
import CPIChart from './inflation/CPIChart'

export default function USAInflationCharts() {
  const queryResult = useUSAInflationDashboard()

  return (
    <DashboardContainer queryResult={queryResult} categoryName="物価">
      {(dashboardData) => (
        <>
          <ChartWrapper id="cpi">
            <CPIChart
              cpiData={dashboardData?.cpi ?? null}
              coreCpiData={dashboardData?.core_cpi ?? null}
            />
          </ChartWrapper>
        </>
      )}
    </DashboardContainer>
  )
}
