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
import GSCPIChart from './inflation/GSCPIChart'
import InflationNowcastingTable from './inflation/InflationNowcastingTable'
import ImportExportPriceChart from './inflation/ImportExportPriceChart'
import RetailFoodServicesPriceChart from './inflation/RetailFoodServicesPriceChart'
import NYInflationExpectationsChart from './inflation/NYInflationExpectationsChart'
import MichiganInflationExpectationsChart from './inflation/MichiganInflationExpectationsChart'
import TrimmedMeanPCEChart from './inflation/TrimmedMeanPCEChart'
import MedianCPIChart from './inflation/MedianCPIChart'

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
          <ChartWrapper id="median-cpi">
            <MedianCPIChart
              data={dashboardData?.median_cpi ?? null}
            />
          </ChartWrapper>
          <ChartWrapper id="pce-deflator">
            <PCEDeflatorChart
              pceData={dashboardData?.pce_deflator ?? null}
              corePceData={dashboardData?.core_pce_deflator ?? null}
            />
          </ChartWrapper>
          <ChartWrapper id="trimmed-mean-pce">
            <TrimmedMeanPCEChart
              data={dashboardData?.trimmed_mean_pce ?? null}
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
          <ChartWrapper id="gscpi">
            <GSCPIChart
              gscpiData={dashboardData?.gscpi ?? null}
            />
          </ChartWrapper>
          <ChartWrapper id="inflation-nowcasting">
            <InflationNowcastingTable
              nowcastingData={dashboardData?.inflation_nowcasting ?? null}
            />
          </ChartWrapper>
          <ChartWrapper id="import-export-price">
            <ImportExportPriceChart
              importExportPriceData={dashboardData?.import_export_price ?? null}
            />
          </ChartWrapper>
          <ChartWrapper id="retail-food-services-price">
            <RetailFoodServicesPriceChart
              retailFoodServicesPriceData={dashboardData?.retail_food_services_price ?? null}
            />
          </ChartWrapper>
          <ChartWrapper id="ny-inflation-expectations">
            <NYInflationExpectationsChart
              nyInflationExpectationsData={dashboardData?.ny_inflation_expectations ?? null}
            />
          </ChartWrapper>
          <ChartWrapper id="michigan-inflation-expectations">
            <MichiganInflationExpectationsChart
              michiganInflationExpectationsData={dashboardData?.michigan_inflation_expectations ?? null}
            />
          </ChartWrapper>
        </>
      )}
    </DashboardContainer>
  )
}
