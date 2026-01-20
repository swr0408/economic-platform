/**
 * UK ONS小売売上高チャートコンポーネント
 *
 * データ:
 * - 小売売上高前年比 (YoY) - 全小売（燃料込み）
 * - 小売売上高前月比 (MoM) - 全小売（燃料込み）
 * - コア小売売上高前年比 (Core YoY) - 燃料除く
 * - コア小売売上高前月比 (Core MoM) - 燃料除く
 *
 * データソース:
 * - Office for National Statistics (ONS)
 * - DRSI Dataset (Volume Seasonally Adjusted)
 *
 * 発表スケジュール:
 * - 毎月（通常月中旬）
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip, Segmented } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMonthlyTableData,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  ViewModeButtonGroup,
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { ONSRetailSalesData } from '../../../../hooks/useDashboardData'

interface ONSRetailSalesChartProps {
  data: ONSRetailSalesData | null
}

interface ChartDataPoint {
  date: string
  yoy: number
  mom: number
  core_yoy: number
  core_mom: number
  [key: string]: unknown
}

type ViewMode = 'yoy' | 'mom_table' | 'mom_chart'
type SeriesType = 'all' | 'core'

// グラフの色
const COLORS = {
  yoy: '#1890ff',
  mom: '#52c41a',
  core_yoy: '#722ed1',
  core_mom: '#eb2f96',
}

export default function ONSRetailSalesChart({ data }: ONSRetailSalesChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('yoy')
  const [seriesType, setSeriesType] = useState<SeriesType>('all')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy: 'default',
    mom_table: 'default',
    mom_chart: 3,
  })

  // propsのデータをチャート用に変換（全系列をマージ）
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const dateMap = new Map<string, ChartDataPoint>()

    const initPoint = (date: string): ChartDataPoint => ({
      date, yoy: 0, mom: 0, core_yoy: 0, core_mom: 0
    })

    // 全小売YoY
    if (data.yoy) {
      data.yoy.forEach(point => {
        if (!dateMap.has(point.date)) {
          dateMap.set(point.date, initPoint(point.date))
        }
        dateMap.get(point.date)!.yoy = point.value
      })
    }

    // 全小売MoM
    if (data.mom) {
      data.mom.forEach(point => {
        if (!dateMap.has(point.date)) {
          dateMap.set(point.date, initPoint(point.date))
        }
        dateMap.get(point.date)!.mom = point.value
      })
    }

    // コアYoY
    if (data.core_yoy) {
      data.core_yoy.forEach(point => {
        if (!dateMap.has(point.date)) {
          dateMap.set(point.date, initPoint(point.date))
        }
        dateMap.get(point.date)!.core_yoy = point.value
      })
    }

    // コアMoM
    if (data.core_mom) {
      data.core_mom.forEach(point => {
        if (!dateMap.has(point.date)) {
          dateMap.set(point.date, initPoint(point.date))
        }
        dateMap.get(point.date)!.core_mom = point.value
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
    seriesType === 'all' ? item.mom : item.core_mom
  )

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (!chartData.length) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  // 現在の表示値を取得
  const currentValue = useMemo(() => {
    if (!latest) return null
    if (viewMode === 'yoy') {
      return seriesType === 'all' ? latest.yoy : latest.core_yoy
    }
    return seriesType === 'all' ? latest.mom : latest.core_mom
  }, [latest, viewMode, seriesType])

  const currentColor = useMemo(() => {
    if (viewMode === 'yoy') {
      return seriesType === 'all' ? COLORS.yoy : COLORS.core_yoy
    }
    return seriesType === 'all' ? COLORS.mom : COLORS.core_mom
  }, [viewMode, seriesType])

  if (data === null) {
    return <LoadingChart title="小売売上高（イギリス）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="小売売上高（イギリス）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const yoyDataKey = seriesType === 'all' ? 'yoy' : 'core_yoy'
  const momDataKey = seriesType === 'all' ? 'mom' : 'core_mom'
  const seriesLabel = seriesType === 'all' ? '全小売（燃料込み）' : 'コア（燃料除く）'

  return (
    <div id="uk-retail-sales-chart">
      <ChartContainer
        title="小売売上高"
        showPeriodSelector={false}
        dataSource="ONS"
        sourceUrl="https://www.ons.gov.uk/businessindustryandtrade/retailindustry"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={currentValue}
          valueColor={currentColor}
          date={latest?.date}
          nextRelease={data.next_release}
          format="percent"
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
                  {/* 系列選択（全小売 vs コア） */}
                  <div style={{ marginBottom: 12 }}>
                    <Segmented
                      options={[
                        { label: '全小売（燃料込み）', value: 'all' },
                        { label: 'コア（燃料除く）', value: 'core' },
                      ]}
                      value={seriesType}
                      onChange={(value) => setSeriesType(value as SeriesType)}
                    />
                  </div>

                  <ViewModeButtonGroup
                    currentMode={viewMode}
                    onChange={(mode) => setViewMode(mode)}
                    options={[
                      { mode: 'mom_chart', label: '前月比グラフ' },
                      { mode: 'mom_table', label: '前月比テーブル' },
                      { mode: 'yoy', label: '前年比' },
                    ]}
                  />

                  {/* 期間セレクター */}
                  {(viewMode === 'yoy' || viewMode === 'mom_chart') && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <Tooltip title="比較ページを開く">
                        <Button
                          icon={<AreaChartOutlined />}
                          onClick={() => window.open(`/compare?s=uk_retail_sales_yoy&s=uk_retail_sales_core_yoy`, '_blank')}
                        >
                          データ比較
                        </Button>
                      </Tooltip>
                    </div>
                  )}

                  {/* コンテンツ表示 */}
                  {viewMode === 'mom_table' && <MonthlyTable data={momTableData} />}

                  {viewMode === 'yoy' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        {
                          dataKey: yoyDataKey,
                          color: seriesType === 'all' ? COLORS.yoy : COLORS.core_yoy,
                          name: `小売売上高 ${seriesLabel}（前年比）`,
                          hide: hiddenSeries.has(yoyDataKey)
                        },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      onLegendClick={handleLegendClick}
                      yDomain={['dataMin - 2', 'dataMax + 2']}
                      
                    />
                  )}

                  {viewMode === 'mom_chart' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        {
                          dataKey: momDataKey,
                          color: seriesType === 'all' ? COLORS.mom : COLORS.core_mom,
                          name: `小売売上高 ${seriesLabel}（前月比）`
                        },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="ons_retail_sales" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
