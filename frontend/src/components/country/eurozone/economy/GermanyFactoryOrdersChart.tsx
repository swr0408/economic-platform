/**
 * ドイツ製造業新規受注チャートコンポーネント
 *
 * データ:
 * - 前月比（MoM）: 季節・カレンダー調整済み（総合・国内・国外）
 * - 前年比（YoY）: カレンダー調整済み（総合・国内・国外）
 * - 指数原数値（Index）: 季節・カレンダー調整済み（総合・国内・国外）
 *
 * データソース:
 * - GENESIS-Online (42151-0004)
 * - FMP economic_calendar_events
 *
 * 発表スケジュール:
 * - 月次
 */
import { useState, useMemo } from 'react'
import { Tabs } from 'antd'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabel,
  formatDateLabelJP,
  useMonthlyTableData,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
  StandardBarChart,
  ViewModeButtonGroup,
  ChartControlRow,
  CompareButton,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'
import { CHART_COLORS } from '../../usa/common/chartConstants'

import type { GermanyFactoryOrdersData } from '../../../../hooks/useDashboardData'
import type { PeriodValue } from '../../../common/PeriodSelector'

interface GermanyFactoryOrdersChartProps {
  data: GermanyFactoryOrdersData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  domestic?: number | null
  foreign?: number | null
  [key: string]: unknown
}

type DataKind = 'index' | 'yoy' | 'mom'
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'index', label: '指数' },
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom', label: '前月比' },
]
type DisplayMode = 'chart' | 'heatmap'
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// カラー設定
const COLORS = {
  total: CHART_COLORS.primary,
  domestic: '#52c41a',  // 国内 - 緑
  foreign: '#faad14',   // 国外 - 黄
}

// 系列名（日本語）
const SERIES_NAMES = {
  total: '総合',
  domestic: '国内',
  foreign: '国外',
}

// 初期非表示の系列（国内・国外）
const INITIAL_HIDDEN = ['domestic', 'foreign']

export default function GermanyFactoryOrdersChart({ data }: GermanyFactoryOrdersChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>('default')
  const [dataKind, setDataKind] = useState<DataKind>('index')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries(INITIAL_HIDDEN)

  // 現在のデータタイプを判定
  const dataType = dataKind

  // propsのデータをチャート用に変換（総合・国内・国外を統合）
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    let totalData: { date: string; value: number | null }[]
    let domesticData: { date: string; value: number | null }[] | undefined
    let foreignData: { date: string; value: number | null }[] | undefined

    if (dataType === 'index') {
      totalData = data.index_total
      domesticData = data.index_domestic
      foreignData = data.index_foreign
    } else if (dataType === 'yoy') {
      totalData = data.yoy
      domesticData = data.domestic_yoy
      foreignData = data.foreign_yoy
    } else {
      totalData = data.mom
      domesticData = data.domestic_mom
      foreignData = data.foreign_mom
    }

    if (!totalData || !Array.isArray(totalData)) return []

    // 日付をキーにしてデータをマージ
    const dateMap = new Map<string, ChartDataPoint>()

    // 総合データ
    totalData.forEach(point => {
      if (point.value !== null) {
        dateMap.set(point.date, {
          date: point.date,
          value: point.value,
          domestic: null,
          foreign: null,
        })
      }
    })

    // 国内データをマージ
    if (domesticData && Array.isArray(domesticData)) {
      domesticData.forEach(point => {
        if (point.value !== null) {
          const existing = dateMap.get(point.date)
          if (existing) {
            existing.domestic = point.value
          }
        }
      })
    }

    // 国外データをマージ
    if (foreignData && Array.isArray(foreignData)) {
      foreignData.forEach(point => {
        if (point.value !== null) {
          const existing = dateMap.get(point.date)
          if (existing) {
            existing.foreign = point.value
          }
        }
      })
    }

    return Array.from(dateMap.values())
  }, [data, dataType])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ
  const tableData = useMonthlyTableData(chartData, (item) => item.value, 10)

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestMom = data?.latest_mom
  const latestYoy = data?.latest_yoy
  const nextRelease = data?.next_release ?? null

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="製造業新規受注（ドイツ）" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="製造業新規受注（ドイツ）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 指数モードの最新値を取得
  const latestIndex = useMemo(() => {
    if (!data?.index_total || data.index_total.length === 0) return null
    return data.index_total[data.index_total.length - 1]
  }, [data])

  const latestIndexDomestic = useMemo(() => {
    if (!data?.index_domestic || data.index_domestic.length === 0) return null
    return data.index_domestic[data.index_domestic.length - 1]
  }, [data])

  const latestIndexForeign = useMemo(() => {
    if (!data?.index_foreign || data.index_foreign.length === 0) return null
    return data.index_foreign[data.index_foreign.length - 1]
  }, [data])

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    const items = []

    if (dataType === 'index') {
      // 指数モード：総合・国内・国外の指数値を表示
      if (latestIndex?.value !== null && latestIndex?.value !== undefined) {
        items.push({
          label: '総合',
          value: latestIndex.value.toFixed(1),
          color: COLORS.total,
        })
      }
      if (latestIndexDomestic?.value !== null && latestIndexDomestic?.value !== undefined) {
        items.push({
          label: '国内',
          value: latestIndexDomestic.value.toFixed(1),
          color: COLORS.domestic,
        })
      }
      if (latestIndexForeign?.value !== null && latestIndexForeign?.value !== undefined) {
        items.push({
          label: '国外',
          value: latestIndexForeign.value.toFixed(1),
          color: COLORS.foreign,
        })
      }
    } else {
      // 前月比/前年比モード
      const latest = dataType === 'mom' ? latestMom : latestYoy

      if (latest?.value !== null && latest?.value !== undefined) {
        items.push({
          label: dataType === 'mom' ? '前月比' : '前年比',
          value: `${latest.value >= 0 ? '+' : ''}${latest.value.toFixed(1)}%`,
          color: latest.value >= 0 ? '#10b981' : '#ef4444',
        })
      }
    }

    return items
  }

  // 最新値の日付を取得
  const getLatestDate = () => {
    if (dataType === 'index') {
      return latestIndex?.date
    }
    return dataType === 'mom' ? latestMom?.date : latestYoy?.date
  }

  // 比較用指標ID
  const compareIndicatorId = dataType === 'mom'
    ? 'germany_factory_orders_mom'
    : 'germany_factory_orders_yoy'

  return (
    <div id="germany-factory-orders-chart">
      <ChartContainer
        title="製造業新規受注（ドイツ）"
        showPeriodSelector={false}
        dataSource="Destatis"
        sourceUrl="https://www.destatis.de/DE/Themen/Branchen-Unternehmen/Industrie-Verarbeitendes-Gewerbe/_inhalt.html#"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={getLatestDate()}
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
                    <CompareButton indicatorId={compareIndicatorId} />
                  </div>

                  {/* 下段: 表示形式（前月比のときのみ） */}
                  {dataKind === 'mom' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* チャート/テーブル表示 */}
                  {dataKind === 'mom' && displayMode === 'heatmap' ? (
                    <MonthlyTable
                      data={tableData}
                      formatValue={(v) => v === null ? '-' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}`}
                      decimals={1}
                    />
                  ) : (
                    <>
                      <ChartControlRow
                        selectedPeriod={currentPeriod}
                        onPeriodChange={setCurrentPeriod}
                        indicatorId={compareIndicatorId}
                        hideCompareButton
                      />

                      {dataKind === 'mom' && displayMode === 'chart' && (
                        <StandardBarChart
                          data={filteredData}
                          bars={[
                            {
                              dataKey: 'value',
                              name: '前月比',
                              color: CHART_COLORS.primary,
                            },
                          ]}
                          xAxisFormatter={formatDateLabel}
                          yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                          tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
                          tooltipLabelFormatter={formatDateLabelJP}
                          showZeroLine={true}
                          showLegend={false}
                        />
                      )}

                      {dataKind === 'index' && (
                        <StandardLineChart
                          data={filteredData}
                          lines={[
                            {
                              dataKey: 'value',
                              color: COLORS.total,
                              name: SERIES_NAMES.total,
                              hide: hiddenSeries.has('total'),
                            },
                            {
                              dataKey: 'domestic',
                              color: COLORS.domestic,
                              name: SERIES_NAMES.domestic,
                              hide: hiddenSeries.has('domestic'),
                            },
                            {
                              dataKey: 'foreign',
                              color: COLORS.foreign,
                              name: SERIES_NAMES.foreign,
                              hide: hiddenSeries.has('foreign'),
                            },
                          ]}
                          xAxisFormatter={formatDateLabel}
                          yAxisFormatter={(v) => v.toFixed(1)}
                          tooltipValueFormatter={(v) => v.toFixed(1)}
                          tooltipLabelFormatter={formatDateLabelJP}
                          showZeroLine={false}
                          onLegendClick={handleLegendClick}
                          yDomain={['dataMin - 5', 'dataMax + 5']}
                        />
                      )}

                      {dataKind === 'yoy' && (
                        <StandardLineChart
                          data={filteredData}
                          lines={[
                            {
                              dataKey: 'value',
                              color: COLORS.total,
                              name: SERIES_NAMES.total,
                              hide: hiddenSeries.has('total'),
                            },
                            {
                              dataKey: 'domestic',
                              color: COLORS.domestic,
                              name: SERIES_NAMES.domestic,
                              hide: hiddenSeries.has('domestic'),
                            },
                            {
                              dataKey: 'foreign',
                              color: COLORS.foreign,
                              name: SERIES_NAMES.foreign,
                              hide: hiddenSeries.has('foreign'),
                            },
                          ]}
                          xAxisFormatter={formatDateLabel}
                          yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                          tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
                          tooltipLabelFormatter={formatDateLabelJP}
                          showZeroLine={true}
                          onLegendClick={handleLegendClick}
                          yDomain={['dataMin - 5', 'dataMax + 5']}
                        />
                      )}
                    </>
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="germany_factory_orders" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
