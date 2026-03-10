import { useState, useMemo } from 'react'
import { Typography, Tooltip, Button } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import {
  ComposedChart,
  Line,
  Bar,
  Area,
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
import { ViewModeButtonGroup } from '../../country/usa/common/ChartComponents'

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

const COLOR_SELL = '#ef4444'     // 売残 - red
const COLOR_BUY = '#3b82f6'      // 買残 - blue
const COLOR_RATIO = '#f59e0b'    // 信用倍率 - amber
const COLOR_NIKKEI = '#10b981'   // 日経平均 - green

interface MarginItem {
  date: string
  sell_balance: number | null
  buy_balance: number | null
  sell_change: number | null
  buy_change: number | null
  margin_ratio: number | null
  nikkei_close: number | null
}

interface MarginResponse {
  data: MarginItem[]
  latest: MarginItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

type ViewMode = 'balance' | 'change'
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'balance', label: '残高' },
  { mode: 'change', label: '増減' },
]

type BalanceSeriesKey = 'sell_balance' | 'buy_balance' | 'margin_ratio' | 'nikkei_close'
type ChangeSeriesKey = 'sell_change' | 'buy_change'

const BALANCE_SERIES: { key: BalanceSeriesKey; label: string; color: string }[] = [
  { key: 'sell_balance', label: '信用売残', color: COLOR_SELL },
  { key: 'buy_balance', label: '信用買残', color: COLOR_BUY },
  { key: 'margin_ratio', label: '信用倍率', color: COLOR_RATIO },
  { key: 'nikkei_close', label: '日経平均', color: COLOR_NIKKEI },
]

const CHANGE_SERIES: { key: ChangeSeriesKey; label: string; color: string }[] = [
  { key: 'sell_change', label: '売残増減', color: COLOR_SELL },
  { key: 'buy_change', label: '買残増減', color: COLOR_BUY },
]

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function BalanceTooltip({ active, payload, label, hiddenSeries }: { active?: boolean; payload?: any[]; label?: string; hiddenSeries: Set<string> }) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))

  return (
    <div style={{
      backgroundColor: DARK_THEME.tooltipBg,
      border: `1px solid ${DARK_THEME.tooltipBorder}`,
      borderRadius: 8,
      padding: '12px 16px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
    }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: '#f1f5f9' }}>{formattedLabel}</div>
      {BALANCE_SERIES.map(({ key, label: seriesLabel, color }) => {
        if (hiddenSeries.has(key)) return null
        const item = payload.find((p: { dataKey: string }) => p.dataKey === key)
        if (!item || typeof item.value !== 'number') return null
        const formatted = key === 'margin_ratio'
          ? `${item.value.toFixed(2)}倍`
          : key === 'nikkei_close'
            ? item.value.toLocaleString(undefined, { maximumFractionDigits: 0 })
            : item.value.toLocaleString()
        return (
          <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: color, marginRight: 6 }} />
              {seriesLabel}
            </span>
            <span style={{ fontWeight: 500, color }}>{formatted}</span>
          </div>
        )
      })}
    </div>
  )
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ChangeTooltip({ active, payload, label, hiddenSeries }: { active?: boolean; payload?: any[]; label?: string; hiddenSeries: Set<string> }) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))

  return (
    <div style={{
      backgroundColor: DARK_THEME.tooltipBg,
      border: `1px solid ${DARK_THEME.tooltipBorder}`,
      borderRadius: 8,
      padding: '12px 16px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
    }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: '#f1f5f9' }}>{formattedLabel}</div>
      {CHANGE_SERIES.map(({ key, label: seriesLabel, color }) => {
        if (hiddenSeries.has(key)) return null
        const item = payload.find((p: { dataKey: string }) => p.dataKey === key)
        if (!item || typeof item.value !== 'number') return null
        const sign = item.value > 0 ? '+' : ''
        return (
          <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: color, marginRight: 6 }} />
              {seriesLabel}
            </span>
            <span style={{ fontWeight: 500, color }}>{sign}{item.value.toLocaleString()}</span>
          </div>
        )
      })}
    </div>
  )
}


export default function NikkeiDoubleInverseChart() {
  const [viewMode, setViewMode] = useState<ViewMode>('balance')
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(5)
  const { hiddenSeries, handleLegendClick, isHidden } = useHiddenSeries<BalanceSeriesKey | ChangeSeriesKey>()

  const { data: marginData, isLoading } = useQuery({
    queryKey: ['market', 'nikkei-double-inverse'],
    queryFn: async () => {
      const { data } = await axios.get<MarginResponse>('/api/market/nikkei-double-inverse')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })

  const chartData = useMemo(() => {
    if (!marginData?.data) return []
    return marginData.data
  }, [marginData])

  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all') return chartData
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 5
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return chartData.filter((d) => d.date >= cutoffStr)
  }, [chartData, selectedPeriod])

  const latest = marginData?.latest ?? null

  if (isLoading) {
    return (
      <ChartContainer title="日経ダブルインバース 信用残" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (chartData.length === 0) {
    return (
      <ChartContainer title="日経ダブルインバース 信用残" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  return (
    <ChartContainer
      title="日経ダブルインバース 信用残"
      dataSource="JPX / yfinance"
      showPeriodSelector={false}
      sourceUrl="https://www.nikkei.com/nkd/company/history/trust/?scode=1357"
      // https://www.jpx.co.jp/markets/statistics-equities/margin/05.html
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
        {latest?.sell_balance != null && (
          <div
            style={{ display: 'flex', alignItems: 'baseline', gap: 6, opacity: isHidden('sell_balance') ? 0.3 : 1, cursor: 'pointer' }}
            onClick={() => handleLegendClick('sell_balance')}
          >
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>売残</Text>
            <Text style={{ color: COLOR_SELL, fontSize: 16, fontWeight: 700 }} className="tabular-nums">
              {latest.sell_balance.toLocaleString()}
            </Text>
          </div>
        )}
        {latest?.buy_balance != null && (
          <div
            style={{ display: 'flex', alignItems: 'baseline', gap: 6, opacity: isHidden('buy_balance') ? 0.3 : 1, cursor: 'pointer' }}
            onClick={() => handleLegendClick('buy_balance')}
          >
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>買残</Text>
            <Text style={{ color: COLOR_BUY, fontSize: 16, fontWeight: 700 }} className="tabular-nums">
              {latest.buy_balance.toLocaleString()}
            </Text>
          </div>
        )}
        {latest?.margin_ratio != null && (
          <div
            style={{ display: 'flex', alignItems: 'baseline', gap: 6, opacity: isHidden('margin_ratio') ? 0.3 : 1, cursor: 'pointer' }}
            onClick={() => handleLegendClick('margin_ratio')}
          >
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>信用倍率</Text>
            <Text style={{ color: COLOR_RATIO, fontSize: 16, fontWeight: 700 }} className="tabular-nums">
              {latest.margin_ratio.toFixed(2)}倍
            </Text>
          </div>
        )}
        {latest?.nikkei_close != null && (
          <div
            style={{ display: 'flex', alignItems: 'baseline', gap: 6, opacity: isHidden('nikkei_close') ? 0.3 : 1, cursor: 'pointer' }}
            onClick={() => handleLegendClick('nikkei_close')}
          >
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>日経平均</Text>
            <Text style={{ color: COLOR_NIKKEI, fontSize: 16, fontWeight: 700 }} className="tabular-nums">
              {latest.nikkei_close.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </Text>
          </div>
        )}
        {latest?.date && (
          <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>({latest.date})</Text>
        )}
      </div>

      {/* 2. ViewMode + Compare button */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            size="small"
            onClick={() => window.open('/compare?s=nikkei_di_buy&s=nikkei_di_sell', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 3. Period selector */}
      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

      {/* 4. Chart */}
      {viewMode === 'balance' ? (
        <ResponsiveContainer width="100%" height={400}>
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

            {/* Left Y: 売残・買残（株数） */}
            <YAxis
              yAxisId="left"
              domain={['dataMin', 'dataMax']}
              tickFormatter={(v: number) => v >= 1_000_000 ? `${(v / 1_000_000).toFixed(1)}M` : v >= 1000 ? `${(v / 1000).toFixed(0)}K` : `${v}`}
              axisLine={{ stroke: DARK_THEME.axisLine }}
              tickLine={{ stroke: DARK_THEME.axisLine }}
              tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
              tickMargin={8}
            />

            {/* Right Y: 信用倍率 + 日経平均 */}
            <YAxis
              yAxisId="right"
              orientation="right"
              domain={['dataMin - 1', 'dataMax + 5']}
              tickFormatter={(v: number) => `${v.toFixed(0)}倍`}
              axisLine={{ stroke: COLOR_RATIO }}
              tickLine={{ stroke: COLOR_RATIO }}
              tick={{ fill: COLOR_RATIO, fontSize: 11 }}
              tickMargin={4}
              width={50}
            />

            {/* Far right Y: 日経平均 */}
            <YAxis
              yAxisId="nikkei"
              orientation="right"
              domain={['dataMin - 2000', 'dataMax + 2000']}
              tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}K` : `${v}`}
              axisLine={{ stroke: COLOR_NIKKEI }}
              tickLine={{ stroke: COLOR_NIKKEI }}
              tick={{ fill: COLOR_NIKKEI, fontSize: 11 }}
              tickMargin={4}
              width={50}
              hide
            />

            <RechartsTooltip content={<BalanceTooltip hiddenSeries={hiddenSeries} />} />

            <Legend
              wrapperStyle={{ paddingTop: 8 }}
              onClick={(e) => handleLegendClick(e.dataKey as string)}
              formatter={(value: string, entry) => (
                <span style={{ color: hiddenSeries.has(entry.dataKey as BalanceSeriesKey) ? '#64748b' : DARK_THEME.textPrimary }}>
                  {value}
                </span>
              )}
            />

            <Area
              type="monotone"
              dataKey="sell_balance"
              stroke={COLOR_SELL}
              fill={COLOR_SELL}
              fillOpacity={0.15}
              strokeWidth={1.5}
              dot={false}
              name="信用売残"
              yAxisId="left"
              connectNulls
              isAnimationActive={false}
              hide={isHidden('sell_balance')}
            />
            <Area
              type="monotone"
              dataKey="buy_balance"
              stroke={COLOR_BUY}
              fill={COLOR_BUY}
              fillOpacity={0.15}
              strokeWidth={1.5}
              dot={false}
              name="信用買残"
              yAxisId="left"
              connectNulls
              isAnimationActive={false}
              hide={isHidden('buy_balance')}
            />
            <Line
              type="monotone"
              dataKey="margin_ratio"
              stroke={COLOR_RATIO}
              strokeWidth={2}
              dot={false}
              name="信用倍率"
              yAxisId="right"
              connectNulls
              isAnimationActive={false}
              hide={isHidden('margin_ratio')}
            />
            <Line
              type="monotone"
              dataKey="nikkei_close"
              stroke={COLOR_NIKKEI}
              strokeWidth={1.5}
              strokeDasharray="6 3"
              dot={false}
              name="日経平均"
              yAxisId="nikkei"
              connectNulls
              isAnimationActive={false}
              hide={isHidden('nikkei_close')}
            />
          </ComposedChart>
        </ResponsiveContainer>
      ) : (
        /* ViewMode B: 増減 bar chart */
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart
            data={filteredData}
            margin={{ top: 16, right: 8, bottom: 0, left: 0 }}
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
            <YAxis
              tickFormatter={(v: number) => v >= 1_000_000 || v <= -1_000_000 ? `${(v / 1_000_000).toFixed(1)}M` : v >= 1000 || v <= -1000 ? `${(v / 1000).toFixed(0)}K` : `${v}`}
              axisLine={{ stroke: DARK_THEME.axisLine }}
              tickLine={{ stroke: DARK_THEME.axisLine }}
              tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
              tickMargin={8}
            />

            <RechartsTooltip content={<ChangeTooltip hiddenSeries={hiddenSeries} />} />

            <Legend
              wrapperStyle={{ paddingTop: 8 }}
              onClick={(e) => handleLegendClick(e.dataKey as string)}
              formatter={(value: string, entry) => (
                <span style={{ color: hiddenSeries.has(entry.dataKey as ChangeSeriesKey) ? '#64748b' : DARK_THEME.textPrimary }}>
                  {value}
                </span>
              )}
            />

            <Bar
              dataKey="sell_change"
              fill={COLOR_SELL}
              fillOpacity={0.85}
              name="売残増減"
              maxBarSize={8}
              isAnimationActive={false}
              hide={isHidden('sell_change')}
            />
            <Bar
              dataKey="buy_change"
              fill={COLOR_BUY}
              fillOpacity={0.85}
              name="買残増減"
              maxBarSize={8}
              isAnimationActive={false}
              hide={isHidden('buy_change')}
            />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </ChartContainer>
  )
}
