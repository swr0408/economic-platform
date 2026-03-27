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
import ADPEmploymentChart from './employment/ADPEmploymentChart'
import FullPartTimeChart from './employment/FullPartTimeChart'
import CBJobsLaborChart from './employment/CBJobsLaborChart'
import MultipleJobsPartTimeChart from './employment/MultipleJobsPartTimeChart'
import JoltsIndeedChart from './employment/JoltsIndeedChart'
import HiresLayoffsChart from './employment/HiresLayoffsChart'
import JobOpeningsPerUnemployedChart from './employment/JobOpeningsPerUnemployedChart'
import NERPulseChart from './employment/NERPulseChart'
import InitialClaimsChart from './employment/InitialClaimsChart'
import ContinuedClaimsChart from './employment/ContinuedClaimsChart'
import ChallengerJobCutsChart from './employment/ChallengerJobCutsChart'
import AverageHourlyEarningsChart from './employment/AverageHourlyEarningsChart'
import LaborForceParticipationChart from './employment/LaborForceParticipationChart'
import ADPWageGrowthChart from './employment/ADPWageGrowthChart'
import AtlantaFedWageGrowthChart from './employment/AtlantaFedWageGrowthChart'
import IndeedWageGrowthChart from './employment/IndeedWageGrowthChart'
import PCEFoodRecreationChart from './employment/PCEFoodRecreationChart'
import EmploymentCostIndexChart from './employment/EmploymentCostIndexChart'
import UnitLaborCostChart from './employment/UnitLaborCostChart'
import NFIBCompensationChart from './employment/NFIBCompensationChart'
import NFIBCompensationUnemploymentChart from './employment/NFIBCompensationUnemploymentChart'
import OvertimeHoursChart from './employment/OvertimeHoursChart'
import UsAverageWeeklyWorkingHoursChart from './employment/UsAverageWeeklyWorkingHoursChart'
import SahmRuleChart from './employment/SahmRuleChart'

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

          <ChartWrapper id="sahm-rule">
            <SahmRuleChart data={dashboardData?.sahm_rule?.data ?? null} />
          </ChartWrapper>

          <ChartWrapper id="job-openings-per-unemployed">
            <JobOpeningsPerUnemployedChart data={dashboardData?.job_openings_per_unemployed ?? null} />
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

          <ChartWrapper id="multiple-jobs-parttime">
            <MultipleJobsPartTimeChart data={dashboardData?.multiple_jobs_parttime ?? null} />
          </ChartWrapper>

          <ChartWrapper id="adp-employment">
            <ADPEmploymentChart data={dashboardData?.adp_employment ?? null} />
          </ChartWrapper>

          <ChartWrapper id="ner-pulse">
            <NERPulseChart data={dashboardData?.ner_pulse ?? null} />
          </ChartWrapper>

          <ChartWrapper id="jolts-indeed">
            <JoltsIndeedChart data={dashboardData?.jolts_indeed ?? null} />
          </ChartWrapper>

          <ChartWrapper id="jolts-hires-layoffs">
            <HiresLayoffsChart data={dashboardData?.jolts_hires_layoffs ?? null} />
          </ChartWrapper>

          <ChartWrapper id="initial-claims">
            <InitialClaimsChart data={dashboardData?.initial_claims ?? null} />
          </ChartWrapper>

          <ChartWrapper id="continued-claims">
            <ContinuedClaimsChart data={dashboardData?.continued_claims ?? null} />
          </ChartWrapper>

          <ChartWrapper id="challenger-job-cuts">
            <ChallengerJobCutsChart data={dashboardData?.challenger_job_cuts ?? null} />
          </ChartWrapper>

          <ChartWrapper id="average-hourly-earnings">
            <AverageHourlyEarningsChart data={dashboardData?.average_hourly_earnings ?? null} />
          </ChartWrapper>

          <ChartWrapper id="labor-force-participation">
            <LaborForceParticipationChart data={dashboardData?.labor_force_participation ?? null} />
          </ChartWrapper>

          <ChartWrapper id="adp-wage-growth">
            <ADPWageGrowthChart data={dashboardData?.adp_wage_growth ?? null} />
          </ChartWrapper>

          <ChartWrapper id="atlanta-fed-wage">
            <AtlantaFedWageGrowthChart data={dashboardData?.atlanta_fed_wage ?? null} />
          </ChartWrapper>

          <ChartWrapper id="indeed-wage-tracker">
            <IndeedWageGrowthChart data={dashboardData?.indeed_wage_tracker ?? null} />
          </ChartWrapper>

          <ChartWrapper id="pce-food-recreation">
            <PCEFoodRecreationChart data={dashboardData?.pce_food_recreation ?? null} />
          </ChartWrapper>

          <ChartWrapper id="employment-cost-index">
            <EmploymentCostIndexChart data={dashboardData?.employment_cost_index ?? null} />
          </ChartWrapper>

          <ChartWrapper id="unit-labor-cost">
            <UnitLaborCostChart data={dashboardData?.unit_labor_cost ?? null} />
          </ChartWrapper>

          <ChartWrapper id="nfib-compensation">
            <NFIBCompensationChart data={dashboardData?.nfib_compensation ?? null} />
          </ChartWrapper>

          <ChartWrapper id="nfib-compensation-unemployment">
            <NFIBCompensationUnemploymentChart data={dashboardData?.nfib_compensation_unemployment ?? null} />
          </ChartWrapper>

          <ChartWrapper id="overtime-hours">
            <OvertimeHoursChart data={dashboardData?.overtime_hours ?? null} />
          </ChartWrapper>

          <ChartWrapper id="average-weekly-working-hours">
            <UsAverageWeeklyWorkingHoursChart data={dashboardData?.us_average_weekly_working_hours ?? null} />
          </ChartWrapper>
        </>
      )}
    </DashboardContainer>
  )
}
