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
import { CHART_MARGIN } from '../../country/usa/common/chartConstants'

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

// 5系列の色
const COLOR_2S10S  = '#ef4444'  // red - 2s10s（最も注目度が高い）
const COLOR_3M10Y  = '#3b82f6'  // blue - 3m10y
const COLOR_5S30S  = '#f59e0b'  // amber - 5s30s
const COLOR_10S30S = '#8b5cf6'  // purple - 10s30s
const COLOR_3M2Y   = '#10b981'  // green - 3m2y

interface SpreadItem {
  date: string
  spread_2s10s?: number | null
  spread_3m10y?: number | null
  spread_5s30s?: number | null
  spread_10s30s?: number | null
  spread_3m2y?: number | null
  dgs3mo?: number | null
  dgs2?: number | null
  dgs5?: number | null
  dgs10?: number | null
  dgs30?: number | null
}

interface SpreadResponse {
  data: SpreadItem[]
  latest: SpreadItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

function useSpreadData() {
  return useQuery({
    queryKey: ['market', 'us-interest-rate-spread'],
    queryFn: async () => {
      const { data } = await axios.get<SpreadResponse>('/api/market/us-interest-rate-spread')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

type SeriesKey = 'spread_2s10s' | 'spread_3m10y' | 'spread_5s30s' | 'spread_10s30s' | 'spread_3m2y'
type YieldKey = 'dgs3mo' | 'dgs2' | 'dgs5' | 'dgs10' | 'dgs30'

const SERIES_CONFIG: { key: SeriesKey; label: string; color: string; shortLabel: string }[] = [
  { key: 'spread_2s10s',  label: '2s10s (10Y−2Y)',   color: COLOR_2S10S,  shortLabel: '2s10s' },
  { key: 'spread_3m10y',  label: '3m10y (10Y−3M)',   color: COLOR_3M10Y,  shortLabel: '3m10y' },
  { key: 'spread_5s30s',  label: '5s30s (30Y−5Y)',   color: COLOR_5S30S,  shortLabel: '5s30s' },
  { key: 'spread_10s30s', label: '10s30s (30Y−10Y)', color: COLOR_10S30S, shortLabel: '10s30s' },
  { key: 'spread_3m2y',   label: '3m2y (2Y−3M)',     color: COLOR_3M2Y,   shortLabel: '3m2y' },
]

// ===== イールドカーブ分析ロジック =====

interface YieldPair {
  shortKey: YieldKey
  longKey: YieldKey
  shortLabel: string
  longLabel: string
}

const SPREAD_YIELD_MAP: Record<SeriesKey, YieldPair> = {
  spread_2s10s:  { shortKey: 'dgs2',   longKey: 'dgs10', shortLabel: '2Y',  longLabel: '10Y' },
  spread_3m10y:  { shortKey: 'dgs3mo', longKey: 'dgs10', shortLabel: '3M',  longLabel: '10Y' },
  spread_5s30s:  { shortKey: 'dgs5',   longKey: 'dgs30', shortLabel: '5Y',  longLabel: '30Y' },
  spread_10s30s: { shortKey: 'dgs10',  longKey: 'dgs30', shortLabel: '10Y', longLabel: '30Y' },
  spread_3m2y:   { shortKey: 'dgs3mo', longKey: 'dgs2',  shortLabel: '3M',  longLabel: '2Y' },
}

type CurvePattern =
  | 'bear_steepening'
  | 'bull_steepening'
  | 'twist_steepening'
  | 'bear_flattening'
  | 'bull_flattening'
  | 'twist_flattening'
  | 'unchanged'

interface SpreadAnalysis {
  spreadKey: SeriesKey
  spreadChange: number
  shortYieldChange: number
  longYieldChange: number
  pattern: CurvePattern
  driver: 'short_end' | 'long_end' | 'both' | 'unchanged'
}

type TimeframeKey = 'daily' | 'weekly' | 'monthly'

interface TimeframeAnalysis {
  timeframe: TimeframeKey
  label: string
  comparisonDate: string
  latestDate: string
  spreads: SpreadAnalysis[]
  primaryKeys: SeriesKey[]
}

interface YieldCurveAnalysis {
  daily: TimeframeAnalysis
  weekly: TimeframeAnalysis
  monthly: TimeframeAnalysis
}

const THRESHOLD = 0.005 // 0.5bp

function classifyPattern(shortChange: number, longChange: number, spreadChange: number): CurvePattern {
  const isSteepening = spreadChange > THRESHOLD
  const isFlattening = spreadChange < -THRESHOLD

  if (!isSteepening && !isFlattening) return 'unchanged'

  const shortUp = shortChange > THRESHOLD
  const shortDown = shortChange < -THRESHOLD
  const longUp = longChange > THRESHOLD
  const longDown = longChange < -THRESHOLD

  if (isSteepening) {
    if (shortDown && longUp) return 'twist_steepening'
    if (shortDown || (shortDown && longDown)) return 'bull_steepening'
    if (longUp || (shortUp && longUp)) return 'bear_steepening'
    return 'bull_steepening'
  }

  // isFlattening
  if (shortUp && longDown) return 'twist_flattening'
  if (longDown || (shortDown && longDown)) return 'bull_flattening'
  if (shortUp || (shortUp && longUp)) return 'bear_flattening'
  return 'bear_flattening'
}

function determineDriver(shortChange: number, longChange: number): 'short_end' | 'long_end' | 'both' | 'unchanged' {
  const absShort = Math.abs(shortChange)
  const absLong = Math.abs(longChange)
  if (absShort < THRESHOLD && absLong < THRESHOLD) return 'unchanged'
  if (absShort > absLong * 1.5) return 'short_end'
  if (absLong > absShort * 1.5) return 'long_end'
  return 'both'
}

const PATTERN_LABELS: Record<CurvePattern, string> = {
  bear_steepening:  'ベアSt.',
  bull_steepening:  'ブルSt.',
  twist_steepening: 'ツイストSt.',
  bear_flattening:  'ベアFl.',
  bull_flattening:  'ブルFl.',
  twist_flattening: 'ツイストFl.',
  unchanged:        '横ばい',
}

const PATTERN_COLORS: Record<CurvePattern, { bg: string; text: string }> = {
  bear_steepening:  { bg: 'rgba(239, 68, 68, 0.20)', text: '#ef4444' },
  bull_steepening:  { bg: 'rgba(16, 185, 129, 0.20)', text: '#10b981' },
  twist_steepening: { bg: 'rgba(245, 158, 11, 0.20)', text: '#f59e0b' },
  bear_flattening:  { bg: 'rgba(239, 68, 68, 0.20)', text: '#ef4444' },
  bull_flattening:  { bg: 'rgba(16, 185, 129, 0.20)', text: '#10b981' },
  twist_flattening: { bg: 'rgba(245, 158, 11, 0.20)', text: '#f59e0b' },
  unchanged:        { bg: 'rgba(100, 116, 139, 0.20)', text: '#64748b' },
}

const DRIVER_LABELS: Record<string, string> = {
  short_end: '短期主導',
  long_end:  '長期主導',
  both:      '両端',
  unchanged: '—',
}

function formatCompactDate(dateStr: string): string {
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

function analyzeTimeframe(
  latest: SpreadItem,
  comparison: SpreadItem,
  timeframeKey: TimeframeKey,
  label: string,
  primaryKeys: SeriesKey[],
): TimeframeAnalysis {
  const spreads = SERIES_CONFIG.map(({ key }) => {
    const pair = SPREAD_YIELD_MAP[key]
    const latestSpread = (latest[key] as number | null | undefined) ?? null
    const compSpread = (comparison[key] as number | null | undefined) ?? null
    const latestShort = (latest[pair.shortKey] as number | null | undefined) ?? null
    const compShort = (comparison[pair.shortKey] as number | null | undefined) ?? null
    const latestLong = (latest[pair.longKey] as number | null | undefined) ?? null
    const compLong = (comparison[pair.longKey] as number | null | undefined) ?? null

    if (latestSpread == null || compSpread == null || latestShort == null || compShort == null || latestLong == null || compLong == null) {
      return {
        spreadKey: key,
        spreadChange: 0,
        shortYieldChange: 0,
        longYieldChange: 0,
        pattern: 'unchanged' as CurvePattern,
        driver: 'unchanged' as const,
      }
    }

    const spreadChange = latestSpread - compSpread
    const shortYieldChange = latestShort - compShort
    const longYieldChange = latestLong - compLong

    return {
      spreadKey: key,
      spreadChange,
      shortYieldChange,
      longYieldChange,
      pattern: classifyPattern(shortYieldChange, longYieldChange, spreadChange),
      driver: determineDriver(shortYieldChange, longYieldChange),
    }
  })

  return { timeframe: timeframeKey, label, comparisonDate: comparison.date, latestDate: latest.date, spreads, primaryKeys }
}

// ===== 分析パネルコンポーネント =====

const cellBase: React.CSSProperties = {
  padding: '6px 4px',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 3,
  background: DARK_THEME.chartBg,
}

function YieldCurveAnalysisPanel({ analysis }: { analysis: YieldCurveAnalysis }) {
  const timeframes: TimeframeAnalysis[] = [analysis.daily, analysis.weekly, analysis.monthly]

  return (
    <div style={{
      marginBottom: 12,
      padding: '10px 12px',
      background: DARK_THEME.bgTertiary,
      borderRadius: 8,
      border: '1px solid rgba(100, 116, 139, 0.3)',
    }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: DARK_THEME.textPrimary, marginBottom: 8 }}>
        イールドカーブ変化分析
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: '68px repeat(5, 1fr)',
        gap: 1,
        fontSize: 11,
        background: 'rgba(100, 116, 139, 0.25)',
        borderRadius: 4,
        overflow: 'hidden',
      }}>
        {/* ヘッダー行 */}
        <div style={{ ...cellBase, padding: '6px 4px', fontWeight: 700, color: DARK_THEME.textSecondary, fontSize: 10 }}>
          期間
        </div>
        {SERIES_CONFIG.map(({ key, shortLabel, color }) => (
          <div key={key} style={{ ...cellBase, padding: '6px 4px', fontWeight: 700, color, fontSize: 10 }}>
            {shortLabel}
          </div>
        ))}

        {/* データ行 */}
        {timeframes.map((tf) => (
          <>
            {/* 行ヘッダー */}
            <div key={`${tf.timeframe}-header`} style={{
              ...cellBase,
              alignItems: 'flex-start',
              padding: '8px 6px',
            }}>
              <div style={{ fontWeight: 700, color: DARK_THEME.textPrimary, fontSize: 11 }}>{tf.label}</div>
              <div style={{ color: DARK_THEME.textSecondary, fontSize: 9, lineHeight: '1.3' }}>
                {formatCompactDate(tf.comparisonDate)} → {formatCompactDate(tf.latestDate)}
              </div>
            </div>

            {/* スプレッドセル */}
            {tf.spreads.map((spread) => {
              const isPrimary = tf.primaryKeys.includes(spread.spreadKey)
              const pColor = PATTERN_COLORS[spread.pattern]
              const bpChange = Math.round(spread.spreadChange * 100)

              return (
                <div key={`${tf.timeframe}-${spread.spreadKey}`} style={{
                  ...cellBase,
                  borderLeft: isPrimary ? '2px solid rgba(245, 158, 11, 0.5)' : 'none',
                  opacity: isPrimary ? 1 : 0.7,
                }}>
                  {/* パターンバッジ */}
                  <div style={{
                    padding: '1px 5px',
                    borderRadius: 3,
                    background: pColor.bg,
                    color: pColor.text,
                    fontWeight: 600,
                    fontSize: 10,
                    whiteSpace: 'nowrap',
                  }}>
                    {PATTERN_LABELS[spread.pattern]}
                  </div>

                  {/* bp変化 */}
                  <div style={{
                    fontWeight: 600,
                    fontSize: 11,
                    fontVariantNumeric: 'tabular-nums',
                    color: bpChange > 0 ? '#10b981' : bpChange < 0 ? '#ef4444' : DARK_THEME.textSecondary,
                  }}>
                    {bpChange > 0 ? '+' : ''}{bpChange}bp
                  </div>

                  {/* 主導要因 */}
                  <div style={{ color: DARK_THEME.textSecondary, fontSize: 9 }}>
                    {DRIVER_LABELS[spread.driver]}
                  </div>
                </div>
              )
            })}
          </>
        ))}
      </div>

      {/* 凡例 */}
      <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 9, color: DARK_THEME.textSecondary, flexWrap: 'wrap' }}>
        <span><span style={{ color: '#ef4444' }}>■</span> ベア（利回り↑）</span>
        <span><span style={{ color: '#10b981' }}>■</span> ブル（利回り↓）</span>
        <span><span style={{ color: '#f59e0b' }}>■</span> ツイスト（ねじれ）</span>
        <span>St.=スティープ化　Fl.=フラット化</span>
        <span style={{ color: '#f59e0b' }}>│</span>
        <span>= 各期間で重要なスプレッド</span>
      </div>
    </div>
  )
}

// ===== ツールチップ =====

function SpreadTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))

  return (
    <div style={{ backgroundColor: DARK_THEME.tooltipBg, border: `1px solid ${DARK_THEME.tooltipBorder}`, borderRadius: 8, padding: '12px 16px', boxShadow: '0 4px 16px rgba(0,0,0,0.3)' }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: '#f1f5f9' }}>{formattedLabel}</div>
      {SERIES_CONFIG.map(({ key, label: seriesLabel, color }) => {
        if (hiddenSeries.has(key)) return null
        const item = payload.find((p: { dataKey: string }) => p.dataKey === key)
        if (!item || typeof item.value !== 'number') return null
        return (
          <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: color, marginRight: 6 }} />
              {seriesLabel}
            </span>
            <span style={{ fontWeight: 500, color }}>{item.value > 0 ? '+' : ''}{item.value.toFixed(2)}%</span>
          </div>
        )
      })}
    </div>
  )
}

// ===== メインコンポーネント =====

export default function UsInterestRateSpreadChart() {
  const { data: apiData, isLoading, error } = useSpreadData()
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(5)
  const hiddenSeries = useHiddenSeries<SeriesKey>()

  const chartData = useMemo(() => {
    if (!apiData?.data) return []
    return apiData.data.sort((a, b) => a.date.localeCompare(b.date))
  }, [apiData])

  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all') return chartData
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 5
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return chartData.filter((d) => d.date >= cutoffStr)
  }, [chartData, selectedPeriod])

  // イールドカーブ変化分析
  const yieldCurveAnalysis = useMemo<YieldCurveAnalysis | null>(() => {
    if (chartData.length < 2) return null

    const latest = chartData[chartData.length - 1]
    const prevDay = chartData[chartData.length - 2]
    const weekAgo = chartData[Math.max(0, chartData.length - 6)]
    const monthAgo = chartData[Math.max(0, chartData.length - 23)]

    return {
      daily: analyzeTimeframe(latest, prevDay, 'daily', '日次', ['spread_2s10s', 'spread_5s30s']),
      weekly: chartData.length >= 6
        ? analyzeTimeframe(latest, weekAgo, 'weekly', '週次', ['spread_2s10s', 'spread_3m10y', 'spread_5s30s'])
        : analyzeTimeframe(latest, prevDay, 'weekly', '週次', ['spread_2s10s', 'spread_3m10y', 'spread_5s30s']),
      monthly: chartData.length >= 23
        ? analyzeTimeframe(latest, monthAgo, 'monthly', '月次', ['spread_3m10y', 'spread_2s10s'])
        : analyzeTimeframe(latest, prevDay, 'monthly', '月次', ['spread_3m10y', 'spread_2s10s']),
    }
  }, [chartData])

  if (isLoading) {
    return (
      <ChartContainer title="米国長短金利差（イールドスプレッド）" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (error || !apiData || chartData.length === 0) {
    return (
      <ChartContainer title="米国長短金利差（イールドスプレッド）" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  const latest = apiData.latest

  return (
    <ChartContainer
      title="米国長短金利差（イールドスプレッド）"
      dataSource="FRED"
      sourceUrl="https://fred.stlouisfed.org/series/DGS10"
      showPeriodSelector={false}
      handbookId="us-interest-rate-spread"
    >
      {/* 最新値 */}
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
          {SERIES_CONFIG.map(({ key, label, color }) => {
            const val = latest[key]
            if (val == null) return null
            return (
              <div key={key} style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
                <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>{label}</Text>
                <Text
                  style={{
                    color: val < 0 ? '#ef4444' : color,
                    fontSize: 14,
                    fontWeight: 700,
                  }}
                  className="tabular-nums"
                >
                  {val > 0 ? '+' : ''}{val.toFixed(2)}%
                </Text>
              </div>
            )
          })}
          <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>
            ({latest.date})
          </Text>
        </div>
      )}

      {/* イールドカーブ変化分析パネル */}
      {yieldCurveAnalysis && <YieldCurveAnalysisPanel analysis={yieldCurveAnalysis} />}

      {/* データ比較ボタン */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            size="small"
            onClick={() => window.open('/compare?s=us_interest_rate_spread_2s10s', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 期間選択 */}
      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

      {/* 注釈 */}
      <div style={{ marginBottom: 8, padding: '6px 10px', background: 'rgba(239,68,68,0.08)', borderRadius: 6, fontSize: 11, color: DARK_THEME.textSecondary }}>
        マイナス = 逆イールド（短期金利 {'>'} 長期金利）。2s10sと3m10yは景気後退の先行指標として注目される。凡例クリックで系列の表示/非表示を切替
      </div>

      {/* チャート */}
      <ResponsiveContainer width="100%" height={450}>
        <ComposedChart data={filteredData} margin={CHART_MARGIN} style={{ backgroundColor: DARK_THEME.chartBg }}>
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
            domain={['dataMin - 0.1', 'dataMax + 0.1']}
            tickFormatter={(v: number) => `${v.toFixed(1)}%`}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            tickMargin={8}
          />

          {/* ゼロライン */}
          <ReferenceLine y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" strokeWidth={1.5} />

          <RechartsTooltip content={<SpreadTooltip hiddenSeries={hiddenSeries.hiddenSeries} />} />

          <Legend
            wrapperStyle={{ paddingTop: 8 }}
            onClick={(e) => hiddenSeries.handleLegendClick(e.dataKey as string)}
            formatter={(value: string, entry) => (
              <span style={{ color: hiddenSeries.hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : DARK_THEME.textPrimary, fontSize: 11 }}>
                {value}
              </span>
            )}
          />

          {SERIES_CONFIG.map(({ key, label, color }) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              name={label}
              stroke={color}
              strokeWidth={key === 'spread_2s10s' ? 2.5 : 1.5}
              dot={false}
              connectNulls
              isAnimationActive={false}
              hide={hiddenSeries.isHidden(key)}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
