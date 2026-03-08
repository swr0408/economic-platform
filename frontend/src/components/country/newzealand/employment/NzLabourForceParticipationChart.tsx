/**
 * NZ 労働参加率チャートコンポーネント
 *
 * データ:
 * - Labour Force Participation Rate（労働参加率）- 季節調整済み（%）
 *
 * データソース:
 * - Stats NZ Household Labour Force Survey (HLFS)
 * - https://www.stats.govt.nz/indicators/?filters=Employment%20and%20unemployment
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
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { NzLabourForceParticipationData } from '../../../../hooks/useDashboardData'

interface NzLabourForceParticipationChartProps {
  data: NzLabourForceParticipationData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
}

const CHART_COLOR = '#7c3aed'

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

export default function NzLabourForceParticipationChart({ data }: NzLabourForceParticipationChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>('default')

  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter((item) => item.value !== null)
      .map((item) => ({
        date: item.date,
        value: item.value,
      }))
  }, [data])

  const sortedData = useSortedData(chartData)

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2016,
  })

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="労働参加率" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="労働参加率" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  return (
    <div id="labour-force-participation">
      <ChartContainer
        title="労働参加率"
        showPeriodSelector={false}
        dataSource="Stats NZ"
        sourceUrl="https://www.stats.govt.nz/indicators/?filters=Employment%20and%20unemployment&topicFiltersID=160"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="労働参加率"
          value={latest?.value}
          valueColor={CHART_COLOR}
          format="percent"
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
                  <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=nz_labour_force_participation', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'value', color: CHART_COLOR, name: '労働参加率' },
                    ]}
                    yAxisFormatter={(v) => `${v}%`}
                    tooltipValueFormatter={(v) => `${v.toFixed(1)}%`}
                    yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                    xAxisFormatter={formatQuarterLabel}
                    tooltipLabelFormatter={formatQuarterLabelJP}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="nz_labour_force_participation" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
