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

const COLOR_STOCK = '#fb923c'  // Orange-400 (SHFE copper)

interface ShfeItem {
  date: string
  stock_tonnes: number | null
}

interface ShfeResponse {
  data: ShfeItem[]
  latest: ShfeItem | null
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

function formatTonnes(val: number): string {
  if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`
  if (val >= 1_000) return `${(val / 1_000).toFixed(0)}K`
  return val.toFixed(0)
}

export default function ShfeCopperStockChart() {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>('all')
  const [viewMode, setViewMode] = useState<ViewMode>('raw')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')

  const { data: response } = useQuery<ShfeResponse>({
    queryKey: ['shfe-copper-stock'],
    queryFn: async () => {
      const res = await axios.get('/api/market/shfe-copper-stock')
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

  // Monthly averages
  const monthAvg = useMemo(() => {
    if (!chartData.length) return {} as Record<string, number>
    const monthAccum: Record<string, number[]> = {}
    for (const item of chartData) {
      const d = new Date(item.date)
      const val = item.stock_tonnes
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

  return (
    <ChartContainer
      title="SHFE Copper Warehouse Stock"
      dataSource="SHFE"
      sourceUrl="https://www.shfe.com.cn/eng/reports/StatisticalData/DailyData/"
      showPeriodSelector={false}
    >
      {/* 最新値 */}
      {latest && (
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            <span style={{ color: TEXT_COLORS.secondary, fontSize: 12 }}>{latest.date}</span>

            <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
              <span style={{ color: TEXT_COLORS.secondary, fontSize: 11 }}>Stock</span>
              <span style={{ color: COLOR_STOCK, fontSize: 20, fontWeight: 700 }} className="tabular-nums">
                {latest.stock_tonnes?.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </span>
              <span style={{ color: TEXT_COLORS.secondary, fontSize: 11 }}>tonnes</span>
            </div>
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
            onClick={() => window.open('/compare?s=shfe_copper_stock', '_blank')}
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
                tickFormatter={(v: number) => formatTonnes(v)}
                axisLine={{ stroke: DARK_THEME.axisLine }}
                tickLine={{ stroke: DARK_THEME.axisLine }}
                tick={{ fill: COLOR_STOCK, fontSize: 10 }}
                width={60}
                label={{ value: 'Tonnes', angle: -90, position: 'insideLeft', offset: -8, fill: COLOR_STOCK, fontSize: 10 }}
              />
              <RechartsTooltip
                contentStyle={{
                  backgroundColor: DARK_THEME.tooltipBg,
                  border: `1px solid ${DARK_THEME.tooltipBorder}`,
                  borderRadius: 8,
                }}
                labelFormatter={(v: string) => formatDayLabel(v)}
                formatter={(v: number) => [`${v.toLocaleString(undefined, { maximumFractionDigits: 0 })} tonnes`, 'Stock']}
              />
              <Legend wrapperStyle={{ paddingTop: 8 }} />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="stock_tonnes"
                name="Stock (tonnes)"
                stroke={COLOR_STOCK}
                strokeWidth={1.5}
                dot={false}
                connectNulls
                isAnimationActive={false}
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
              <Bar dataKey="mom" name="在庫 前月比 (%)" fill={COLOR_STOCK} isAnimationActive={false} />
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
          helperText="※ SHFE銅在庫 前月比（日次データの月平均から算出, 単位: %）"
        />
      )}
    </ChartContainer>
  )
}
