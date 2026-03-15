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

const COLOR_HOLDINGS = '#f59e0b'     // 金保有量 - gold/amber
const COLOR_GOLD_PRICE = '#94a3b8'   // 金価格 - gray (dashed)

interface HoldingsItem {
  date: string
  holdings_ton: number | null
  gold_price_usd: number | null
}

interface LatestGold {
  date: string
  close: number
}

interface HoldingsResponse {
  data: HoldingsItem[]
  latest: HoldingsItem | null
  latest_gold: LatestGold | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

type SeriesKey = 'holdings_ton' | 'gold_price_usd'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function GoldTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))
  const dataPoint = payload[0]?.payload as Record<string, unknown> | undefined

  return (
    <div style={{
      backgroundColor: DARK_THEME.tooltipBg,
      border: `1px solid ${DARK_THEME.tooltipBorder}`,
      borderRadius: 8,
      padding: '12px 16px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
    }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: '#f1f5f9' }}>{formattedLabel}</div>
      {!hiddenSeries.has('holdings_ton') && (() => {
        const val = dataPoint?.holdings_ton
        if (typeof val !== 'number') return null
        return (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: COLOR_HOLDINGS, marginRight: 6 }} />
              金ETF残高
            </span>
            <span style={{ fontWeight: 500, color: COLOR_HOLDINGS }}>{val.toLocaleString(undefined, { maximumFractionDigits: 1 })} トン</span>
          </div>
        )
      })()}
      {!hiddenSeries.has('gold_price_usd') && (() => {
        const val = dataPoint?.gold_price_usd
        if (typeof val !== 'number') return null
        return (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: COLOR_GOLD_PRICE, marginRight: 6 }} />
              金価格
            </span>
            <span style={{ fontWeight: 500, color: COLOR_GOLD_PRICE }}>${val.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
          </div>
        )
      })()}
    </div>
  )
}


export default function GoldEtfHoldingsChart() {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(2)
  const { hiddenSeries, handleLegendClick, isHidden } = useHiddenSeries<SeriesKey>()

  const { data: holdingsData, isLoading } = useQuery({
    queryKey: ['market', 'gold-etf-holdings'],
    queryFn: async () => {
      const { data } = await axios.get<HoldingsResponse>('/api/market/gold-etf-holdings')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })

  const chartData = useMemo(() => {
    if (!holdingsData?.data) return []
    return holdingsData.data
  }, [holdingsData])

  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all') return chartData
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 2
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return chartData.filter((d) => d.date >= cutoffStr)
  }, [chartData, selectedPeriod])

  const latest = holdingsData?.latest ?? null
  const latestGold = holdingsData?.latest_gold ?? null

  // 金価格の表示値: latest_gold（yfinance日足最新）があればそれを使い、なければlatest.gold_price_usdにフォールバック
  const goldDisplay = useMemo(() => {
    if (latestGold) return { value: latestGold.close, date: latestGold.date }
    if (latest?.gold_price_usd != null) return { value: latest.gold_price_usd, date: latest.date }
    return null
  }, [latestGold, latest])

  if (isLoading) {
    return (
      <ChartContainer title="金ETF保有残高" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (chartData.length === 0) {
    return (
      <ChartContainer title="金ETF保有残高" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  return (
    <ChartContainer
      title="金ETF保有残高"
      dataSource="SPDR Gold Shares"
      showPeriodSelector={false}
      sourceUrl="https://www.spdrgoldshares.com/ja/japan/gld/"
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
        {latest?.holdings_ton != null && (
          <div
            style={{ display: 'flex', alignItems: 'baseline', gap: 6, opacity: isHidden('holdings_ton') ? 0.3 : 1, cursor: 'pointer' }}
            onClick={() => handleLegendClick('holdings_ton')}
          >
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>金保有量</Text>
            <Text style={{ color: COLOR_HOLDINGS, fontSize: 15, fontWeight: 700 }} className="tabular-nums">
              {latest.holdings_ton.toLocaleString(undefined, { maximumFractionDigits: 1 })} トン
            </Text>
          </div>
        )}
        {goldDisplay && (
          <div
            style={{ display: 'flex', alignItems: 'baseline', gap: 6, opacity: isHidden('gold_price_usd') ? 0.3 : 1, cursor: 'pointer' }}
            onClick={() => handleLegendClick('gold_price_usd')}
          >
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>金価格</Text>
            <Text style={{ color: COLOR_GOLD_PRICE, fontSize: 15, fontWeight: 700 }} className="tabular-nums">
              ${goldDisplay.value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </Text>
            {goldDisplay.date !== latest?.date && (
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>({goldDisplay.date})</Text>
            )}
          </div>
        )}
        {latest?.date && (
          <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>({latest.date})</Text>
        )}
      </div>

      {/* 2. Compare button */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            size="small"
            onClick={() => window.open('/compare?s=gold_etf_holdings_ton&s=gold_etf_gold_price', '_blank')}
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

          {/* Left Y: トン */}
          <YAxis
            yAxisId="left"
            domain={['dataMin - 20', 'dataMax + 20']}
            tickFormatter={(v: number) => `${v.toFixed(0)}`}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            tickMargin={8}
            label={{ value: 'トン', position: 'top', offset: 8, style: { fill: DARK_THEME.textSecondary, fontSize: 10 } }}
          />

          {/* Right Y: USD/oz */}
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

          <RechartsTooltip content={<GoldTooltip hiddenSeries={hiddenSeries} />} />

          <Legend
            wrapperStyle={{ paddingTop: 8 }}
            onClick={(e) => handleLegendClick(e.dataKey as string)}
            formatter={(value: string, entry) => (
              <span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : DARK_THEME.textPrimary }}>
                {value}
              </span>
            )}
          />

          {/* Gold ETF Holdings line */}
          <Line
            type="monotone"
            dataKey="holdings_ton"
            stroke={COLOR_HOLDINGS}
            strokeWidth={2}
            dot={false}
            name="金ETF残高 (トン)"
            yAxisId="left"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('holdings_ton')}
          />

          {/* Gold Price line */}
          <Line
            type="monotone"
            dataKey="gold_price_usd"
            stroke={COLOR_GOLD_PRICE}
            strokeWidth={1.5}
            strokeDasharray="6 3"
            dot={false}
            name="金価格 (USD/oz)"
            yAxisId="right"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('gold_price_usd')}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
