/**
 * UK ONS労働生産性チャートコンポーネント
 *
 * データ:
 * - LZVB: Output per hour worked (Index 2022=100) - 時間当たり生産性
 * - A4YM: Output per worker (Index 2022=100) - 労働者当たり生産性
 *
 * 表示モード:
 * - 前年比グラフ (YoY): LZVB, A4YMの2系列
 * - 前期比テーブル (QoQ): LZVB, A4YMの2系列
 * - 前期比グラフ (QoQ): LZVB, A4YMの2系列
 *
 * データソース:
 * - ONS (Office for National Statistics)
 *
 * 発表スケジュール:
 * - 四半期発表（FMPカレンダー）
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip as AntTooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  CHANGE_LEGEND_10PCT,
  getChangeCellColor10pct,
} from '../../usa/common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  formatQuarterLabel,
  formatQuarterLabelJP,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  ViewModeButtonGroup,
  ChangeTooltip,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import { QuarterlyTableWithDataTypes } from '../../usa/common/QuarterlyTable'

import type { ONSProductivityData } from '../../../../hooks/useDashboardData'

interface ONSProductivityChartProps {
  data: ONSProductivityData | null
}

type ViewMode = 'yoy_chart' | 'qoq_table' | 'qoq_chart'
type TableType = 'lzvb' | 'a4ym'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'qoq_chart', label: '前期比グラフ' },
  { mode: 'qoq_table', label: '前期比テーブル' },
  { mode: 'yoy_chart', label: '前年比グラフ' },
]

// カラー設定
const COLORS = {
  lzvb: '#3498db',      // 時間当たり生産性 - 青
  a4ym: '#e74c3c',      // 労働者当たり生産性 - 赤
}

// 系列名（日本語）
const SERIES_NAMES = {
  lzvb: '時間当たり生産性',
  a4ym: '労働者当たり生産性',
}

// データタイプ設定（テーブル用）
const DATA_TYPE_OPTIONS = [
  { type: 'lzvb' as const, label: '時間当たり生産性', color: COLORS.lzvb, bgColor: '#e6f7ff' },
  { type: 'a4ym' as const, label: '労働者当たり生産性', color: COLORS.a4ym, bgColor: '#fff1f0' },
]

export default function ONSProductivityChart({ data }: ONSProductivityChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('qoq_chart')
  const [tableType, setTableType] = useState<TableType>('lzvb')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    qoq_chart: 5,
    qoq_table: 'default',
    yoy_chart: 'default',
  })

  // YoYデータの統合（LZVB + A4YM）- Flash Estimateフラグも含む
  const yoyChartData = useMemo(() => {
    if (!data?.lzvb?.yoy || !data?.a4ym?.yoy) return []

    const lzvbMap = new Map(data.lzvb.yoy.map(d => [d.date, { yoy: d.yoy, is_flash: d.is_flash }]))
    const a4ymMap = new Map(data.a4ym.yoy.map(d => [d.date, { yoy: d.yoy, is_flash: d.is_flash }]))

    const allDates = new Set([...lzvbMap.keys(), ...a4ymMap.keys()])

    return Array.from(allDates).map(date => ({
      date,
      lzvb_yoy: lzvbMap.get(date)?.yoy ?? null,
      a4ym_yoy: a4ymMap.get(date)?.yoy ?? null,
      is_flash: lzvbMap.get(date)?.is_flash || a4ymMap.get(date)?.is_flash || false,
    })).sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  // QoQデータの統合（LZVB + A4YM）- Flash Estimateフラグも含む
  const qoqChartData = useMemo(() => {
    if (!data?.lzvb?.qoq || !data?.a4ym?.qoq) return []

    const lzvbMap = new Map(data.lzvb.qoq.map(d => [d.date, { qoq: d.qoq, is_flash: d.is_flash }]))
    const a4ymMap = new Map(data.a4ym.qoq.map(d => [d.date, { qoq: d.qoq, is_flash: d.is_flash }]))

    const allDates = new Set([...lzvbMap.keys(), ...a4ymMap.keys()])

    return Array.from(allDates).map(date => ({
      date,
      lzvb_qoq: lzvbMap.get(date)?.qoq ?? null,
      a4ym_qoq: a4ymMap.get(date)?.qoq ?? null,
      is_flash: lzvbMap.get(date)?.is_flash || a4ymMap.get(date)?.is_flash || false,
    })).sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  // データのソート
  const sortedYoYData = useSortedData(yoyChartData)
  const sortedQoQData = useSortedData(qoqChartData)

  // 期間フィルタリング
  const filteredYoYData = usePeriodFiltering(sortedYoYData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const filteredQoQData = usePeriodFiltering(sortedQoQData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // 四半期テーブルデータの生成
  const tableData = useMemo(() => {
    if (sortedQoQData.length === 0) return { years: [], quarterlyData: {} }

    const currentYear = new Date().getFullYear()
    const startYear = currentYear - 9

    const years: number[] = []
    for (let y = startYear; y <= currentYear; y++) {
      years.push(y)
    }

    const quarterlyData: Record<number, Record<number, { lzvb: number | null; a4ym: number | null }>> = {}

    sortedQoQData.forEach((item) => {
      const date = new Date(item.date)
      const year = date.getFullYear()
      const quarter = Math.floor(date.getMonth() / 3)

      if (year >= startYear && year <= currentYear) {
        if (!quarterlyData[year]) {
          quarterlyData[year] = {}
        }
        quarterlyData[year][quarter] = {
          lzvb: item.lzvb_qoq ?? null,
          a4ym: item.a4ym_qoq ?? null,
        }
      }
    })

    return { years, quarterlyData }
  }, [sortedQoQData])

  const hasData = sortedYoYData.length > 0 || sortedQoQData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="労働生産性" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="労働生産性" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値を取得（QoQデータから、Flash Estimateを優先）
  const latestQoQ = useMemo(() => {
    const lzvbQoq = data?.lzvb?.qoq ?? []
    if (lzvbQoq.length === 0) return null
    return lzvbQoq[lzvbQoq.length - 1]
  }, [data])

  const nextRelease = data.next_release

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (!latestQoQ) return []

    const isFlash = latestQoQ.is_flash === true
    const labelSuffix = isFlash ? '（速報値）' : ''

    return [
      {
        label: `${SERIES_NAMES.lzvb}（前期比）${labelSuffix}`,
        value: latestQoQ.qoq !== null ? `${latestQoQ.qoq >= 0 ? '+' : ''}${latestQoQ.qoq.toFixed(1)}%` : 'N/A',
        color: latestQoQ.qoq !== null && latestQoQ.qoq >= 0 ? '#52c41a' : '#f5222d',
      },
    ]
  }

  // データ比較ページを開く
  const handleCompare = () => {
    window.open('/compare?s=uk_productivity_lzvb_yoy&s=uk_productivity_a4ym_yoy', '_blank')
  }

  return (
    <div id="uk-ons-productivity-chart">
      <ChartContainer
        title="労働生産性"
        showPeriodSelector={false}
        dataSource="ONS"
        sourceUrl="https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/labourproductivity"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latestQoQ?.date}
          nextRelease={nextRelease}
          dateFormatter={formatQuarterLabel}
        />

        {/* ビューモード切り替え */}
        <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />

        {/* 前年比グラフ（YoY） */}
        {viewMode === 'yoy_chart' && (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
              <AntTooltip title="比較ページを開く">
                <Button
                  icon={<AreaChartOutlined />}
                  onClick={handleCompare}
                >
                  データ比較
                </Button>
              </AntTooltip>
            </div>
            <StandardLineChart
              data={filteredYoYData}
              lines={[
                {
                  dataKey: 'lzvb_yoy',
                  color: COLORS.lzvb,
                  name: SERIES_NAMES.lzvb,
                  hide: hiddenSeries.has('lzvb_yoy'),
                },
                {
                  dataKey: 'a4ym_yoy',
                  color: COLORS.a4ym,
                  name: SERIES_NAMES.a4ym,
                  hide: hiddenSeries.has('a4ym_yoy'),
                },
              ]}
              xAxisFormatter={formatQuarterLabel}
              yAxisFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
              tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
              tooltipLabelFormatter={formatQuarterLabelJP}
              onLegendClick={handleLegendClick}
              yDomain={['dataMin - 1', 'dataMax + 1']}
              showZeroLine
            />
          </>
        )}

        {/* 前期比グラフ（QoQ） */}
        {viewMode === 'qoq_chart' && (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
              <AntTooltip title="比較ページを開く">
                <Button
                  icon={<AreaChartOutlined />}
                  onClick={handleCompare}
                >
                  データ比較
                </Button>
              </AntTooltip>
            </div>
            <ResponsiveContainer width="100%" height={450}>
              <BarChart data={filteredQoQData} margin={CHART_MARGIN} barCategoryGap="20%">
                <CartesianGrid {...CARTESIAN_GRID_PROPS} />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatQuarterLabel}
                  tick={AXIS_STYLE.tick}
                  interval={AXIS_STYLE.interval}
                />
                <YAxis
                  tick={AXIS_STYLE.tick}
                  tickFormatter={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}`}
                  domain={['dataMin - 1', 'dataMax + 1']}
                  label={{
                    angle: -90,
                    position: 'insideLeft',
                    dy: 20,
                    style: { fontSize: 11, fill: '#666' }
                  }}
                />
                <Tooltip content={<ChangeTooltip unit="%" decimals={1} labelFormatter={formatQuarterLabelJP} />} />
                <Legend onClick={(e) => handleLegendClick(e.dataKey as string)} />
                <ReferenceLine y={0} stroke="#000" strokeWidth={1} />

                <Bar
                  dataKey="lzvb_qoq"
                  fill={COLORS.lzvb}
                  name={SERIES_NAMES.lzvb}
                  hide={hiddenSeries.has('lzvb_qoq')}
                />
                <Bar
                  dataKey="a4ym_qoq"
                  fill={COLORS.a4ym}
                  name={SERIES_NAMES.a4ym}
                  hide={hiddenSeries.has('a4ym_qoq')}
                />
              </BarChart>
            </ResponsiveContainer>
          </>
        )}

        {/* 前期比テーブル */}
        {viewMode === 'qoq_table' && (
          <QuarterlyTableWithDataTypes
            data={tableData}
            dataTypes={DATA_TYPE_OPTIONS}
            selectedType={tableType}
            onTypeChange={setTableType}
            getCellBgColor={getChangeCellColor10pct}
            legendItems={CHANGE_LEGEND_10PCT}
          />
        )}
      </ChartContainer>
    </div>
  )
}
