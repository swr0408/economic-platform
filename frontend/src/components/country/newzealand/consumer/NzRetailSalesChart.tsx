/**
 * NZ 小売売上高チャートコンポーネント
 *
 * データ:
 * - Total Retail Sales QoQ%（総合・実質SA）
 * - Core Retail Sales QoQ%（コア・実質SA）
 * - Total Retail Sales YoY%（総合・実質）
 * - Core Retail Sales YoY%（コア・実質）
 *
 * データソース:
 * - Stats NZ Retail Trade Survey
 * - https://www.stats.govt.nz/topics/retail-and-wholesale-trade/
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
  DataTypeButtonGroup,
} from '../../usa/common/ChartComponents'
import { QuarterlyTableWithDataTypes } from '../../usa/common/QuarterlyTable'

import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { NzRetailSalesData } from '../../../../hooks/useDashboardData'

interface NzRetailSalesChartProps {
  data: NzRetailSalesData | null
}

interface ChartDataPoint {
  date: string
  total_qoq: number | null
  core_qoq: number | null
  total_yoy: number | null
  core_yoy: number | null
}

const COLORS = {
  total: '#2563eb',
  core: '#dc2626',
}

// 指標種別
type DataType = 'qoq' | 'yoy'

const DATA_TYPE_OPTIONS: { mode: DataType; label: string }[] = [
  { mode: 'qoq', label: '前期比' },
  { mode: 'yoy', label: '前年比' },
]

// 表示形式
type DisplayMode = 'chart' | 'heatmap'

const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
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

type QoQDataType = 'total' | 'core'

const QOQ_DATA_TYPE_OPTIONS: { type: QoQDataType; label: string }[] = [
  { type: 'total', label: '総合' },
  { type: 'core', label: 'コア' },
]

export default function NzRetailSalesChart({ data }: NzRetailSalesChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [dataType, setDataType] = useState<DataType>('qoq')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [qoqDataType, setQoqDataType] = useState<QoQDataType>('total')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataType, {
    qoq: 5,
    yoy: 20,
  })

  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter((item) => item.total_qoq !== null || item.core_qoq !== null ||
                         item.total_yoy !== null || item.core_yoy !== null)
      .map((item) => ({
        date: item.date,
        total_qoq: item.total_qoq,
        core_qoq: item.core_qoq,
        total_yoy: item.total_yoy,
        core_yoy: item.core_yoy,
      }))
  }, [data])

  const sortedData = useSortedData(chartData)

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2018,
  })

  // ヒートマップ用データ
  const quarterlyTableData = useMultiValueQuarterlyTableData(
    sortedData,
    {
      total: (item: ChartDataPoint) => item.total_qoq,
      core: (item: ChartDataPoint) => item.core_qoq,
    },
    10
  )

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="小売売上高" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="小売売上高" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  return (
    <div id="retail-sales">
      <ChartContainer
        title="小売売上高"
        showPeriodSelector={false}
        dataSource="Stats NZ"
        sourceUrl="https://www.stats.govt.nz/topics/retail-and-wholesale-trade/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '総合',
              value: latest?.total_yoy,
              color: COLORS.total,
              format: 'percent',
            },
            {
              label: 'コア（前年比）',
              value: latest?.core_yoy,
              color: COLORS.core,
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
                  {/* 上段: 指標種別 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      options={DATA_TYPE_OPTIONS}
                      currentMode={dataType}
                      onChange={setDataType}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=nz_retail_sales', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 下段: 表示形式（前期比のときのみ） */}
                  {dataType === 'qoq' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 前期比チャート（棒グラフ） */}
                  {dataType === 'qoq' && displayMode === 'chart' && (
                    <>
                      <DataTypeButtonGroup options={QOQ_DATA_TYPE_OPTIONS} currentType={qoqDataType} onChange={setQoqDataType} />
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          qoqDataType === 'total'
                            ? { dataKey: 'total_qoq', color: COLORS.total, name: '総合（前期比）' }
                            : { dataKey: 'core_qoq', color: COLORS.core, name: 'コア（前期比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 1', 'dataMax + 1']}
                        xAxisFormatter={formatQuarterLabel}
                        tooltipLabelFormatter={formatQuarterLabelJP}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                      />
                    </>
                  )}

                  {/* 前期比ヒートマップ */}
                  {dataType === 'qoq' && displayMode === 'heatmap' && (
                    <QuarterlyTableWithDataTypes<QoQDataType>
                      data={quarterlyTableData}
                      dataTypes={QOQ_DATA_TYPE_OPTIONS}
                      selectedType={qoqDataType}
                      onTypeChange={setQoqDataType}
                      decimals={1}
                      helperText="※ 直近10年間の前期比データ（単位: %、季節調整済み実質）"
                      formatValue={(v) => {
                        if (v === null || v === undefined) return '-'
                        return `${v >= 0 ? '+' : ''}${v.toFixed(1)}`
                      }}
                    />
                  )}

                  {/* 前年比チャート（折れ線グラフ） */}
                  {dataType === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'total_yoy', color: COLORS.total, name: '総合（前年比）', hide: hiddenSeries.has('total_yoy') },
                          { dataKey: 'core_yoy', color: COLORS.core, name: 'コア（前年比）', hide: hiddenSeries.has('core_yoy') },
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
                <MarketImpactTab indicatorId="nz_retail_sales" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
