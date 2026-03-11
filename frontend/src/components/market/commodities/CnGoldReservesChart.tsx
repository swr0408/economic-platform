import { useState, useMemo } from 'react'
import { Tooltip, Button } from 'antd'
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
import { formatMonthLabel } from '../../../utils/dateFormatters'
import { useHiddenSeries } from '../../country/usa/common/useChartData'
import { useMarketBatchData } from '../../../hooks/useMarketData'
import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../../country/usa/common/chartConstants'

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

const COLOR_OUNCES = '#DC143C'       // Crimson red
const COLOR_USD = '#22c55e'          // Green
const COLOR_GOLD = '#f59e0b'         // Gold

interface ReservesItem {
  date: string
  gold_ounces_wan: number | null
  gold_value_usd_yi: number | null
}

interface ReservesResponse {
  data: ReservesItem[]
  latest: ReservesItem | null
  metadata: Record<string, unknown>
  next_release: { date: string; label: string } | null
  last_updated: string | null
}

interface MergedItem {
  date: string
  gold_ounces_wan: number | null
  gold_value_usd_yi: number | null
  gold_price: number | null
}

type SeriesKey = 'gold_ounces_wan' | 'gold_value_usd_yi' | 'gold_price'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ChartTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatMonthLabel(String(label))
  const dp = payload[0]?.payload as MergedItem | undefined
  if (!dp) return null

  return (
    <div style={{
      backgroundColor: DARK_THEME.tooltipBg,
      border: `1px solid ${DARK_THEME.tooltipBorder}`,
      borderRadius: 8,
      padding: '12px 16px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
    }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>{formattedLabel}</div>
      {!hiddenSeries.has('gold_ounces_wan') && dp.gold_ounces_wan != null && (
        <div style={{ color: COLOR_OUNCES, fontSize: 13, marginBottom: 3 }}>
          金準備: {dp.gold_ounces_wan.toLocaleString()} 万oz
        </div>
      )}
      {!hiddenSeries.has('gold_value_usd_yi') && dp.gold_value_usd_yi != null && (
        <div style={{ color: COLOR_USD, fontSize: 13, marginBottom: 3 }}>
          評価額: {dp.gold_value_usd_yi.toLocaleString()} 億USD
        </div>
      )}
      {!hiddenSeries.has('gold_price') && dp.gold_price != null && (
        <div style={{ color: COLOR_GOLD, fontSize: 13, marginBottom: 3 }}>
          金価格: {dp.gold_price.toLocaleString()} USD/oz
        </div>
      )}
    </div>
  )
}

export default function CnGoldReservesChart() {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<SeriesKey>()

  const { data: response } = useQuery<ReservesResponse>({
    queryKey: ['cn-gold-reserves'],
    queryFn: async () => {
      const res = await axios.get('/api/china/safe/gold-reserves')
      return res.data
    },
    staleTime: 1000 * 60 * 30,
  })

  // Gold price monthly data
  const { data: marketData } = useMarketBatchData(['gold'])

  const mergedData = useMemo(() => {
    if (!response?.data) return []

    // Gold price: get month-end close from daily data
    const goldMonthMap = new Map<string, number>()
    if (marketData?.gold?.data) {
      for (const d of marketData.gold.data) {
        // Map daily dates to month key YYYY-MM
        const monthKey = d.date.slice(0, 7)
        goldMonthMap.set(monthKey, d.close) // last value per month
      }
    }

    return response.data.map(item => ({
      date: item.date,
      gold_ounces_wan: item.gold_ounces_wan,
      gold_value_usd_yi: item.gold_value_usd_yi,
      gold_price: goldMonthMap.get(item.date.slice(0, 7)) ?? null,
    }))
  }, [response, marketData])

  const filteredData = useMemo(() => {
    if (!mergedData.length) return []
    if (currentPeriod === 'all') return mergedData
    const years = typeof currentPeriod === 'number' ? currentPeriod : 10
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return mergedData.filter(d => d.date >= cutoffStr)
  }, [mergedData, currentPeriod])

  const latest = response?.latest
  const nextRelease = response?.next_release

  return (
    <ChartContainer
      title="中国人民銀行金準備"
      dataSource="PBOC / SAFE"
      sourceUrl="https://www.safe.gov.cn/en/ForexReserves/index.html"
      showPeriodSelector={false}
    >
      {/* Latest value box */}
      <div style={LATEST_VALUE_BOX_STYLE}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          {latest?.date && (
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
              {latest.date.replace(/-/g, '/').replace(/\/01$/, '')}
            </span>
          )}
          <div>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>金準備: </span>
            <span style={{ fontSize: 20, fontWeight: 'bold', color: COLOR_OUNCES }}>
              {latest?.gold_ounces_wan != null ? `${latest.gold_ounces_wan.toLocaleString()} 万oz` : '—'}
            </span>
          </div>
          {latest?.gold_value_usd_yi != null && (
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>評価額: </span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: COLOR_USD }}>
                {latest.gold_value_usd_yi.toLocaleString()} 億USD
              </span>
            </div>
          )}
          {nextRelease && (
            <span style={{ fontSize: 11, color: TEXT_COLORS.secondary }}>
              次回: {nextRelease.date}
            </span>
          )}
        </div>
        <Tooltip title="比較ページを開く">
          <Button
            size="small"
            icon={<AreaChartOutlined />}
            onClick={() => window.open('/compare?s=china_official_reserve_assets_gold', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* Period selector */}
      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

      {/* Chart */}
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart data={filteredData} margin={{ top: 10, right: 60, left: 10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
          <XAxis
            dataKey="date"
            tickFormatter={(v) => formatMonthLabel(v)}
            stroke={DARK_THEME.axisLine}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            minTickGap={40}
          />
          <YAxis
            yAxisId="left"
            domain={['dataMin - 50', 'dataMax + 50']}
            tickFormatter={(v: number) => `${v.toLocaleString()}`}
            stroke={DARK_THEME.axisLine}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            width={55}
            label={{ value: '万oz', angle: -90, position: 'insideLeft', fill: DARK_THEME.textSecondary, fontSize: 11 }}
          />
          <YAxis
            yAxisId="gold"
            orientation="right"
            domain={['dataMin - 100', 'dataMax + 100']}
            tickFormatter={(v: number) => `$${v.toFixed(0)}`}
            stroke={COLOR_GOLD}
            tick={{ fill: COLOR_GOLD, fontSize: 10 }}
            width={55}
            axisLine={{ stroke: COLOR_GOLD, strokeDasharray: '4 3' }}
          />
          <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} />} />
          <Legend
            onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)}
            wrapperStyle={{ cursor: 'pointer' }}
            formatter={(value: string, entry: any) => (
              <span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>
                {value}
              </span>
            )}
          />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="gold_ounces_wan"
            name="金準備 (万oz)"
            stroke={COLOR_OUNCES}
            strokeWidth={2}
            dot={false}
            hide={hiddenSeries.has('gold_ounces_wan')}
            connectNulls
          />
          <Line
            yAxisId="gold"
            type="monotone"
            dataKey="gold_price"
            name="金価格 (USD/oz)"
            stroke={COLOR_GOLD}
            strokeWidth={1.5}
            strokeDasharray="4 3"
            dot={false}
            hide={hiddenSeries.has('gold_price')}
            connectNulls
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
