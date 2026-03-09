/**
 * BOJ GDP Gap Chart Component
 * GDPギャップ（日銀）チャート
 *
 * データ項目:
 * - value: GDPギャップ (%)
 */

import { useEffect, useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import {
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import {
  fetchBOJGDPGapData,
  formatQuarterDate,
  parseQuarterDate,
  type BOJGDPGapResponse,
  type BOJGDPGapDataPoint,
} from '../../../../utils/japan/bojGDPGapApi'

// =============================================================================
// 定数
// =============================================================================

// カラー設定
const COLORS = {
  bojGdpGap: '#FF6B6B',
}

// =============================================================================
// 日付フォーマット
// =============================================================================

const formatDateLabel = (dateStr: string): string => {
  try {
    const [year, quarter] = dateStr.split('-')
    return `${year} ${quarter}`
  } catch {
    return dateStr
  }
}

// =============================================================================
// 期間フィルタリング（四半期データ用）
// =============================================================================

const filterByPeriod = (
  data: BOJGDPGapDataPoint[],
  period: number | 'default' | 'all'
): BOJGDPGapDataPoint[] => {
  if (period === 'all') {
    return [...data].sort((a, b) => {
      const dateA = parseQuarterDate(a.date)
      const dateB = parseQuarterDate(b.date)
      if (!dateA || !dateB) return 0
      return dateA.getTime() - dateB.getTime()
    })
  }

  const now = new Date()
  let startDate: Date

  if (period === 'default') {
    startDate = new Date(2015, 0, 1)  // 2015年Q1から
  } else if (typeof period === 'number') {
    startDate = new Date(now.getFullYear() - period, now.getMonth(), now.getDate())
  } else {
    return data
  }

  return data
    .filter(point => {
      const pointDate = parseQuarterDate(point.date)
      return pointDate && pointDate >= startDate
    })
    .sort((a, b) => {
      const dateA = parseQuarterDate(a.date)
      const dateB = parseQuarterDate(b.date)
      if (!dateA || !dateB) return 0
      return dateA.getTime() - dateB.getTime()
    })
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function BOJGDPGapChart() {
  const [data, setData] = useState<BOJGDPGapResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentPeriod, setCurrentPeriod] = useState<number | 'default' | 'all'>(20)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データ取得
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true)
        setError(null)
        const res = await fetchBOJGDPGapData()
        if (res.error) {
          setError(res.error)
        } else {
          setData(res)
        }
      } catch (err) {
        console.error('Error loading BOJ GDP Gap data:', err)
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
      .filter((d: BOJGDPGapDataPoint) => d.value !== null && d.value !== undefined)
      .map((d: BOJGDPGapDataPoint) => ({
        date: d.date,
        value: d.value,
      }))
  }, [data])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    return filterByPeriod(chartData, currentPeriod)
  }, [chartData, currentPeriod])

  const hasData = chartData.length > 0

  // ローディング状態
  if (loading) {
    return <LoadingChart title="GDPギャップ（日銀）" />
  }

  // エラー状態
  if (error) {
    return (
      <ChartContainer title="GDPギャップ（日銀）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>{error}</div>
      </ChartContainer>
    )
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="GDPギャップ（日銀）" showPeriodSelector={false} showDataSource={false}>
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
    <div id="boj-gdp-gap-chart">
      <ChartContainer
        title="GDPギャップ（日銀）"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="日本銀行"
        sourceUrl="https://www.boj.or.jp/research/research_data/gap/index.htm"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: 'GDPギャップ',
              value: latest?.value,
              color: COLORS.bojGdpGap,
              format: 'percent',
              decimals: 2,
            },
          ]}
          date={latest?.date}
          dateFormatter={formatQuarterDate}
          nextRelease={data?.next_release ? { date: formatNextRelease() || '' } : undefined}
        />

        {/* 期間セレクター + データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=japan_boj_gdp_gap', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* チャート */}
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'value', color: COLORS.bojGdpGap, name: 'GDPギャップ（日銀）', hide: hiddenSeries.has('value') },
          ]}
          yAxisFormatter={(v: number) => `${v.toFixed(1)}%`}
          yDomain={['dataMin - 1', 'dataMax + 1']}
          xAxisFormatter={formatDateLabel}
          tooltipLabelFormatter={formatQuarterDate}
          tooltipValueFormatter={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
          onLegendClick={handleLegendClick}
          showZeroLine={true}
        />
      </ChartContainer>
    </div>
  )
}
