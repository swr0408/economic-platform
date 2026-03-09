/**
 * NZ 雇用者数チャートコンポーネント
 *
 * データ:
 * - Total Employed（総雇用者数）- 千人
 * - Full-time Employed（フルタイム雇用者数）- 千人
 * - Part-time Employed（パートタイム雇用者数）- 千人
 * - QoQ%（前期比）/ YoY%（前年比）
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

import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useHiddenSeries,
  useMultiValueQuarterlyTableData,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
  StandardBarChart,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'
import { QuarterlyTableWithDataTypes } from '../../usa/common/QuarterlyTable'

import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { NzNumberOfEmployeesData } from '../../../../hooks/useDashboardData'

interface NzNumberOfEmployeesChartProps {
  data: NzNumberOfEmployeesData | null
}

interface ChartDataPoint {
  date: string
  total: number | null
  fulltime: number | null
  parttime: number | null
  total_qoq: number | null
  fulltime_qoq: number | null
  parttime_qoq: number | null
  total_yoy: number | null
  fulltime_yoy: number | null
  parttime_yoy: number | null
}

const COLORS = {
  total: '#2563eb',
  fulltime: '#16a34a',
  parttime: '#dc2626',
}

type DataKind = 'value' | 'qoq' | 'yoy'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'value', label: '現数値' },
  { mode: 'qoq', label: '前期比' },
  { mode: 'yoy', label: '前年比' },
]

// 表示形式
type DisplayMode = 'chart' | 'heatmap'

const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

type QoQTableType = 'total' | 'fulltime' | 'parttime'

const QOQ_DATA_TYPE_OPTIONS: { type: QoQTableType; label: string; color: string; bgColor: string }[] = [
  { type: 'total', label: '総雇用者数', color: COLORS.total, bgColor: '#e6f0ff' },
  { type: 'fulltime', label: 'フルタイム', color: COLORS.fulltime, bgColor: '#e6f7e6' },
  { type: 'parttime', label: 'パートタイム', color: COLORS.parttime, bgColor: '#fff1f0' },
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

export default function NzNumberOfEmployeesChart({ data }: NzNumberOfEmployeesChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [dataKind, setDataKind] = useState<DataKind>('value')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [tableType, setTableType] = useState<QoQTableType>('total')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    value: 20,
    qoq: 5,
    yoy: 20,
  })

  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter((item) => item.total !== null)
      .map((item) => ({
        date: item.date,
        total: item.total,
        fulltime: item.fulltime,
        parttime: item.parttime,
        total_qoq: item.total_qoq,
        fulltime_qoq: item.fulltime_qoq,
        parttime_qoq: item.parttime_qoq,
        total_yoy: item.total_yoy,
        fulltime_yoy: item.fulltime_yoy,
        parttime_yoy: item.parttime_yoy,
      }))
  }, [data])

  const sortedData = useSortedData(chartData)

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2009,
  })

  // ヒートマップ用データ
  const quarterlyTableData = useMultiValueQuarterlyTableData(
    sortedData,
    {
      total: (item: ChartDataPoint) => item.total_qoq,
      fulltime: (item: ChartDataPoint) => item.fulltime_qoq,
      parttime: (item: ChartDataPoint) => item.parttime_qoq,
    },
    10
  )

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="雇用者数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="雇用者数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  return (
    <div id="number-of-employees">
      <ChartContainer
        title="雇用者数"
        showPeriodSelector={false}
        dataSource="Stats NZ"
        sourceUrl="https://www.stats.govt.nz/indicators/?filters=Employment%20and%20unemployment&topicFiltersID=160"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '総雇用者数',
              value: latest?.total,
              color: COLORS.total,
              format: 'number',
              unit: '千人',
            },
            {
              label: 'フルタイム',
              value: latest?.fulltime,
              color: COLORS.fulltime,
              format: 'number',
              unit: '千人',
            },
            {
              label: 'パートタイム',
              value: latest?.parttime,
              color: COLORS.parttime,
              format: 'number',
              unit: '千人',
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
                        onClick={() => window.open('/compare?s=nz_number_of_employees', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 原数値グラフ（折れ線グラフ） - パートタイムは右Y軸 */}
                  {dataKind === 'value' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'total', color: COLORS.total, name: '総雇用者数', hide: hiddenSeries.has('total') },
                          { dataKey: 'fulltime', color: COLORS.fulltime, name: 'フルタイム', hide: hiddenSeries.has('fulltime') },
                          { dataKey: 'parttime', color: COLORS.parttime, name: 'パートタイム（右軸）', hide: hiddenSeries.has('parttime'), yAxisId: 'right' },
                        ]}
                        yAxisFormatter={(v) => `${v.toLocaleString()}`}
                        tooltipValueFormatter={(v) => `${v.toLocaleString()} 千人`}
                        yDomain={['dataMin - 50', 'dataMax + 50']}
                        rightYAxisFormatter={(v) => `${v.toLocaleString()}`}
                        rightYDomain={['dataMin - 20', 'dataMax + 20']}
                        xAxisFormatter={formatQuarterLabel}
                        tooltipLabelFormatter={formatQuarterLabelJP}
                        onLegendClick={handleLegendClick}
                      />
                    </>
                  )}

                  {/* 下段: 表示形式（前期比のときのみ） */}
                  {dataKind === 'qoq' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 前期比チャート（棒グラフ） */}
                  {dataKind === 'qoq' && displayMode === 'chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: 'total_qoq', color: COLORS.total, name: '総雇用者数（前期比）' },
                          { dataKey: 'fulltime_qoq', color: COLORS.fulltime, name: 'フルタイム（前期比）' },
                          { dataKey: 'parttime_qoq', color: COLORS.parttime, name: 'パートタイム（前期比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        xAxisFormatter={formatQuarterLabel}
                        tooltipLabelFormatter={formatQuarterLabelJP}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                      />
                    </>
                  )}

                  {/* 前期比ヒートマップ */}
                  {dataKind === 'qoq' && displayMode === 'heatmap' && (
                    <QuarterlyTableWithDataTypes<QoQTableType>
                      data={quarterlyTableData}
                      dataTypes={QOQ_DATA_TYPE_OPTIONS}
                      selectedType={tableType}
                      onTypeChange={setTableType}
                      decimals={1}
                      helperText="※ 直近10年間の前期比データ（単位: %）"
                      formatValue={(v) => {
                        if (v === null || v === undefined) return '-'
                        return `${v >= 0 ? '+' : ''}${v.toFixed(1)}`
                      }}
                    />
                  )}

                  {/* 前年比グラフ（折れ線グラフ） */}
                  {dataKind === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'total_yoy', color: COLORS.total, name: '総雇用者数（前年比）', hide: hiddenSeries.has('total_yoy') },
                          { dataKey: 'fulltime_yoy', color: COLORS.fulltime, name: 'フルタイム（前年比）', hide: hiddenSeries.has('fulltime_yoy') },
                          { dataKey: 'parttime_yoy', color: COLORS.parttime, name: 'パートタイム（前年比）', hide: hiddenSeries.has('parttime_yoy') },
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
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="nz_number_of_employees" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
