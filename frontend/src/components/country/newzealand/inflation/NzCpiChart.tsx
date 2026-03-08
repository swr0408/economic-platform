/**
 * NZ消費者物価指数（CPI）チャートコンポーネント
 *
 * データ:
 * - All Groups CPI（全グループ）- QoQ / YoY
 * - Tradable CPI（貿易財）- QoQ / YoY
 * - Non-Tradable CPI（非貿易財）- QoQ / YoY
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

import type { NzCpiData } from '../../../../hooks/useDashboardData'

interface NzCpiChartProps {
  data: NzCpiData | null
}

interface ChartDataPoint {
  date: string
  all_qoq: number | null
  all_yoy: number | null
  tradable_qoq: number | null
  tradable_yoy: number | null
  non_tradable_qoq: number | null
  non_tradable_yoy: number | null
}

const COLORS = {
  all: '#2563eb',
  tradable: '#16a34a',
  non_tradable: '#dc2626',
}

type DataKind = 'yoy' | 'qoq'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'qoq', label: '前期比' },
]

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

export default function NzCpiChart({ data }: NzCpiChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [tableDataType, setTableDataType] = useState<string>('all_qoq')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 'default',
    qoq: 5,
  })

  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter((item) =>
        item.all_qoq !== null || item.all_yoy !== null
      )
      .map((item) => ({
        date: item.date,
        all_qoq: item.all_qoq,
        all_yoy: item.all_yoy,
        tradable_qoq: item.tradable_qoq,
        tradable_yoy: item.tradable_yoy,
        non_tradable_qoq: item.non_tradable_qoq,
        non_tradable_yoy: item.non_tradable_yoy,
      }))
  }, [data])

  const sortedData = useSortedData(chartData)

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ
  const qoqTableData = useMultiValueQuarterlyTableData(
    sortedData,
    {
      all_qoq: (item: ChartDataPoint) => item.all_qoq,
      tradable_qoq: (item: ChartDataPoint) => item.tradable_qoq,
      non_tradable_qoq: (item: ChartDataPoint) => item.non_tradable_qoq,
    },
    10
  )

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="CPI" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="CPI" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  return (
    <div id="cpi">
      <ChartContainer
        title="消費者物価指数（CPI）"
        showPeriodSelector={false}
        dataSource="Stats NZ"
        sourceUrl="https://www.stats.govt.nz/indicators/consumers-price-index-cpi/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: 'All Groups（YoY）',
              value: latest?.all_yoy,
              color: COLORS.all,
              format: 'percent',
            },
            {
              label: 'Tradable（YoY）',
              value: latest?.tradable_yoy,
              color: COLORS.tradable,
              format: 'percent',
            },
            {
              label: 'Non-Tradable（YoY）',
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
                  {/* 上段: 指標種別 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      options={DATA_KIND_OPTIONS}
                      currentMode={dataKind}
                      onChange={setDataKind}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=nz_cpi', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>
                  {/* 下段: 表示形式（前期比のときのみ） */}
                  {dataKind === 'qoq' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 前年比グラフ（折れ線グラフ） */}
                  {dataKind === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'all_yoy', color: COLORS.all, name: 'All Groups（前年比）', hide: hiddenSeries.has('all_yoy') },
                          { dataKey: 'tradable_yoy', color: COLORS.tradable, name: 'Tradable（前年比）', hide: hiddenSeries.has('tradable_yoy') },
                          { dataKey: 'non_tradable_yoy', color: COLORS.non_tradable, name: 'Non-Tradable（前年比）', hide: hiddenSeries.has('non_tradable_yoy') },
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

                  {/* 前期比グラフ（棒グラフ） */}
                  {dataKind === 'qoq' && displayMode === 'chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: 'all_qoq', color: COLORS.all, name: 'All Groups（前期比）' },
                          { dataKey: 'tradable_qoq', color: COLORS.tradable, name: 'Tradable（前期比）' },
                          { dataKey: 'non_tradable_qoq', color: COLORS.non_tradable, name: 'Non-Tradable（前期比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        xAxisFormatter={formatQuarterLabel}
                        tooltipLabelFormatter={formatQuarterLabelJP}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                      />
                    </>
                  )}

                  {/* テーブル */}
                  {dataKind === 'qoq' && displayMode === 'heatmap' && (
                    <QuarterlyTableWithDataTypes
                      data={qoqTableData}
                      dataTypes={[
                        { type: 'all_qoq', label: 'All Groups（QoQ）', color: COLORS.all },
                        { type: 'tradable_qoq', label: 'Tradable（QoQ）', color: COLORS.tradable },
                        { type: 'non_tradable_qoq', label: 'Non-Tradable（QoQ）', color: COLORS.non_tradable },
                      ]}
                      selectedType={tableDataType}
                      onTypeChange={setTableDataType}
                      decimals={1}
                      helperText="※ 直近10年間のデータ（単位: %）"
                    />
                  )}
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
