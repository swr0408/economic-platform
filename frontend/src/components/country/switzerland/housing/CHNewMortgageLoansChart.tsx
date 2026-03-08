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

// データ種別
type DataKind = 'value' | 'yoy' | 'qoq'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'value', label: '金額' },
  { mode: 'qoq', label: '前期比' },
]

// 表示形式
type DisplayMode = 'chart' | 'heatmap'

const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
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
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    value: 'default',
    yoy: 'default',
    qoq: 'default',
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

  // 現在のデータ種別に応じた最新値を取得
  const currentLatestValue = useMemo(() => {
    if (!latestValue) return null
    if (dataKind === 'value') return latestValue.value
    if (dataKind === 'qoq') return latestValue.qoq
    if (dataKind === 'yoy') return latestValue.yoy
    return latestValue.value
  }, [latestValue, dataKind])

  // 現在のデータ種別に応じた色を取得
  const currentColor = useMemo(() => {
    if (dataKind === 'value') return COLORS.value
    if (dataKind === 'qoq') return COLORS.qoq
    if (dataKind === 'yoy') return COLORS.yoy
    return COLORS.value
  }, [dataKind])

  // 最新値ラベルを取得
  const getLatestLabel = () => {
    if (dataKind === 'value') return '新規住宅ローンの融資限度額の合計金額'
    if (dataKind === 'qoq') return '新規住宅ローンの融資限度額の合計金額（前期比）'
    if (dataKind === 'yoy') return '新規住宅ローンの融資限度額の合計金額（前年比）'
    return '新規住宅ローンの融資限度額の合計金額'
  }

  // フォーマット種別
  const getFormat = () => {
    if (dataKind === 'value') return 'number' as const
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
          unit={dataKind === 'value' ? 'MillionCHF' : undefined}
          valueColor={currentColor}
          nextRelease={data.next_release ? { date: data.next_release } : null}
        />

        {/* 上段: データ種別 + データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <ViewModeButtonGroup
            options={DATA_KIND_OPTIONS}
            currentMode={dataKind}
            onChange={setDataKind}
          />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=ch_new_mortgage_loans', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 下段: 表示形式（qoqのときのみ） */}
        {dataKind === 'qoq' && (
          <div style={{ marginBottom: 8 }}>
            <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
          </div>
        )}

        {/* 期間セレクター（ヒートマップ以外で表示） */}
        {!(dataKind === 'qoq' && displayMode === 'heatmap') && (
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
        )}

        {/* 金額チャート */}
        {dataKind === 'value' && (
          <StandardLineChart
            data={filteredData}
            lines={[{ dataKey: 'value', color: COLORS.value, name: '新規住宅ローンの融資限度額の合計金額' }]}
            yAxisFormatter={(v) => `${v.toFixed(1)}`}
            tooltipValueFormatter={(v) => `${v.toFixed(2)} Million CHF`}
            yDomain={['dataMin - 1', 'dataMax + 1']}
            showZeroLine={false}
          />
        )}

        {/* 前期比チャート */}
        {dataKind === 'qoq' && displayMode === 'chart' && (
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

        {/* 前期比ヒートマップ */}
        {dataKind === 'qoq' && displayMode === 'heatmap' && (
          <QuarterlyTable
            data={quarterlyTableData}
            showLegend={true}
            showHelperText={true}
            helperText="※ 直近10年間の前期比データ（単位: %）"
          />
        )}

        {/* 前年比チャート */}
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
            yDomain={['dataMin - 2', 'dataMax + 2']}
            showZeroLine={true}
          />
        )}
      </ChartContainer>
    </div>
  )
}
