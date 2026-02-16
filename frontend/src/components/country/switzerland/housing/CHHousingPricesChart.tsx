/**
 * スイス住宅価格指数チャートコンポーネント
 *
 * BFS（スイス連邦統計局）から住宅価格指数（四半期）を表示
 *
 * データソース:
 * - BFS: https://www.bfs.admin.ch/
 *
 * 発表スケジュール:
 * - 四半期
 */
import { useMemo, useState } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
  StandardBarChart,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'
import { QuarterlyTable } from '../../usa/common/QuarterlyTable'

// 型定義
import type { CHHousingPricesData } from '../../../../hooks/useDashboardData'

interface CHHousingPricesChartProps {
  data: CHHousingPricesData | null
}

interface ChartDataPoint {
  date: string
  quarter: string
  value: number | null
  qoq: number | null
  yoy: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  qoq: '#FF6B6B',    // 赤系（前期比）
  yoy: '#00CED1',    // シアン系（前年比）
}

// 表示モード
type ViewMode = 'qoq' | 'qoq_table' | 'yoy'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'qoq', label: '前期比' },
  { mode: 'qoq_table', label: '前期比テーブル' },
]

// 日付から年を抽出
const getYearFromDate = (dateStr: string): number => {
  return parseInt(dateStr.split('-')[0], 10)
}

// 日付から四半期を抽出（0-indexed: Q1=0, Q2=1, Q3=2, Q4=3）
const getQuarterFromDate = (dateStr: string): number => {
  const month = parseInt(dateStr.split('-')[1], 10)
  return Math.floor((month - 1) / 3)
}

export default function CHHousingPricesChart({ data }: CHHousingPricesChartProps) {
  // 表示モード
  const [viewMode, setViewMode] = useState<ViewMode>('yoy')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement('default', {
    default: 'default',
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map((item) => ({
      date: item.date,
      quarter: item.quarter,
      value: item.value,
      qoq: item.qoq ?? null,
      yoy: item.yoy ?? null,
    }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = useMemo(() => {
    if (!chartData.length) return null
    for (let i = chartData.length - 1; i >= 0; i--) {
      const item = chartData[i]
      if (item.value !== null) {
        return item
      }
    }
    return null
  }, [chartData])

  // テーブル用データ（四半期：年別×四半期のマトリックス）
  const quarterlyTableData = useMemo(() => {
    if (!chartData.length) return { years: [] as number[], quarterlyData: {} as Record<number, Record<number, number | null>> }

    const years = new Set<number>()
    const quarterlyData: Record<number, Record<number, number | null>> = {}

    chartData.forEach(item => {
      const year = getYearFromDate(item.date)
      const quarter = getQuarterFromDate(item.date)

      if (year > 0) {
        years.add(year)
        if (!quarterlyData[year]) {
          quarterlyData[year] = {}
        }
        quarterlyData[year][quarter] = item.qoq
      }
    })

    const sortedYears = Array.from(years).sort((a, b) => b - a).slice(0, 10).reverse()
    return { years: sortedYears, quarterlyData }
  }, [chartData])

  // 現在のビューモードに応じた最新値を取得
  const currentLatestValue = useMemo(() => {
    if (!latestValue) return null
    if (viewMode === 'qoq' || viewMode === 'qoq_table') return latestValue.qoq
    if (viewMode === 'yoy') return latestValue.yoy
    return latestValue.yoy
  }, [latestValue, viewMode])

  // 現在のビューモードに応じた色を取得
  const currentColor = useMemo(() => {
    if (viewMode === 'qoq' || viewMode === 'qoq_table') return COLORS.qoq
    if (viewMode === 'yoy') return COLORS.yoy
    return COLORS.yoy
  }, [viewMode])

  // 最新値ラベルを取得
  const getLatestLabel = () => {
    if (viewMode === 'qoq' || viewMode === 'qoq_table') return '住宅価格指数（前期比）'
    if (viewMode === 'yoy') return '住宅価格指数（前年比）'
    return '住宅価格指数（前年比）'
  }

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="住宅価格指数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="住宅価格指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ch-housing-prices-chart">
      <ChartContainer
        title="住宅価格指数"
        showPeriodSelector={false}
        dataSource="Swiss Federal Statistical Office"
        sourceUrl="https://www.bfs.admin.ch/"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={getLatestLabel()}
          value={currentLatestValue}
          date={latestValue?.date}
          format="percent"
          decimals={2}
          valueColor={currentColor}
          nextRelease={data.next_release ? { date: data.next_release } : null}
        />

        {/* ビューモード切替 */}
        <ViewModeButtonGroup
          options={VIEW_MODE_OPTIONS}
          currentMode={viewMode}
          onChange={setViewMode}
        />

        {/* 期間セレクター・データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=ch_housing_prices_qoq&s=ch_housing_prices_yoy', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* グラフ */}
        {viewMode === 'qoq' && (
          <StandardBarChart
            data={filteredData}
            bars={[{
              dataKey: 'qoq',
              color: COLORS.qoq,
              name: '前期比'
            }]}
            yAxisFormatter={(v) => `${v.toFixed(1)}%`}
            tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
          />
        )}
        {viewMode === 'qoq_table' && (
          <QuarterlyTable
            data={quarterlyTableData}
            showLegend={true}
            showHelperText={true}
            helperText="※ 直近10年間の前期比データ（単位: %）"
          />
        )}
        {viewMode === 'yoy' && (
          <StandardLineChart
            data={filteredData}
            lines={[{
              dataKey: 'yoy',
              color: COLORS.yoy,
              name: '前年比'
            }]}
            yAxisFormatter={(v) => `${v.toFixed(1)}%`}
            tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
            yDomain={['dataMin - 2', 'dataMax + 2']}
            showZeroLine={true}
          />
        )}
      </ChartContainer>
    </div>
  )
}
