/**
 * AU Inflation Expectations Chart Component
 * オーストラリア インフレ期待チャート
 *
 * データ項目:
 * - value: Consumer Inflation Expectations (%)
 *
 * データソース: Melbourne Institute
 */

import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PeriodValue } from '../../../common/PeriodSelector'

import {
  CHART_COLORS,
} from '../../usa/common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { AuInflationExpectationsData, AuInflationExpectationsDataPoint } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface ChartDataPoint {
  date: string
  value: number | null
}

interface AuInflationExpectationsChartProps {
  data: AuInflationExpectationsData | null
}

// カラー設定
const CHART_COLOR = CHART_COLORS.primary

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function AuInflationExpectationsChart({ data }: AuInflationExpectationsChartProps) {
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データを変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter((d: AuInflationExpectationsDataPoint) => d.value !== null)
      .map((d: AuInflationExpectationsDataPoint) => ({
        date: d.date,
        value: d.value,
      }))
  }, [data])

  // データを日付昇順にソート
  const sortedData = useSortedData(chartData)

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="インフレ期待" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="インフレ期待" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  return (
    <div id="au-inflation-expectations-chart">
      <ChartContainer
        title="インフレ期待"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="Melbourne Institute"
        sourceUrl="https://melbourneinstitute.unimelb.edu.au/news/news/macroeconomics/survey-of-consumer-inflationary-and-wage-expectations"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="インフレ期待"
          value={latest?.value}
          unit="%"
          date={latest?.date}
          valueColor={CHART_COLOR}
          nextRelease={data?.next_release ?? undefined}
          format="percent"
        />

        {/* タブ切替 */}
        <Tabs
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <TimeSeriesView
                  data={sortedData}
                  hiddenSeries={hiddenSeries}
                  handleLegendClick={handleLegendClick}
                />
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="au_inflation_expectations" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}

// =============================================================================
// 時系列ビュー
// =============================================================================

function TimeSeriesView({
  data,
  hiddenSeries,
  handleLegendClick,
}: {
  data: ChartDataPoint[]
  hiddenSeries: Set<string>
  handleLegendClick: (dataKey: string) => void
}) {
  const { filteredData, selectedPeriod, setSelectedPeriod } = usePeriodFilteringWithState(data)

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            onClick={() => window.open('/compare?s=au_inflation_expectations', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      <StandardLineChart
        data={filteredData}
        lines={[
          { dataKey: 'value', color: CHART_COLOR, name: 'インフレ期待', hide: hiddenSeries.has('value') },
        ]}
        yAxisFormatter={(v) => `${v}%`}
        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
        tooltipValueFormatter={(v) => `${v.toFixed(1)}%`}
        onLegendClick={handleLegendClick}
      />
    </>
  )
}

// PeriodSelector state wrapper
function usePeriodFilteringWithState(data: ChartDataPoint[]) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(10)
  const filteredData = usePeriodFiltering(data, {
    selectedPeriod,
    defaultStartYear: 2015,
  })
  return { filteredData, selectedPeriod, setSelectedPeriod }
}
