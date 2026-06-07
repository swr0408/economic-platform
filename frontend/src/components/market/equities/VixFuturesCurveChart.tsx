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

const COLOR_FRONT = '#ef4444'    // M1-M2 (赤)
const COLOR_DOUBLE = '#f59e0b'   // M1-2M2+M3 (アンバー)
const COLOR_SLOPE = '#8b5cf6'    // M1-M3 (パープル)
const COLOR_DTE = '#94a3b8'      // DTE (グレー)
const COLOR_M1 = '#ef4444'
const COLOR_M2 = '#f59e0b'
const COLOR_M3 = '#8b5cf6'
const COLOR_SP500 = '#3b82f6'

interface VixFuturesCurveItem {
  date: string
  m1_settle: number
  m2_settle: number
  m3_settle: number
  front_spread: number
  double_spread: number
  m1_m3_slope: number
  m1_dte: number
  m1_expiry: string
  sp500?: number | null
}

interface VixFuturesCurveResponse {
  data: VixFuturesCurveItem[]
  latest: VixFuturesCurveItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

function useVixFuturesCurveData() {
  return useQuery({
    queryKey: ['market', 'vix-futures-curve'],
    queryFn: async () => {
      const { data } = await axios.get<VixFuturesCurveResponse>('/api/market/vix-futures-curve')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

type ViewMode = 'spreads' | 'levels'

const VIEW_MODE_OPTIONS = [
  { mode: 'spreads' as ViewMode, label: 'スプレッド時系列' },
  { mode: 'levels' as ViewMode, label: 'M1/M2/M3 セトル' },
]

type SpreadSeriesKey = 'front_spread' | 'double_spread' | 'm1_m3_slope' | 'sp500'
type LevelSeriesKey = 'm1_settle' | 'm2_settle' | 'm3_settle' | 'sp500'

// ----- Spread tooltip -----
function SpreadTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))

  const series = [
    { key: 'front_spread', label: 'Front Spread (M1-M2)', color: COLOR_FRONT, fmt: (v: number) => v.toFixed(3) },
    { key: 'double_spread', label: 'Double Spread / 曲率', color: COLOR_DOUBLE, fmt: (v: number) => v.toFixed(3) },
    { key: 'm1_m3_slope', label: 'M1-M3 Slope', color: COLOR_SLOPE, fmt: (v: number) => v.toFixed(3) },
    { key: 'sp500', label: 'S&P 500', color: COLOR_SP500, fmt: (v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 0 }) },
  ]

  return (
    <div style={{ backgroundColor: DARK_THEME.tooltipBg, border: `1px solid ${DARK_THEME.tooltipBorder}`, borderRadius: 8, padding: '12px 16px', boxShadow: '0 4px 16px rgba(0,0,0,0.3)' }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: '#f1f5f9' }}>{formattedLabel}</div>
      {series.map(({ key, label: seriesLabel, color, fmt }) => {
        if (hiddenSeries.has(key)) return null
        const item = payload.find((p: { dataKey: string }) => p.dataKey === key)
        if (!item || typeof item.value !== 'number') return null
        return (
          <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: color, marginRight: 6 }} />
              {seriesLabel}
            </span>
            <span style={{ fontWeight: 500, color }}>{fmt(item.value)}</span>
          </div>
        )
      })}
    </div>
  )
}

// ----- Level tooltip -----
function LevelTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))

  const series = [
    { key: 'm1_settle', label: 'VX1 (M1)', color: COLOR_M1, fmt: (v: number) => v.toFixed(2) },
    { key: 'm2_settle', label: 'VX2 (M2)', color: COLOR_M2, fmt: (v: number) => v.toFixed(2) },
    { key: 'm3_settle', label: 'VX3 (M3)', color: COLOR_M3, fmt: (v: number) => v.toFixed(2) },
    { key: 'sp500', label: 'S&P 500', color: COLOR_SP500, fmt: (v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 0 }) },
  ]

  return (
    <div style={{ backgroundColor: DARK_THEME.tooltipBg, border: `1px solid ${DARK_THEME.tooltipBorder}`, borderRadius: 8, padding: '12px 16px', boxShadow: '0 4px 16px rgba(0,0,0,0.3)' }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: '#f1f5f9' }}>{formattedLabel}</div>
      {series.map(({ key, label: seriesLabel, color, fmt }) => {
        if (hiddenSeries.has(key)) return null
        const item = payload.find((p: { dataKey: string }) => p.dataKey === key)
        if (!item || typeof item.value !== 'number') return null
        return (
          <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: color, marginRight: 6 }} />
              {seriesLabel}
            </span>
            <span style={{ fontWeight: 500, color }}>{fmt(item.value)}</span>
          </div>
        )
      })}
    </div>
  )
}

export default function VixFuturesCurveChart() {
  const { data: apiData, isLoading, error } = useVixFuturesCurveData()
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(2)
  const [viewMode, setViewMode] = useState<ViewMode>('spreads')
  const spreadHidden = useHiddenSeries<SpreadSeriesKey>()
  const levelHidden = useHiddenSeries<LevelSeriesKey>()

  const chartData = useMemo(() => {
    if (!apiData?.data) return []
    return [...apiData.data].sort((a, b) => a.date.localeCompare(b.date))
  }, [apiData])

  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all') return chartData
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 2
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return chartData.filter((d) => d.date >= cutoffStr)
  }, [chartData, selectedPeriod])

  if (isLoading) {
    return (
      <ChartContainer title="VIX先物カーブ（M1-M3）" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (error || !apiData || chartData.length === 0) {
    return (
      <ChartContainer title="VIX先物カーブ（M1-M3）" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  const latest = apiData.latest

  return (
    <ChartContainer
      title="VIX先物カーブ（M1-M3）"
      dataSource="cboe"
      sourceUrl="https://www.cboe.com/us/futures/market_statistics/settlement/"
      handbookId="vix-futures-curve"
      showPeriodSelector={false}
    >
      {/* 最新値ボックス */}
      {latest && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            marginBottom: 12,
            padding: '10px 14px',
            background: DARK_THEME.bgTertiary,
            borderRadius: 8,
            flexWrap: 'wrap',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>VX1</Text>
            <Text style={{ color: COLOR_M1, fontSize: 16, fontWeight: 700 }} className="tabular-nums">
              {latest.m1_settle.toFixed(2)}
            </Text>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>VX2</Text>
            <Text style={{ color: COLOR_M2, fontSize: 16, fontWeight: 700 }} className="tabular-nums">
              {latest.m2_settle.toFixed(2)}
            </Text>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>VX3</Text>
            <Text style={{ color: COLOR_M3, fontSize: 16, fontWeight: 700 }} className="tabular-nums">
              {latest.m3_settle.toFixed(2)}
            </Text>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>Front</Text>
            <Text
              style={{
                color: latest.front_spread > 0 ? '#fbbf24' : COLOR_FRONT,
                fontSize: 14,
                fontWeight: 600,
              }}
              className="tabular-nums"
            >
              {latest.front_spread >= 0 ? '+' : ''}{latest.front_spread.toFixed(3)}
            </Text>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>Double</Text>
            <Text style={{ color: COLOR_DOUBLE, fontSize: 14, fontWeight: 600 }} className="tabular-nums">
              {latest.double_spread >= 0 ? '+' : ''}{latest.double_spread.toFixed(3)}
            </Text>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>M1-M3</Text>
            <Text style={{ color: COLOR_SLOPE, fontSize: 14, fontWeight: 600 }} className="tabular-nums">
              {latest.m1_m3_slope >= 0 ? '+' : ''}{latest.m1_m3_slope.toFixed(3)}
            </Text>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>M1 DTE</Text>
            <Text style={{ color: COLOR_DTE, fontSize: 14, fontWeight: 600 }} className="tabular-nums">
              {latest.m1_dte}日
            </Text>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>({latest.m1_expiry})</Text>
          </div>
          {latest.sp500 != null && (
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>S&P 500</Text>
              <Text style={{ color: COLOR_SP500, fontSize: 14, fontWeight: 600 }} className="tabular-nums">
                {latest.sp500.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </Text>
            </div>
          )}
          <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>
            ({latest.date})
          </Text>
        </div>
      )}

      {/* ViewModeButtonGroup + データ比較ボタン */}
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
            onClick={() => window.open('/compare?s=vx_front_spread', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

      {/* === スプレッドビュー === */}
      {viewMode === 'spreads' && (
        <ResponsiveContainer width="100%" height={450}>
          <ComposedChart
            data={filteredData}
            margin={{ top: 16, right: 8, bottom: 0, left: 0 }}
            style={{ backgroundColor: DARK_THEME.chartBg }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />

            {/* 0ライン: コンタンゴ/バックワーデーション境界 */}
            <ReferenceLine yAxisId="left" y={0} stroke="#94a3b8" strokeDasharray="6 3" strokeWidth={1} />

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
              yAxisId="left"
              domain={['dataMin - 1', 'dataMax + 1']}
              tickFormatter={(v: number) => v.toFixed(1)}
              axisLine={{ stroke: DARK_THEME.axisLine }}
              tickLine={{ stroke: DARK_THEME.axisLine }}
              tick={{ fill: DARK_THEME.textPrimary, fontSize: 11 }}
              tickMargin={8}
              label={{ value: 'スプレッド (pt)', angle: -90, position: 'insideLeft', offset: -8, fill: DARK_THEME.textPrimary, fontSize: 11 }}
            />

            <YAxis
              yAxisId="right"
              orientation="right"
              domain={['dataMin', 'dataMax']}
              tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(1)}K` : `${v}`}
              axisLine={{ stroke: DARK_THEME.axisLine }}
              tickLine={{ stroke: DARK_THEME.axisLine }}
              tick={{ fill: COLOR_SP500, fontSize: 11 }}
              tickMargin={8}
              label={{ value: 'S&P 500', angle: 90, position: 'insideRight', offset: -4, fill: COLOR_SP500, fontSize: 11 }}
            />

            <RechartsTooltip content={<SpreadTooltip hiddenSeries={spreadHidden.hiddenSeries} />} />

            <Legend
              wrapperStyle={{ paddingTop: 8 }}
              onClick={(e) => spreadHidden.handleLegendClick(e.dataKey as string)}
              formatter={(value: string, entry) => (
                <span style={{ color: spreadHidden.hiddenSeries.has(entry.dataKey as SpreadSeriesKey) ? '#64748b' : DARK_THEME.textPrimary, fontSize: 11 }}>
                  {value}
                </span>
              )}
            />

            <Line type="monotone" dataKey="front_spread" stroke={COLOR_FRONT} strokeWidth={2} dot={false} name="Front (M1-M2)" yAxisId="left" connectNulls isAnimationActive={false} hide={spreadHidden.isHidden('front_spread')} />
            <Line type="monotone" dataKey="double_spread" stroke={COLOR_DOUBLE} strokeWidth={1.5} dot={false} name="Double / 曲率" yAxisId="left" connectNulls isAnimationActive={false} hide={spreadHidden.isHidden('double_spread')} />
            <Line type="monotone" dataKey="m1_m3_slope" stroke={COLOR_SLOPE} strokeWidth={1.5} dot={false} name="M1-M3" yAxisId="left" connectNulls isAnimationActive={false} hide={spreadHidden.isHidden('m1_m3_slope')} />
            <Line type="monotone" dataKey="sp500" stroke={COLOR_SP500} strokeWidth={1.5} strokeDasharray="4 2" dot={false} name="S&P 500" yAxisId="right" connectNulls isAnimationActive={false} hide={spreadHidden.isHidden('sp500')} />
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* === レベルビュー === */}
      {viewMode === 'levels' && (
        <ResponsiveContainer width="100%" height={450}>
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
              yAxisId="left"
              domain={['dataMin - 1', 'dataMax + 2']}
              tickFormatter={(v: number) => v.toFixed(0)}
              axisLine={{ stroke: DARK_THEME.axisLine }}
              tickLine={{ stroke: DARK_THEME.axisLine }}
              tick={{ fill: COLOR_M1, fontSize: 11 }}
              tickMargin={8}
              label={{ value: 'VX Settle (pt)', angle: -90, position: 'insideLeft', offset: -8, fill: COLOR_M1, fontSize: 11 }}
            />

            <YAxis
              yAxisId="right"
              orientation="right"
              domain={['dataMin', 'dataMax']}
              tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(1)}K` : `${v}`}
              axisLine={{ stroke: DARK_THEME.axisLine }}
              tickLine={{ stroke: DARK_THEME.axisLine }}
              tick={{ fill: COLOR_SP500, fontSize: 11 }}
              tickMargin={8}
              label={{ value: 'S&P 500', angle: 90, position: 'insideRight', offset: -4, fill: COLOR_SP500, fontSize: 11 }}
            />

            <RechartsTooltip content={<LevelTooltip hiddenSeries={levelHidden.hiddenSeries} />} />

            <Legend
              wrapperStyle={{ paddingTop: 8 }}
              onClick={(e) => levelHidden.handleLegendClick(e.dataKey as string)}
              formatter={(value: string, entry) => (
                <span style={{ color: levelHidden.hiddenSeries.has(entry.dataKey as LevelSeriesKey) ? '#64748b' : DARK_THEME.textPrimary, fontSize: 11 }}>
                  {value}
                </span>
              )}
            />

            <Line type="monotone" dataKey="m1_settle" stroke={COLOR_M1} strokeWidth={2} dot={false} name="VX1 (M1)" yAxisId="left" connectNulls isAnimationActive={false} hide={levelHidden.isHidden('m1_settle')} />
            <Line type="monotone" dataKey="m2_settle" stroke={COLOR_M2} strokeWidth={1.5} dot={false} name="VX2 (M2)" yAxisId="left" connectNulls isAnimationActive={false} hide={levelHidden.isHidden('m2_settle')} />
            <Line type="monotone" dataKey="m3_settle" stroke={COLOR_M3} strokeWidth={1.5} dot={false} name="VX3 (M3)" yAxisId="left" connectNulls isAnimationActive={false} hide={levelHidden.isHidden('m3_settle')} />
            <Line type="monotone" dataKey="sp500" stroke={COLOR_SP500} strokeWidth={1.5} strokeDasharray="4 2" dot={false} name="S&P 500" yAxisId="right" connectNulls isAnimationActive={false} hide={levelHidden.isHidden('sp500')} />
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* 解説 */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: 16, marginTop: 8, flexWrap: 'wrap' }}>
        <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>
          {viewMode === 'spreads'
            ? 'Front>0 = バックワーデーション（短期ストレス） / Front<0 = コンタンゴ（通常）'
            : 'M1<M2<M3 = コンタンゴ / M1>M2>M3 = バックワーデーション'}
        </Text>
      </div>
    </ChartContainer>
  )
}
