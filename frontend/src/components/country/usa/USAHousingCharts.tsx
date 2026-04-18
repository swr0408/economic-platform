/**
 * 米国住宅チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 * DashboardContainerを使用してローディング・エラー処理を共通化
 */
import { useUSAHousingDashboard } from '../../../hooks/useDashboardData'
import { DashboardContainer, ChartWrapper } from './common/DashboardContainer'

// チャートコンポーネント
import MortgageRatesChart from './housing/MortgageRatesChart'
import RedfinCaseShillerChart from './housing/RedfinCaseShillerChart'
import NewHomeSalesChart from './housing/NewHomeSalesChart'
import PendingHomeSalesChart from './housing/PendingHomeSalesChart'
import ExistingHomeSalesChart from './housing/ExistingHomeSalesChart'
import NAHBHMIChart from './housing/NAHBHMIChart'
import HousingStartsPermitsChart from './housing/HousingStartsPermitsChart'
import RentalVacancyRateChart from './housing/RentalVacancyRateChart'

export default function USAHousingCharts() {
  const queryResult = useUSAHousingDashboard()

  return (
    <DashboardContainer queryResult={queryResult} categoryName="住宅">
      {(dashboardData) => (
        <>
          <ChartWrapper id="mortgage-rates">
            <MortgageRatesChart
              mortgageRatesData={dashboardData?.mortgage_rates ?? null}
            />
          </ChartWrapper>
          <ChartWrapper id="redfin-case-shiller">
            <RedfinCaseShillerChart
              redfinMedianPriceData={dashboardData?.redfin_median_price ?? null}
              caseShillerData={dashboardData?.case_shiller ?? null}
            />
          </ChartWrapper>
          <ChartWrapper id="new-home-sales">
            <NewHomeSalesChart
              newHomeSalesData={dashboardData?.new_home_sales ?? null}
            />
          </ChartWrapper>
          <ChartWrapper id="pending-home-sales">
            <PendingHomeSalesChart
              pendingHomeSalesData={dashboardData?.pending_home_sales ?? null}
            />
          </ChartWrapper>
          <ChartWrapper id="existing-home-sales">
            <ExistingHomeSalesChart
              existingHomeSalesData={dashboardData?.existing_home_sales ?? null}
            />
          </ChartWrapper>
          <ChartWrapper id="housing-starts-permits">
            <HousingStartsPermitsChart
              housingStartsPermitsData={dashboardData?.housing_starts_permits ?? null}
            />
          </ChartWrapper>
          <ChartWrapper id="nahb-hmi">
            <NAHBHMIChart
              nahbHMIData={dashboardData?.nahb_hmi ?? null}
            />
          </ChartWrapper>
          <ChartWrapper id="rental-vacancy-rate">
            <RentalVacancyRateChart
              rentalVacancyRateData={dashboardData?.rental_vacancy_rate ?? null}
            />
          </ChartWrapper>
        </>
      )}
    </DashboardContainer>
  )
}
