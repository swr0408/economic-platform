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

const COLOR_HV20 = '#f59e0b'     // アンバー
const COLOR_HV30 = '#8b5cf6'     // パープル
const COLOR_VIX = '#ef4444'      // 赤
const COLOR_SP500 = '#3b82f6'    // 青
const COLOR_DIFF20 = '#f59e0b'   // アンバー (VIX-HV20)
const COLOR_DIFF30 = '#8b5cf6'   // パープル (VIX-HV30)
const COLOR_RATIO20 = '#f59e0b'  // アンバー (VIX/HV20)
const COLOR_RATIO30 = '#8b5cf6'  // パープル (VIX/HV30)

interface HVItem {
  date: string
  hv20: number
  hv30: number
  sp500?: number | null
  vix?: number | null
  vix_minus_hv20?: number | null
  vix_minus_hv30?: number | null
  vix_div_hv20?: number | null
  vix_div_hv30?: number | null
}

interface HVResponse {
  data: HVItem[]
  latest: HVItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

function useHistoricalVolatilityData() {
  return useQuery({
    queryKey: ['market', 'historical-volatility'],
    queryFn: async () => {
      const { data } = await axios.get<HVResponse>('/api/market/historical-volatility')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

type ViewMode = 'hv' | 'premium' | 'ratio'

const VIEW_MODE_OPTIONS = [
  { mode: 'premium' as ViewMode, label: 'VIX − HV' },
  { mode: 'ratio' as ViewMode, label: 'VIX / HV' },
  { mode: 'hv' as ViewMode, label: 'HV20 / HV30' },
]

type HvSeriesKey = 'hv20' | 'hv30' | 'vix' | 'sp500'
type PremiumSeriesKey = 'vix_minus_hv20' | 'vix_minus_hv30' | 'sp500'
type RatioSeriesKey = 'vix_div_hv20' | 'vix_div_hv30' | 'sp500'

// --- HV mode tooltip ---
function HvTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))

  const series = [
    { key: 'hv20', label: 'HV20', color: COLOR_HV20, fmt: (v: number) => `${v.toFixed(1)}%` },
    { key: 'hv30', label: 'HV30', color: COLOR_HV30, fmt: (v: number) => `${v.toFixed(1)}%` },
    { key: 'vix', label: 'VIX', color: COLOR_VIX, fmt: (v: number) => v.toFixed(2) },
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

// --- Premium mode tooltip (VIX - HV) ---
function PremiumTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))

  const series = [
    { key: 'vix_minus_hv20', label: 'VIX − HV20', color: COLOR_DIFF20, fmt: (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}pt` },
    { key: 'vix_minus_hv30', label: 'VIX − HV30', color: COLOR_DIFF30, fmt: (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}pt` },
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

// --- Ratio mode tooltip (VIX / HV) ---
function RatioTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))

  const series = [
    { key: 'vix_div_hv20', label: 'VIX / HV20', color: COLOR_RATIO20, fmt: (v: number) => v.toFixed(2) },
    { key: 'vix_div_hv30', label: 'VIX / HV30', color: COLOR_RATIO30, fmt: (v: number) => v.toFixed(2) },
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

export default function HistoricalVolatilityChart() {
  const { data: apiData, isLoading, error } = useHistoricalVolatilityData()
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(2)
  const [viewMode, setViewMode] = useState<ViewMode>('premium')
  const hvHidden = useHiddenSeries<HvSeriesKey>()
  const premiumHidden = useHiddenSeries<PremiumSeriesKey>()
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

  if (isLoading) {
    return (
      <ChartContainer title="ヒストリカルボラティリティ" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (error || !apiData || chartData.length === 0) {
    return (
      <ChartContainer title="ヒストリカルボラティリティ" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  const latest = apiData.latest

  return (
    <ChartContainer
      title="インプライドボラプレミアム"
      dataSource="cboe"
      sourceUrl="https://www.cboe.com/"
      showPeriodSelector={false}
      handbookId="implied-vol-premium"
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
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>HV20</Text>
            <Text style={{ color: COLOR_HV20, fontSize: 16, fontWeight: 700 }} className="tabular-nums">
              {latest.hv20.toFixed(1)}%
            </Text>
          </div>

          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>HV30</Text>
            <Text style={{ color: COLOR_HV30, fontSize: 16, fontWeight: 700 }} className="tabular-nums">
              {latest.hv30.toFixed(1)}%
            </Text>
          </div>

          {latest.vix != null && (
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>VIX</Text>
              <Text style={{ color: COLOR_VIX, fontSize: 16, fontWeight: 700 }} className="tabular-nums">
                {latest.vix.toFixed(2)}
              </Text>
            </div>
          )}

          {latest.vix_minus_hv20 != null && (
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>VIX−HV20</Text>
              <Text style={{ color: latest.vix_minus_hv20 >= 0 ? '#10b981' : '#ef4444', fontSize: 14, fontWeight: 600 }} className="tabular-nums">
                {latest.vix_minus_hv20 >= 0 ? '+' : ''}{latest.vix_minus_hv20.toFixed(1)}
              </Text>
            </div>
          )}

          {latest.vix_div_hv20 != null && (
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>VIX/HV20</Text>
              <Text style={{ color: DARK_THEME.textPrimary, fontSize: 14, fontWeight: 600 }} className="tabular-nums">
                {latest.vix_div_hv20.toFixed(2)}
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
            onClick={() => window.open('/compare?s=historical_volatility_hv20&s=historical_volatility_hv30', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 期間選択 */}
      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

      {/* === HV チャート === */}
      {viewMode === 'hv' && (
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

            {/* 左Y軸: ボラティリティ(%) */}
            <YAxis
              yAxisId="left"
              domain={['dataMin - 2', 'dataMax + 5']}
              tickFormatter={(v: number) => `${v.toFixed(0)}%`}
              axisLine={{ stroke: DARK_THEME.axisLine }}
              tickLine={{ stroke: DARK_THEME.axisLine }}
              tick={{ fill: COLOR_HV20, fontSize: 11 }}
              tickMargin={8}
              label={{ value: 'Vol (%)', angle: -90, position: 'insideLeft', offset: -8, fill: COLOR_HV20, fontSize: 11 }}
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

            <RechartsTooltip content={<HvTooltip hiddenSeries={hvHidden.hiddenSeries} />} />

            <Legend
              wrapperStyle={{ paddingTop: 8 }}
              onClick={(e) => hvHidden.handleLegendClick(e.dataKey as string)}
              formatter={(value: string, entry) => (
                <span style={{ color: hvHidden.hiddenSeries.has(entry.dataKey as HvSeriesKey) ? '#64748b' : DARK_THEME.textPrimary, fontSize: 11 }}>
                  {value}
                </span>
              )}
            />

            <Line type="monotone" dataKey="hv20" stroke={COLOR_HV20} strokeWidth={2} dot={false} name="HV20" yAxisId="left" connectNulls isAnimationActive={false} hide={hvHidden.isHidden('hv20')} />
            <Line type="monotone" dataKey="hv30" stroke={COLOR_HV30} strokeWidth={2} dot={false} name="HV30" yAxisId="left" connectNulls isAnimationActive={false} hide={hvHidden.isHidden('hv30')} />
            <Line type="monotone" dataKey="vix" stroke={COLOR_VIX} strokeWidth={1.5} strokeDasharray="4 2" dot={false} name="VIX" yAxisId="left" connectNulls isAnimationActive={false} hide={hvHidden.isHidden('vix')} />
            <Line type="monotone" dataKey="sp500" stroke={COLOR_SP500} strokeWidth={1.5} strokeDasharray="4 2" dot={false} name="S&P 500" yAxisId="right" connectNulls isAnimationActive={false} hide={hvHidden.isHidden('sp500')} />
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* === VIX - HV (ボラティリティ・リスクプレミアム) === */}
      {viewMode === 'premium' && (
        <>
          <ResponsiveContainer width="100%" height={450}>
            <ComposedChart
              data={filteredData}
              margin={{ top: 16, right: 8, bottom: 0, left: 0 }}
              style={{ backgroundColor: DARK_THEME.chartBg }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />

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

              {/* 左Y軸: VIX - HV (pt) */}
              <YAxis
                yAxisId="left"
                domain={['dataMin - 2', 'dataMax + 2']}
                tickFormatter={(v: number) => `${v.toFixed(0)}pt`}
                axisLine={{ stroke: DARK_THEME.axisLine }}
                tickLine={{ stroke: DARK_THEME.axisLine }}
                tick={{ fill: COLOR_DIFF20, fontSize: 11 }}
                tickMargin={8}
                label={{ value: 'VIX − HV (pt)', angle: -90, position: 'insideLeft', offset: -8, fill: COLOR_DIFF20, fontSize: 11 }}
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

              <RechartsTooltip content={<PremiumTooltip hiddenSeries={premiumHidden.hiddenSeries} />} />

              <Legend
                wrapperStyle={{ paddingTop: 8 }}
                onClick={(e) => premiumHidden.handleLegendClick(e.dataKey as string)}
                formatter={(value: string, entry) => (
                  <span style={{ color: premiumHidden.hiddenSeries.has(entry.dataKey as PremiumSeriesKey) ? '#64748b' : DARK_THEME.textPrimary, fontSize: 11 }}>
                    {value}
                  </span>
                )}
              />

              <Line type="monotone" dataKey="vix_minus_hv20" stroke={COLOR_DIFF20} strokeWidth={2} dot={false} name="VIX − HV20" yAxisId="left" connectNulls isAnimationActive={false} hide={premiumHidden.isHidden('vix_minus_hv20')} />
              <Line type="monotone" dataKey="vix_minus_hv30" stroke={COLOR_DIFF30} strokeWidth={2} dot={false} name="VIX − HV30" yAxisId="left" connectNulls isAnimationActive={false} hide={premiumHidden.isHidden('vix_minus_hv30')} />
              <Line type="monotone" dataKey="sp500" stroke={COLOR_SP500} strokeWidth={1.5} strokeDasharray="4 2" dot={false} name="S&P 500" yAxisId="right" connectNulls isAnimationActive={false} hide={premiumHidden.isHidden('sp500')} />
            </ComposedChart>
          </ResponsiveContainer>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 16, marginTop: 8, flexWrap: 'wrap' }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>
              {'> 0 = VIXがHVより高い（通常、リスクプレミアム有り） | < 0 = VIXがHVより低い（警戒サイン）'}
            </Text>
          </div>
        </>
      )}

      {/* === VIX / HV (ボラティリティ・レシオ) === */}
      {viewMode === 'ratio' && (
        <>
          <ResponsiveContainer width="100%" height={450}>
            <ComposedChart
              data={filteredData}
              margin={{ top: 16, right: 8, bottom: 0, left: 0 }}
              style={{ backgroundColor: DARK_THEME.chartBg }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />

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

              {/* 左Y軸: VIX / HV (レシオ) */}
              <YAxis
                yAxisId="left"
                domain={['dataMin - 0.1', 'dataMax + 0.1']}
                tickFormatter={(v: number) => v.toFixed(1)}
                axisLine={{ stroke: DARK_THEME.axisLine }}
                tickLine={{ stroke: DARK_THEME.axisLine }}
                tick={{ fill: COLOR_RATIO20, fontSize: 11 }}
                tickMargin={8}
                label={{ value: 'VIX / HV', angle: -90, position: 'insideLeft', offset: -8, fill: COLOR_RATIO20, fontSize: 11 }}
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

              <RechartsTooltip content={<RatioTooltip hiddenSeries={ratioHidden.hiddenSeries} />} />

              <Legend
                wrapperStyle={{ paddingTop: 8 }}
                onClick={(e) => ratioHidden.handleLegendClick(e.dataKey as string)}
                formatter={(value: string, entry) => (
                  <span style={{ color: ratioHidden.hiddenSeries.has(entry.dataKey as RatioSeriesKey) ? '#64748b' : DARK_THEME.textPrimary, fontSize: 11 }}>
                    {value}
                  </span>
                )}
              />

              <Line type="monotone" dataKey="vix_div_hv20" stroke={COLOR_RATIO20} strokeWidth={2} dot={false} name="VIX / HV20" yAxisId="left" connectNulls isAnimationActive={false} hide={ratioHidden.isHidden('vix_div_hv20')} />
              <Line type="monotone" dataKey="vix_div_hv30" stroke={COLOR_RATIO30} strokeWidth={2} dot={false} name="VIX / HV30" yAxisId="left" connectNulls isAnimationActive={false} hide={ratioHidden.isHidden('vix_div_hv30')} />
              <Line type="monotone" dataKey="sp500" stroke={COLOR_SP500} strokeWidth={1.5} strokeDasharray="4 2" dot={false} name="S&P 500" yAxisId="right" connectNulls isAnimationActive={false} hide={ratioHidden.isHidden('sp500')} />
            </ComposedChart>
          </ResponsiveContainer>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 16, marginTop: 8, flexWrap: 'wrap' }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>
              {'> 1.0 = VIX > HV（IVプレミアム） | < 1.0 = VIX < HV（IVディスカウント、警戒）'}
            </Text>
          </div>
        </>
      )}
    </ChartContainer>
  )
}
