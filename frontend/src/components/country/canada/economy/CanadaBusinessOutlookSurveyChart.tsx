/**
 * カナダ企業景況感調査（BOS）チャートコンポーネント
 *
 * Bank of CanadaのBusiness Outlook Surveyから各Balance of Opinionの推移を表示
 *
 * データソース:
 * - Bank of Canada Valet API
 * - Business Outlook Survey (BOS)
 *
 * 発表スケジュール:
 * - 四半期（1月, 4月, 7月, 10月）10:30 ET
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

import type { CaBosData } from '../../../../hooks/useDashboardData'

interface CanadaBusinessOutlookSurveyChartProps {
  data: CaBosData | null
}

type ViewMode = 'sentiment' | 'prices'

const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'sentiment', label: '景況感' },
  { mode: 'prices', label: '物価' },
]

const COLORS = {
  future_sales: CHART_COLORS.primary,
  investment: '#52c41a',
  employment: '#faad14',
  input_prices: '#ff4d4f',
  output_prices: '#722ed1',
  credit: '#13c2c2',
}

export default function CanadaBusinessOutlookSurveyChart({ data }: CanadaBusinessOutlookSurveyChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('sentiment')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    sentiment: 20 as const,
    prices: 20 as const,
  })

  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        date: item.date,
        future_sales: item.future_sales ?? null,
        investment: item.investment ?? null,
        employment: item.employment ?? null,
        input_prices: item.input_prices ?? null,
        output_prices: item.output_prices ?? null,
        credit: item.credit ?? null,
      }))
  }, [data])

  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2005,
  })

  const hasData = chartData.length > 0
  const latestValue = data?.latest

  if (data === null) {
    return <LoadingChart title="Business Outlook Survey（BOS）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="Business Outlook Survey（BOS）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const getLatestDisplay = () => {
    if (viewMode === 'sentiment') {
      return {
        label: '将来売上見通し（BO）',
        value: latestValue?.future_sales,
        color: COLORS.future_sales,
      }
    }
    return {
      label: '投入価格インフレ（BO）',
      value: latestValue?.input_prices,
      color: COLORS.input_prices,
    }
  }

  const latestDisplay = getLatestDisplay()

  const getSentimentLines = () => [
    { dataKey: 'future_sales', color: COLORS.future_sales, name: '将来売上見通し', hide: hiddenSeries.has('future_sales') },
    { dataKey: 'investment', color: COLORS.investment, name: '設備投資見通し', hide: hiddenSeries.has('investment') },
    { dataKey: 'employment', color: COLORS.employment, name: '雇用見通し', hide: hiddenSeries.has('employment') },
    { dataKey: 'credit', color: COLORS.credit, name: '信用条件', hide: hiddenSeries.has('credit') },
  ]

  const getPriceLines = () => [
    { dataKey: 'input_prices', color: COLORS.input_prices, name: '投入価格インフレ', hide: hiddenSeries.has('input_prices') },
    { dataKey: 'output_prices', color: COLORS.output_prices, name: '産出価格インフレ', hide: hiddenSeries.has('output_prices') },
  ]

  return (
    <div id="ca-bos-chart">
      <ChartContainer
        title="Business Outlook Survey（BOS）"
        showPeriodSelector={false}
        dataSource="Bank of Canada"
        sourceUrl="https://www.bankofcanada.ca/publications/bos/"
      >
        <SimpleLatestValueBox
          label={latestDisplay.label}
          value={latestDisplay.value}
          date={latestValue?.date}
          format="number"
          decimals={0}
          unit="pt"
          valueColor={latestDisplay.color}
          nextRelease={data.next_release ?? null}
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=canada_bos_future_sales', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

        {viewMode === 'sentiment' && (
          <StandardLineChart
            data={filteredData}
            lines={getSentimentLines()}
            yAxisFormatter={(v) => `${v}`}
            yDomain={['dataMin - 5', 'dataMax + 5']}
            showZeroLine={true}
            tooltipValueFormatter={(v) => (v != null ? `${v}pt` : 'N/A')}
            onLegendClick={handleLegendClick}
          />
        )}

        {viewMode === 'prices' && (
          <StandardLineChart
            data={filteredData}
            lines={getPriceLines()}
            yAxisFormatter={(v) => `${v}`}
            yDomain={['dataMin - 5', 'dataMax + 5']}
            showZeroLine={true}
            tooltipValueFormatter={(v) => (v != null ? `${v}pt` : 'N/A')}
            onLegendClick={handleLegendClick}
          />
        )}
      </ChartContainer>
    </div>
  )
}
