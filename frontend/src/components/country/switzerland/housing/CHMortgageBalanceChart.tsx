/**
 * スイス住宅ローン残高チャートコンポーネント
 *
 * SNB Data Portalから住宅ローン残高（国内・CHF建て・全銀行）を表示
 *
 * データソース:
 * - SNB Data Portal: https://data.snb.ch/
 *
 * 発表スケジュール:
 * - 月次（Monthly banking statistics）- 20日以降の最初の営業日 09:00（チューリッヒ時間）
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
import { MonthlyTable } from '../../usa/common/MonthlyTable'

// 型定義
import type { CHMortgageBalanceData } from '../../../../hooks/useDashboardData'

interface CHMortgageBalanceChartProps {
  data: CHMortgageBalanceData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  mom: number | null
  yoy: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  value: '#4169E1',  // 青系（残高）
  mom: '#FF6B6B',    // 赤系（前月比）
  yoy: '#00CED1',    // シアン系（前年比）
}

// 表示モード
type ViewMode = 'value' | 'mom' | 'mom_table' | 'yoy'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'value', label: '残高' },
  { mode: 'mom', label: '前月比' },
  { mode: 'mom_table', label: '前月比テーブル' },
]

// 日付から年を抽出
const getYearFromDate = (dateStr: string): number => {
  return parseInt(dateStr.split('-')[0], 10)
}

// 日付から月を抽出（0-indexed）
const getMonthFromDate = (dateStr: string): number => {
  return parseInt(dateStr.split('-')[1], 10) - 1
}

export default function CHMortgageBalanceChart({ data }: CHMortgageBalanceChartProps) {
  // 表示モード（残高 / 前月比 / 前年比）
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
      value: item.value,
      mom: item.mom ?? null,
      yoy: item.yoy ?? null,
    }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
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

  // テーブル用データ（月次：年別×月のマトリックス）
  const monthlyTableData = useMemo(() => {
    if (!chartData.length) return { years: [] as number[], monthlyData: {} as Record<number, Record<number, number | null>> }

    const years = new Set<number>()
    const monthlyData: Record<number, Record<number, number | null>> = {}

    chartData.forEach(item => {
      const year = getYearFromDate(item.date)
      const month = getMonthFromDate(item.date)

      if (year > 0) {
        years.add(year)
        if (!monthlyData[year]) {
          monthlyData[year] = {}
        }
        monthlyData[year][month] = item.mom
      }
    })

    const sortedYears = Array.from(years).sort((a, b) => b - a).slice(0, 10).reverse()
    return { years: sortedYears, monthlyData }
  }, [chartData])

  // 現在のビューモードに応じた最新値を取得
  const currentLatestValue = useMemo(() => {
    if (!latestValue) return null
    if (viewMode === 'value') return latestValue.value
    if (viewMode === 'mom' || viewMode === 'mom_table') return latestValue.mom
    if (viewMode === 'yoy') return latestValue.yoy
    return latestValue.value
  }, [latestValue, viewMode])

  // 現在のビューモードに応じた色を取得
  const currentColor = useMemo(() => {
    if (viewMode === 'value') return COLORS.value
    if (viewMode === 'mom' || viewMode === 'mom_table') return COLORS.mom
    if (viewMode === 'yoy') return COLORS.yoy
    return COLORS.value
  }, [viewMode])

  // 最新値ラベルを取得
  const getLatestLabel = () => {
    if (viewMode === 'value') return '住宅ローン残高'
    if (viewMode === 'mom' || viewMode === 'mom_table') return '住宅ローン残高（前月比）'
    if (viewMode === 'yoy') return '住宅ローン残高（前年比）'
    return '住宅ローン残高'
  }

  // フォーマット種別
  const getFormat = () => {
    if (viewMode === 'value') return 'number' as const
    return 'percent' as const
  }

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="住宅ローン残高" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="住宅ローン残高" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ch-mortgage-balance-chart">
      <ChartContainer
        title="住宅ローン残高"
        showPeriodSelector={false}
        dataSource="Swiss National Bank"
        sourceUrl="https://data.snb.ch/en/warehouse/BSTA/cube/BSTA@SNB.MONA_B.BIL.PAS.FFV.STP?utm_source=chatgpt.com&fromDate=2015-11&toDate=2025-12&dimSel=INLANDAUSLAND(I),WAEHRUNG(CHF)"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={getLatestLabel()}
          value={currentLatestValue}
          date={latestValue?.date}
          format={getFormat()}
          decimals={2}
          unit={viewMode === 'value' ? 'BillionCHF' : undefined}
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
              onClick={() => window.open('/compare?s=ch_mortgage_balance&s=ch_mortgage_balance_yoy', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* グラフ */}
        {viewMode === 'value' && (
          <StandardLineChart
            data={filteredData}
            lines={[{ dataKey: 'value', color: COLORS.value, name: '住宅ローン残高' }]}
            yAxisFormatter={(v) => `${v.toFixed(1)}`}
            tooltipValueFormatter={(v) => `${v.toFixed(2)} BillionCHF`}
            yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
            showZeroLine={false}
          />
        )}
        {viewMode === 'mom' && (
          <StandardBarChart
            data={filteredData}
            bars={[{
              dataKey: 'mom',
              color: COLORS.mom,
              name: '前月比'
            }]}
            yAxisFormatter={(v) => `${v.toFixed(1)}%`}
            tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
          />
        )}
        {viewMode === 'mom_table' && (
          <MonthlyTable
            data={monthlyTableData}
            showLegend={true}
            showHelperText={true}
            helperText="※ 直近10年間の前月比データ（単位: %）"
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
            yDomain={['dataMin - 0.2', 'dataMax + 0.2']}
            showZeroLine={true}
          />
        )}
      </ChartContainer>
    </div>
  )
}
