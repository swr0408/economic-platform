import { useState, useMemo } from 'react'
import { Tooltip, Button } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import {
  ComposedChart,
  Area,
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
import { formatMonthLabel } from '../../../utils/dateFormatters'
import { useHiddenSeries } from '../../country/usa/common/useChartData'
import { ViewModeButtonGroup } from '../../country/usa/common/ChartComponents'
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

// Region colors
const REGION_COLORS: Record<string, string> = {
  east_asia_se_asia: '#ef4444',     // Red
  europe: '#3b82f6',               // Blue
  south_central_america: '#22c55e', // Green
  middle_east_africa: '#f59e0b',    // Amber
  south_asia: '#a855f7',           // Purple
}

const REGION_LABELS: Record<string, string> = {
  east_asia_se_asia: 'East Asia & Southeast Asia',
  europe: 'Europe',
  south_central_america: 'South & Central America',
  middle_east_africa: 'Middle East & North Africa',
  south_asia: 'South Asia',
}

// Europe country colors
const EU_COUNTRY_COLORS: Record<string, string> = {
  netherlands: '#f97316',  // Orange
  france: '#3b82f6',       // Blue
  uk: '#6366f1',           // Indigo
  germany: '#eab308',      // Yellow
  spain: '#ef4444',        // Red
  turkey: '#14b8a6',       // Teal
}

const EU_COUNTRY_LABELS: Record<string, string> = {
  netherlands: 'オランダ',
  france: 'フランス',
  uk: '英国',
  germany: 'ドイツ',
  spain: 'スペイン',
  turkey: 'トルコ',
}

// Asia country colors
const ASIA_COUNTRY_COLORS: Record<string, string> = {
  japan: '#ec4899',        // Pink
  south_korea: '#8b5cf6',  // Violet
  india: '#f59e0b',        // Amber
  china: '#dc2626',        // Red-600
}

const ASIA_COUNTRY_LABELS: Record<string, string> = {
  japan: '日本',
  south_korea: '韓国',
  india: 'インド',
  china: '中国',
}

interface DataItem {
  date: string
  total: number | null
  east_asia_se_asia: number | null
  south_asia: number | null
  europe: number | null
  south_central_america: number | null
  middle_east_africa: number | null
  netherlands: number | null
  france: number | null
  uk: number | null
  germany: number | null
  spain: number | null
  turkey: number | null
  japan: number | null
  south_korea: number | null
  india: number | null
  china: number | null
}

interface ApiResponse {
  data: DataItem[]
  latest: DataItem | null
  next_release: { date: string; label?: string } | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

type ViewMode = 'region' | 'europe' | 'asia'
const VIEW_MODE_OPTIONS = [
  { mode: 'region' as ViewMode, label: 'エリア別' },
  { mode: 'europe' as ViewMode, label: '欧州（国別）' },
  { mode: 'asia' as ViewMode, label: 'アジア（国別）' },
]

const REGION_KEYS = ['east_asia_se_asia', 'europe', 'south_central_america', 'middle_east_africa', 'south_asia'] as const
const EU_COUNTRY_KEYS = ['netherlands', 'france', 'uk', 'germany', 'spain', 'turkey'] as const
const ASIA_COUNTRY_KEYS = ['japan', 'south_korea', 'india', 'china'] as const

type SeriesKey = (typeof REGION_KEYS)[number] | (typeof EU_COUNTRY_KEYS)[number] | (typeof ASIA_COUNTRY_KEYS)[number] | 'total'

const fmtBcf = (v: number) => `${v.toLocaleString(undefined, { maximumFractionDigits: 1 })} BCF`

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function RegionTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatMonthLabel(String(label))
  const dp = payload[0]?.payload as DataItem | undefined
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
      {REGION_KEYS.map(key => {
        if (hiddenSeries.has(key)) return null
        const val = dp[key]
        if (val == null) return null
        return (
          <div key={key} style={{ display: 'flex', justifyContent: 'space-between', gap: 24, marginBottom: 2, fontSize: 12 }}>
            <span style={{ display: 'flex', alignItems: 'center' }}>
              <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 2, backgroundColor: REGION_COLORS[key], marginRight: 6 }} />
              <span style={{ color: DARK_THEME.textPrimary }}>{REGION_LABELS[key]}</span>
            </span>
            <span style={{ color: REGION_COLORS[key], fontWeight: 500 }}>{fmtBcf(val)}</span>
          </div>
        )
      })}
      {!hiddenSeries.has('total') && dp.total != null && (
        <div style={{ borderTop: '1px solid #475569', marginTop: 4, paddingTop: 4, display: 'flex', justifyContent: 'space-between', gap: 24, fontSize: 13 }}>
          <span style={{ color: DARK_THEME.textPrimary, fontWeight: 600 }}>Total</span>
          <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{fmtBcf(dp.total)}</span>
        </div>
      )}
    </div>
  )
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CountryTooltip({ active, payload, label, hiddenSeries, keys, colors, labels }: {
  active?: boolean
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
  keys: readonly string[]
  colors: Record<string, string>
  labels: Record<string, string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatMonthLabel(String(label))
  const dp = payload[0]?.payload as DataItem | undefined
  if (!dp) return null

  const entries = keys
    .filter(key => !hiddenSeries.has(key) && dp[key as keyof DataItem] != null)
    .map(key => ({ key, val: dp[key as keyof DataItem] as number }))
    .sort((a, b) => b.val - a.val)

  return (
    <div style={{
      backgroundColor: DARK_THEME.tooltipBg,
      border: `1px solid ${DARK_THEME.tooltipBorder}`,
      borderRadius: 8,
      padding: '12px 16px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
    }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>{formattedLabel}</div>
      {entries.map(({ key, val }) => (
        <div key={key} style={{ display: 'flex', justifyContent: 'space-between', gap: 24, marginBottom: 2, fontSize: 12 }}>
          <span style={{ display: 'flex', alignItems: 'center' }}>
            <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 2, backgroundColor: colors[key], marginRight: 6 }} />
            <span style={{ color: DARK_THEME.textPrimary }}>{labels[key]}</span>
          </span>
          <span style={{ color: colors[key], fontWeight: 500 }}>{fmtBcf(val)}</span>
        </div>
      ))}
    </div>
  )
}


export default function LngExportsByRegionChart() {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)
  const [viewMode, setViewMode] = useState<ViewMode>('region')
  const { hiddenSeries, handleLegendClick, isHidden } = useHiddenSeries<SeriesKey>()

  const { data: response } = useQuery<ApiResponse>({
    queryKey: ['lng-exports-by-region'],
    queryFn: async () => {
      const res = await axios.get('/api/market/lng-exports-by-region')
      return res.data
    },
    staleTime: 1000 * 60 * 30,
  })

  const filteredData = useMemo(() => {
    if (!response?.data) return []
    if (currentPeriod === 'all') return response.data
    const years = typeof currentPeriod === 'number' ? currentPeriod : 10
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return response.data.filter(d => d.date >= cutoffStr)
  }, [response, currentPeriod])

  const latest = response?.latest
  const nextRelease = response?.next_release

  const latestRegions = useMemo(() => {
    if (!latest) return []
    return REGION_KEYS
      .map(key => ({ key, label: REGION_LABELS[key], value: latest[key] as number | null, color: REGION_COLORS[key] }))
      .filter(r => r.value != null && r.value > 0)
      .sort((a, b) => (b.value ?? 0) - (a.value ?? 0))
  }, [latest])

  // Shared chart rendering helper
  const renderLineChart = (
    keys: readonly string[],
    colors: Record<string, string>,
    labels: Record<string, string>,
  ) => (
    <ResponsiveContainer width="100%" height={450}>
      <ComposedChart data={filteredData} margin={CHART_MARGIN}>
        <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
        <XAxis
          dataKey="date"
          tickFormatter={formatMonthLabel}
          stroke={DARK_THEME.axisLine}
          tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
          minTickGap={40}
        />
        <YAxis
          yAxisId="left"
          domain={['dataMin', 'dataMax + 5']}
          tickFormatter={(v: number) => `${v.toFixed(0)}`}
          stroke={DARK_THEME.textSecondary}
          tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
          width={55}
          // label={{ value: 'BCF', position: 'top', offset: 8, style: { fill: DARK_THEME.textSecondary, fontSize: 10 } }}
        />

        <RechartsTooltip content={<CountryTooltip hiddenSeries={hiddenSeries} keys={keys} colors={colors} labels={labels} />} />

        <Legend
          wrapperStyle={{ paddingTop: 8 }}
          onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)}
          formatter={(value: string, entry: any) => (
            <span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : DARK_THEME.textPrimary, fontSize: 12 }}>
              {value}
            </span>
          )}
        />

        {keys.map(key => (
          <Line
            key={key}
            type="monotone"
            dataKey={key}
            name={labels[key]}
            stroke={colors[key]}
            strokeWidth={2}
            dot={false}
            yAxisId="left"
            hide={isHidden(key as SeriesKey)}
            connectNulls
            isAnimationActive={false}
          />
        ))}
      </ComposedChart>
    </ResponsiveContainer>
  )

  return (
    <ChartContainer
      title="米国LNG輸出"
      dataSource="EIA"
      sourceUrl="https://www.eia.gov/totalenergy/data/monthly/"
      showPeriodSelector={false}
    >
      {/* Latest value box */}
      <div style={LATEST_VALUE_BOX_STYLE}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          {latest?.date && (
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
              {latest.date.slice(0, 7).replace('-', '/')}
            </span>
          )}
          <div>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>Total: </span>
            <span style={{ fontSize: 18, fontWeight: 'bold', color: '#f1f5f9' }}>
              {latest?.total != null ? `${latest.total.toLocaleString(undefined, { maximumFractionDigits: 1 })} BCF` : '—'}
            </span>
          </div>
          {latestRegions.slice(0, 3).map(r => (
            <div key={r.key}>
              <span style={{ fontSize: 11, color: TEXT_COLORS.secondary }}>{r.label}: </span>
              <span style={{ fontSize: 13, fontWeight: 'bold', color: r.color }}>
                {r.value != null ? `${r.value.toLocaleString(undefined, { maximumFractionDigits: 1 })}` : '—'}
              </span>
            </div>
          ))}
        </div>
        {nextRelease && (
          <span style={{ fontSize: 11, color: TEXT_COLORS.secondary, whiteSpace: 'nowrap' }}>
            次回: {nextRelease.date}
          </span>
        )}
      </div>

      {/* ViewMode + データ比較ボタン */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, marginTop: 8 }}>
        <ViewModeButtonGroup
          options={VIEW_MODE_OPTIONS}
          currentMode={viewMode}
          onChange={(m) => setViewMode(m as ViewMode)}
        />
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            onClick={() => window.open('/compare?s=lng_exports_total', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

      {/* エリア別ビュー: stacked area */}
      {viewMode === 'region' && (
        <ResponsiveContainer width="100%" height={450}>
          <ComposedChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
            <XAxis
              dataKey="date"
              tickFormatter={formatMonthLabel}
              stroke={DARK_THEME.axisLine}
              tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
              minTickGap={40}
            />
            <YAxis
              yAxisId="left"
              domain={['dataMin', 'dataMax']}
              tickFormatter={(v: number) => `${v.toFixed(0)}`}
              stroke={DARK_THEME.textSecondary}
              tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
              width={55}
              // label={{ value: 'BCF', position: 'top', offset: 8, style: { fill: DARK_THEME.textSecondary, fontSize: 10 } }}
            />

            <RechartsTooltip content={<RegionTooltip hiddenSeries={hiddenSeries} />} />

            <Legend
              wrapperStyle={{ paddingTop: 8 }}
              onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)}
              formatter={(value: string, entry: any) => (
                <span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : DARK_THEME.textPrimary, fontSize: 12 }}>
                  {value}
                </span>
              )}
            />

            {REGION_KEYS.map(key => (
              <Area
                key={key}
                type="monotone"
                dataKey={key}
                name={REGION_LABELS[key]}
                fill={REGION_COLORS[key]}
                fillOpacity={0.6}
                stroke={REGION_COLORS[key]}
                strokeWidth={1.5}
                yAxisId="left"
                stackId="region"
                hide={isHidden(key)}
                connectNulls
                isAnimationActive={false}
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* 欧州（国別）ビュー */}
      {viewMode === 'europe' && renderLineChart(EU_COUNTRY_KEYS, EU_COUNTRY_COLORS, EU_COUNTRY_LABELS)}

      {/* アジア（国別）ビュー */}
      {viewMode === 'asia' && renderLineChart(ASIA_COUNTRY_KEYS, ASIA_COUNTRY_COLORS, ASIA_COUNTRY_LABELS)}
    </ChartContainer>
  )
}
