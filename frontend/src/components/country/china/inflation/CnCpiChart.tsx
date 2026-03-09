/**
 * 中国 CPI（Consumer Price Index）チャートコンポーネント
 *
 * 4系列: CPI総合 / コアCPI / 非食品CPI / 食品CPI
 * 前年比: 折れ線グラフ（3系列同時表示）
 * 前月比: 棒グラフ（DataTypeButtonGroup切替）/ ヒートマップ
 *
 * データソース: NBS
 *
 * FMPマッピング: cn_cpi → "CPI", "Inflation Rate MoM", "Inflation Rate YoY"
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PeriodValue } from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import {
  CHART_COLORS,
} from '../../usa/common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useHiddenSeries,
  useMultiValueMonthlyTableData,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  ViewModeButtonGroup,
  DataTypeButtonGroup,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { MonthlyTableWithDataTypes } from '../../usa/common/MonthlyTable'

import type { CnCpiData, CnCpiItem } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

interface Props {
  data: CnCpiData | null
}

interface ChartDataPoint {
  date: string
  yoy: number | null
  mom: number | null
  food_yoy: number | null
  food_mom: number | null
  nonfood_yoy: number | null
  nonfood_mom: number | null
  core_yoy: number | null
  core_mom: number | null
}

type DataKind = 'yoy' | 'mom'
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom', label: '前月比' },
]

type DisplayMode = 'chart' | 'heatmap'
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// ヒートマップ / 前月比棒グラフ用データタイプ
type CPIDataType = 'total' | 'core' | 'nonfood' | 'food'
const CPI_DATA_TYPE_OPTIONS: { type: CPIDataType; label: string }[] = [
  { type: 'total', label: '総合' },
  { type: 'core', label: 'コア' },
  { type: 'nonfood', label: '非食品' },
  { type: 'food', label: '食品' },
]

// カラー設定
const COLOR_TOTAL = CHART_COLORS.primary    // 青 - 総合
const COLOR_NONFOOD = CHART_COLORS.positive // 緑 - 非食品
const COLOR_CORE = '#FF8C00'               // オレンジ - コア
const COLOR_FOOD = '#DC143C'               // 赤 - 食品

const formatDateLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}/${month}`
}

const formatDateFull = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}年${parseInt(month)}月`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function CnCpiChart({ data }: Props) {
  const [activeTab, setActiveTab] = useState('timeseries')
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [dataType, setDataType] = useState<CPIDataType>('total')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 10,
    mom: 3,
  })

  const chartData = useMemo((): ChartDataPoint[] => {
    if (!data?.data) return []
    return data.data.map((d: CnCpiItem) => ({
      date: d.date,
      yoy: d.yoy,
      mom: d.mom,
      food_yoy: d.food_yoy,
      food_mom: d.food_mom,
      nonfood_yoy: d.nonfood_yoy,
      nonfood_mom: d.nonfood_mom,
      core_yoy: d.core_yoy,
      core_mom: d.core_mom,
    }))
  }, [data])

  const sortedData = useSortedData(chartData)

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2016,
  })

  // ヒートマップ用データ（前月比: 総合/非食品/食品）
  const momTableData = useMultiValueMonthlyTableData(
    sortedData,
    {
      total: (item: ChartDataPoint) => item.mom,
      core: (item: ChartDataPoint) => item.core_mom,
      nonfood: (item: ChartDataPoint) => item.nonfood_mom,
      food: (item: ChartDataPoint) => item.food_mom,
    },
    10
  )

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="CPI（消費者物価指数）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="CPI（消費者物価指数）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  // 前月比棒グラフ用: 選択中のdataTypeに応じたdataKeyを決定
  const momBarMap: Record<CPIDataType, { dataKey: string; label: string; color: string }> = {
    total: { dataKey: 'mom', label: 'CPI総合（前月比）', color: COLOR_TOTAL },
    core: { dataKey: 'core_mom', label: 'コアCPI（前月比）', color: COLOR_CORE },
    nonfood: { dataKey: 'nonfood_mom', label: '非食品CPI（前月比）', color: COLOR_NONFOOD },
    food: { dataKey: 'food_mom', label: '食品CPI（前月比）', color: COLOR_FOOD },
  }
  const { dataKey: momBarDataKey, label: momBarLabel, color: momBarColor } = momBarMap[dataType]

  return (
    <div id="cpi">
      <ChartContainer
        title="CPI（消費者物価指数）"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="NBS"
        sourceUrl="https://www.stats.gov.cn/english/PressRelease/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: dataKind === 'yoy' ? 'CPI（YoY）' : 'CPI（MoM）',
              value: dataKind === 'yoy' ? (latest?.yoy ?? null) : (latest?.mom ?? null),
              color: COLOR_TOTAL,
              format: 'percent',
              decimals: 1,
            },
            {
              label: dataKind === 'yoy' ? 'コア（YoY）' : 'コア（MoM）',
              value: dataKind === 'yoy' ? (latest?.core_yoy ?? null) : (latest?.core_mom ?? null),
              color: COLOR_CORE,
              format: 'percent',
              decimals: 1,
            },
            {
              label: dataKind === 'yoy' ? '非食品（YoY）' : '非食品（MoM）',
              value: dataKind === 'yoy' ? (latest?.nonfood_yoy ?? null) : (latest?.nonfood_mom ?? null),
              color: COLOR_NONFOOD,
              format: 'percent',
              decimals: 1,
            },
            {
              label: dataKind === 'yoy' ? '食品（YoY）' : '食品（MoM）',
              value: dataKind === 'yoy' ? (latest?.food_yoy ?? null) : (latest?.food_mom ?? null),
              color: COLOR_FOOD,
              format: 'percent',
              decimals: 1,
            },
          ]}
          date={latest?.date}
          dateFormatter={formatDateFull}
          nextRelease={data.next_release ?? null}
        />

        {/* タブ切替 */}
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          size="small"
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  {/* ViewMode + 比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup options={DATA_KIND_OPTIONS} currentMode={dataKind} onChange={setDataKind} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=cn_cpi', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 前月比: チャート/ヒートマップ切替 */}
                  {dataKind === 'mom' && (
                    <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                  )}

                  {/* 前年比グラフ（折れ線グラフ: 3系列同時表示） */}
                  {dataKind === 'yoy' && (
                    <>
                      <PeriodSelector
                        onPeriodChange={(p: PeriodValue) => setCurrentPeriod(p)}
                        selectedPeriod={currentPeriod}
                      />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'yoy', color: COLOR_TOTAL, name: 'CPI総合(L)', hide: hiddenSeries.has('yoy') },
                          { dataKey: 'core_yoy', color: COLOR_CORE, name: 'コアCPI(L)', hide: hiddenSeries.has('core_yoy') },
                          { dataKey: 'nonfood_yoy', color: COLOR_NONFOOD, name: '非食品CPI(L)', hide: hiddenSeries.has('nonfood_yoy') },
                          { dataKey: 'food_yoy', color: COLOR_FOOD, name: '食品CPI(R)', hide: hiddenSeries.has('food_yoy'), yAxisId: 'right' },
                        ]}
                        yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                        rightYAxisFormatter={(v) => `${v.toFixed(0)}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        xAxisFormatter={formatDateLabel}
                        tooltipLabelFormatter={formatDateFull}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                        showZeroLine={true}
                        onLegendClick={handleLegendClick}
                      />
                    </>
                  )}

                  {/* 前月比ヒートマップ */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTableWithDataTypes
                      data={momTableData}
                      dataTypes={CPI_DATA_TYPE_OPTIONS}
                      selectedType={dataType}
                      onTypeChange={setDataType}
                      decimals={1}
                    />
                  )}

                  {/* 前月比グラフ（棒グラフ: DataType切替） */}
                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <>
                      <DataTypeButtonGroup options={CPI_DATA_TYPE_OPTIONS} currentType={dataType} onChange={setDataType} />
                      <PeriodSelector
                        onPeriodChange={(p: PeriodValue) => setCurrentPeriod(p)}
                        selectedPeriod={currentPeriod}
                      />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: momBarDataKey, color: momBarColor, name: momBarLabel },
                        ]}
                        yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        xAxisFormatter={formatDateLabel}
                        tooltipLabelFormatter={formatDateFull}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
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
                <MarketImpactTab indicatorId="cn_cpi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
