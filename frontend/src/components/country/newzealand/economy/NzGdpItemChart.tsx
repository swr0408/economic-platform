/**
 * NZ GDP項目別チャートコンポーネント
 *
 * データ項目:
 * - hce_qoq/yoy: 家計消費（HCE）前期比/前年比
 * - gfcf_qoq/yoy: 固定資本形成（GFCF）前期比/前年比
 * - exports_qoq/yoy: 輸出 前期比/前年比（YoY初期非表示）
 * - imports_qoq/yoy: 輸入 前期比/前年比（YoY初期非表示）
 * - gdp_expenditure_qoq/yoy: GDP支出合計 前期比/前年比
 * - net_exports_qoq/yoy: 純輸出 前期比/前年比
 * - inventories / inventories_diff / inventories_yoy_diff: 在庫変動
 *
 * データソース: Stats NZ
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  CHART_COLORS,
} from '../../usa/common/chartConstants'
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

import type { NzGdpItemData } from '../../../../hooks/useDashboardData'

interface NzGdpItemChartProps {
  data: NzGdpItemData | null
}

interface ChartDataPoint {
  date: string
  hce_qoq: number | null
  gfcf_qoq: number | null
  exports_qoq: number | null
  imports_qoq: number | null
  gdp_expenditure_qoq: number | null
  net_exports_qoq: number | null
  hce_yoy: number | null
  gfcf_yoy: number | null
  exports_yoy: number | null
  imports_yoy: number | null
  gdp_expenditure_yoy: number | null
  net_exports_yoy: number | null
  inventories: number | null
  inventories_diff: number | null
  inventories_yoy_diff: number | null
  net_exports: number | null
}

const COLORS = {
  hce: CHART_COLORS.primary,
  gfcf: CHART_COLORS.positive,
  exports: '#f59e0b',
  imports: CHART_COLORS.purple,
  gdp: '#ed3e3e',
  net_exports: '#ea7c06',
  inventories: '#f97316',
}

// 指標種別
type DataKind = 'qoq' | 'yoy' | 'inventories'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'qoq', label: '前期比' },
  { mode: 'yoy', label: '前年比' },
  { mode: 'inventories', label: '在庫変動' },
]

// 表示形式
type DisplayMode = 'chart' | 'heatmap'

const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// データタイプ（前期比棒グラフ用）
type QoqDataType = 'hce' | 'gfcf' | 'exports' | 'imports' | 'gdp_expenditure' | 'net_exports'

const QOQ_DATA_TYPE_OPTIONS: { type: QoqDataType; label: string }[] = [
  { type: 'gdp_expenditure', label: 'GDP支出' },
  { type: 'hce', label: '家計消費' },
  { type: 'gfcf', label: '固定資本形成' },
  { type: 'exports', label: '輸出' },
  { type: 'imports', label: '輸入' },
  { type: 'net_exports', label: '純輸出' },
]

// ヒートマップ用（全6系列）
type HeatmapDataType = 'hce' | 'gfcf' | 'exports' | 'imports' | 'gdp_expenditure' | 'net_exports'

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

// DataTypeButtonGroupに渡す系列定義
const QOQ_BAR_MAP: Record<QoqDataType, { dataKey: string; color: string; name: string }> = {
  gdp_expenditure: { dataKey: 'gdp_expenditure_qoq', color: COLORS.gdp, name: 'GDP支出（前期比）' },
  hce: { dataKey: 'hce_qoq', color: COLORS.hce, name: 'HCE（前期比）' },
  gfcf: { dataKey: 'gfcf_qoq', color: COLORS.gfcf, name: 'GFCF（前期比）' },
  exports: { dataKey: 'exports_qoq', color: COLORS.exports, name: '輸出（前期比）' },
  imports: { dataKey: 'imports_qoq', color: COLORS.imports, name: '輸入（前期比）' },
  net_exports: { dataKey: 'net_exports_qoq', color: COLORS.net_exports, name: '純輸出（前期比）' },
}

export default function NzGdpItemChart({ data }: NzGdpItemChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [dataKind, setDataKind] = useState<DataKind>('qoq')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [qoqDataType, setQoqDataType] = useState<QoqDataType>('hce')

  // YoY初期非表示: 輸出・輸入
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<string>(['exports_yoy', 'imports_yoy'])

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    qoq: 5,
    yoy: 'default',
    inventories: 'default',
  })

  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter((item) =>
        item.hce_qoq !== null || item.gfcf_qoq !== null ||
        item.exports_qoq !== null || item.imports_qoq !== null ||
        item.hce_yoy !== null || item.gfcf_yoy !== null
      )
      .map((item) => ({
        date: item.date,
        hce_qoq: item.hce_qoq,
        gfcf_qoq: item.gfcf_qoq,
        exports_qoq: item.exports_qoq,
        imports_qoq: item.imports_qoq,
        gdp_expenditure_qoq: item.gdp_expenditure_qoq,
        net_exports_qoq: item.net_exports_qoq,
        hce_yoy: item.hce_yoy,
        gfcf_yoy: item.gfcf_yoy,
        exports_yoy: item.exports_yoy,
        imports_yoy: item.imports_yoy,
        gdp_expenditure_yoy: item.gdp_expenditure_yoy,
        net_exports_yoy: item.net_exports_yoy,
        inventories: item.inventories,
        inventories_diff: item.inventories_diff,
        inventories_yoy_diff: item.inventories_yoy_diff,
        net_exports: item.net_exports,
      }))
  }, [data])

  const sortedData = useSortedData(chartData)

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // ヒートマップ用データ（HCE/GFCF/輸出/輸入/GDP支出/純輸出 の6系列）
  const quarterlyTableData = useMultiValueQuarterlyTableData(
    sortedData,
    {
      hce: (item: ChartDataPoint) => item.hce_qoq,
      gfcf: (item: ChartDataPoint) => item.gfcf_qoq,
      exports: (item: ChartDataPoint) => item.exports_qoq,
      imports: (item: ChartDataPoint) => item.imports_qoq,
      gdp_expenditure: (item: ChartDataPoint) => item.gdp_expenditure_qoq,
      net_exports: (item: ChartDataPoint) => item.net_exports_qoq,
    },
    10
  )

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="GDP項目" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="GDP項目" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  return (
    <div id="nz-gdp-item">
      <ChartContainer
        title="GDP項目"
        showPeriodSelector={false}
        dataSource="Stats NZ"
        sourceUrl="https://www.stats.govt.nz/indicators/gross-domestic-product-gdp/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: 'GDP支出（QoQ）',
              value: latest?.gdp_expenditure_qoq,
              color: COLORS.gdp,
              format: 'percent',
            },
            {
              label: '家計消費（QoQ）',
              value: latest?.hce_qoq,
              color: COLORS.hce,
              format: 'percent',
            },
            {
              label: '固定資本形成（QoQ）',
              value: latest?.gfcf_qoq,
              color: COLORS.gfcf,
              format: 'percent',
            },
            {
              label: '輸出（QoQ）',
              value: latest?.exports_qoq,
              color: COLORS.exports,
              format: 'percent',
            },
            {
              label: '輸入（QoQ）',
              value: latest?.imports_qoq,
              color: COLORS.imports,
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
                        onClick={() => window.open('/compare?s=nz_gdp_item_hce', '_blank')}
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

                  {/* 前期比チャート（棒グラフ） */}
                  {dataKind === 'qoq' && displayMode === 'chart' && (
                    <>
                      <DataTypeButtonGroup
                        options={QOQ_DATA_TYPE_OPTIONS}
                        currentType={qoqDataType}
                        onChange={setQoqDataType}
                      />
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[QOQ_BAR_MAP[qoqDataType]]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 1', 'dataMax + 1']}
                        xAxisFormatter={formatQuarterLabel}
                        tooltipLabelFormatter={formatQuarterLabelJP}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                      />
                    </>
                  )}

                  {/* 前期比ヒートマップ（HCE/GFCF/輸出/輸入/GDP支出/純輸出） */}
                  {dataKind === 'qoq' && displayMode === 'heatmap' && (
                    <QuarterlyTableWithDataTypes
                      data={quarterlyTableData}
                      dataTypes={[
                        { type: 'gdp_expenditure', label: 'GDP支出' },
                        { type: 'hce', label: '家計消費' },
                        { type: 'gfcf', label: '固定資本形成' },
                        { type: 'net_exports', label: '純輸出' },
                        { type: 'exports', label: '輸出' },
                        { type: 'imports', label: '輸入' },
                      ]}
                      selectedType={qoqDataType as HeatmapDataType}
                      onTypeChange={(t) => setQoqDataType(t as QoqDataType)}
                      decimals={1}
                      helperText="※ 直近10年間の前期比データ（単位: %、季節調整済み実質）"
                      formatValue={(v) => {
                        if (v === null || v === undefined) return '-'
                        return `${v >= 0 ? '+' : ''}${v.toFixed(1)}`
                      }}
                    />
                  )}

                  {/* 前年比チャート（折れ線グラフ・全系列表示、輸出・輸入は初期非表示） */}
                  {dataKind === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'gdp_expenditure_yoy', color: COLORS.gdp, name: 'GDP支出', hide: hiddenSeries.has('gdp_expenditure_yoy') },
                          { dataKey: 'hce_yoy', color: COLORS.hce, name: '家計消費', hide: hiddenSeries.has('hce_yoy') },
                          { dataKey: 'gfcf_yoy', color: COLORS.gfcf, name: '固定資本形成', hide: hiddenSeries.has('gfcf_yoy') },
                          { dataKey: 'net_exports_yoy', color: COLORS.net_exports, name: '純輸出', hide: hiddenSeries.has('net_exports_yoy'), yAxisId: 'right' },
                          { dataKey: 'exports_yoy', color: COLORS.exports, name: '輸出', hide: hiddenSeries.has('exports_yoy') },
                          { dataKey: 'imports_yoy', color: COLORS.imports, name: '輸入', hide: hiddenSeries.has('imports_yoy') },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        rightYAxisFormatter={(v) => `${v}%`}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                        yDomain={['dataMin - 2', 'dataMax + 2']}
                        showZeroLine={true}
                        xAxisFormatter={formatQuarterLabel}
                        tooltipLabelFormatter={formatQuarterLabelJP}
                        onLegendClick={handleLegendClick}
                      />
                    </>
                  )}

                  {/* 在庫変動チャート */}
                  {dataKind === 'inventories' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'inventories', color: COLORS.inventories, name: '在庫変動（水準値）' },
                          { dataKey: 'inventories_diff', color: CHART_COLORS.primary, name: '前期差額', yAxisId: 'right' },
                          { dataKey: 'inventories_yoy_diff', color: CHART_COLORS.positive, name: '前年差額', yAxisId: 'right' },
                        ]}
                        yAxisFormatter={(v) => `${(v / 1000).toFixed(1)}B`}
                        rightYAxisFormatter={(v) => `${v >= 0 ? '+' : ''}${(v / 1000).toFixed(1)}B`}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toLocaleString()}M`}
                        yDomain={['dataMin - 500', 'dataMax + 500']}
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
                <MarketImpactTab indicatorId="nz_gdp_growth_rate" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
