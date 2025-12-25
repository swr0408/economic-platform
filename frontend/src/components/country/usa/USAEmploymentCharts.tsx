/**
 * 米国雇用チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 * DashboardContainerを使用してローディング・エラー処理を共通化
 */
import { useUSAEmploymentDashboard } from '../../../hooks/useDashboardData'
import { DashboardContainer, ChartWrapper } from './common/DashboardContainer'

// チャートコンポーネント
import UnemploymentRateChart from './employment/UnemploymentRateChart'
import UnemploymentByReasonChart from './employment/UnemploymentByReasonChart'
import NonfarmPayrollsChart from './employment/NonfarmPayrollsChart'
import FullPartTimeChart from './employment/FullPartTimeChart'
import CBJobsLaborChart from './employment/CBJobsLaborChart'

export default function USAEmploymentCharts() {
  const queryResult = useUSAEmploymentDashboard()

  return (
    <DashboardContainer queryResult={queryResult} categoryName="雇用">
      {(dashboardData) => (
        <>
          <ChartWrapper id="unemployment">
            <UnemploymentRateChart data={dashboardData?.unemployment_rate ?? null} />
          </ChartWrapper>

          <ChartWrapper id="unemployment-by-reason">
            <UnemploymentByReasonChart data={dashboardData?.unemployment_by_reason ?? null} />
          </ChartWrapper>

          <ChartWrapper id="cb-jobs-labor">
            <CBJobsLaborChart
              data={dashboardData?.cb_jobs_labor ?? null}
              unemploymentData={dashboardData?.unemployment_rate ?? null}
            />
          </ChartWrapper>

          <ChartWrapper id="nonfarm-payrolls">
            <NonfarmPayrollsChart data={dashboardData?.nonfarm_payrolls ?? null} />
          </ChartWrapper>

          <ChartWrapper id="fullpart-time">
            <FullPartTimeChart data={dashboardData?.fullpart_time_employment ?? null} />
          </ChartWrapper>
        </>
      )}
    </DashboardContainer>
  )
}
