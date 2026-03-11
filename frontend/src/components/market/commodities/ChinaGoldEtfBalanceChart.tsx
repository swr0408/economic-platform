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

const COLOR_ETF = '#ef4444'
const COLOR_GOLD = '#f59e0b'

interface BalanceItem {
  date: string
  total_shares_wan: number | null
}

interface BalanceResponse {
  data: BalanceItem[]
  latest: BalanceItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

interface MergedItem {
  date: string
  total_shares_wan: number | null
  gold_price: number | null
}

type SeriesKey = 'total_shares_wan' | 'gold_price'

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
      {!hiddenSeries.has('total_shares_wan') && dp.total_shares_wan != null && (
        <div style={{ color: COLOR_ETF, fontSize: 13, marginBottom: 3 }}>
          総份額: {(dp.total_shares_wan / 10000).toLocaleString(undefined, { maximumFractionDigits: 1 })} 億份
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

export default function ChinaGoldEtfBalanceChart() {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(3)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<SeriesKey>()

  const { data: response } = useQuery<BalanceResponse>({
    queryKey: ['china-gold-etf-balance'],
    queryFn: async () => {
      const res = await axios.get('/api/market/china-gold-etf-balance')
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
      total_shares_wan: item.total_shares_wan,
      gold_price: goldMap.get(item.date) ?? null,
    }))
  }, [response, marketData])

  const filteredData = useMemo(() => {
    if (!mergedData.length) return []
    if (currentPeriod === 'all') return mergedData
    const years = typeof currentPeriod === 'number' ? currentPeriod : 3
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return mergedData.filter(d => d.date >= cutoffStr)
  }, [mergedData, currentPeriod])

  const latest = response?.latest
  const latestGold = marketData?.gold?.latest

  return (
    <ChartContainer
      title="中国金ETF残高"
      dataSource="Shanghai Stock Exchange"
      sourceUrl="https://www.sse.com.cn/assortment/fund/list/etfinfo/basic/index.shtml?FUNDID=518880"
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
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>総份額 (518880): </span>
            <span style={{ fontSize: 20, fontWeight: 'bold', color: COLOR_ETF }}>
              {latest?.total_shares_wan != null
                ? `${(latest.total_shares_wan / 10000).toLocaleString(undefined, { maximumFractionDigits: 1 })} 億份`
                : '—'}
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
            onClick={() => window.open('/compare?s=china_gold_etf_balance', '_blank')}
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
            domain={['dataMin * 0.9', 'dataMax * 1.05']}
            tickFormatter={(v: number) => `${(v / 10000).toFixed(0)}億`}
            stroke={DARK_THEME.axisLine}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            width={50}
            label={{ value: '億份', angle: -90, position: 'insideLeft', fill: DARK_THEME.textSecondary, fontSize: 11 }}
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
            dataKey="total_shares_wan"
            name="総份額 (万份)"
            stroke={COLOR_ETF}
            strokeWidth={2}
            dot={false}
            hide={hiddenSeries.has('total_shares_wan')}
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
