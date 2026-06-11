/**
 * 米国消費チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 * DashboardContainerを使用してローディング・エラー処理を共通化
 */
import { useUSAConsumerDashboard } from '../../../hooks/useDashboardData'
import { DashboardContainer, ChartWrapper } from './common/DashboardContainer'

// チャートコンポーネント
import RetailSalesChart from './consumer/RetailSalesChart'
import AdvanceRealRetailSalesChart from './consumer/AdvanceRealRetailSalesChart'
import CartsChart from './consumer/CartsChart'
import AffinitySpendChart from './consumer/AffinitySpendChart'
import VisaSpendingChart from './consumer/VisaSpendingChart'
import TotalVehicleSalesChart from './consumer/TotalVehicleSalesChart'
import RedbookChart from './consumer/RedbookChart'
import ConsumerCreditChart from './consumer/ConsumerCreditChart'
import DelinquencyRateChart from './consumer/DelinquencyRateChart'
import CBConsumerConfidenceChart from './consumer/CBConsumerConfidenceChart'
import MichiganConsumerSentimentChart from './consumer/MichiganConsumerSentimentChart'
import PersonalSavingRateChart from './consumer/PersonalSavingRateChart'
import PersonalIncomeChart from './consumer/PersonalIncomeChart'
import DisposableIncomeChart from './consumer/DisposableIncomeChart'
import PCEChart from './consumer/PCEChart'
import PersonalConsumptionExpendituresServicesChart from './consumer/PersonalConsumptionExpendituresServicesChart'

export default function USAConsumerCharts() {
  const queryResult = useUSAConsumerDashboard()

  return (
    <DashboardContainer queryResult={queryResult} categoryName="消費">
      {(dashboardData) => (
        <>
          <ChartWrapper id="retail-sales">
            <RetailSalesChart
              data={dashboardData?.retail_sales ?? null}
              controlData={dashboardData?.retail_control ?? null}
            />
          </ChartWrapper>

          <ChartWrapper id="advance-real-retail-sales">
            <AdvanceRealRetailSalesChart data={dashboardData?.advance_real_retail_sales ?? null} />
          </ChartWrapper>

          <ChartWrapper id="carts">
            <CartsChart data={dashboardData?.carts ?? null} />
          </ChartWrapper>

          <ChartWrapper id="affinity-spend">
            <AffinitySpendChart data={dashboardData?.affinity_spend ?? null} />
          </ChartWrapper>

          <ChartWrapper id="visa-spending">
            <VisaSpendingChart data={dashboardData?.visa_spending ?? null} />
          </ChartWrapper>

          <ChartWrapper id="total-vehicle-sales">
            <TotalVehicleSalesChart data={dashboardData?.total_vehicle_sales ?? null} />
          </ChartWrapper>

          <ChartWrapper id="redbook">
            <RedbookChart data={dashboardData?.redbook ?? null} />
          </ChartWrapper>

          <ChartWrapper id="consumer-credit">
            <ConsumerCreditChart data={dashboardData?.consumer_credit ?? null} />
          </ChartWrapper>

          <ChartWrapper id="delinquency-rate">
            <DelinquencyRateChart data={dashboardData?.delinquency_rate ?? null} />
          </ChartWrapper>

          <ChartWrapper id="cb-consumer-confidence">
            <CBConsumerConfidenceChart data={dashboardData?.cb_consumer_confidence ?? null} />
          </ChartWrapper>

          <ChartWrapper id="michigan-consumer-sentiment">
            <MichiganConsumerSentimentChart data={dashboardData?.michigan_consumer_sentiment ?? null} />
          </ChartWrapper>

          <ChartWrapper id="pce">
            <PCEChart data={dashboardData?.pce ?? null} />
          </ChartWrapper>

          <ChartWrapper id="personal-consumption-services">
            <PersonalConsumptionExpendituresServicesChart data={dashboardData?.personal_consumption_expenditures_services ?? null} />
          </ChartWrapper>

          <ChartWrapper id="personal-saving-rate">
            <PersonalSavingRateChart data={dashboardData?.personal_saving_rate ?? null} />
          </ChartWrapper>

          <ChartWrapper id="personal-income">
            <PersonalIncomeChart data={dashboardData?.personal_income ?? null} />
          </ChartWrapper>

          <ChartWrapper id="disposable-income">
            <DisposableIncomeChart data={dashboardData?.disposable_income ?? null} />
          </ChartWrapper>
        </>
      )}
    </DashboardContainer>
  )
}
