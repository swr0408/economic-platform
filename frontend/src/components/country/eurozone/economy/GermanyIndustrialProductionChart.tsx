/**
 * ドイツ鉱工業生産チャートコンポーネント
 *
 * データ:
 * - 前月比（MoM）: 季節・カレンダー調整済み
 * - 前年比（YoY）: カレンダー調整済み
 *
 * データソース:
 * - GENESIS-Online (42153-0001)
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

import type { GermanyIndustrialProductionData } from '../../../../hooks/useDashboardData'
import type { PeriodValue } from '../../../common/PeriodSelector'

interface GermanyIndustrialProductionChartProps {
  data: GermanyIndustrialProductionData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
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

export default function GermanyIndustrialProductionChart({ data }: GermanyIndustrialProductionChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')

  // 現在のデータタイプを判定
  const dataType = dataKind

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const sourceData = dataType === 'mom' ? data.mom : data.yoy
    if (!sourceData || !Array.isArray(sourceData)) return []

    return sourceData
      .filter(point => point.value !== null)
      .map(point => ({
        date: point.date,
        value: point.value,
      }))
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
    return <LoadingChart title="鉱工業生産（ドイツ）" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="鉱工業生産（ドイツ）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    const items = []
    const latest = dataType === 'mom' ? latestMom : latestYoy

    if (latest?.value !== null && latest?.value !== undefined) {
      items.push({
        label: dataType === 'mom' ? '前月比' : '前年比',
        value: `${latest.value >= 0 ? '+' : ''}${latest.value.toFixed(1)}%`,
        color: latest.value >= 0 ? '#10b981' : '#ef4444',
      })
    }

    return items
  }

  // 比較用指標ID
  const compareIndicatorId = dataType === 'mom'
    ? 'germany_industrial_production_mom'
    : 'germany_industrial_production_yoy'

  return (
    <div id="germany-industrial-production-chart">
      <ChartContainer
        title="鉱工業生産（ドイツ）"
        showPeriodSelector={false}
        dataSource="Destatis"
        sourceUrl="https://www.destatis.de/DE/Themen/Branchen-Unternehmen/Industrie-Verarbeitendes-Gewerbe/_inhalt.html#"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={dataType === 'mom' ? latestMom?.date : latestYoy?.date}
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

                      {dataKind === 'yoy' && (
                        <StandardLineChart
                          data={filteredData}
                          lines={[
                            {
                              dataKey: 'value',
                              color: CHART_COLORS.primary,
                              name: '前年比',
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
                    </>
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="germany_industrial_production" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
