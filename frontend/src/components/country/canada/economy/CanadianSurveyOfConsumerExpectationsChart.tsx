/**
 * カナダ消費者期待調査（CSCE）チャートコンポーネント
 *
 * Bank of CanadaのCanadian Survey of Consumer Expectationsから
 * 賃金・雇用・所得・支出・インフレ期待の推移を表示
 *
 * データソース:
 * - Bank of Canada Valet API
 * - CSCE Group
 *
 * 発表スケジュール:
 * - 四半期（1月, 4月, 7月, 10月）10:30 ET（BOSと同時）
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  usePeriodFiltering,
  useViewModePeriodManagement,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  ViewModeButtonGroup,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import { CHART_COLORS } from '../../usa/common/chartConstants'

import type { CaCsceData } from '../../../../hooks/useDashboardData'

interface CanadianSurveyOfConsumerExpectationsChartProps {
  data: CaCsceData | null
}

type ViewMode = 'expectations' | 'labor' | 'inflation'

const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'expectations', label: '賃金・所得' },
  { mode: 'labor', label: '雇用' },
  { mode: 'inflation', label: 'インフレ' },
]

const COLORS = {
  wage_next_12m: CHART_COLORS.primary,
  wage_past_12m: '#8c8c8c',
  income_growth: '#52c41a',
  spending_growth: '#faad14',
  prob_lose_job: '#ff4d4f',
  prob_leave_job: '#722ed1',
  prob_find_job: '#13c2c2',
  inflation_1y: CHART_COLORS.primary,
  inflation_2y: '#52c41a',
  inflation_5y: '#faad14',
}

export default function CanadianSurveyOfConsumerExpectationsChart({ data }: CanadianSurveyOfConsumerExpectationsChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('expectations')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    expectations: 'default' as const,
    labor: 'default' as const,
    inflation: 'default' as const,
  })

  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        date: item.date,
        wage_next_12m: item.wage_next_12m ?? null,
        wage_past_12m: item.wage_past_12m ?? null,
        income_growth: item.income_growth ?? null,
        spending_growth: item.spending_growth ?? null,
        prob_lose_job: item.prob_lose_job ?? null,
        prob_leave_job: item.prob_leave_job ?? null,
        prob_find_job: item.prob_find_job ?? null,
        inflation_1y: item.inflation_1y ?? null,
        inflation_2y: item.inflation_2y ?? null,
        inflation_5y: item.inflation_5y ?? null,
      }))
  }, [data])

  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = chartData.length > 0
  const latestValue = data?.latest

  if (data === null) {
    return <LoadingChart title="Canadian Survey of Consumer Expectations（CSCE）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="Canadian Survey of Consumer Expectations（CSCE）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const getLatestDisplay = () => {
    if (viewMode === 'expectations') {
      return {
        label: '賃金成長期待（次の12ヶ月）',
        value: latestValue?.wage_next_12m,
        color: COLORS.wage_next_12m,
      }
    }
    if (viewMode === 'labor') {
      return {
        label: '失業確率（次の12ヶ月）',
        value: latestValue?.prob_lose_job,
        color: COLORS.prob_lose_job,
      }
    }
    return {
      label: '1年先インフレ期待',
      value: latestValue?.inflation_1y,
      color: COLORS.inflation_1y,
    }
  }

  const latestDisplay = getLatestDisplay()

  const getExpectationsLines = () => [
    { dataKey: 'wage_next_12m', color: COLORS.wage_next_12m, name: '賃金成長期待（次の12ヶ月）', hide: hiddenSeries.has('wage_next_12m') },
    { dataKey: 'wage_past_12m', color: COLORS.wage_past_12m, name: '賃金成長実績（過去12ヶ月）', hide: hiddenSeries.has('wage_past_12m') },
    { dataKey: 'income_growth', color: COLORS.income_growth, name: '所得成長期待', hide: hiddenSeries.has('income_growth') },
    { dataKey: 'spending_growth', color: COLORS.spending_growth, name: '支出成長期待', hide: hiddenSeries.has('spending_growth') },
  ]

  const getLaborLines = () => [
    { dataKey: 'prob_lose_job', color: COLORS.prob_lose_job, name: '失業確率', hide: hiddenSeries.has('prob_lose_job'), yAxisId: 'left' as const },
    { dataKey: 'prob_leave_job', color: COLORS.prob_leave_job, name: '自発的退職確率', hide: hiddenSeries.has('prob_leave_job'), yAxisId: 'left' as const },
    { dataKey: 'prob_find_job', color: COLORS.prob_find_job, name: '求職成功確率（右軸）', hide: hiddenSeries.has('prob_find_job'), yAxisId: 'right' as const },
  ]

  const getInflationLines = () => [
    { dataKey: 'inflation_1y', color: COLORS.inflation_1y, name: '1年先インフレ期待', hide: hiddenSeries.has('inflation_1y') },
    { dataKey: 'inflation_2y', color: COLORS.inflation_2y, name: '2年先インフレ期待', hide: hiddenSeries.has('inflation_2y') },
    { dataKey: 'inflation_5y', color: COLORS.inflation_5y, name: '5年先インフレ期待', hide: hiddenSeries.has('inflation_5y') },
  ]

  return (
    <div id="ca-csce-chart">
      <ChartContainer
        title="Canadian Survey of Consumer Expectations（CSCE）"
        showPeriodSelector={false}
        dataSource="Bank of Canada"
        sourceUrl="https://www.bankofcanada.ca/publications/canadian-survey-of-consumer-expectations/"
      >
        <SimpleLatestValueBox
          label={latestDisplay.label}
          value={latestDisplay.value}
          date={latestValue?.date}
          format="number"
          decimals={1}
          unit="%"
          valueColor={latestDisplay.color}
          nextRelease={data.next_release ?? null}
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=canadian_survey_of_consumer_expectations', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

        {viewMode === 'expectations' && (
          <StandardLineChart
            data={filteredData}
            lines={getExpectationsLines()}
            yAxisFormatter={(v) => `${v}%`}
            yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
            onLegendClick={handleLegendClick}
          />
        )}

        {viewMode === 'labor' && (
          <StandardLineChart
            data={filteredData}
            lines={getLaborLines()}
            yAxisFormatter={(v) => `${v}%`}
            yDomain={['dataMin - 2', 'dataMax + 2']}
            showRightYAxis={true}
            rightYAxisFormatter={(v) => `${v}%`}
            rightYDomain={['dataMin - 2', 'dataMax + 2']}
            onLegendClick={handleLegendClick}
          />
        )}

        {viewMode === 'inflation' && (
          <StandardLineChart
            data={filteredData}
            lines={getInflationLines()}
            yAxisFormatter={(v) => `${v}%`}
            yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
            onLegendClick={handleLegendClick}
          />
        )}
      </ChartContainer>
    </div>
  )
}
