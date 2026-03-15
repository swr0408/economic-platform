import { useState, useMemo } from 'react'
import { Tooltip, Button } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import {
  ComposedChart,
  Bar,
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

const COLOR_TOTAL = '#f97316'       // Orange (copper)
const COLOR_REGISTERED = '#60a5fa'  // Blue
const COLOR_ELIGIBLE = '#a78bfa'    // Purple

interface CopperItem {
  date: string
  registered_tons: number | null
  eligible_tons: number | null
  total_tons: number | null
}

interface CopperResponse {
  data: CopperItem[]
  latest: CopperItem | null
  latest_copper: { date: string; close: number } | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

type ViewMode = 'raw' | 'mom'
const VIEW_MODE_OPTIONS = [
  { mode: 'raw' as ViewMode, label: '水準' },
  { mode: 'mom' as ViewMode, label: '前月比' },
]

type DisplayMode = 'chart' | 'heatmap'
const DISPLAY_MODE_OPTIONS = [
  { mode: 'chart' as DisplayMode, label: 'チャート' },
  { mode: 'heatmap' as DisplayMode, label: 'ヒートマップ' },
]

function formatTons(val: number): string {
  if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`
  if (val >= 1_000) return `${(val / 1_000).toFixed(0)}K`
  return val.toFixed(0)
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ChartTooltip({ active, payload, label }: {
  active?: boolean
  payload?: any[]
  label?: string
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))
  const dp = payload[0]?.payload as CopperItem | undefined
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
      {dp.total_tons != null && (
        <div style={{ color: COLOR_TOTAL, fontSize: 13, marginBottom: 3 }}>
          Total: {dp.total_tons.toLocaleString(undefined, { maximumFractionDigits: 0 })} short tons
        </div>
      )}
      {dp.registered_tons != null && (
        <div style={{ color: COLOR_REGISTERED, fontSize: 13, marginBottom: 3 }}>
          Registered: {dp.registered_tons.toLocaleString(undefined, { maximumFractionDigits: 0 })} short tons
        </div>
      )}
      {dp.eligible_tons != null && (
        <div style={{ color: COLOR_ELIGIBLE, fontSize: 13, marginBottom: 3 }}>
          Eligible: {dp.eligible_tons.toLocaleString(undefined, { maximumFractionDigits: 0 })} short tons
        </div>
      )}
    </div>
  )
}

export default function ComexCopperStockChart() {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(5)
  const [viewMode, setViewMode] = useState<ViewMode>('raw')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<'total_tons' | 'registered_tons' | 'eligible_tons'>()

  const { data: response } = useQuery<CopperResponse>({
    queryKey: ['comex-copper-stock'],
    queryFn: async () => {
      const res = await axios.get('/api/market/comex-copper-stock')
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

  // Monthly averages for total_tons
  const monthAvg = useMemo(() => {
    if (!chartData.length) return {} as Record<string, number>
    const monthAccum: Record<string, number[]> = {}
    for (const item of chartData) {
      const d = new Date(item.date)
      const val = item.total_tons
      if (val == null) continue
      const key = `${d.getFullYear()}-${String(d.getMonth()).padStart(2, '0')}`
      if (!monthAccum[key]) monthAccum[key] = []
      monthAccum[key].push(val)
    }
    const avg: Record<string, number> = {}
    for (const [key, vals] of Object.entries(monthAccum)) {
      avg[key] = vals.reduce((a, b) => a + b, 0) / vals.length
    }
    return avg
  }, [chartData])

  // MoM heatmap
  const momHeatmapData = useMemo(() => {
    const currentYear = new Date().getFullYear()
    const startYear = currentYear - 9
    const years: number[] = []
    for (let y = startYear; y <= currentYear; y++) years.push(y)
    const monthlyData: Record<number, Record<number, number | null>> = {}
    for (const year of years) {
      monthlyData[year] = {}
      for (let m = 0; m < 12; m++) {
        const curVal = monthAvg[`${year}-${String(m).padStart(2, '0')}`]
        if (curVal == null) { monthlyData[year][m] = null; continue }
        let prevYear = year; let prevMonth = m - 1
        if (prevMonth < 0) { prevMonth = 11; prevYear-- }
        const prevVal = monthAvg[`${prevYear}-${String(prevMonth).padStart(2, '0')}`]
        monthlyData[year][m] = (prevVal != null && prevVal !== 0)
          ? Math.round(((curVal - prevVal) / prevVal) * 10000) / 100 : null
      }
    }
    return { years, monthlyData }
  }, [monthAvg])

  // MoM bar chart data
  const momChartData = useMemo(() => {
    const entries = Object.entries(monthAvg).sort(([a], [b]) => a.localeCompare(b))
    const result: { date: string; mom: number | null }[] = []
    for (let i = 1; i < entries.length; i++) {
      const [curKey, curVal] = entries[i]
      const [, prevVal] = entries[i - 1]
      const [y, m] = curKey.split('-').map(Number)
      result.push({
        date: `${y}-${String(m + 1).padStart(2, '0')}-15`,
        mom: (prevVal != null && prevVal !== 0)
          ? Math.round(((curVal - prevVal) / prevVal) * 10000) / 100 : null,
      })
    }
    return result
  }, [monthAvg])

  const filteredMomChartData = useMemo(() => {
    if (!momChartData.length) return []
    if (currentPeriod === 'all') return momChartData
    const years = typeof currentPeriod === 'number' ? currentPeriod : 5
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return momChartData.filter(d => d.date >= cutoffStr)
  }, [momChartData, currentPeriod])

  const latest = response?.latest
  const latestCopper = response?.latest_copper

  return (
    <ChartContainer
      title="COMEX Total Copper Inventory"
      dataSource="CME COMEX"
      sourceUrl="https://www.cmegroup.com/solutions/clearing/operations-and-deliveries/nymex-delivery-notices.html"
      showPeriodSelector={false}
    >
      {/* 最新値 */}
      {latest && (
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            <span style={{ color: TEXT_COLORS.secondary, fontSize: 12 }}>{latest.date}</span>

            <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
              <span style={{ color: TEXT_COLORS.secondary, fontSize: 11 }}>Total</span>
              <span style={{ color: COLOR_TOTAL, fontSize: 20, fontWeight: 700 }} className="tabular-nums">
                {latest.total_tons?.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </span>
              <span style={{ color: TEXT_COLORS.secondary, fontSize: 11 }}>short tons</span>
            </div>

            {latest.registered_tons != null && (
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
                <span style={{ color: TEXT_COLORS.secondary, fontSize: 11 }}>Registered</span>
                <span style={{ color: COLOR_REGISTERED, fontSize: 15, fontWeight: 600 }} className="tabular-nums">
                  {latest.registered_tons.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </span>
                <span style={{ color: TEXT_COLORS.secondary, fontSize: 11 }}>short tons</span>
              </div>
            )}

            {latest.eligible_tons != null && (
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
                <span style={{ color: TEXT_COLORS.secondary, fontSize: 11 }}>Eligible</span>
                <span style={{ color: COLOR_ELIGIBLE, fontSize: 15, fontWeight: 600 }} className="tabular-nums">
                  {latest.eligible_tons.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </span>
                <span style={{ color: TEXT_COLORS.secondary, fontSize: 11 }}>short tons</span>
              </div>
            )}

            {latestCopper && (
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
                <span style={{ color: TEXT_COLORS.secondary, fontSize: 11 }}>先物(HG=F)</span>
                <span style={{ color: '#e2e8f0', fontSize: 15, fontWeight: 600 }} className="tabular-nums">
                  ${latestCopper.close.toFixed(4)}
                </span>
                <span style={{ color: TEXT_COLORS.secondary, fontSize: 11 }}>/lb</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ViewMode + 比較ボタン（同一行） */}
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
            onClick={() => window.open('/compare?s=comex_copper_stock', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* チャート/ヒートマップ切替（前月比のみ） */}
      {viewMode === 'mom' && (
        <div style={{ marginBottom: 8 }}>
          <ViewModeButtonGroup
            options={DISPLAY_MODE_OPTIONS}
            currentMode={displayMode}
            onChange={(m) => setDisplayMode(m as DisplayMode)}
          />
        </div>
      )}

      {/* 水準チャート */}
      {viewMode === 'raw' && (
        <>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <ResponsiveContainer width="100%" height={400}>
            <ComposedChart data={filteredData} margin={CHART_MARGIN}>
              <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
              <XAxis
                type="category"
                dataKey="date"
                tickFormatter={(v: string) => {
                  const d = new Date(v)
                  return `${d.getFullYear()}/${d.getMonth() + 1}`
                }}
                axisLine={{ stroke: DARK_THEME.axisLine }}
                tickLine={{ stroke: DARK_THEME.axisLine }}
                tick={{ fill: DARK_THEME.textSecondary, fontSize: 10 }}
                tickMargin={16}
                height={60}
                interval="preserveStartEnd"
              />
              <YAxis
                yAxisId="left"
                domain={['dataMin * 0.9', 'dataMax * 1.1']}
                tickFormatter={(v: number) => formatTons(v)}
                axisLine={{ stroke: DARK_THEME.axisLine }}
                tickLine={{ stroke: DARK_THEME.axisLine }}
                tick={{ fill: COLOR_TOTAL, fontSize: 10 }}
                width={60}
                label={{ value: 'Short Tons', angle: -90, position: 'insideLeft', offset: -8, fill: COLOR_TOTAL, fontSize: 10 }}
              />
              <RechartsTooltip content={<ChartTooltip />} />
              <Legend wrapperStyle={{ paddingTop: 8 }} onClick={(e) => handleLegendClick(e.dataKey as 'total_tons' | 'registered_tons' | 'eligible_tons')} />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="total_tons"
                name="Total (short tons)"
                stroke={COLOR_TOTAL}
                strokeWidth={1.5}
                dot={false}
                connectNulls
                isAnimationActive={false}
                hide={hiddenSeries.has('total_tons')}
              />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="registered_tons"
                name="Registered (short tons)"
                stroke={COLOR_REGISTERED}
                strokeWidth={1.2}
                dot={false}
                connectNulls
                isAnimationActive={false}
                hide={hiddenSeries.has('registered_tons')}
              />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="eligible_tons"
                name="Eligible (short tons)"
                stroke={COLOR_ELIGIBLE}
                strokeWidth={1.2}
                dot={false}
                connectNulls
                isAnimationActive={false}
                hide={hiddenSeries.has('eligible_tons')}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </>
      )}

      {/* 前月比バーチャート */}
      {viewMode === 'mom' && displayMode === 'chart' && (
        <>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <ResponsiveContainer width="100%" height={400}>
            <ComposedChart data={filteredMomChartData} margin={CHART_MARGIN}>
              <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
              <XAxis
                type="category"
                dataKey="date"
                tickFormatter={(v: string) => {
                  const d = new Date(v)
                  return `${d.getFullYear()}/${d.getMonth() + 1}`
                }}
                axisLine={{ stroke: DARK_THEME.axisLine }}
                tickLine={{ stroke: DARK_THEME.axisLine }}
                tick={{ fill: DARK_THEME.textSecondary, fontSize: 10 }}
                tickMargin={16}
                height={60}
                interval="preserveStartEnd"
              />
              <YAxis
                tickFormatter={(v: number) => `${v.toFixed(0)}%`}
                axisLine={{ stroke: DARK_THEME.axisLine }}
                tickLine={{ stroke: DARK_THEME.axisLine }}
                tick={{ fill: DARK_THEME.textSecondary, fontSize: 10 }}
                width={50}
              />
              <RechartsTooltip
                contentStyle={{
                  backgroundColor: DARK_THEME.tooltipBg,
                  border: `1px solid ${DARK_THEME.tooltipBorder}`,
                  borderRadius: 8,
                }}
                labelFormatter={(v: string) => formatDayLabel(v)}
                formatter={(v: number) => [`${v >= 0 ? '+' : ''}${v.toFixed(2)}%`, 'MoM']}
              />
              <ReferenceLine y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />
              <Bar dataKey="mom" name="在庫 前月比 (%)" fill={COLOR_TOTAL} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </>
      )}

      {/* 前月比ヒートマップ */}
      {viewMode === 'mom' && displayMode === 'heatmap' && (
        <MonthlyTable
          data={momHeatmapData}
          decimals={2}
          showLegend
          helperText="※ COMEX銅在庫 前月比（日次データの月平均から算出, 単位: %）"
        />
      )}
    </ChartContainer>
  )
}
