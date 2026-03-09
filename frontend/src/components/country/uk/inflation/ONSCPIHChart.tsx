/**
 * UK ONS CPI/CPIHチャートコンポーネント
 *
 * データ:
 * - CPI All Items YoY (D7BT計算)
 * - CPI Core YoY (DKC6計算)
 * - CPI All Items MoM (D7OE)
 * - CPI Core MoM (DKI7)
 * - CPIH All Items YoY (L55O)
 * - CPIH Core YoY (L5LQ)
 *
 * 表示モード:
 * - 前年比グラフ (YoY): CPI総合・コアの2系列
 * - 前月比テーブル (MoM): 月別テーブル
 * - 前月比グラフ (MoM): CPI総合・コアの2系列
 *
 * データソース:
 * - ONS MM23 Dataset (Consumer Price Indices)
 *
 * 発表スケジュール:
 * - 毎月中旬（FMPカレンダー）
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip as AntTooltip, Segmented, Tabs } from 'antd'
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

import type { ONSCPIHData } from '../../../../hooks/useDashboardData'

interface ONSCPIHChartProps {
  data: ONSCPIHData | null
}

interface ChartDataPoint {
  date: string
  cpi_all_yoy: number | null
  cpi_core_yoy: number | null
  cpi_all_mom: number | null
  cpi_core_mom: number | null
  cpih_all_yoy: number | null
  cpih_core_yoy: number | null
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

type SeriesType = 'all' | 'core'

// グラフの色
const COLORS = {
  cpi_all: '#e74c3c',    // CPI総合 - 赤
  cpi_core: '#3498db',   // CPIコア - 青
  cpih_all: '#f39c12',   // CPIH総合 - オレンジ
  cpih_core: '#9b59b6',  // CPIHコア - 紫
}

// 系列名
const SERIES_NAMES = {
  cpi_all: 'CPI総合',
  cpi_core: 'CPIコア（エネルギー・食品・酒・たばこ除く）',
  cpih_all: 'CPIH総合',
  cpih_core: 'CPIHコア（エネルギー・食品・酒・たばこ除く）',
}

// 初期非表示系列（CPIH系列）
const INITIAL_HIDDEN_SERIES = new Set(['cpih_all_yoy', 'cpih_core_yoy'])

export default function ONSCPIHChart({ data }: ONSCPIHChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [seriesType, setSeriesType] = useState<SeriesType>('all')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries(INITIAL_HIDDEN_SERIES)

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
      cpi_all_yoy: null,
      cpi_core_yoy: null,
      cpi_all_mom: null,
      cpi_core_mom: null,
      cpih_all_yoy: null,
      cpih_core_yoy: null,
    })

    // CPI All Items YoY
    if (data.series.cpi_all_yoy?.data) {
      data.series.cpi_all_yoy.data.forEach(point => {
        if (!dateMap.has(point.date)) {
          dateMap.set(point.date, initPoint(point.date))
        }
        dateMap.get(point.date)!.cpi_all_yoy = point.value
      })
    }

    // CPI Core YoY
    if (data.series.cpi_core_yoy?.data) {
      data.series.cpi_core_yoy.data.forEach(point => {
        if (!dateMap.has(point.date)) {
          dateMap.set(point.date, initPoint(point.date))
        }
        dateMap.get(point.date)!.cpi_core_yoy = point.value
      })
    }

    // CPI All Items MoM
    if (data.series.cpi_all_mom?.data) {
      data.series.cpi_all_mom.data.forEach(point => {
        if (!dateMap.has(point.date)) {
          dateMap.set(point.date, initPoint(point.date))
        }
        dateMap.get(point.date)!.cpi_all_mom = point.value
      })
    }

    // CPI Core MoM
    if (data.series.cpi_core_mom?.data) {
      data.series.cpi_core_mom.data.forEach(point => {
        if (!dateMap.has(point.date)) {
          dateMap.set(point.date, initPoint(point.date))
        }
        dateMap.get(point.date)!.cpi_core_mom = point.value
      })
    }

    // CPIH All Items YoY
    if (data.series.cpih_all_yoy?.data) {
      data.series.cpih_all_yoy.data.forEach(point => {
        if (!dateMap.has(point.date)) {
          dateMap.set(point.date, initPoint(point.date))
        }
        dateMap.get(point.date)!.cpih_all_yoy = point.value
      })
    }

    // CPIH Core YoY
    if (data.series.cpih_core_yoy?.data) {
      data.series.cpih_core_yoy.data.forEach(point => {
        if (!dateMap.has(point.date)) {
          dateMap.set(point.date, initPoint(point.date))
        }
        dateMap.get(point.date)!.cpih_core_yoy = point.value
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
    seriesType === 'all' ? item.cpi_all_mom : item.cpi_core_mom
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
    return <LoadingChart title="消費者物価指数（CPI）" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="消費者物価指数（CPI）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (!latest) return []

    const items = []
    if (latest.cpi_all_yoy !== null) {
      items.push({
        label: 'CPI総合（前年比）',
        value: `${latest.cpi_all_yoy >= 0 ? '+' : ''}${latest.cpi_all_yoy.toFixed(1)}%`,
        color: latest.cpi_all_yoy >= 0 ? '#f5222d' : '#52c41a',
      })
    }
    if (latest.cpi_core_yoy !== null) {
      items.push({
        label: 'CPIコア（前年比）',
        value: `${latest.cpi_core_yoy >= 0 ? '+' : ''}${latest.cpi_core_yoy.toFixed(1)}%`,
        color: latest.cpi_core_yoy >= 0 ? '#f5222d' : '#52c41a',
      })
    }
    if (latest.cpih_all_yoy !== null) {
      items.push({
        label: 'CPIH総合（前年比）',
        value: `${latest.cpih_all_yoy >= 0 ? '+' : ''}${latest.cpih_all_yoy.toFixed(1)}%`,
        color: latest.cpih_all_yoy >= 0 ? '#f5222d' : '#52c41a',
      })
    }
    if (latest.cpih_core_yoy !== null) {
      items.push({
        label: 'CPIHコア（前年比）',
        value: `${latest.cpih_core_yoy >= 0 ? '+' : ''}${latest.cpih_core_yoy.toFixed(1)}%`,
        color: latest.cpih_core_yoy >= 0 ? '#f5222d' : '#52c41a',
      })
    }
    return items
  }

  // データ比較ページを開く
  const handleCompare = () => {
    window.open('/compare?s=uk_cpi_all_yoy&s=uk_cpi_core_yoy', '_blank')
  }

  return (
    <div id="uk-ons-cpih-chart">
      <ChartContainer
        title="消費者物価指数（CPI）"
        showPeriodSelector={false}
        dataSource="ONS"
        sourceUrl="https://www.ons.gov.uk/economy/inflationandpriceindices"
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
                            dataKey: 'cpi_all_yoy',
                            color: COLORS.cpi_all,
                            name: SERIES_NAMES.cpi_all,
                            hide: hiddenSeries.has('cpi_all_yoy'),
                          },
                          {
                            dataKey: 'cpi_core_yoy',
                            color: COLORS.cpi_core,
                            name: SERIES_NAMES.cpi_core,
                            hide: hiddenSeries.has('cpi_core_yoy'),
                          },
                          {
                            dataKey: 'cpih_all_yoy',
                            color: COLORS.cpih_all,
                            name: SERIES_NAMES.cpih_all,
                            hide: hiddenSeries.has('cpih_all_yoy'),
                          },
                          {
                            dataKey: 'cpih_core_yoy',
                            color: COLORS.cpih_core,
                            name: SERIES_NAMES.cpih_core,
                            hide: hiddenSeries.has('cpih_core_yoy'),
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
                      <div style={{ marginBottom: 12 }}>
                        <Segmented
                          options={[
                            { label: 'CPI総合', value: 'all' },
                            { label: 'CPIコア', value: 'core' },
                          ]}
                          value={seriesType}
                          onChange={(value) => setSeriesType(value as SeriesType)}
                        />
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
                            dataKey: 'cpi_all_mom',
                            color: COLORS.cpi_all,
                            name: `${SERIES_NAMES.cpi_all}`,
                            hide: hiddenSeries.has('cpi_all_mom'),
                          },
                          {
                            dataKey: 'cpi_core_mom',
                            color: COLORS.cpi_core,
                            name: `${SERIES_NAMES.cpi_core}`,
                            hide: hiddenSeries.has('cpi_core_mom'),
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
                <MarketImpactTab indicatorId="ons_cpih" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
