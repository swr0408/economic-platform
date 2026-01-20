/**
 * UK ONS単位労働コストチャートコンポーネント
 *
 * データ:
 * - DMWN: Unit labour costs (YoY % change) - 単位労働コスト前年比
 * - DMWO: Unit labour costs (QoQ % change) - 単位労働コスト前期比
 *
 * 表示モード:
 * - 前期比グラフ (QoQ): 棒グラフ
 * - 前期比テーブル (QoQ): 四半期テーブル
 * - 前年比グラフ (YoY): 折れ線グラフ
 *
 * データソース:
 * - ONS (Office for National Statistics)
 *
 * 発表スケジュール:
 * - 四半期発表（労働生産性と同日・FMPカレンダー）
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
import { QuarterlyTable } from '../../usa/common/QuarterlyTable'

import type { ONSUnitLabourCostsData } from '../../../../hooks/useDashboardData'

interface ONSUnitLabourCostsChartProps {
  data: ONSUnitLabourCostsData | null
}

type ViewMode = 'qoq_chart' | 'qoq_table' | 'yoy_chart'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'qoq_chart', label: '前期比グラフ' },
  { mode: 'qoq_table', label: '前期比テーブル' },
  { mode: 'yoy_chart', label: '前年比グラフ' },
]

// グラフの色
const CHART_COLOR = '#e74c3c'  // 赤色（コスト増加を示すため）

export default function ONSUnitLabourCostsChart({ data }: ONSUnitLabourCostsChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('qoq_chart')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    qoq_chart: 'default',
    qoq_table: 'default',
    yoy_chart: 'default',
  })

  // QoQデータをチャート用に変換
  const qoqChartData = useMemo(() => {
    if (!data?.qoq?.data) return []

    return data.qoq.data
      .filter(point => point.value !== null)
      .map(point => ({
        date: point.date,
        value: point.value as number,
      }))
  }, [data])

  // YoYデータをチャート用に変換
  const yoyChartData = useMemo(() => {
    if (!data?.yoy?.data) return []

    return data.yoy.data
      .filter(point => point.value !== null)
      .map(point => ({
        date: point.date,
        value: point.value as number,
      }))
  }, [data])

  // データを日付昇順にソート
  const sortedQoQData = useSortedData(qoqChartData)
  const sortedYoYData = useSortedData(yoyChartData)

  // 期間フィルタリング
  const filteredQoQData = usePeriodFiltering(sortedQoQData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const filteredYoYData = usePeriodFiltering(sortedYoYData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // 四半期テーブル用のデータ生成（QoQ）
  const tableData = useMemo(() => {
    if (sortedQoQData.length === 0) return { years: [], quarterlyData: {} }

    const currentYear = new Date().getFullYear()
    const startYear = currentYear - 9

    const years: number[] = []
    for (let y = startYear; y <= currentYear; y++) {
      years.push(y)
    }

    const quarterlyData: Record<number, Record<number, number | null>> = {}

    sortedQoQData.forEach((item) => {
      const date = new Date(item.date)
      const year = date.getFullYear()
      const quarter = Math.floor(date.getMonth() / 3)

      if (year >= startYear && year <= currentYear) {
        if (!quarterlyData[year]) {
          quarterlyData[year] = {}
        }
        quarterlyData[year][quarter] = item.value
      }
    })

    return { years, quarterlyData }
  }, [sortedQoQData])

  const hasData = sortedQoQData.length > 0 || sortedYoYData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="単位労働コスト" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="単位労働コスト" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値を取得（QoQデータから）
  const latestQoQ = useMemo(() => {
    const qoqData = data?.qoq?.data ?? []
    if (qoqData.length === 0) return null
    return qoqData[qoqData.length - 1]
  }, [data])

  const nextRelease = data.next_release

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (!latestQoQ) return []

    const value = latestQoQ.value
    const isPositive = value >= 0

    return [
      {
        label: '単位労働コスト（前期比）',
        value: `${isPositive ? '+' : ''}${value.toFixed(1)}%`,
        color: isPositive ? '#f5222d' : '#52c41a',  // 上昇=赤、下降=緑
      },
    ]
  }

  // データ比較ページを開く
  const handleCompare = () => {
    window.open('/compare?s=uk_unit_labour_costs&s=uk_productivity_lzvb_yoy', '_blank')
  }

  return (
    <div id="uk-ons-unit-labour-costs-chart">
      <ChartContainer
        title="単位労働コスト"
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
                  dataKey="value"
                  fill={CHART_COLOR}
                  name="単位労働コスト"
                  hide={hiddenSeries.has('value')}
                />
              </BarChart>
            </ResponsiveContainer>
          </>
        )}

        {/* 前期比テーブル */}
        {viewMode === 'qoq_table' && (
          <QuarterlyTable
            data={tableData}
            getCellBgColor={getChangeCellColor10pct}
            legendItems={CHANGE_LEGEND_10PCT}
          />
        )}

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
                  dataKey: 'value',
                  color: CHART_COLOR,
                  name: '単位労働コスト',
                  hide: hiddenSeries.has('value'),
                },
              ]}
              xAxisFormatter={formatQuarterLabel}
              yAxisFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(0)}%`}
              tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
              tooltipLabelFormatter={formatQuarterLabelJP}
              onLegendClick={handleLegendClick}
              yDomain={['dataMin - 1', 'dataMax + 1']}
              showZeroLine
            />
          </>
        )}
      </ChartContainer>
    </div>
  )
}
