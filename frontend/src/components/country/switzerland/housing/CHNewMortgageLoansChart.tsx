/**
 * スイス新規住宅ローンの融資限度額の合計金額チャートコンポーネント
 *
 * SNB Data Portalから新規住宅ローンの融資限度額の合計金額（四半期）を表示
 *
 * データソース:
 * - SNB Data Portal: https://data.snb.ch/en/topics/banken/cube/bahypoakredq
 *
 * 発表スケジュール:
 * - 四半期（Quarterly banking statistics）
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
import type { CHNewMortgageLoansData } from '../../../../hooks/useDashboardData'

interface CHNewMortgageLoansChartProps {
  data: CHNewMortgageLoansData | null
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
  value: '#DC143C',  // クリムゾン
  qoq: '#FF6B6B',    // 赤系（前期比）
  yoy: '#00CED1',    // シアン系（前年比）
}

// 表示モード
type ViewMode = 'value' | 'qoq' | 'qoq_table' | 'yoy'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'value', label: '金額' },
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

export default function CHNewMortgageLoansChart({ data }: CHNewMortgageLoansChartProps) {
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
    defaultStartYear: 2018,
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
    if (viewMode === 'value') return latestValue.value
    if (viewMode === 'qoq' || viewMode === 'qoq_table') return latestValue.qoq
    if (viewMode === 'yoy') return latestValue.yoy
    return latestValue.value
  }, [latestValue, viewMode])

  // 現在のビューモードに応じた色を取得
  const currentColor = useMemo(() => {
    if (viewMode === 'value') return COLORS.value
    if (viewMode === 'qoq' || viewMode === 'qoq_table') return COLORS.qoq
    if (viewMode === 'yoy') return COLORS.yoy
    return COLORS.value
  }, [viewMode])

  // 最新値ラベルを取得
  const getLatestLabel = () => {
    if (viewMode === 'value') return '新規住宅ローンの融資限度額の合計金額'
    if (viewMode === 'qoq' || viewMode === 'qoq_table') return '新規住宅ローンの融資限度額の合計金額（前期比）'
    if (viewMode === 'yoy') return '新規住宅ローンの融資限度額の合計金額（前年比）'
    return '新規住宅ローンの融資限度額の合計金額'
  }

  // フォーマット種別
  const getFormat = () => {
    if (viewMode === 'value') return 'number' as const
    return 'percent' as const
  }

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="新規住宅ローンの融資限度額の合計金額" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="新規住宅ローンの融資限度額の合計金額" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ch-new-mortgage-loans-chart">
      <ChartContainer
        title="新規住宅ローンの融資限度額の合計金額"
        showPeriodSelector={false}
        dataSource="Swiss National Bank"
        sourceUrl="https://data.snb.ch/en/topics/banken/cube/bahypoakredq"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={getLatestLabel()}
          value={currentLatestValue}
          date={latestValue?.date}
          format={getFormat()}
          decimals={2}
          unit={viewMode === 'value' ? 'MillionCHF' : undefined}
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
              onClick={() => window.open('/compare?s=ch_new_mortgage_loans', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* グラフ */}
        {viewMode === 'value' && (
          <StandardLineChart
            data={filteredData}
            lines={[{ dataKey: 'value', color: COLORS.value, name: '新規住宅ローンの融資限度額の合計金額' }]}
            yAxisFormatter={(v) => `${v.toFixed(1)}`}
            tooltipValueFormatter={(v) => `${v.toFixed(2)} Million CHF`}
            yDomain={['dataMin - 1', 'dataMax + 1']}
            showZeroLine={false}
          />
        )}
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
