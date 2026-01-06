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
import CPICategoriesChart from './inflation/CPICategoriesChart'
import PCEDeflatorChart from './inflation/PCEDeflatorChart'
import PPIChart from './inflation/PPIChart'
import PPICategoriesChart from './inflation/PPICategoriesChart'
import HousingIndicatorsChart from './inflation/HousingIndicatorsChart'
import ZillowRentCPIChart from './inflation/ZillowRentCPIChart'

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
          <ChartWrapper id="cpi-categories">
            <CPICategoriesChart
              categoriesData={dashboardData?.cpi_categories ?? null}
            />
          </ChartWrapper>
          <ChartWrapper id="pce-deflator">
            <PCEDeflatorChart
              pceData={dashboardData?.pce_deflator ?? null}
              corePceData={dashboardData?.core_pce_deflator ?? null}
            />
          </ChartWrapper>
          <ChartWrapper id="housing-indicators">
            <HousingIndicatorsChart
              housingData={dashboardData?.housing_indicators ?? null}
            />
          </ChartWrapper>
          <ChartWrapper id="zillow-rent-cpi">
            <ZillowRentCPIChart
              zillowData={dashboardData?.zillow_rent_index ?? null}
              rentCPIData={dashboardData?.rent_cpi ?? null}
            />
          </ChartWrapper>
          <ChartWrapper id="ppi">
            <PPIChart
              ppiData={dashboardData?.ppi ?? null}
              corePpiData={dashboardData?.core_ppi ?? null}
            />
          </ChartWrapper>
          <ChartWrapper id="ppi-categories">
            <PPICategoriesChart
              categoriesData={dashboardData?.ppi_categories ?? null}
            />
          </ChartWrapper>
        </>
      )}
    </DashboardContainer>
  )
}
