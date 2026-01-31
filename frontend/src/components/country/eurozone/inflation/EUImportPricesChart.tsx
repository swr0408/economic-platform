/**
 * EU輸入物価チャートコンポーネント
 *
 * Eurostat APIからEU輸入物価指数データを取得し、表示
 *
 * データ:
 * - Import Prices YoY (輸入物価 前年比)
 * - Import Prices MoM (輸入物価 前月比)
 *
 * データソース:
 * - Eurostat (teiis011)
 *
 * 発表スケジュール:
 * - Eurostatリリースカレンダーから取得
 */
import { useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'

import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMonthlyTableData,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
  StandardBarChart,
  ViewModeButtonGroup,
  ChartControlRow,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'

import type { EUImportPricesData } from '../../../../hooks/useDashboardData'

interface EUImportPricesChartProps {
  data: EUImportPricesData | null
}

interface ChartDataPoint {
  date: string
  yoy: number | null
  mom: number | null
  [key: string]: unknown
}

// 表示モード: YoYはチャートのみ、MoMはテーブル＋チャート
type ViewMode = 'yoy' | 'mom_table' | 'mom_chart'

const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom_chart', label: '前月比' },
  { mode: 'mom_table', label: '前月比（テーブル）' },
]

// グラフの色
const COLORS = {
  import_prices: '#1890ff',
}

export default function EUImportPricesChart({ data }: EUImportPricesChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('yoy')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy: 'default',
    mom_table: 'default',
    mom_chart: 3,
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const yoyData = data.yoy || []
    const momData = data.mom || []

    // 日付をキーにしたマップを作成
    const dateMap = new Map<string, ChartDataPoint>()

    const initPoint = (date: string): ChartDataPoint => ({
      date,
      yoy: null,
      mom: null,
    })

    yoyData.forEach((point) => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      dateMap.get(point.date)!.yoy = point.value
    })

    momData.forEach((point) => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      dateMap.get(point.date)!.mom = point.value
    })

    return Array.from(dateMap.values())
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  // テーブル用データ
  const momTableData = useMonthlyTableData(chartData, (item) => item.mom, 10)

  const hasData = chartData.length > 0

  // 最新値を取得（YoY）
  const latestYoy = useMemo(() => {
    if (!chartData.length) return null
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].yoy !== null) {
        return chartData[i]
      }
    }
    return null
  }, [chartData])

  // 前月比の最新値を取得
  const latestMom = useMemo(() => {
    if (!chartData.length) return null
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].mom !== null) {
        return chartData[i]
      }
    }
    return null
  }, [chartData])

  if (data === null) {
    return <LoadingChart title="輸入物価（ユーロ圏）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="輸入物価（ユーロ圏）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="eu-import-prices-chart">
      <ChartContainer
        title="輸入物価（ユーロ圏）"
        showPeriodSelector={false}
        dataSource="Eurostat"
        sourceUrl="https://ec.europa.eu/eurostat/statistics-explained/index.php?title=Industrial_import_price_index_overview"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={
            viewMode === 'yoy'
              ? [
                  {
                    label: '輸入物価（前年比）',
                    value: latestYoy?.yoy,
                    color: COLORS.import_prices,
                    format: 'percent',
                  },
                ]
              : [
                  {
                    label: '輸入物価（前月比）',
                    value: latestMom?.mom,
                    color: COLORS.import_prices,
                    format: 'percent',
                  },
                ]
          }
          date={viewMode === 'yoy' ? latestYoy?.date : latestMom?.date}
          nextRelease={data.next_release}
        />

        {/* ビューモード切り替え */}
        <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />

        {/* 期間セレクタとデータ比較ボタン（テーブル表示以外） */}
        {viewMode !== 'mom_table' && (
          <ChartControlRow
            selectedPeriod={currentPeriod}
            onPeriodChange={setCurrentPeriod}
            indicatorId={viewMode === 'yoy' ? 'eu_import_prices_yoy' : 'eu_import_prices_mom'}
          />
        )}

        {/* 前年比グラフ */}
        {viewMode === 'yoy' && (
          <StandardLineChart
            data={filteredData}
            lines={[
              { dataKey: 'yoy', color: COLORS.import_prices, name: '輸入物価（前年比）' },
            ]}
            yAxisFormatter={(v) => `${v}%`}
            yDomain={['dataMin - 1', 'dataMax + 1']}
            showZeroLine={true}
            showLegend={false}
          />
        )}

        {/* 前月比テーブル */}
        {viewMode === 'mom_table' && (
          <MonthlyTable
            data={momTableData}
            helperText="※ 直近10年間の前月比データ（単位: %）"
          />
        )}

        {/* 前月比グラフ */}
        {viewMode === 'mom_chart' && (
          <StandardBarChart
            data={filteredData}
            bars={[
              { dataKey: 'mom', color: COLORS.import_prices, name: '輸入物価（前月比）' },
            ]}
            yAxisFormatter={(v) => `${v}%`}
            yDomain={['dataMin - 1', 'dataMax + 1']}
          />
        )}
      </ChartContainer>
    </div>
  )
}
