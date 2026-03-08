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

// データ種別
type DataKind = 'yoy' | 'qoq'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
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

export default function CHHousingPricesChart({ data }: CHHousingPricesChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
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

  // 現在のデータ種別に応じた最新値を取得
  const currentLatestValue = useMemo(() => {
    if (!latestValue) return null
    if (dataKind === 'qoq') return latestValue.qoq
    if (dataKind === 'yoy') return latestValue.yoy
    return latestValue.yoy
  }, [latestValue, dataKind])

  // 現在のデータ種別に応じた色を取得
  const currentColor = useMemo(() => {
    if (dataKind === 'qoq') return COLORS.qoq
    if (dataKind === 'yoy') return COLORS.yoy
    return COLORS.yoy
  }, [dataKind])

  // 最新値ラベルを取得
  const getLatestLabel = () => {
    if (dataKind === 'qoq') return '住宅価格指数（前期比）'
    if (dataKind === 'yoy') return '住宅価格指数（前年比）'
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
              onClick={() => window.open('/compare?s=ch_housing_prices_qoq&s=ch_housing_prices_yoy', '_blank')}
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
