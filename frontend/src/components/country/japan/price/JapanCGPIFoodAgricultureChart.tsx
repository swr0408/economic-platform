/**
 * Japan CGPI Food & Agriculture Chart Component
 * 企業物価指数：飲食料品・農林水産物チャート
 *
 * データ項目:
 * - food_yoy: 飲食料品 前年同月比 (%)
 * - agriculture_yoy: 農林水産物 前年同月比 (%)
 */

import { useEffect, useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import {
  fetchCGPIFoodAgricultureData,
  type CGPIFoodAgricultureResponse,
  type CGPIFoodAgricultureDataPoint,
} from '../../../../utils/japan/cgpiFoodAgricultureApi'

// =============================================================================
// 定数
// =============================================================================

// カラー設定
const COLORS = {
  food: '#ff6384',
  agriculture: '#36a2eb',
}

// =============================================================================
// 日付フォーマット
// =============================================================================

const formatDateLabel = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}`
}

const formatDateLabelJP = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return `${date.getFullYear()}年${date.getMonth() + 1}月`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function JapanCGPIFoodAgricultureChart() {
  const [data, setData] = useState<CGPIFoodAgricultureResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentPeriod, setCurrentPeriod] = useState<number | 'default' | 'all'>(10)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データ取得
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true)
        setError(null)
        const res = await fetchCGPIFoodAgricultureData()
        if (res.error) {
          setError(res.error)
        } else {
          setData(res)
        }
      } catch (err) {
        console.error('Error loading CGPI Food/Agriculture data:', err)
        setError('データの読み込みに失敗しました')
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [])

  // データを変換
  const chartData = useMemo(() => {
    if (!data?.data) return []

    return data.data
      .filter((d: CGPIFoodAgricultureDataPoint) => d.food_yoy !== null || d.agriculture_yoy !== null)
      .map((d: CGPIFoodAgricultureDataPoint) => ({
        date: d.date,
        food_yoy: d.food_yoy,
        agriculture_yoy: d.agriculture_yoy,
      }))
  }, [data])

  // データを日付昇順にソート
  const sortedData = useSortedData(chartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2021,
  })

  const hasData = sortedData.length > 0

  // ローディング状態
  if (loading) {
    return <LoadingChart title="企業物価指数：飲食料品 / 農林水産物（前年比）" />
  }

  // エラー状態
  if (error) {
    return (
      <ChartContainer title="企業物価指数：飲食料品 / 農林水産物（前年比）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>{error}</div>
      </ChartContainer>
    )
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="企業物価指数：飲食料品 / 農林水産物（前年比）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  // 次回発表日のフォーマット
  const formatNextRelease = () => {
    if (!data?.next_release) return null
    const nr = data.next_release
    if (nr.datetime_jst) {
      const dt = new Date(nr.datetime_jst)
      return `${dt.getMonth() + 1}/${dt.getDate()} ${dt.getHours().toString().padStart(2, '0')}:${dt.getMinutes().toString().padStart(2, '0')}`
    }
    if (nr.date) {
      const dt = new Date(nr.date)
      return `${dt.getMonth() + 1}/${dt.getDate()}`
    }
    return null
  }

  return (
    <div id="japan-cgpi-food-agriculture-chart">
      <ChartContainer
        title="企業物価指数：飲食料品 / 農林水産物（前年比）"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="日本銀行"
        sourceUrl="https://www.boj.or.jp/statistics/pi/cgpi_release/index.htm"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '飲食料品',
              value: latest?.food_yoy,
              color: COLORS.food,
              format: 'percent',
            },
            {
              label: '農林水産物',
              value: latest?.agriculture_yoy,
              color: COLORS.agriculture,
              format: 'percent',
            },
          ]}
          date={latest?.date}
          dateFormatter={formatDateLabelJP}
          nextRelease={data?.next_release ? { date: formatNextRelease() || '' } : undefined}
        />

        {/* 期間セレクター + データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=japan_cgpi_food_yoy&s=japan_cgpi_agriculture_yoy', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* チャート */}
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'agriculture_yoy', color: COLORS.agriculture, name: '農林水産物（前年比）', hide: hiddenSeries.has('agriculture_yoy') },
            { dataKey: 'food_yoy', color: COLORS.food, name: '飲食料品（前年比）', hide: hiddenSeries.has('food_yoy'), yAxisId: 'right' },
          ]}
          yAxisFormatter={(v: number) => `${v}%`}
          yDomain={['dataMin - 1', 'dataMax + 1']}
          xAxisFormatter={formatDateLabel}
          tooltipLabelFormatter={formatDateLabelJP}
          tooltipValueFormatter={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
          onLegendClick={handleLegendClick}
          showRightYAxis={true}
          rightYAxisFormatter={(v: number) => `${v}%`}
          rightYDomain={['dataMin - 1', 'dataMax + 1']}
        />
      </ChartContainer>
    </div>
  )
}
