/**
 * UK ONS PPIチャートコンポーネント
 *
 * データ:
 * - PPI Output (Factory Gate / 出荷価格): JVZ7計算 → YoY/MoM
 * - PPI Input (投入価格): K646計算 → YoY/MoM
 *
 * 表示モード:
 * - 前年比グラフ (YoY): Output/Inputの2系列
 * - 前月比テーブル (MoM): 月別テーブル
 * - 前月比グラフ (MoM): Output/Inputの2系列
 *
 * データソース:
 * - ONS PPI Dataset (Producer Price Index)
 *
 * 発表スケジュール:
 * - 毎月中旬（CPIと同日・FMPカレンダー）
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip as AntTooltip, Tabs } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMonthlyTableData,
  useHiddenSeries,
  formatDateLabel,
  formatDateLabelJP,
} from '../../usa/common/useChartData'
import {
  ViewModeButtonGroup,
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'
import {
  CHANGE_LEGEND_10PCT,
  getChangeCellColor10pct,
} from '../../usa/common/chartConstants'

import type { ONSPPIData } from '../../../../hooks/useDashboardData'

interface ONSPPIChartProps {
  data: ONSPPIData | null
}

interface ChartDataPoint {
  date: string
  output_yoy: number | null
  output_mom: number | null
  input_yoy: number | null
  input_mom: number | null
  [key: string]: unknown
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

type SeriesType = 'output' | 'input'
const SERIES_TYPE_OPTIONS: { mode: SeriesType; label: string }[] = [
  { mode: 'output', label: '出荷価格' },
  { mode: 'input', label: '投入価格' },
]

// グラフの色
const COLORS = {
  output: '#e74c3c',   // 出荷価格 - 赤
  input: '#3498db',    // 投入価格 - 青
}

// 系列名
const SERIES_NAMES = {
  output: 'PPI出荷価格（Factory Gate）',
  input: 'PPI投入価格（原材料）',
}

export default function ONSPPIChart({ data }: ONSPPIChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [seriesType, setSeriesType] = useState<SeriesType>('output')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 10,
    mom: 3,
  })

  // propsのデータをチャート用に変換（全系列をマージ）
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.series) return []

    const dateMap = new Map<string, ChartDataPoint>()

    const initPoint = (date: string): ChartDataPoint => ({
      date,
      output_yoy: null,
      output_mom: null,
      input_yoy: null,
      input_mom: null,
    })

    // Output YoY
    if (data.series.output_yoy?.data) {
      data.series.output_yoy.data.forEach(point => {
        if (!dateMap.has(point.date)) {
          dateMap.set(point.date, initPoint(point.date))
        }
        dateMap.get(point.date)!.output_yoy = point.value
      })
    }

    // Output MoM
    if (data.series.output_mom?.data) {
      data.series.output_mom.data.forEach(point => {
        if (!dateMap.has(point.date)) {
          dateMap.set(point.date, initPoint(point.date))
        }
        dateMap.get(point.date)!.output_mom = point.value
      })
    }

    // Input YoY
    if (data.series.input_yoy?.data) {
      data.series.input_yoy.data.forEach(point => {
        if (!dateMap.has(point.date)) {
          dateMap.set(point.date, initPoint(point.date))
        }
        dateMap.get(point.date)!.input_yoy = point.value
      })
    }

    // Input MoM
    if (data.series.input_mom?.data) {
      data.series.input_mom.data.forEach(point => {
        if (!dateMap.has(point.date)) {
          dateMap.set(point.date, initPoint(point.date))
        }
        dateMap.get(point.date)!.input_mom = point.value
      })
    }

    return Array.from(dateMap.values()).sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  // テーブル用データ（年別×月別のマトリックス）
  const momTableData = useMonthlyTableData(chartData, (item) =>
    seriesType === 'output' ? item.output_mom : item.input_mom
  )

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (chartData.length === 0) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  const nextRelease = data?.next_release

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="生産者物価指数（PPI）" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="生産者物価指数（PPI）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (!latest) return []

    const items = []
    if (latest.output_yoy !== null) {
      items.push({
        label: 'PPI出荷価格（前年比）',
        value: `${latest.output_yoy >= 0 ? '+' : ''}${latest.output_yoy.toFixed(1)}%`,
        color: latest.output_yoy >= 0 ? '#f5222d' : '#52c41a',
      })
    }
    if (latest.input_yoy !== null) {
      items.push({
        label: 'PPI投入価格（原材料・前年比）',
        value: `${latest.input_yoy >= 0 ? '+' : ''}${latest.input_yoy.toFixed(1)}%`,
        color: latest.input_yoy >= 0 ? '#f5222d' : '#52c41a',
      })
    }
    return items
  }

  // データ比較ページを開く
  const handleCompare = () => {
    window.open('/compare?s=uk_ppi_output_yoy&s=uk_ppi_input_yoy', '_blank')
  }

  return (
    <div id="uk-ons-ppi-chart">
      <ChartContainer
        title="生産者物価指数（PPI）"
        showPeriodSelector={false}
        dataSource="ONS"
        sourceUrl="https://www.ons.gov.uk/economy/inflationandpriceindices/bulletins/producerpriceinflation/latest"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latest?.date}
          nextRelease={nextRelease}
        />

        <Tabs
          defaultActiveKey="chart"
          items={[
            {
              key: 'chart',
              label: '時系列',
              children: (
                <>
                  {/* 上段: 指標種別 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup options={DATA_KIND_OPTIONS} currentMode={dataKind} onChange={setDataKind} />
                    <AntTooltip title="比較ページを開く">
                      <Button icon={<AreaChartOutlined />} onClick={handleCompare}>データ比較</Button>
                    </AntTooltip>
                  </div>

                  {/* 下段: 表示形式（前月比のときのみ） */}
                  {dataKind === 'mom' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 前年比グラフ（YoY） */}
                  {dataKind === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          {
                            dataKey: 'output_yoy',
                            color: COLORS.output,
                            name: SERIES_NAMES.output,
                            hide: hiddenSeries.has('output_yoy'),
                          },
                          {
                            dataKey: 'input_yoy',
                            color: COLORS.input,
                            name: SERIES_NAMES.input,
                            hide: hiddenSeries.has('input_yoy'),
                          },
                        ]}
                        xAxisFormatter={formatDateLabel}
                        yAxisFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
                        tooltipLabelFormatter={formatDateLabelJP}
                        onLegendClick={handleLegendClick}
                        yDomain={['dataMin - 1', 'dataMax + 1']}
                        showZeroLine
                      />
                    </>
                  )}

                  {/* 前月比テーブル（MoM） */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <>
                      <div style={{ marginBottom: 8 }}>
                        <ViewModeButtonGroup options={SERIES_TYPE_OPTIONS} currentMode={seriesType} onChange={setSeriesType} />
                      </div>
                      <MonthlyTable
                        data={momTableData}
                        getCellBgColor={getChangeCellColor10pct}
                        legendItems={CHANGE_LEGEND_10PCT}
                      />
                    </>
                  )}

                  {/* 前月比グラフ（MoM） */}
                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          {
                            dataKey: 'output_mom',
                            color: COLORS.output,
                            name: `${SERIES_NAMES.output}`,
                            hide: hiddenSeries.has('output_mom'),
                          },
                          {
                            dataKey: 'input_mom',
                            color: COLORS.input,
                            name: `${SERIES_NAMES.input}`,
                            hide: hiddenSeries.has('input_mom'),
                          },
                        ]}
                        xAxisFormatter={formatDateLabel}
                        yAxisFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
                        tooltipLabelFormatter={formatDateLabelJP}
                        yDomain={['dataMin - 1', 'dataMax + 1']}
                        showZeroLine
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
                <MarketImpactTab indicatorId="ons_ppi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
