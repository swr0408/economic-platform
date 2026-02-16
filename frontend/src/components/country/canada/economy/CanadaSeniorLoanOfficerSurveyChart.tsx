/**
 * カナダ貸出態度調査（SLOS）チャートコンポーネント
 *
 * Bank of CanadaのSenior Loan Officer Surveyから
 * 企業向け・住宅ローン・非住宅ローンの貸出条件（Balance of Opinion）を表示
 *
 * 正(+) = 厳格化（tightening）、負(-) = 緩和（easing）
 *
 * データソース:
 * - Bank of Canada Valet API
 * - SLOS Group
 *
 * 発表スケジュール:
 * - 四半期 10:30 ET
 */
import { useMemo, useState } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  usePeriodFiltering,
  useHiddenSeries,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import { CHART_COLORS } from '../../usa/common/chartConstants'

import type { CaSlosData } from '../../../../hooks/useDashboardData'

interface CanadaSeniorLoanOfficerSurveyChartProps {
  data: CaSlosData | null
}

const COLORS = {
  business: CHART_COLORS.primary,
  mortgage: '#52c41a',
  non_mortgage: '#faad14',
}

export default function CanadaSeniorLoanOfficerSurveyChart({ data }: CanadaSeniorLoanOfficerSurveyChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>('default')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        date: item.date,
        business: item.business ?? null,
        mortgage: item.mortgage ?? null,
        non_mortgage: item.non_mortgage ?? null,
      }))
  }, [data])

  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2005,
  })

  const hasData = chartData.length > 0
  const latestValue = data?.latest

  if (data === null) {
    return <LoadingChart title="Senior Loan Officer Survey（SLOS）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="Senior Loan Officer Survey（SLOS）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const lines = [
    { dataKey: 'business', color: COLORS.business, name: '企業向け貸出条件', hide: hiddenSeries.has('business') },
    { dataKey: 'mortgage', color: COLORS.mortgage, name: '住宅ローン貸出条件', hide: hiddenSeries.has('mortgage') },
    { dataKey: 'non_mortgage', color: COLORS.non_mortgage, name: '非住宅ローン貸出条件', hide: hiddenSeries.has('non_mortgage') },
  ]

  return (
    <div id="ca-slos-chart">
      <ChartContainer
        title="Senior Loan Officer Survey（SLOS）"
        showPeriodSelector={false}
        dataSource="Bank of Canada"
        sourceUrl="https://www.bankofcanada.ca/publications/slos/"
      >
        <SimpleLatestValueBox
          label="企業向け貸出条件（BO）"
          value={latestValue?.business}
          date={latestValue?.date}
          format="number"
          decimals={1}
          unit="%"
          valueColor={COLORS.business}
          nextRelease={data.next_release ?? null}
        />

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=canada_senior_loan_officer_survey', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

        <StandardLineChart
          data={filteredData}
          lines={lines}
          yAxisFormatter={(v) => `${v}%`}
          yDomain={['dataMin - 5', 'dataMax + 5']}
          showZeroLine={true}
          onLegendClick={handleLegendClick}
        />
      </ChartContainer>
    </div>
  )
}
