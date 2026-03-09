/**
 * NZ 賃金チャートコンポーネント
 *
 * データ:
 * - All Salary and Wage Rates Index（全給与・賃金率指数）- LCIQ.SG53Z9
 * - Average Hourly Earnings（平均時給）- QEMQ.SASZ9A
 * - QoQ%（前期比）/ YoY%（前年比）
 *
 * データソース:
 * - Stats NZ Labour Cost Index (LCI)
 * - Stats NZ Quarterly Employment Survey (QES)
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
  StandardBarChart,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'

import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { NzWagesData } from '../../../../hooks/useDashboardData'

interface NzWagesChartProps {
  data: NzWagesData | null
}

interface ChartDataPoint {
  date: string
  wage_index_qoq: number | null
  hourly_earnings_qoq: number | null
  wage_index_yoy: number | null
  hourly_earnings_yoy: number | null
}

const COLORS = {
  wage_index: '#2563eb',
  hourly_earnings: '#dc2626',
}

type DataKind = 'qoq' | 'yoy'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'qoq', label: '前期比' },
]

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

export default function NzWagesChart({ data }: NzWagesChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    qoq: 5,
    yoy: 20,
  })

  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter((item) => item.wage_index_qoq !== null || item.hourly_earnings_qoq !== null ||
                         item.wage_index_yoy !== null || item.hourly_earnings_yoy !== null)
      .map((item) => ({
        date: item.date,
        wage_index_qoq: item.wage_index_qoq,
        hourly_earnings_qoq: item.hourly_earnings_qoq,
        wage_index_yoy: item.wage_index_yoy,
        hourly_earnings_yoy: item.hourly_earnings_yoy,
      }))
  }, [data])

  const sortedData = useSortedData(chartData)

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2018,
  })

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="賃金" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="賃金" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  return (
    <div id="wages">
      <ChartContainer
        title="賃金"
        showPeriodSelector={false}
        dataSource="Stats NZ"
        sourceUrl="https://www.stats.govt.nz/information-releases/labour-market-statistics/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '賃金率指数（前年比）',
              value: latest?.wage_index_yoy,
              color: COLORS.wage_index,
              format: 'percent',
            },
            {
              label: '平均時給（前年比）',
              value: latest?.hourly_earnings_yoy,
              color: COLORS.hourly_earnings,
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
                    <ViewModeButtonGroup
                      options={DATA_KIND_OPTIONS}
                      currentMode={dataKind}
                      onChange={setDataKind}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=nz_wages', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 前期比グラフ（棒グラフ） */}
                  {dataKind === 'qoq' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: 'wage_index_qoq', color: COLORS.wage_index, name: '賃金率指数（前期比）' },
                          { dataKey: 'hourly_earnings_qoq', color: COLORS.hourly_earnings, name: '平均時給（前期比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        xAxisFormatter={formatQuarterLabel}
                        tooltipLabelFormatter={formatQuarterLabelJP}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                      />
                    </>
                  )}

                  {/* 前年比グラフ（折れ線グラフ） */}
                  {dataKind === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'wage_index_yoy', color: COLORS.wage_index, name: '賃金率指数（前年比）', hide: hiddenSeries.has('wage_index_yoy') },
                          { dataKey: 'hourly_earnings_yoy', color: COLORS.hourly_earnings, name: '平均時給（前年比）', hide: hiddenSeries.has('hourly_earnings_yoy') },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        showZeroLine={true}
                        xAxisFormatter={formatQuarterLabel}
                        tooltipLabelFormatter={formatQuarterLabelJP}
                        onLegendClick={handleLegendClick}
                      />
                    </>
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="nz_wages" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
