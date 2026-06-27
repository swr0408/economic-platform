/**
 * NZ生産者物価指数（PPI）チャートコンポーネント
 *
 * データ:
 * - PPI Outputs (All Industries) - 産出価格指数
 * - PPI Inputs (All Industries) - 投入価格指数
 * - QoQ（前期比）/ YoY（前年比）
 *
 * データソース:
 * - Stats NZ Business Price Indexes
 * - https://www.stats.govt.nz/information-releases/business-price-indexes-december-2025-quarter/
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

import type { NzPpiData } from '../../../../hooks/useDashboardData'

interface NzPpiChartProps {
  data: NzPpiData | null
}

interface ChartDataPoint {
  date: string
  output_qoq: number | null
  output_yoy: number | null
  input_qoq: number | null
  input_yoy: number | null
}

const COLORS = {
  output: '#2563eb',
  input: '#dc2626',
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

export default function NzPpiChart({ data }: NzPpiChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [dataKind, setDataKind] = useState<DataKind>('qoq')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [tableDataType, setTableDataType] = useState<string>('output_qoq')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    qoq: 5,
    yoy: 20,
  })

  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter((item) =>
        item.output_qoq !== null || item.output_yoy !== null ||
        item.input_qoq !== null || item.input_yoy !== null
      )
      .map((item) => ({
        date: item.date,
        output_qoq: item.output_qoq,
        output_yoy: item.output_yoy,
        input_qoq: item.input_qoq,
        input_yoy: item.input_yoy,
      }))
  }, [data])

  const sortedData = useSortedData(chartData)

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ（Output QoQ / Input QoQ の2系列）
  const qoqTableData = useMultiValueQuarterlyTableData(
    sortedData,
    {
      output_qoq: (item: ChartDataPoint) => item.output_qoq,
      input_qoq: (item: ChartDataPoint) => item.input_qoq,
    },
    10
  )

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="PPI" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="PPI" showPeriodSelector={false} showDataSource={false} handbookId="nz-ppi">
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  return (
    <div id="ppi">
      <ChartContainer
        title="生産者物価指数（PPI）"
        showPeriodSelector={false}
        dataSource="Stats NZ"
        sourceUrl="https://www.stats.govt.nz/insights/?filters=Business+price+indexes%2CInformation+releases"
        handbookId="nz-ppi"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: 'Output（QoQ）',
              value: latest?.output_qoq,
              color: COLORS.output,
              format: 'percent',
            },
            {
              label: 'Input（QoQ）',
              value: latest?.input_qoq,
              color: COLORS.input,
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
                        onClick={() => window.open('/compare?s=nz_ppi', '_blank')}
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

                  {/* 前期比グラフ（棒グラフ） */}
                  {dataKind === 'qoq' && displayMode === 'chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: 'output_qoq', color: COLORS.output, name: 'PPI Output（前期比）' },
                          { dataKey: 'input_qoq', color: COLORS.input, name: 'PPI Input（前期比）' },
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
                        { type: 'output_qoq', label: 'Output（QoQ）', color: COLORS.output },
                        { type: 'input_qoq', label: 'Input（QoQ）', color: COLORS.input },
                      ]}
                      selectedType={tableDataType}
                      onTypeChange={setTableDataType}
                      decimals={1}
                      helperText="※ 直近10年間のデータ（単位: %）"
                    />
                  )}

                  {/* 前年比グラフ（折れ線グラフ） */}
                  {dataKind === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'output_yoy', color: COLORS.output, name: 'PPI Output（前年比）', hide: hiddenSeries.has('output_yoy') },
                          { dataKey: 'input_yoy', color: COLORS.input, name: 'PPI Input（前年比）', hide: hiddenSeries.has('input_yoy') },
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
                <MarketImpactTab indicatorId="nz_ppi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
