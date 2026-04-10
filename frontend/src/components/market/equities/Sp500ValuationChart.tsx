import { useState, useMemo } from 'react'
import { Tooltip, Button } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import {
  ComposedChart,
  Line,
  Area,
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
import { formatDayLabel } from '../../../utils/dateFormatters'
import { ViewModeButtonGroup } from '../../country/usa/common/ChartComponents'
import { MonthlyTable } from '../../country/usa/common/MonthlyTable'
import { useHiddenSeries } from '../../country/usa/common/useChartData'
import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS, CHART_MARGIN } from '../../country/usa/common/chartConstants'

const DARK_THEME = {
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  gridLine: '#475569',
  axisLine: '#64748b',
  tooltipBg: '#334155',
  tooltipBorder: '#475569',
  chartBg: '#1e293b',
}

// Colors
const COLOR_SP500 = '#3b82f6'       // Blue - S&P500
const COLOR_PE = '#f59e0b'          // Amber - Forward PE
const COLOR_EPS = '#10b981'         // Green - Forward EPS
const COLOR_EARNINGS_YIELD = '#8b5cf6' // Purple - Earnings yield
const COLOR_YIELD_10Y = '#ef4444'   // Red - 10Y Treasury
const COLOR_SPREAD = '#06b6d4'      // Cyan - Yield spread

interface DataItem {
  date: string
  close: number
  forward_pe: number
  forward_eps: number
  earnings_yield: number
  yield_10y: number | null
  yield_spread: number | null
  real_yield_10y: number | null
  real_yield_spread: number | null
  forward_pe_yoy: number | null
  forward_eps_yoy: number | null
  earnings_yield_yoy: number | null
}

interface MonthlyItem {
  date: string
  forward_pe: number
  forward_eps: number
  earnings_yield: number
  close: number
  yield_10y: number
  forward_pe_mom: number | null
  forward_eps_mom: number | null
  earnings_yield_mom: number | null
}

interface ValuationResponse {
  data: DataItem[]
  monthly_table: MonthlyItem[]
  latest: DataItem | null
  metadata: {
    source: string
    source_url: string
    pe_source_url: string
    pe_source: string
    date_range: { start: string; end: string }
    series: string[]
  }
  cached: boolean
  source: string
  last_updated: string | null
}

type ViewMode = 'raw' | 'yoy' | 'mom' | 'yield_spread' | 'real_yield_spread'
const VIEW_MODE_OPTIONS = [
  { mode: 'raw' as ViewMode, label: '原数値' },
  { mode: 'yoy' as ViewMode, label: '前年比' },
  { mode: 'mom' as ViewMode, label: '前月比' },
  { mode: 'yield_spread' as ViewMode, label: 'スプレッド' },
  { mode: 'real_yield_spread' as ViewMode, label: '実質スプレッド' },
]

type RawSeriesKey = 'close' | 'forward_pe' | 'forward_eps'
type YoYSeriesKey = 'forward_pe_yoy' | 'forward_eps_yoy' | 'earnings_yield_yoy'
type SpreadSeriesKey = 'earnings_yield_pct' | 'yield_10y_pct' | 'yield_spread_pct' | 'close'
type RealSpreadSeriesKey = 'earnings_yield_pct' | 'real_yield_10y_pct' | 'real_yield_spread_pct' | 'close'

function fmtPct(v: number, decimals = 2): string {
  return `${v >= 0 ? '+' : ''}${v.toFixed(decimals)}%`
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ChartTooltip({ active, payload, label, viewMode }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  viewMode: ViewMode
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const dp = payload[0]?.payload as any
  if (!dp) return null

  const items: { label: string; value: string; color: string }[] = []

  if (viewMode === 'raw') {
    items.push({ label: 'S&P 500', value: Number(dp.close).toLocaleString(undefined, { maximumFractionDigits: 0 }), color: COLOR_SP500 })
    items.push({ label: '予想PER', value: Number(dp.forward_pe).toFixed(2), color: COLOR_PE })
    items.push({ label: '予想EPS', value: Number(dp.forward_eps).toFixed(2), color: COLOR_EPS })
  } else if (viewMode === 'yoy') {
    if (dp.forward_pe_yoy != null) items.push({ label: '予想PER 前年比', value: fmtPct(dp.forward_pe_yoy), color: COLOR_PE })
    if (dp.forward_eps_yoy != null) items.push({ label: '予想EPS 前年比', value: fmtPct(dp.forward_eps_yoy), color: COLOR_EPS })
    if (dp.earnings_yield_yoy != null) items.push({ label: '益利回り 前年比', value: fmtPct(dp.earnings_yield_yoy), color: COLOR_EARNINGS_YIELD })
  } else if (viewMode === 'yield_spread') {
    items.push({ label: 'S&P 500', value: Number(dp.close).toLocaleString(undefined, { maximumFractionDigits: 0 }), color: COLOR_SP500 })
    if (dp.earnings_yield_pct != null) items.push({ label: '益利回り', value: `${dp.earnings_yield_pct.toFixed(2)}%`, color: COLOR_EARNINGS_YIELD })
    if (dp.yield_10y_pct != null) items.push({ label: '10年債利回り', value: `${dp.yield_10y_pct.toFixed(2)}%`, color: COLOR_YIELD_10Y })
    if (dp.yield_spread_pct != null) items.push({ label: 'スプレッド', value: `${dp.yield_spread_pct >= 0 ? '+' : ''}${dp.yield_spread_pct.toFixed(2)}%`, color: COLOR_SPREAD })
  } else if (viewMode === 'real_yield_spread') {
    items.push({ label: 'S&P 500', value: Number(dp.close).toLocaleString(undefined, { maximumFractionDigits: 0 }), color: COLOR_SP500 })
    if (dp.earnings_yield_pct != null) items.push({ label: '益利回り', value: `${dp.earnings_yield_pct.toFixed(2)}%`, color: COLOR_EARNINGS_YIELD })
    if (dp.real_yield_10y_pct != null) items.push({ label: '実質10年債利回り', value: `${dp.real_yield_10y_pct.toFixed(2)}%`, color: COLOR_YIELD_10Y })
    if (dp.real_yield_spread_pct != null) items.push({ label: '実質スプレッド', value: `${dp.real_yield_spread_pct >= 0 ? '+' : ''}${dp.real_yield_spread_pct.toFixed(2)}%`, color: COLOR_SPREAD })
  }

  return (
    <div style={{
      backgroundColor: DARK_THEME.tooltipBg,
      border: `1px solid ${DARK_THEME.tooltipBorder}`,
      borderRadius: 8,
      padding: '12px 16px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
    }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>{formattedLabel}</div>
      {items.map((item, i) => (
        <div key={i} style={{ color: item.color, fontSize: 13, marginBottom: 3 }}>
          {item.label}: {item.value}
        </div>
      ))}
    </div>
  )
}

export default function Sp500ValuationChart() {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(5)
  const [viewMode, setViewMode] = useState<ViewMode>('raw')
  const { hiddenSeries: hiddenRaw, handleLegendClick: handleRawLegend } = useHiddenSeries<RawSeriesKey>()
  const { hiddenSeries: hiddenYoY, handleLegendClick: handleYoYLegend } = useHiddenSeries<YoYSeriesKey>()
  const { hiddenSeries: hiddenSpread, handleLegendClick: handleSpreadLegend } = useHiddenSeries<SpreadSeriesKey>()
  const { hiddenSeries: hiddenRealSpread, handleLegendClick: handleRealSpreadLegend } = useHiddenSeries<RealSpreadSeriesKey>()

  const { data: response } = useQuery<ValuationResponse>({
    queryKey: ['sp500-valuation'],
    queryFn: async () => {
      const res = await axios.get('/api/market/sp500-valuation')
      return res.data
    },
    staleTime: 1000 * 60 * 30,
  })

  const chartData = useMemo(() => {
    if (!response?.data) return []
    return response.data
  }, [response])

  const filteredData = useMemo(() => {
    if (!chartData.length) return []
    if (currentPeriod === 'all') return chartData
    const years = typeof currentPeriod === 'number' ? currentPeriod : 5
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return chartData.filter(d => d.date >= cutoffStr)
  }, [chartData, currentPeriod])

  // Yield chart data (convert to %)
  const yieldChartData = useMemo(() => {
    return filteredData.map(d => ({
      ...d,
      earnings_yield_pct: d.earnings_yield != null ? d.earnings_yield * 100 : null,
      yield_10y_pct: d.yield_10y != null ? d.yield_10y * 100 : null,
      yield_spread_pct: d.yield_spread != null ? d.yield_spread * 100 : null,
      real_yield_10y_pct: d.real_yield_10y != null ? d.real_yield_10y * 100 : null,
      real_yield_spread_pct: d.real_yield_spread != null ? d.real_yield_spread * 100 : null,
    }))
  }, [filteredData])

  // Monthly table for MoM heatmap
  const momHeatmapData = useMemo(() => {
    if (!response?.monthly_table) return { years: [] as number[], monthlyData: {} as Record<number, Record<number, number | null>> }
    const currentYear = new Date().getFullYear()
    const startYear = currentYear - 9
    const years: number[] = []
    for (let y = startYear; y <= currentYear; y++) years.push(y)

    const monthlyData: Record<number, Record<number, number | null>> = {}
    for (const year of years) {
      monthlyData[year] = {}
      for (let m = 0; m < 12; m++) {
        const ym = `${year}-${String(m + 1).padStart(2, '0')}`
        const row = response.monthly_table.find(r => r.date === ym)
        monthlyData[year][m] = row?.forward_pe_mom ?? null
      }
    }
    return { years, monthlyData }
  }, [response?.monthly_table])


  const latest = response?.latest

  const xAxisProps = {
    type: 'category' as const,
    dataKey: 'date',
    tickFormatter: (v: string) => {
      const d = new Date(v)
      return `${d.getFullYear()}/${d.getMonth() + 1}`
    },
    axisLine: { stroke: DARK_THEME.axisLine },
    tickLine: { stroke: DARK_THEME.axisLine },
    tick: { fill: DARK_THEME.textSecondary, fontSize: 10 },
    tickMargin: 16,
    height: 60,
    interval: 'preserveStartEnd' as const,
  }

  return (
    <ChartContainer
      title="S&P 500 Valuation"
      dataSource="cboe"
      sourceUrl="https://www.cboe.com/"
      handbookId="eps-per-earnings-yield"
      showPeriodSelector={false}
    >
      {/* Latest values */}
      {latest && (
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            <span style={{ color: TEXT_COLORS.secondary, fontSize: 12 }}>{latest.date}</span>

            <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
              <span style={{ color: TEXT_COLORS.secondary, fontSize: 11 }}>S&P 500</span>
              <span style={{ color: COLOR_SP500, fontSize: 20, fontWeight: 700 }} className="tabular-nums">
                {latest.close.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
              <span style={{ color: TEXT_COLORS.secondary, fontSize: 11 }}>Fwd PE</span>
              <span style={{ color: COLOR_PE, fontSize: 15, fontWeight: 600 }} className="tabular-nums">
                {latest.forward_pe.toFixed(2)}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
              <span style={{ color: TEXT_COLORS.secondary, fontSize: 11 }}>Fwd EPS</span>
              <span style={{ color: COLOR_EPS, fontSize: 15, fontWeight: 600 }} className="tabular-nums">
                {latest.forward_eps.toFixed(2)}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
              <span style={{ color: TEXT_COLORS.secondary, fontSize: 11 }}>益利回り</span>
              <span style={{ color: COLOR_EARNINGS_YIELD, fontSize: 15, fontWeight: 600 }} className="tabular-nums">
                {(latest.earnings_yield * 100).toFixed(2)}%
              </span>
            </div>

            {latest.yield_10y != null && (
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
                <span style={{ color: TEXT_COLORS.secondary, fontSize: 11 }}>10Y</span>
                <span style={{ color: COLOR_YIELD_10Y, fontSize: 15, fontWeight: 600 }} className="tabular-nums">
                  {(latest.yield_10y * 100).toFixed(2)}%
                </span>
              </div>
            )}

            {latest.yield_spread != null && (
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
                <span style={{ color: TEXT_COLORS.secondary, fontSize: 11 }}>Spread</span>
                <span style={{ color: COLOR_SPREAD, fontSize: 15, fontWeight: 600 }} className="tabular-nums">
                  {(latest.yield_spread * 100) >= 0 ? '+' : ''}{(latest.yield_spread * 100).toFixed(2)}%
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ViewMode + Compare button */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <ViewModeButtonGroup
          options={VIEW_MODE_OPTIONS}
          currentMode={viewMode}
          onChange={(m) => setViewMode(m as ViewMode)}
        />
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            size="small"
            onClick={() => window.open('/compare?s=sp500_valuation', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* ===== Chart 1: Raw (S&P500 + Forward EPS + Forward PE) ===== */}
      {viewMode === 'raw' && (
        <>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <ResponsiveContainer width="100%" height={400}>
            <ComposedChart data={filteredData} margin={CHART_MARGIN}>
              <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
              <XAxis {...xAxisProps} />
              <YAxis
                yAxisId="left"
                domain={['dataMin * 0.9', 'dataMax * 1.05']}
                tickFormatter={(v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                axisLine={{ stroke: DARK_THEME.axisLine }}
                tickLine={{ stroke: DARK_THEME.axisLine }}
                tick={{ fill: COLOR_SP500, fontSize: 10 }}
                width={55}
                label={{ value: 'S&P 500', angle: -90, position: 'insideLeft', offset: -5, fill: COLOR_SP500, fontSize: 10 }}
              />
              <YAxis
                yAxisId="eps"
                orientation="right"
                domain={['dataMin * 0.85', 'dataMax * 1.1']}
                axisLine={{ stroke: COLOR_EPS }}
                tickLine={{ stroke: COLOR_EPS }}
                tick={{ fill: COLOR_EPS, fontSize: 10 }}
                width={50}
                // label={{ value: 'Forward EPS', angle: 90, position: 'insideRight', offset: -5, fill: COLOR_EPS, fontSize: 10 }}
              />
              <YAxis
                yAxisId="pe"
                orientation="right"
                domain={['dataMin * 0.8', 'dataMax * 1.15']}
                axisLine={{ stroke: COLOR_PE, strokeDasharray: '4 3' }}
                tickLine={{ stroke: COLOR_PE }}
                tick={{ fill: COLOR_PE, fontSize: 10 }}
                width={40}
                // label={{ value: 'PE', angle: 90, position: 'insideRight', offset: -5, fill: COLOR_PE, fontSize: 10 }}
              />
              <RechartsTooltip content={<ChartTooltip viewMode="raw" />} />
              <Legend wrapperStyle={{ paddingTop: 8 }} onClick={(e) => handleRawLegend(e.dataKey as RawSeriesKey)} />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="close"
                name="S&P 500"
                stroke={COLOR_SP500}
                strokeWidth={1.5}
                dot={false}
                connectNulls
                isAnimationActive={false}
                hide={hiddenRaw.has('close')}
              />
              <Line
                yAxisId="eps"
                type="monotone"
                dataKey="forward_eps"
                name="予想EPS"
                stroke={COLOR_EPS}
                strokeWidth={1.5}
                dot={false}
                connectNulls
                isAnimationActive={false}
                hide={hiddenRaw.has('forward_eps')}
              />
              <Line
                yAxisId="pe"
                type="monotone"
                dataKey="forward_pe"
                name="予想PER"
                stroke={COLOR_PE}
                strokeWidth={1.5}
                dot={false}
                connectNulls
                isAnimationActive={false}
                hide={hiddenRaw.has('forward_pe')}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </>
      )}

      {/* ===== Chart 2: YoY (Forward PE / Forward EPS / Earnings Yield YoY) ===== */}
      {viewMode === 'yoy' && (
        <>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <ResponsiveContainer width="100%" height={400}>
            <ComposedChart data={filteredData} margin={CHART_MARGIN}>
              <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
              <XAxis {...xAxisProps} />
              <YAxis
                domain={['dataMin - 5', 'dataMax + 5']}
                tickFormatter={(v: number) => `${v.toFixed(0)}%`}
                axisLine={{ stroke: DARK_THEME.axisLine }}
                tickLine={{ stroke: DARK_THEME.axisLine }}
                tick={{ fill: DARK_THEME.textSecondary, fontSize: 10 }}
                width={50}
              />
              <RechartsTooltip content={<ChartTooltip viewMode="yoy" />} />
              <ReferenceLine y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />
              <Legend wrapperStyle={{ paddingTop: 8 }} onClick={(e) => handleYoYLegend(e.dataKey as YoYSeriesKey)} />
              <Line
                type="monotone"
                dataKey="forward_pe_yoy"
                name="予想PER 前年比 (%)"
                stroke={COLOR_PE}
                strokeWidth={1.5}
                dot={false}
                connectNulls
                isAnimationActive={false}
                hide={hiddenYoY.has('forward_pe_yoy')}
              />
              <Line
                type="monotone"
                dataKey="forward_eps_yoy"
                name="予想EPS 前年比 (%)"
                stroke={COLOR_EPS}
                strokeWidth={1.5}
                dot={false}
                connectNulls
                isAnimationActive={false}
                hide={hiddenYoY.has('forward_eps_yoy')}
              />
              <Line
                type="monotone"
                dataKey="earnings_yield_yoy"
                name="益利回り 前年比 (%)"
                stroke={COLOR_EARNINGS_YIELD}
                strokeWidth={1.5}
                dot={false}
                connectNulls
                isAnimationActive={false}
                hide={hiddenYoY.has('earnings_yield_yoy')}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </>
      )}

      {/* ===== Chart 3: MoM Heatmap ===== */}
      {viewMode === 'mom' && (
        <>
          <div style={{ marginBottom: 16 }}>
            <div style={{ color: DARK_THEME.textPrimary, fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
              予想PER 前月比 (%)
            </div>
            <MonthlyTable
              data={momHeatmapData}
              decimals={2}
              showLegend
              helperText="※ 日次データの月平均から前月比を算出（単位: %）"
            />
          </div>
        </>
      )}

      {/* ===== Chart 4: Yield Spread (Earnings Yield vs 10Y + Spread + S&P500) ===== */}
      {viewMode === 'yield_spread' && (
        <>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <ResponsiveContainer width="100%" height={400}>
            <ComposedChart data={yieldChartData} margin={CHART_MARGIN}>
              <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
              <XAxis {...xAxisProps} />
              <YAxis
                yAxisId="left"
                domain={['auto', 'auto']}
                tickFormatter={(v: number) => `${v.toFixed(1)}%`}
                axisLine={{ stroke: DARK_THEME.axisLine }}
                tickLine={{ stroke: DARK_THEME.axisLine }}
                tick={{ fill: DARK_THEME.textSecondary, fontSize: 10 }}
                width={50}
                label={{ value: '利回り (%)', angle: -90, position: 'insideLeft', offset: -5, fill: DARK_THEME.textSecondary, fontSize: 10 }}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                domain={['dataMin * 0.9', 'dataMax * 1.05']}
                tickFormatter={(v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                axisLine={{ stroke: COLOR_SP500, strokeDasharray: '4 3' }}
                tickLine={{ stroke: COLOR_SP500 }}
                tick={{ fill: COLOR_SP500, fontSize: 10 }}
                width={55}
              />
              <RechartsTooltip content={<ChartTooltip viewMode="yield_spread" />} />
              <ReferenceLine yAxisId="left" y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />
              <Legend wrapperStyle={{ paddingTop: 8 }} onClick={(e) => handleSpreadLegend(e.dataKey as SpreadSeriesKey)} />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="earnings_yield_pct"
                name="予想株式益利回り (%)"
                stroke={COLOR_EARNINGS_YIELD}
                strokeWidth={1.5}
                dot={false}
                connectNulls
                isAnimationActive={false}
                hide={hiddenSpread.has('earnings_yield_pct')}
              />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="yield_10y_pct"
                name="米国10年債利回り (%)"
                stroke={COLOR_YIELD_10Y}
                strokeWidth={1.5}
                dot={false}
                connectNulls
                isAnimationActive={false}
                hide={hiddenSpread.has('yield_10y_pct')}
              />
              <Area
                yAxisId="left"
                type="monotone"
                dataKey="yield_spread_pct"
                name="イールドスプレッド (%)"
                stroke={COLOR_SPREAD}
                fill={COLOR_SPREAD}
                fillOpacity={0.15}
                strokeWidth={1.5}
                dot={false}
                connectNulls
                isAnimationActive={false}
                hide={hiddenSpread.has('yield_spread_pct')}
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="close"
                name="S&P 500"
                stroke={COLOR_SP500}
                strokeWidth={1}
                strokeDasharray="4 3"
                dot={false}
                connectNulls
                isAnimationActive={false}
                hide={hiddenSpread.has('close')}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </>
      )}

      {/* ===== Chart 5: Real Yield Spread (Earnings Yield vs Real 10Y + Spread + S&P500) ===== */}
      {viewMode === 'real_yield_spread' && (
        <>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <ResponsiveContainer width="100%" height={400}>
            <ComposedChart data={yieldChartData} margin={CHART_MARGIN}>
              <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
              <XAxis {...xAxisProps} />
              <YAxis
                yAxisId="left"
                domain={['auto', 'auto']}
                tickFormatter={(v: number) => `${v.toFixed(1)}%`}
                axisLine={{ stroke: DARK_THEME.axisLine }}
                tickLine={{ stroke: DARK_THEME.axisLine }}
                tick={{ fill: DARK_THEME.textSecondary, fontSize: 10 }}
                width={50}
                label={{ value: '利回り (%)', angle: -90, position: 'insideLeft', offset: -5, fill: DARK_THEME.textSecondary, fontSize: 10 }}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                domain={['dataMin * 0.9', 'dataMax * 1.05']}
                tickFormatter={(v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                axisLine={{ stroke: COLOR_SP500, strokeDasharray: '4 3' }}
                tickLine={{ stroke: COLOR_SP500 }}
                tick={{ fill: COLOR_SP500, fontSize: 10 }}
                width={55}
              />
              <RechartsTooltip content={<ChartTooltip viewMode="real_yield_spread" />} />
              <ReferenceLine yAxisId="left" y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />
              <Legend wrapperStyle={{ paddingTop: 8 }} onClick={(e) => handleRealSpreadLegend(e.dataKey as RealSpreadSeriesKey)} />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="earnings_yield_pct"
                name="予想株式益利回り (%)"
                stroke={COLOR_EARNINGS_YIELD}
                strokeWidth={1.5}
                dot={false}
                connectNulls
                isAnimationActive={false}
                hide={hiddenRealSpread.has('earnings_yield_pct')}
              />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="real_yield_10y_pct"
                name="米国実質10年債利回り (%)"
                stroke={COLOR_YIELD_10Y}
                strokeWidth={1.5}
                dot={false}
                connectNulls
                isAnimationActive={false}
                hide={hiddenRealSpread.has('real_yield_10y_pct')}
              />
              <Area
                yAxisId="left"
                type="monotone"
                dataKey="real_yield_spread_pct"
                name="実質イールドスプレッド (%)"
                stroke={COLOR_SPREAD}
                fill={COLOR_SPREAD}
                fillOpacity={0.15}
                strokeWidth={1.5}
                dot={false}
                connectNulls
                isAnimationActive={false}
                hide={hiddenRealSpread.has('real_yield_spread_pct')}
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="close"
                name="S&P 500"
                stroke={COLOR_SP500}
                strokeWidth={1}
                strokeDasharray="4 3"
                dot={false}
                connectNulls
                isAnimationActive={false}
                hide={hiddenRealSpread.has('close')}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </>
      )}
    </ChartContainer>
  )
}
