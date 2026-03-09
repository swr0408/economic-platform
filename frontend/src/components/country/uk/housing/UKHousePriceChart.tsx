/**
 * UK住宅価格指数チャートコンポーネント
 *
 * データ:
 * - 住宅価格指数（前年比）- 全体・戸建・セミデタッチド・テラスハウス・フラット
 *
 * 表示モード:
 * - 前年比グラフ (YoY): 全物件タイプの折れ線グラフ
 * - 前年比テーブル (YoY Table): 月別テーブル
 *
 * データソース:
 * - Land Registry UK House Price Index
 *
 * 発表スケジュール:
 * - 月次（不定期・FMPカレンダーから取得）
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
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'
import {
  CHANGE_LEGEND_10PCT,
  getChangeCellColor10pct,
} from '../../usa/common/chartConstants'

import type { UKHousePriceData } from '../../../../hooks/useDashboardData'

interface UKHousePriceChartProps {
  data: UKHousePriceData | null
}

interface ChartDataPoint {
  date: string
  all: number | null
  detached: number | null
  semi_detached: number | null
  terraced: number | null
  flat: number | null
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

type PropertyType = 'all' | 'detached' | 'semi_detached' | 'terraced' | 'flat'

// グラフの色
const COLORS = {
  all: '#e74c3c',           // 全物件 - 赤
  detached: '#3498db',      // 戸建 - 青
  semi_detached: '#2ecc71', // セミデタッチド - 緑
  terraced: '#f39c12',      // テラスハウス - オレンジ
  flat: '#9b59b6',          // フラット - 紫
}

// 系列名
const SERIES_NAMES: Record<PropertyType, string> = {
  all: '全物件',
  detached: '戸建',
  semi_detached: 'セミデタッチド',
  terraced: 'テラスハウス',
  flat: 'フラット',
}

// 初期状態で非表示にする系列（全物件以外）
const INITIAL_HIDDEN_SERIES: PropertyType[] = ['detached', 'semi_detached', 'terraced', 'flat']

export default function UKHousePriceChart({ data }: UKHousePriceChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [propertyType, setPropertyType] = useState<PropertyType>('all')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<PropertyType>(INITIAL_HIDDEN_SERIES)

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 10,
    mom: 10,
  })

  // propsのデータをチャート用に変換（YoY - 全系列をマージ）
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.series) return []

    const dateMap = new Map<string, ChartDataPoint>()

    const initPoint = (date: string): ChartDataPoint => ({
      date,
      all: null,
      detached: null,
      semi_detached: null,
      terraced: null,
      flat: null,
    })

    // 各物件タイプのデータをマージ
    const propertyTypes: PropertyType[] = ['all', 'detached', 'semi_detached', 'terraced', 'flat']

    for (const pType of propertyTypes) {
      const seriesData = data.series[pType]
      if (seriesData?.data) {
        seriesData.data.forEach(point => {
          if (!dateMap.has(point.date)) {
            dateMap.set(point.date, initPoint(point.date))
          }
          dateMap.get(point.date)![pType] = point.value
        })
      }
    }

    return Array.from(dateMap.values()).sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  // propsのデータをチャート用に変換（MoM - 全系列をマージ）
  const rawMomChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.series_mom) return []

    const dateMap = new Map<string, ChartDataPoint>()

    const initPoint = (date: string): ChartDataPoint => ({
      date,
      all: null,
      detached: null,
      semi_detached: null,
      terraced: null,
      flat: null,
    })

    // 各物件タイプのデータをマージ
    const propertyTypes: PropertyType[] = ['all', 'detached', 'semi_detached', 'terraced', 'flat']

    for (const pType of propertyTypes) {
      const seriesData = data.series_mom[pType]
      if (seriesData?.data) {
        seriesData.data.forEach(point => {
          if (!dateMap.has(point.date)) {
            dateMap.set(point.date, initPoint(point.date))
          }
          dateMap.get(point.date)![pType] = point.value
        })
      }
    }

    return Array.from(dateMap.values()).sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)
  const momChartData = useSortedData(rawMomChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  const filteredMomData = usePeriodFiltering(momChartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  // テーブル用データ（年別×月別のマトリックス）- MoM
  const momTableData = useMonthlyTableData(momChartData, (item) => item[propertyType] as number | null)

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (chartData.length === 0) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  const nextRelease = data?.next_release

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="住宅価格指数（前年比）" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="住宅価格指数（前年比）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (!latest) return []

    const items = []
    if (latest.all !== null) {
      items.push({
        label: '全物件',
        value: `${latest.all >= 0 ? '+' : ''}${latest.all.toFixed(1)}%`,
        color: latest.all >= 0 ? '#f5222d' : '#52c41a',
      })
    }
    return items
  }

  // データ比較ページを開く
  const handleCompare = () => {
    window.open('/compare?s=uk_house_price_yoy', '_blank')
  }

  return (
    <div id="uk-house-price-chart">
      <ChartContainer
        title="国家統計局住宅価格指数"
        showPeriodSelector={false}
        dataSource="ONS"
        sourceUrl="https://www.ons.gov.uk/economy/inflationandpriceindices/bulletins/privaterentandhousepricesuk/latest"
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
                            dataKey: 'all',
                            color: COLORS.all,
                            name: SERIES_NAMES.all,
                            hide: hiddenSeries.has('all'),
                          },
                          {
                            dataKey: 'detached',
                            color: COLORS.detached,
                            name: SERIES_NAMES.detached,
                            hide: hiddenSeries.has('detached'),
                          },
                          {
                            dataKey: 'semi_detached',
                            color: COLORS.semi_detached,
                            name: SERIES_NAMES.semi_detached,
                            hide: hiddenSeries.has('semi_detached'),
                          },
                          {
                            dataKey: 'terraced',
                            color: COLORS.terraced,
                            name: SERIES_NAMES.terraced,
                            hide: hiddenSeries.has('terraced'),
                          },
                          {
                            dataKey: 'flat',
                            color: COLORS.flat,
                            name: SERIES_NAMES.flat,
                            hide: hiddenSeries.has('flat'),
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

                  {/* 前月比グラフ（MoM） */}
                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredMomData}
                        lines={[
                          {
                            dataKey: 'all',
                            color: COLORS.all,
                            name: SERIES_NAMES.all,
                            hide: hiddenSeries.has('all'),
                          },
                          {
                            dataKey: 'detached',
                            color: COLORS.detached,
                            name: SERIES_NAMES.detached,
                            hide: hiddenSeries.has('detached'),
                          },
                          {
                            dataKey: 'semi_detached',
                            color: COLORS.semi_detached,
                            name: SERIES_NAMES.semi_detached,
                            hide: hiddenSeries.has('semi_detached'),
                          },
                          {
                            dataKey: 'terraced',
                            color: COLORS.terraced,
                            name: SERIES_NAMES.terraced,
                            hide: hiddenSeries.has('terraced'),
                          },
                          {
                            dataKey: 'flat',
                            color: COLORS.flat,
                            name: SERIES_NAMES.flat,
                            hide: hiddenSeries.has('flat'),
                          },
                        ]}
                        xAxisFormatter={formatDateLabel}
                        yAxisFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
                        tooltipLabelFormatter={formatDateLabelJP}
                        onLegendClick={handleLegendClick}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        showZeroLine
                      />
                    </>
                  )}

                  {/* 前月比テーブル（MoM Table） */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <>
                      <div style={{ marginBottom: 12 }}>
                        <Segmented
                          options={[
                            { label: '全物件', value: 'all' },
                            { label: '戸建', value: 'detached' },
                            { label: 'セミデタッチド', value: 'semi_detached' },
                            { label: 'テラスハウス', value: 'terraced' },
                            { label: 'フラット', value: 'flat' },
                          ]}
                          value={propertyType}
                          onChange={(value) => setPropertyType(value as PropertyType)}
                        />
                      </div>
                      <MonthlyTable
                        data={momTableData}
                        getCellBgColor={getChangeCellColor10pct}
                        legendItems={CHANGE_LEGEND_10PCT}
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
                <MarketImpactTab indicatorId="uk_house_price" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
