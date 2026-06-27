/**
 * 日本 企業の物価見通し（日銀短観 表7）チャートコンポーネント
 *
 * 全規模合計・全産業・1年後の「販売価格の見通し」と「物価全般の見通し」を
 * 同一チャートに2本の折れ線で表示する（凡例クリックで個別に表示/非表示）。
 *
 * データソース:
 * - 日銀短観 概要ZIP同梱 Excel（GA_J1.xlsx）「表7 企業の物価見通し」
 * - /api/japan/inflation-outlook
 *
 * 発表スケジュール: 四半期（3/6/9/12月調査）
 */

import { useEffect, useState, useMemo } from 'react'
import { Tabs } from 'antd'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface InflationOutlookDataPoint {
  date: string
  selling_price_outlook: number | null
  general_price_outlook: number | null
}

interface NextRelease {
  date?: string
  datetime_jst?: string
  time_jst?: string
  label?: string
}

interface InflationOutlookResponse {
  data: InflationOutlookDataPoint[]
  latest: InflationOutlookDataPoint | null
  metadata?: Record<string, unknown>
  next_release?: NextRelease | null
  cached: boolean
  source: string
  last_updated: string | null
}

interface ChartDataPoint {
  date: string
  selling_price_outlook: number | null
  general_price_outlook: number | null
}

// =============================================================================
// 定数
// =============================================================================

const SERIES = {
  selling_price_outlook: { name: '販売価格の見通し（1年後）', color: '#cf1322' },
  general_price_outlook: { name: '物価全般の見通し（1年後）', color: '#1890ff' },
} as const

// =============================================================================
// ユーティリティ
// =============================================================================

function formatQuarterLabel(dateStr: string): string {
  const date = new Date(dateStr)
  const year = date.getFullYear() % 100
  const quarter = Math.floor(date.getMonth() / 3) + 1
  return `'${year.toString().padStart(2, '0')} Q${quarter}`
}

// =============================================================================
// API
// =============================================================================

async function fetchInflationOutlookData(): Promise<InflationOutlookResponse | null> {
  try {
    const response = await fetch('/api/japan/inflation-outlook')
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    return await response.json()
  } catch (error) {
    console.error('Failed to fetch inflation outlook data:', error)
    return null
  }
}

// =============================================================================
// コンポーネント
// =============================================================================

export default function JapanInflationOutlookChart() {
  const [data, setData] = useState<InflationOutlookResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(10)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      const result = await fetchInflationOutlookData()
      setData(result)
      setLoading(false)
    }
    loadData()
  }, [])

  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data || data.data.length === 0) return []
    return data.data.map((item) => ({
      date: item.date,
      selling_price_outlook: item.selling_price_outlook,
      general_price_outlook: item.general_price_outlook,
    }))
  }, [data])

  const sortedData = useSortedData(chartData)
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2021,
  })

  // 表示中の値域から Y 軸ドメインを算出（境界の浮動小数点誤差を避けクリーンに）
  const yDomain = useMemo<[number, number]>(() => {
    const values = filteredData.flatMap((d) =>
      [d.selling_price_outlook, d.general_price_outlook].filter(
        (v): v is number => typeof v === 'number'
      )
    )
    if (values.length === 0) return [0, 4]
    const min = Math.floor((Math.min(...values) - 0.3) * 10) / 10
    const max = Math.ceil((Math.max(...values) + 0.3) * 10) / 10
    return [min, max]
  }, [filteredData])

  if (loading) {
    return <LoadingChart title="企業の物価見通し（全規模合計・全産業／1年後）" />
  }

  if (!data || !data.data || data.data.length === 0) {
    return (
      <ChartContainer
        title="企業の物価見通し（全規模合計・全産業／1年後）"
        showPeriodSelector={false}
        showDataSource={false}
      >
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release || null

  const lines = (Object.keys(SERIES) as (keyof typeof SERIES)[]).map((key) => ({
    dataKey: key,
    color: SERIES[key].color,
    name: SERIES[key].name,
    strokeWidth: 2,
    hide: hiddenSeries.has(key),
  }))

  return (
    <div id="japan-inflation-outlook-chart">
      <ChartContainer
        title="企業の物価見通し（全規模合計・全産業／1年後）"
        showPeriodSelector={false}
        dataSource="日本銀行（BOJ）短観"
        sourceUrl="https://www.boj.or.jp/statistics/tk/gaiyo/index.htm"
      >
        <LatestValueBox
          items={[
            {
              label: SERIES.selling_price_outlook.name,
              value: latest?.selling_price_outlook,
              format: 'number',
              decimals: 1,
              unit: '%',
              color: SERIES.selling_price_outlook.color,
            },
            {
              label: SERIES.general_price_outlook.name,
              value: latest?.general_price_outlook,
              format: 'number',
              decimals: 1,
              unit: '%',
              color: SERIES.general_price_outlook.color,
            },
          ]}
          date={latest?.date}
          nextRelease={
            nextRelease
              ? {
                  date: nextRelease.date || nextRelease.datetime_jst || '',
                  label: nextRelease.time_jst ? `${nextRelease.time_jst} JST` : nextRelease.label,
                }
              : null
          }
        />

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
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
                    yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                    yDomain={yDomain}
                    showZeroLine={false}
                    xAxisFormatter={formatQuarterLabel}
                    tooltipLabelFormatter={formatQuarterLabel}
                    tooltipValueFormatter={(v) => `${v.toFixed(1)}%`}
                    onLegendClick={handleLegendClick}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="boj_tankan" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
