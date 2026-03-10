import { useState, useMemo } from 'react'
import { Typography, Tooltip, Button } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../common/ChartContainer'
import PeriodSelector, { type PeriodValue } from '../../common/PeriodSelector'
import { formatMonthLabel, formatDayLabel } from '../../../utils/dateFormatters'
import { useHiddenSeries } from '../../country/usa/common/useChartData'

const { Text } = Typography

const DARK_THEME = {
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  bgTertiary: '#334155',
  gridLine: '#475569',
  axisLine: '#64748b',
  tooltipBg: '#334155',
  tooltipBorder: '#475569',
  chartBg: '#1e293b',
}

const COLOR_CHINA = '#DC143C'      // Crimson red
const COLOR_INDIA = '#f59e0b'      // Amber/gold
const COLOR_GOLD_PRICE = '#94a3b8' // Gray (dashed)

interface PremiumItem {
  date: string
  china: number | null
  india: number | null
}

interface LatestInfo {
  date: string
  value: number
}

interface PremiumResponse {
  data: PremiumItem[]
  latest_china: LatestInfo | null
  latest_india: LatestInfo | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

interface GoldDailyItem {
  date: string
  close: number
}

interface GoldDailyResponse {
  data: GoldDailyItem[]
  latest: { date: string; close: number } | null
}

type SeriesKey = 'china' | 'india' | 'gold_price'

interface MergedItem {
  date: string
  china: number | null
  india: number | null
  gold_price: number | null
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function PremiumTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))
  const dataPoint = payload[0]?.payload as MergedItem | undefined

  return (
    <div style={{
      backgroundColor: DARK_THEME.tooltipBg,
      border: `1px solid ${DARK_THEME.tooltipBorder}`,
      borderRadius: 8,
      padding: '12px 16px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
    }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: '#f1f5f9' }}>{formattedLabel}</div>
      {!hiddenSeries.has('china') && (() => {
        const val = dataPoint?.china
        if (typeof val !== 'number') return null
        return (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: COLOR_CHINA, marginRight: 6 }} />
              中国
            </span>
            <span style={{ fontWeight: 500, color: COLOR_CHINA }}>
              {val >= 0 ? '+' : ''}{val.toFixed(2)} $/oz
            </span>
          </div>
        )
      })()}
      {!hiddenSeries.has('india') && (() => {
        const val = dataPoint?.india
        if (typeof val !== 'number') return null
        return (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: COLOR_INDIA, marginRight: 6 }} />
              インド
            </span>
            <span style={{ fontWeight: 500, color: COLOR_INDIA }}>
              {val >= 0 ? '+' : ''}{val.toFixed(2)} $/oz
            </span>
          </div>
        )
      })()}
      {!hiddenSeries.has('gold_price') && (() => {
        const val = dataPoint?.gold_price
        if (typeof val !== 'number') return null
        return (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: COLOR_GOLD_PRICE, marginRight: 6 }} />
              金価格
            </span>
            <span style={{ fontWeight: 500, color: COLOR_GOLD_PRICE }}>
              ${val.toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </span>
          </div>
        )
      })()}
    </div>
  )
}


export default function GoldPremiumChart() {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(2)
  const { hiddenSeries, handleLegendClick, isHidden } = useHiddenSeries<SeriesKey>()

  // プレミアム/ディスカウントデータ
  const { data: premiumData, isLoading: premiumLoading } = useQuery({
    queryKey: ['market', 'gold-premium'],
    queryFn: async () => {
      const { data } = await axios.get<PremiumResponse>('/api/market/gold-premium')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })

  // 金価格日足（週足に変換するため）
  const { data: goldData, isLoading: goldLoading } = useQuery({
    queryKey: ['market', 'gold', 'daily'],
    queryFn: async () => {
      const { data } = await axios.get<GoldDailyResponse>('/api/market/gold/daily')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })

  // 金価格を週足に変換（金曜日の終値 or 週の最終営業日）
  const goldWeeklyMap = useMemo(() => {
    const map = new Map<string, number>()
    if (!goldData?.data) return map

    // 日付をDateオブジェクトにして週単位でグループ
    const weekBuckets = new Map<string, { date: string; close: number }>()
    for (const item of goldData.data) {
      const d = new Date(item.date)
      // ISO week start（月曜日）を計算
      const day = d.getDay()
      const diff = d.getDate() - day + (day === 0 ? -6 : 1)
      const weekStart = new Date(d)
      weekStart.setDate(diff)
      const weekKey = weekStart.toISOString().slice(0, 10)

      const existing = weekBuckets.get(weekKey)
      if (!existing || item.date > existing.date) {
        weekBuckets.set(weekKey, { date: item.date, close: item.close })
      }
    }

    // 各週の最終日の終値をその週のデータポイントの日付にマッピング
    for (const [, { date, close }] of weekBuckets) {
      map.set(date, close)
    }
    return map
  }, [goldData])

  // プレミアムデータを週足にサンプリングしてマージ
  const chartData = useMemo(() => {
    if (!premiumData?.data) return [] as MergedItem[]

    // プレミアムデータを週足にダウンサンプリング（金曜日 or 週最終営業日を採用）
    const weekBuckets = new Map<string, PremiumItem>()
    for (const item of premiumData.data) {
      const d = new Date(item.date)
      const day = d.getDay()
      const diff = d.getDate() - day + (day === 0 ? -6 : 1)
      const weekStart = new Date(d)
      weekStart.setDate(diff)
      const weekKey = weekStart.toISOString().slice(0, 10)

      const existing = weekBuckets.get(weekKey)
      if (!existing || item.date > existing.date) {
        weekBuckets.set(weekKey, item)
      }
    }

    // 週足のマージデータを構築
    const result: MergedItem[] = []
    const sortedWeeks = Array.from(weekBuckets.entries()).sort((a, b) => a[0].localeCompare(b[0]))

    for (const [, premItem] of sortedWeeks) {
      const goldPrice = goldWeeklyMap.get(premItem.date) ?? null
      result.push({
        date: premItem.date,
        china: premItem.china,
        india: premItem.india,
        gold_price: goldPrice,
      })
    }

    return result
  }, [premiumData, goldWeeklyMap])

  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all') return chartData
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 2
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return chartData.filter((d) => d.date >= cutoffStr)
  }, [chartData, selectedPeriod])

  const latestChina = premiumData?.latest_china ?? null
  const latestIndia = premiumData?.latest_india ?? null

  const isLoading = premiumLoading || goldLoading

  if (isLoading) {
    return (
      <ChartContainer title="金プレミアム/ディスカウント（中国・インド）" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (chartData.length === 0) {
    return (
      <ChartContainer title="金プレミアム/ディスカウント（中国・インド）" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  return (
    <ChartContainer
      title="金プレミアム/ディスカウント（中国・インド）"
      dataSource="World Gold Council"
      showPeriodSelector={false}
      sourceUrl="https://www.gold.org/goldhub/data/gold-premium"
    >
      {/* 1. Latest values */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        marginBottom: 12,
        padding: '10px 14px',
        background: DARK_THEME.bgTertiary,
        borderRadius: 8,
        flexWrap: 'wrap',
      }}>
        {latestChina && (
          <div
            style={{ display: 'flex', alignItems: 'baseline', gap: 6, opacity: isHidden('china') ? 0.3 : 1, cursor: 'pointer' }}
            onClick={() => handleLegendClick('china')}
          >
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>中国</Text>
            <Text style={{ color: COLOR_CHINA, fontSize: 15, fontWeight: 700 }} className="tabular-nums">
              {latestChina.value >= 0 ? '+' : ''}{latestChina.value.toFixed(2)} $/oz
            </Text>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>({latestChina.date})</Text>
          </div>
        )}
        {latestIndia && (
          <div
            style={{ display: 'flex', alignItems: 'baseline', gap: 6, opacity: isHidden('india') ? 0.3 : 1, cursor: 'pointer' }}
            onClick={() => handleLegendClick('india')}
          >
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>インド</Text>
            <Text style={{ color: COLOR_INDIA, fontSize: 15, fontWeight: 700 }} className="tabular-nums">
              {latestIndia.value >= 0 ? '+' : ''}{latestIndia.value.toFixed(2)} $/oz
            </Text>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>({latestIndia.date})</Text>
          </div>
        )}
      </div>

      {/* 2. Compare button */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            size="small"
            onClick={() => window.open('/compare?s=gold_premium_china&s=gold_premium_india', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 3. Period selector */}
      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

      {/* 4. Chart */}
      <ResponsiveContainer width="100%" height={420}>
        <ComposedChart
          data={filteredData}
          margin={{ top: 16, right: 60, bottom: 0, left: 0 }}
          style={{ backgroundColor: DARK_THEME.chartBg }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
          <XAxis
            type="category"
            dataKey="date"
            tickFormatter={formatMonthLabel}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            tickMargin={16}
            height={60}
            interval="preserveStartEnd"
          />

          {/* Left Y: Premium/Discount (US$/oz) */}
          <YAxis
            yAxisId="left"
            domain={['dataMin - 5', 'dataMax + 5']}
            tickFormatter={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(0)}`}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            tickMargin={8}
            label={{ value: '$/oz', position: 'top', offset: 8, style: { fill: DARK_THEME.textSecondary, fontSize: 10 } }}
          />

          {/* Right Y: Gold Price (USD/oz) */}
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={['dataMin - 50', 'dataMax + 50']}
            tickFormatter={(v: number) => v >= 1000 ? `$${(v / 1000).toFixed(1)}K` : `$${v}`}
            axisLine={{ stroke: COLOR_GOLD_PRICE }}
            tickLine={{ stroke: COLOR_GOLD_PRICE }}
            tick={{ fill: COLOR_GOLD_PRICE, fontSize: 11 }}
            tickMargin={4}
            width={55}
          />

          <RechartsTooltip content={<PremiumTooltip hiddenSeries={hiddenSeries} />} />

          <Legend
            wrapperStyle={{ paddingTop: 8 }}
            onClick={(e) => handleLegendClick(e.dataKey as string)}
            formatter={(value: string, entry) => (
              <span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : DARK_THEME.textPrimary }}>
                {value}
              </span>
            )}
          />

          <ReferenceLine yAxisId="left" y={0} stroke="#e2e8f0" strokeWidth={1.5} label={{ value: '0', position: 'left', fill: '#e2e8f0', fontSize: 11, offset: 4 }} />

          {/* China premium/discount */}
          <Line
            type="monotone"
            dataKey="china"
            stroke={COLOR_CHINA}
            strokeWidth={2}
            dot={false}
            name="中国 ($/oz)"
            yAxisId="left"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('china')}
          />

          {/* India premium/discount */}
          <Line
            type="monotone"
            dataKey="india"
            stroke={COLOR_INDIA}
            strokeWidth={2}
            dot={false}
            name="インド ($/oz)"
            yAxisId="left"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('india')}
          />

          {/* Gold Price (right Y, dashed) */}
          <Line
            type="monotone"
            dataKey="gold_price"
            stroke={COLOR_GOLD_PRICE}
            strokeWidth={1.5}
            strokeDasharray="6 3"
            dot={false}
            name="金価格 (USD/oz)"
            yAxisId="right"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('gold_price')}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
