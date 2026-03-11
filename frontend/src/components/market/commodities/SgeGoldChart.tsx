import { useState, useMemo } from 'react'
import { Tooltip, Button } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import ChartContainer from '../../common/ChartContainer'
import PeriodSelector, { type PeriodValue } from '../../common/PeriodSelector'
import { formatDayLabel } from '../../../utils/dateFormatters'
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

const COLOR_VOLUME = '#3b82f6'
const COLOR_OI = '#a78bfa'
const COLOR_GOLD = '#f59e0b'

interface SgeItem {
  date: string
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  settlement: number | null
  volume_kg: number | null
  amount_cny: number | null
  open_interest: number | null
}

interface SgeResponse {
  data: SgeItem[]
  latest: SgeItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

interface MergedItem {
  date: string
  volume_kg: number | null
  open_interest: number | null
  gold_price: number | null
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ChartTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))
  const dp = payload[0]?.payload as MergedItem | undefined
  if (!dp) return null

  return (
    <div style={{
      backgroundColor: DARK_THEME.bgTertiary,
      border: `1px solid ${DARK_THEME.tooltipBorder}`,
      borderRadius: 8,
      padding: '12px 16px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
    }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>{formattedLabel}</div>
      {!hiddenSeries.has('volume_kg') && dp.volume_kg != null && (
        <div style={{ color: COLOR_VOLUME, fontSize: 13, marginBottom: 3 }}>
          出来高: {dp.volume_kg.toLocaleString()} kg
        </div>
      )}
      {!hiddenSeries.has('open_interest') && dp.open_interest != null && (
        <div style={{ color: COLOR_OI, fontSize: 13, marginBottom: 3 }}>
          建玉: {dp.open_interest.toLocaleString()}
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

export default function SgeGoldChart() {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(1)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<string>()

  const { data: response } = useQuery<SgeResponse>({
    queryKey: ['sge-gold'],
    queryFn: async () => {
      const res = await axios.get('/api/market/sge-gold')
      return res.data
    },
    staleTime: 1000 * 60 * 30,
  })

  const { data: marketData } = useMarketBatchData(['gold'])

  const mergedData = useMemo(() => {
    if (!response?.data) return []

    const goldMap = new Map<string, number>()
    if (marketData?.gold?.data) {
      for (const d of marketData.gold.data) {
        goldMap.set(d.date, d.close)
      }
    }

    return response.data.map(item => ({
      date: item.date,
      volume_kg: item.volume_kg,
      open_interest: item.open_interest,
      gold_price: goldMap.get(item.date) ?? null,
    }))
  }, [response, marketData])

  const filteredData = useMemo(() => {
    if (!mergedData.length) return []
    if (currentPeriod === 'all') return mergedData
    const years = typeof currentPeriod === 'number' ? currentPeriod : 1
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return mergedData.filter(d => d.date >= cutoffStr)
  }, [mergedData, currentPeriod])

  const latest = response?.latest
  const latestGold = marketData?.gold?.latest

  return (
    <ChartContainer
      title="中国スポット金取引量"
      dataSource="Shanghai Gold Exchange"
      sourceUrl="https://www.sge.com.cn/sjzx/quotation_daily_new"
      showPeriodSelector={false}
    >
      {/* Latest value box */}
      <div style={LATEST_VALUE_BOX_STYLE}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          {latest?.date && (
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
              {latest.date.replace(/-/g, '/')}
            </span>
          )}
          <div>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>出来高: </span>
            <span style={{ fontSize: 20, fontWeight: 'bold', color: COLOR_VOLUME }}>
              {latest?.volume_kg != null ? `${latest.volume_kg.toLocaleString()} kg` : '—'}
            </span>
          </div>
          <div>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>建玉: </span>
            <span style={{ fontSize: 16, fontWeight: 'bold', color: COLOR_OI }}>
              {latest?.open_interest != null ? `${latest.open_interest.toLocaleString()} ` : '—'}
            </span>
          </div>
          {latestGold && (
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>金価格: </span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: COLOR_GOLD }}>
                {latestGold.close.toLocaleString()} USD/oz
              </span>
            </div>
          )}
        </div>
        <Tooltip title="比較ページを開く">
          <Button
            size="small"
            icon={<AreaChartOutlined />}
            onClick={() => window.open('/compare?s=sge_gold_volume', '_blank')}
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
          <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} />
          <XAxis
            dataKey="date"
            tickFormatter={(v) => formatDayLabel(v)}
            stroke={DARK_THEME.axisLine}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            minTickGap={40}
          />
          <YAxis
            yAxisId="left"
            domain={[0, 'dataMax * 1.1']}
            tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}t` : `${v}`}
            stroke={DARK_THEME.axisLine}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            width={45}
            label={{ value: 'kg', angle: -90, position: 'insideLeft', fill: DARK_THEME.textSecondary, fontSize: 11 }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={['dataMin * 0.9', 'dataMax * 1.1']}
            tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`}
            stroke={DARK_THEME.axisLine}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            width={50}
          />
          <YAxis
            yAxisId="gold"
            orientation="right"
            domain={['dataMin * 0.9', 'dataMax * 1.05']}
            tickFormatter={(v: number) => `$${v.toFixed(0)}`}
            stroke={COLOR_GOLD}
            tick={{ fill: COLOR_GOLD, fontSize: 10 }}
            width={55}
            axisLine={{ stroke: COLOR_GOLD, strokeDasharray: '4 3' }}
          />
          <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} />} />
          <Legend
            onClick={(e) => handleLegendClick(e.dataKey as string)}
            wrapperStyle={{ cursor: 'pointer' }}
            formatter={(value: string, entry: any) => (
              <span style={{ color: hiddenSeries.has(entry.dataKey as string) ? '#64748b' : entry.color, fontSize: 12 }}>
                {value}
              </span>
            )}
          />
          <Bar
            yAxisId="left"
            dataKey="volume_kg"
            name="出来高 (kg)"
            fill={COLOR_VOLUME}
            opacity={0.7}
            hide={hiddenSeries.has('volume_kg')}
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="open_interest"
            name="建玉 "
            stroke={COLOR_OI}
            strokeWidth={2}
            dot={false}
            hide={hiddenSeries.has('open_interest')}
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
