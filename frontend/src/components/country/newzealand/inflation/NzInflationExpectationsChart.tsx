/**
 * NZ インフレ期待チャートコンポーネント
 *
 * データ:
 * - 1 year out (SOE.Q.E210.na)
 * - 2 years out (SOE.Q.E215.na)
 * - 5 years out (SOE.Q.E220.na)
 * - 10 years out (SOE.Q.E230.na)
 *
 * データソース:
 * - RBNZ Survey of Expectations
 * - https://www.rbnz.govt.nz/statistics/series/economic-indicators/survey-of-expectations
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PeriodValue } from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { NzInflationExpectationsData } from '../../../../hooks/useDashboardData'

interface NzInflationExpectationsChartProps {
  data: NzInflationExpectationsData | null
}

interface ChartDataPoint {
  date: string
  one_year: number | null
  two_year: number | null
  five_year: number | null
  ten_year: number | null
}

const COLORS = {
  one_year: '#dc2626',
  two_year: '#2563eb',
  five_year: '#16a34a',
  ten_year: '#9333ea',
}

const formatQuarterLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  const monthNum = parseInt(month, 10)
  const quarter = Math.ceil(monthNum / 3)
  return `${year}/Q${quarter}`
}

const formatQuarterLabelJP = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  const monthNum = parseInt(month, 10)
  const quarter = Math.ceil(monthNum / 3)
  return `${year}年 Q${quarter}`
}

export default function NzInflationExpectationsChart({ data }: NzInflationExpectationsChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>('default')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter((item) =>
        item.one_year !== null || item.two_year !== null ||
        item.five_year !== null || item.ten_year !== null
      )
      .map((item) => ({
        date: item.date,
        one_year: item.one_year,
        two_year: item.two_year,
        five_year: item.five_year,
        ten_year: item.ten_year,
      }))
  }, [data])

  const sortedData = useSortedData(chartData)

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="インフレ期待" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="インフレ期待" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  return (
    <div id="inflation-expectations">
      <ChartContainer
        title="インフレ期待（Survey of Expectations）"
        showPeriodSelector={false}
        dataSource="RBNZ"
        sourceUrl="https://www.rbnz.govt.nz/statistics/series/economic-indicators/survey-of-expectations"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '1 Year',
              value: latest?.one_year,
              color: COLORS.one_year,
              format: 'percent',
            },
            {
              label: '2 Years',
              value: latest?.two_year,
              color: COLORS.two_year,
              format: 'percent',
            },
            {
              label: '5 Years',
              value: latest?.five_year,
              color: COLORS.five_year,
              format: 'percent',
            },
            {
              label: '10 Years',
              value: latest?.ten_year,
              color: COLORS.ten_year,
              format: 'percent',
            },
          ]}
          date={latest?.date}
          dateFormatter={formatQuarterLabelJP}
          nextRelease={data?.next_release ? { date: data.next_release.date } : undefined}
        />

        {/* タブ切替 */}
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=nz_inflation_exp_1y&s=nz_inflation_exp_2y', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'one_year', color: COLORS.one_year, name: '1年先', hide: hiddenSeries.has('one_year') },
                      { dataKey: 'two_year', color: COLORS.two_year, name: '2年先', hide: hiddenSeries.has('two_year') },
                      { dataKey: 'five_year', color: COLORS.five_year, name: '5年先', hide: hiddenSeries.has('five_year') },
                      { dataKey: 'ten_year', color: COLORS.ten_year, name: '10年先', hide: hiddenSeries.has('ten_year') },
                    ]}
                    yAxisFormatter={(v) => `${v}%`}
                    tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                    yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                    xAxisFormatter={formatQuarterLabel}
                    tooltipLabelFormatter={formatQuarterLabelJP}
                    onLegendClick={handleLegendClick}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="nz_inflation_expectations" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
