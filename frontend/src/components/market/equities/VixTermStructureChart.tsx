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

const COLOR_VIX9D = '#f59e0b'    // アンバー
const COLOR_VIX = '#ef4444'      // 赤
const COLOR_VIX3M = '#8b5cf6'    // パープル
const COLOR_SP500 = '#3b82f6'    // 青
const COLOR_RATIO = '#10b981'    // エメラルド

interface VixTermStructureItem {
  date: string
  vix: number
  vix9d?: number | null
  vix3m?: number | null
  sp500?: number | null
  ratio_9d_vix?: number | null
  ratio_vix_3m?: number | null
}

interface VixTermStructureResponse {
  data: VixTermStructureItem[]
  latest: VixTermStructureItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

function useVixTermStructureData() {
  return useQuery({
    queryKey: ['market', 'vix-term-structure'],
    queryFn: async () => {
      const { data } = await axios.get<VixTermStructureResponse>('/api/market/vix-term-structure')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

type ViewMode = 'raw' | 'ratio_9d_vix' | 'ratio_vix_3m'

const VIEW_MODE_OPTIONS = [
  { mode: 'raw' as ViewMode, label: 'ターム構造' },
  { mode: 'ratio_9d_vix' as ViewMode, label: 'VIX9D/VIX' },
  { mode: 'ratio_vix_3m' as ViewMode, label: 'VIX/VIX3M' },
]

type RawSeriesKey = 'vix9d' | 'vix' | 'vix3m' | 'sp500'
type RatioSeriesKey = 'ratio' | 'sp500'

// --- Raw mode tooltip ---
function RawTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))

  const series = [
    { key: 'vix9d', label: 'VIX9D', color: COLOR_VIX9D, fmt: (v: number) => v.toFixed(2) },
    { key: 'vix', label: 'VIX', color: COLOR_VIX, fmt: (v: number) => v.toFixed(2) },
    { key: 'vix3m', label: 'VIX3M', color: COLOR_VIX3M, fmt: (v: number) => v.toFixed(2) },
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

// --- Ratio mode tooltip ---
function RatioTooltip({ active, payload, label, hiddenSeries, ratioLabel }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
  ratioLabel: string
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))

  const series = [
    { key: 'ratio', label: ratioLabel, color: COLOR_RATIO, fmt: (v: number) => v.toFixed(4) },
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

export default function VixTermStructureChart() {
  const { data: apiData, isLoading, error } = useVixTermStructureData()
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(2)
  const [viewMode, setViewMode] = useState<ViewMode>('raw')
  const rawHidden = useHiddenSeries<RawSeriesKey>()
  const ratioHidden = useHiddenSeries<RatioSeriesKey>()

  const chartData = useMemo(() => {
    if (!apiData?.data) return []
    return apiData.data.sort((a, b) => a.date.localeCompare(b.date))
  }, [apiData])

  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all') return chartData
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 2
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return chartData.filter((d) => d.date >= cutoffStr)
  }, [chartData, selectedPeriod])

  // Ratio view data
  const ratioData = useMemo(() => {
    const ratioKey = viewMode === 'ratio_9d_vix' ? 'ratio_9d_vix' : 'ratio_vix_3m'
    return filteredData.map((d) => ({
      date: d.date,
      ratio: d[ratioKey] ?? null,
      sp500: d.sp500 ?? null,
    }))
  }, [filteredData, viewMode])

  if (isLoading) {
    return (
      <ChartContainer title="VIX期間構造" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (error || !apiData || chartData.length === 0) {
    return (
      <ChartContainer title="VIX期間構造" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  const latest = apiData.latest
  const ratioLabel = viewMode === 'ratio_9d_vix' ? 'VIX9D/VIX' : 'VIX/VIX3M'

  return (
    <ChartContainer
      title="VIX期間構造"
      dataSource="yfinance"
      sourceUrl="https://finance.yahoo.com/quote/%5EVIX/"
      handbookId="vix-term-structure"
      showPeriodSelector={false}
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
          {latest.vix9d != null && (
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>VIX9D</Text>
              <Text style={{ color: COLOR_VIX9D, fontSize: 16, fontWeight: 700 }} className="tabular-nums">
                {latest.vix9d.toFixed(2)}
              </Text>
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>VIX</Text>
            <Text style={{ color: COLOR_VIX, fontSize: 16, fontWeight: 700 }} className="tabular-nums">
              {latest.vix.toFixed(2)}
            </Text>
          </div>

          {latest.vix3m != null && (
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>VIX3M</Text>
              <Text style={{ color: COLOR_VIX3M, fontSize: 16, fontWeight: 700 }} className="tabular-nums">
                {latest.vix3m.toFixed(2)}
              </Text>
            </div>
          )}

          {latest.ratio_9d_vix != null && (
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>9D/VIX</Text>
              <Text style={{ color: COLOR_RATIO, fontSize: 14, fontWeight: 600 }} className="tabular-nums">
                {latest.ratio_9d_vix.toFixed(4)}
              </Text>
            </div>
          )}

          {latest.ratio_vix_3m != null && (
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>VIX/3M</Text>
              <Text style={{ color: COLOR_RATIO, fontSize: 14, fontWeight: 600 }} className="tabular-nums">
                {latest.ratio_vix_3m.toFixed(4)}
              </Text>
            </div>
          )}

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
            onClick={() => window.open('/compare?s=vix_term_structure', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 期間選択 */}
      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

      {/* === 生値チャート === */}
      {viewMode === 'raw' && (
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

            {/* 左Y軸: VIX系 */}
            <YAxis
              yAxisId="left"
              domain={['dataMin - 2', 'dataMax + 5']}
              tickFormatter={(v: number) => `${v.toFixed(0)}`}
              axisLine={{ stroke: DARK_THEME.axisLine }}
              tickLine={{ stroke: DARK_THEME.axisLine }}
              tick={{ fill: COLOR_VIX, fontSize: 11 }}
              tickMargin={8}
              label={{ value: 'VIX', angle: -90, position: 'insideLeft', offset: -8, fill: COLOR_VIX, fontSize: 11 }}
            />

            {/* 右Y軸: S&P 500 */}
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

            <RechartsTooltip content={<RawTooltip hiddenSeries={rawHidden.hiddenSeries} />} />

            <Legend
              wrapperStyle={{ paddingTop: 8 }}
              onClick={(e) => rawHidden.handleLegendClick(e.dataKey as string)}
              formatter={(value: string, entry) => (
                <span style={{ color: rawHidden.hiddenSeries.has(entry.dataKey as RawSeriesKey) ? '#64748b' : DARK_THEME.textPrimary, fontSize: 11 }}>
                  {value}
                </span>
              )}
            />

            <Line type="monotone" dataKey="vix9d" stroke={COLOR_VIX9D} strokeWidth={1.5} dot={false} name="VIX9D" yAxisId="left" connectNulls isAnimationActive={false} hide={rawHidden.isHidden('vix9d')} />
            <Line type="monotone" dataKey="vix" stroke={COLOR_VIX} strokeWidth={2} dot={false} name="VIX" yAxisId="left" connectNulls isAnimationActive={false} hide={rawHidden.isHidden('vix')} />
            <Line type="monotone" dataKey="vix3m" stroke={COLOR_VIX3M} strokeWidth={1.5} dot={false} name="VIX3M" yAxisId="left" connectNulls isAnimationActive={false} hide={rawHidden.isHidden('vix3m')} />
            <Line type="monotone" dataKey="sp500" stroke={COLOR_SP500} strokeWidth={1.5} strokeDasharray="4 2" dot={false} name="S&P 500" yAxisId="right" connectNulls isAnimationActive={false} hide={rawHidden.isHidden('sp500')} />
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* === レシオチャート (VIX9D/VIX or VIX/VIX3M) === */}
      {(viewMode === 'ratio_9d_vix' || viewMode === 'ratio_vix_3m') && (
        <ResponsiveContainer width="100%" height={450}>
          <ComposedChart
            data={ratioData}
            margin={{ top: 16, right: 8, bottom: 0, left: 0 }}
            style={{ backgroundColor: DARK_THEME.chartBg }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />

            {/* 1.0 基準線 */}
            <ReferenceLine yAxisId="left" y={1} stroke="#94a3b8" strokeDasharray="6 3" strokeWidth={1} />

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

            {/* 左Y軸: レシオ */}
            <YAxis
              yAxisId="left"
              domain={['dataMin - 0.05', 'dataMax + 0.05']}
              tickFormatter={(v: number) => v.toFixed(2)}
              axisLine={{ stroke: DARK_THEME.axisLine }}
              tickLine={{ stroke: DARK_THEME.axisLine }}
              tick={{ fill: COLOR_RATIO, fontSize: 11 }}
              tickMargin={8}
              label={{ value: ratioLabel, angle: -90, position: 'insideLeft', offset: -8, fill: COLOR_RATIO, fontSize: 11 }}
            />

            {/* 右Y軸: S&P 500 */}
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

            <RechartsTooltip content={<RatioTooltip hiddenSeries={ratioHidden.hiddenSeries} ratioLabel={ratioLabel} />} />

            <Legend
              wrapperStyle={{ paddingTop: 8 }}
              onClick={(e) => ratioHidden.handleLegendClick(e.dataKey as string)}
              formatter={(value: string, entry) => (
                <span style={{ color: ratioHidden.hiddenSeries.has(entry.dataKey as RatioSeriesKey) ? '#64748b' : DARK_THEME.textPrimary, fontSize: 11 }}>
                  {value}
                </span>
              )}
            />

            <Line type="monotone" dataKey="ratio" stroke={COLOR_RATIO} strokeWidth={2} dot={false} name={ratioLabel} yAxisId="left" connectNulls isAnimationActive={false} hide={ratioHidden.isHidden('ratio')} />
            <Line type="monotone" dataKey="sp500" stroke={COLOR_SP500} strokeWidth={1.5} strokeDasharray="4 2" dot={false} name="S&P 500" yAxisId="right" connectNulls isAnimationActive={false} hide={ratioHidden.isHidden('sp500')} />
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* レシオ解説 */}
      {(viewMode === 'ratio_9d_vix' || viewMode === 'ratio_vix_3m') && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 16, marginTop: 8, flexWrap: 'wrap' }}>
          <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>
            {'< 1.0 = コンタンゴ（通常） | > 1.0 = バックワーデーション（警戒）'}
          </Text>
        </div>
      )}
    </ChartContainer>
  )
}
