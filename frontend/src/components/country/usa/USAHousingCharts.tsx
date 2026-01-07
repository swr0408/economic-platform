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
        </>
      )}
    </DashboardContainer>
  )
}
