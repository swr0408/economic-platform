/**
 * NZ 貿易財/非貿易財チャートコンポーネント
 *
 * データ:
 * - Tradable（貿易財）YoY%
 * - Non-Tradable（非貿易財）YoY%
 *
 * データソース:
 * - Stats NZ Consumers Price Index
 * - https://www.stats.govt.nz/indicators/consumers-price-index-cpi/
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'

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

import type { NzTradedNontradedData } from '../../../../hooks/useDashboardData'

interface NzTradedNontradedChartProps {
  data: NzTradedNontradedData | null
}

interface ChartDataPoint {
  date: string
  tradable_yoy: number | null
  non_tradable_yoy: number | null
}

const COLORS = {
  tradable: '#2563eb',
  non_tradable: '#dc2626',
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

export default function NzTradedNontradedChart({ data }: NzTradedNontradedChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>('default')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter((item) => item.tradable_yoy !== null || item.non_tradable_yoy !== null)
      .map((item) => ({
        date: item.date,
        tradable_yoy: item.tradable_yoy,
        non_tradable_yoy: item.non_tradable_yoy,
      }))
  }, [data])

  const sortedData = useSortedData(chartData)

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="貿易財 / 非貿易財" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="貿易財 / 非貿易財" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  return (
    <div id="traded-nontraded">
      <ChartContainer
        title="貿易財 / 非貿易財（前年比）"
        showPeriodSelector={false}
        dataSource="Stats NZ"
        sourceUrl="https://www.stats.govt.nz/indicators/consumers-price-index-cpi/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: 'Tradable',
              value: latest?.tradable_yoy,
              color: COLORS.tradable,
              format: 'percent',
            },
            {
              label: 'Non-Tradable',
              value: latest?.non_tradable_yoy,
              color: COLORS.non_tradable,
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
                        onClick={() => window.open('/compare?s=nz_traded_yoy&s=nz_nontraded_yoy', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'tradable_yoy', color: COLORS.tradable, name: '貿易財', hide: hiddenSeries.has('tradable_yoy') },
                      { dataKey: 'non_tradable_yoy', color: COLORS.non_tradable, name: '非貿易財', hide: hiddenSeries.has('non_tradable_yoy') },
                    ]}
                    yAxisFormatter={(v) => `${v}%`}
                    tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                    yDomain={['dataMin - 1', 'dataMax + 1']}
                    showZeroLine={true}
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
                <MarketImpactTab indicatorId="nz_cpi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
