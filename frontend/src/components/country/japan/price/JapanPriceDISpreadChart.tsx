/**
 * 日本 価格DIスプレッド（日銀短観）チャートコンポーネント
 *
 * 販売価格判断DI - 仕入価格判断DI で計算（長期時系列・折れ線）
 * 企業のマージン（採算）とインフレ転嫁状況を表す。
 * - マイナス幅が大きいほど、企業のマージンが圧縮されている
 * - プラスは、コスト上昇を価格転嫁できている状態
 *
 * データソース:
 * - 日銀短観（BOJ Tankan Survey）販売価格判断DI(A12) / 仕入価格判断DI(A13)
 * - /api/japan/price-di-spread （zenyo過去ファイルを蓄積した長期履歴）
 *
 * 発表スケジュール: 四半期（4月、7月、10月、12月）
 */

import { useEffect, useState, useMemo } from 'react'
import { Tabs } from 'antd'
import { CalendarOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import { TEXT_COLORS } from '../../usa/common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface PriceDISpreadDataPoint {
  date: string
  large_manufacturing_spread: number | null
  all_industries_spread: number | null
  large_manufacturing_selling: number | null
  large_manufacturing_purchase: number | null
  all_industries_selling: number | null
  all_industries_purchase: number | null
}

interface NextRelease {
  date: string
  datetime_jst?: string
  time_jst?: string
  label?: string
}

interface PriceDISpreadResponse {
  data: PriceDISpreadDataPoint[]
  latest: PriceDISpreadDataPoint | null
  next_release?: NextRelease
  cached: boolean
  source: string
  last_updated: string
}

// =============================================================================
// 定数
// =============================================================================

// 既定表示はスプレッド2本。販売/仕入DIの内訳は凡例クリックで表示。
const SERIES: { key: keyof PriceDISpreadDataPoint; name: string; color: string; defaultHidden?: boolean }[] = [
  { key: 'large_manufacturing_spread', name: '大企業製造業 スプレッド', color: '#cf1322' },
  { key: 'all_industries_spread', name: '全産業 スプレッド', color: '#fa8c16' },
  { key: 'large_manufacturing_selling', name: '大企業製造業 販売価格DI', color: '#389e0d', defaultHidden: true },
  { key: 'large_manufacturing_purchase', name: '大企業製造業 仕入価格DI', color: '#722ed1', defaultHidden: true },
  { key: 'all_industries_selling', name: '全産業 販売価格DI', color: '#13c2c2', defaultHidden: true },
  { key: 'all_industries_purchase', name: '全産業 仕入価格DI', color: '#2f54eb', defaultHidden: true },
]

const INITIAL_HIDDEN = SERIES.filter((s) => s.defaultHidden).map((s) => s.key as string)

// =============================================================================
// ユーティリティ
// =============================================================================

function formatQuarterLabel(dateStr: string): string {
  const date = new Date(dateStr)
  const year = date.getFullYear() % 100
  const quarter = Math.floor(date.getMonth() / 3) + 1
  return `'${year.toString().padStart(2, '0')} Q${quarter}`
}

function formatNextRelease(nextRelease: NextRelease | null | undefined): string | null {
  if (!nextRelease) return null
  if (nextRelease.datetime_jst) {
    const dt = new Date(nextRelease.datetime_jst)
    return `${dt.getMonth() + 1}/${dt.getDate()} ${dt.getHours().toString().padStart(2, '0')}:${dt.getMinutes().toString().padStart(2, '0')}`
  }
  if (nextRelease.time_jst && nextRelease.date) {
    const dt = new Date(nextRelease.date)
    return `${dt.getMonth() + 1}/${dt.getDate()} ${nextRelease.time_jst}`
  }
  if (nextRelease.date) {
    const dt = new Date(nextRelease.date)
    return `${dt.getMonth() + 1}/${dt.getDate()}`
  }
  return null
}

// =============================================================================
// API
// =============================================================================

async function fetchPriceDISpreadData(): Promise<PriceDISpreadResponse | null> {
  try {
    const response = await fetch('/api/japan/price-di-spread')
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
    return await response.json()
  } catch (error) {
    console.error('Failed to fetch price DI spread data:', error)
    return null
  }
}

// =============================================================================
// コンポーネント
// =============================================================================

export default function JapanPriceDISpreadChart() {
  const [data, setData] = useState<PriceDISpreadResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(10)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries(INITIAL_HIDDEN)

  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      const result = await fetchPriceDISpreadData()
      setData(result)
      setLoading(false)
    }
    loadData()
  }, [])

  const chartData = useMemo(() => {
    if (!data?.data) return []
    return data.data.map((p) => ({
      date: p.date,
      large_manufacturing_spread: p.large_manufacturing_spread,
      all_industries_spread: p.all_industries_spread,
      large_manufacturing_selling: p.large_manufacturing_selling,
      large_manufacturing_purchase: p.large_manufacturing_purchase,
      all_industries_selling: p.all_industries_selling,
      all_industries_purchase: p.all_industries_purchase,
    }))
  }, [data])

  const sortedData = useSortedData(chartData)
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2018,
  })

  // 表示中（非表示でない）の系列のみでY軸範囲を決める。
  // 既定で隠れている内訳DI（販売/仕入=40〜52）を含めるとスプレッド線が潰れるため。
  const yDomain = useMemo<[number, number]>(() => {
    const visibleKeys = SERIES.filter((s) => !hiddenSeries.has(s.key as string)).map((s) => s.key)
    const values = filteredData.flatMap((d) =>
      visibleKeys.map((k) => d[k as keyof typeof d] as number | null).filter(
        (v): v is number => typeof v === 'number'
      )
    )
    if (values.length === 0) return [-30, 10]
    return [Math.floor((Math.min(...values) - 3) / 5) * 5, Math.ceil((Math.max(...values) + 3) / 5) * 5]
  }, [filteredData, hiddenSeries])

  if (loading) {
    return <LoadingChart title="価格DIスプレッド" />
  }

  if (!data || !data.data || data.data.length === 0) {
    return (
      <ChartContainer title="価格DIスプレッド（販売価格DI - 仕入価格DI）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const nextReleaseFormatted = formatNextRelease(data.next_release)
  const lines = SERIES.map((s) => ({
    dataKey: s.key as string,
    color: s.color,
    name: s.name,
    strokeWidth: s.defaultHidden ? 1.5 : 2.5,
    hide: hiddenSeries.has(s.key as string),
  }))

  return (
    <div id="japan-price-di-spread-chart">
      <ChartContainer
        title="価格DIスプレッド（販売価格DI - 仕入価格DI）"
        showPeriodSelector={false}
        dataSource="日本銀行（BOJ）短観"
        sourceUrl="https://www.boj.or.jp/statistics/tk/index.htm"
        handbookId="price-di-spread"
        extra={
          nextReleaseFormatted && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: TEXT_COLORS.secondary }}>
              <CalendarOutlined />
              <span>次回発表: {nextReleaseFormatted}</span>
            </div>
          )
        }
      >
        <Tabs
          defaultActiveKey="timeseries"
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                  </div>
                  <StandardLineChart
                    data={filteredData}
                    lines={lines}
                    yAxisFormatter={(v) => `${v.toFixed(0)}`}
                    yDomain={yDomain}
                    showZeroLine={true}
                    xAxisFormatter={formatQuarterLabel}
                    tooltipLabelFormatter={formatQuarterLabel}
                    tooltipValueFormatter={(v) => `${v.toFixed(1)} %pt`}
                    onLegendClick={handleLegendClick}
                  />
                </>
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
