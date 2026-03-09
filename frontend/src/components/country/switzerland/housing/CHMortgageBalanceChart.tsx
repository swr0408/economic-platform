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

// 指標種別
type DataKind = 'value' | 'yoy' | 'mom'
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'value', label: '残高' },
  { mode: 'mom', label: '前月比' },
]
type DisplayMode = 'chart' | 'heatmap'
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
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
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement('default', {
    default: 10,
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

  // 現在のデータ種別に応じた最新値を取得
  const currentLatestValue = useMemo(() => {
    if (!latestValue) return null
    if (dataKind === 'value') return latestValue.value
    if (dataKind === 'mom') return latestValue.mom
    if (dataKind === 'yoy') return latestValue.yoy
    return latestValue.value
  }, [latestValue, dataKind])

  // 現在のデータ種別に応じた色を取得
  const currentColor = useMemo(() => {
    if (dataKind === 'value') return COLORS.value
    if (dataKind === 'mom') return COLORS.mom
    if (dataKind === 'yoy') return COLORS.yoy
    return COLORS.value
  }, [dataKind])

  // 最新値ラベルを取得
  const getLatestLabel = () => {
    if (dataKind === 'value') return '住宅ローン残高'
    if (dataKind === 'mom') return '住宅ローン残高（前月比）'
    if (dataKind === 'yoy') return '住宅ローン残高（前年比）'
    return '住宅ローン残高'
  }

  // フォーマット種別
  const getFormat = () => {
    if (dataKind === 'value') return 'number' as const
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
          unit={dataKind === 'value' ? 'BillionCHF' : undefined}
          valueColor={currentColor}
          nextRelease={data.next_release ? { date: data.next_release } : null}
        />

        {/* 上段: 指標種別 + データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <ViewModeButtonGroup options={DATA_KIND_OPTIONS} currentMode={dataKind} onChange={setDataKind} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=ch_mortgage_balance&s=ch_mortgage_balance_yoy', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>
        {dataKind === 'mom' && (
          <div style={{ marginBottom: 8 }}>
            <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
          </div>
        )}

        {/* 期間セレクター */}
        {!(dataKind === 'mom' && displayMode === 'heatmap') && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          </div>
        )}

        {/* グラフ */}
        {dataKind === 'value' && (
          <StandardLineChart
            data={filteredData}
            lines={[{ dataKey: 'value', color: COLORS.value, name: '住宅ローン残高' }]}
            yAxisFormatter={(v) => `${v.toFixed(1)}`}
            tooltipValueFormatter={(v) => `${v.toFixed(2)} BillionCHF`}
            yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
            showZeroLine={false}
          />
        )}
        {dataKind === 'mom' && displayMode === 'chart' && (
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
        {dataKind === 'mom' && displayMode === 'heatmap' && (
          <MonthlyTable
            data={monthlyTableData}
            showLegend={true}
            showHelperText={true}
            helperText="※ 直近10年間の前月比データ（単位: %）"
          />
        )}
        {dataKind === 'yoy' && (
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
