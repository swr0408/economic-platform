import { useState, useMemo } from 'react'
import { Tooltip, Button, Switch } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import {
  ComposedChart,
  Line,
  Bar,
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

// Category colors
const COLORS = {
  us_production: '#22c55e',
  us_consumption: '#ef4444',
  us_storage: '#3b82f6',
  lng_exports: '#f59e0b',
  hdd: '#f97316',
  cdd: '#06b6d4',
  henry_hub_price: '#a855f7',
}

interface STEONGItem {
  date: string
  us_production: number | null
  us_consumption: number | null
  us_storage: number | null
  lng_exports: number | null
  hdd: number | null
  cdd: number | null
  henry_hub_price: number | null
}

interface PreviousForecast {
  data: STEONGItem[]
  forecast_month: string
  saved_at: string
}

interface STEONGResponse {
  data: STEONGItem[]
  latest: STEONGItem | null
  next_release: { date: string; label?: string } | null
  previous_forecast: PreviousForecast | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

// Merged item includes prev_ fields
interface MergedItem extends STEONGItem {
  prev_us_production: number | null
  prev_us_consumption: number | null
  prev_us_storage: number | null
  prev_lng_exports: number | null
  prev_hdd: number | null
  prev_cdd: number | null
  prev_henry_hub_price: number | null
}

type ViewMode = 'supply_demand' | 'storage' | 'lng_exports' | 'degree_days' | 'price'
const VIEW_MODE_OPTIONS = [
  { mode: 'supply_demand' as ViewMode, label: '需給' },
  { mode: 'storage' as ViewMode, label: '貯蔵' },
  { mode: 'lng_exports' as ViewMode, label: 'LNG輸出' },
  { mode: 'degree_days' as ViewMode, label: 'HDD/CDD' },
  { mode: 'price' as ViewMode, label: '価格' },
]

type SeriesKey = 'us_production' | 'us_consumption' | 'us_storage' | 'lng_exports' |
  'hdd' | 'cdd' | 'henry_hub_price' |
  'prev_us_production' | 'prev_us_consumption' | 'prev_us_storage' | 'prev_lng_exports' |
  'prev_hdd' | 'prev_cdd' | 'prev_henry_hub_price'

// Tooltip config per viewMode
interface TooltipItem {
  key: string
  prevKey: string
  label: string
  color: string
  format: (v: number) => string
}

const fmtBcfd = (v: number) => `${v.toFixed(2)} bcf/d`
const fmtBcf = (v: number) => `${v.toLocaleString(undefined, { maximumFractionDigits: 0 })} bcf`
const fmtDd = (v: number) => `${v.toFixed(1)}`
const fmtUsd = (v: number) => `$${v.toFixed(2)}`

function getTooltipItems(viewMode: ViewMode): TooltipItem[] {
  if (viewMode === 'supply_demand') return [
    { key: 'us_production', prevKey: 'prev_us_production', label: '生産量', color: COLORS.us_production, format: fmtBcfd },
    { key: 'us_consumption', prevKey: 'prev_us_consumption', label: '消費量', color: COLORS.us_consumption, format: fmtBcfd },
  ]
  if (viewMode === 'storage') return [
    { key: 'us_storage', prevKey: 'prev_us_storage', label: '貯蔵量', color: COLORS.us_storage, format: fmtBcf },
  ]
  if (viewMode === 'lng_exports') return [
    { key: 'lng_exports', prevKey: 'prev_lng_exports', label: 'LNG輸出', color: COLORS.lng_exports, format: fmtBcfd },
  ]
  if (viewMode === 'degree_days') return [
    { key: 'hdd', prevKey: 'prev_hdd', label: 'HDD (暖房)', color: COLORS.hdd, format: fmtDd },
    { key: 'cdd', prevKey: 'prev_cdd', label: 'CDD (冷房)', color: COLORS.cdd, format: fmtDd },
  ]
  if (viewMode === 'price') return [
    { key: 'henry_hub_price', prevKey: 'prev_henry_hub_price', label: 'Henry Hub', color: COLORS.henry_hub_price, format: fmtUsd },
  ]
  return []
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ChartTooltip({ active, payload, label, hiddenSeries, viewMode, showPrev, prevLabel }: {
  active?: boolean
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
  viewMode: ViewMode
  showPrev: boolean
  prevLabel: string
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))
  const dp = payload[0]?.payload as MergedItem | undefined
  if (!dp) return null

  const items = getTooltipItems(viewMode)

  return (
    <div style={{
      backgroundColor: DARK_THEME.tooltipBg,
      border: `1px solid ${DARK_THEME.tooltipBorder}`,
      borderRadius: 8,
      padding: '12px 16px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
    }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>{formattedLabel}</div>
      {items.map(item => {
        const val = (dp as any)[item.key] as number | null
        const prevVal = (dp as any)[item.prevKey] as number | null
        if (hiddenSeries.has(item.key) || val == null) return null

        const diff = (showPrev && prevVal != null && val != null) ? val - prevVal : null

        return (
          <div key={item.key} style={{ marginBottom: 4 }}>
            <div style={{ color: item.color, fontSize: 13 }}>
              {item.label}: {item.format(val)}
              {diff != null && (
                <span style={{ color: diff >= 0 ? '#4ade80' : '#f87171', fontSize: 11, marginLeft: 6 }}>
                  ({diff >= 0 ? '+' : ''}{item.key === 'us_storage' ? diff.toFixed(0) : item.key === 'henry_hub_price' ? diff.toFixed(2) : diff.toFixed(2)})
                </span>
              )}
            </div>
            {showPrev && prevVal != null && !hiddenSeries.has(item.prevKey as SeriesKey) && (
              <div style={{ color: item.color, fontSize: 11, marginLeft: 8 }}>
                {prevLabel}: {item.format(prevVal)}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}


export default function SteoNaturalGasChart() {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)
  const [viewMode, setViewMode] = useState<ViewMode>('supply_demand')
  const [showPrev, setShowPrev] = useState(true)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<SeriesKey>()

  const { data: response } = useQuery<STEONGResponse>({
    queryKey: ['steo-natural-gas'],
    queryFn: async () => {
      const res = await axios.get('/api/market/steo-natural-gas')
      return res.data
    },
    staleTime: 1000 * 60 * 30,
  })

  const hasPrev = !!response?.previous_forecast?.data?.length
  const prevLabel = response?.previous_forecast?.forecast_month
    ? `前回(${response.previous_forecast.forecast_month})`
    : '前回'

  // Merge current + previous forecast data by date
  const mergedData = useMemo(() => {
    if (!response?.data) return [] as MergedItem[]

    const prevMap = new Map<string, STEONGItem>()
    if (response.previous_forecast?.data) {
      for (const item of response.previous_forecast.data) {
        prevMap.set(item.date, item)
      }
    }

    const FIELDS = [
      'us_production', 'us_consumption', 'us_storage', 'lng_exports',
      'hdd', 'cdd', 'henry_hub_price',
    ] as const

    return response.data.map(item => {
      const merged: any = { ...item }
      const prev = prevMap.get(item.date)
      for (const f of FIELDS) {
        merged[`prev_${f}`] = prev?.[f] ?? null
      }
      return merged as MergedItem
    })
  }, [response])

  const filteredData = useMemo(() => {
    if (!mergedData.length) return []
    if (currentPeriod === 'all') return mergedData
    const years = typeof currentPeriod === 'number' ? currentPeriod : 10
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return mergedData.filter(d => d.date >= cutoffStr)
  }, [mergedData, currentPeriod])

  const latest = response?.latest
  const nextRelease = response?.next_release

  // Current month boundary
  const currentDateStr = useMemo(() => {
    const now = new Date()
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`
  }, [])

  // Helper: render prev lines for a given set of fields
  const renderPrevLines = (fields: { dataKey: string; prevKey: string; color: string; name: string; yAxisId?: string }[]) => {
    if (!showPrev || !hasPrev) return null
    return fields.map(f => (
      <Line
        key={f.prevKey}
        yAxisId={f.yAxisId}
        type="monotone"
        dataKey={f.prevKey}
        name={`${f.name} (前回)`}
        stroke={f.color}
        strokeWidth={1}
        strokeDasharray="6 4"
        strokeOpacity={0.4}
        dot={false}
        hide={hiddenSeries.has(f.prevKey as SeriesKey)}
        connectNulls
        isAnimationActive={false}
      />
    ))
  }

  return (
    <ChartContainer
      title="短期エネルギー見通し（天然ガス）"
      dataSource="EIA STEO"
      sourceUrl="https://www.eia.gov/outlooks/steo/"
      showPeriodSelector={false}
    >
      {/* Latest value box */}
      <div style={LATEST_VALUE_BOX_STYLE}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          {latest?.date && (
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
              最新予測: ~{latest.date.slice(0, 7)}
            </span>
          )}
          {latest?.henry_hub_price != null && (
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>Henry Hub: </span>
              <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.henry_hub_price }}>
                ${latest.henry_hub_price.toFixed(2)}/MMBtu
              </span>
            </div>
          )}
          {latest?.us_production != null && (
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>生産: </span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.us_production }}>
                {latest.us_production.toFixed(1)} bcf/d
              </span>
            </div>
          )}
          {latest?.lng_exports != null && (
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>LNG輸出: </span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.lng_exports }}>
                {latest.lng_exports.toFixed(1)} bcf/d
              </span>
            </div>
          )}
        </div>
        {nextRelease && (
          <span style={{ fontSize: 11, color: TEXT_COLORS.secondary, whiteSpace: 'nowrap' }}>
            次回: {nextRelease.date}
          </span>
        )}
      </div>

      {/* ViewMode + Previous toggle + Compare button */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <ViewModeButtonGroup
          options={VIEW_MODE_OPTIONS}
          currentMode={viewMode}
          onChange={(m) => setViewMode(m as ViewMode)}
        />
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {hasPrev && (
            <Tooltip title={`前回見通し（${response?.previous_forecast?.forecast_month ?? ''}）との比較を表示`}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <Switch size="small" checked={showPrev} onChange={setShowPrev} />
                <span style={{ fontSize: 11, color: TEXT_COLORS.secondary }}>前回比較</span>
              </div>
            </Tooltip>
          )}
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=steo_ng_us_production&s=steo_ng_us_consumption', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>
      </div>

      {/* Period selector */}
      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

      {/* Supply/Demand */}
      {viewMode === 'supply_demand' && (
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
            <XAxis dataKey="date" tickFormatter={(v) => formatDayLabel(v)} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} minTickGap={40} />
            <YAxis domain={['dataMin * 0.95', 'dataMax * 1.02']} tickFormatter={(v: number) => `${v.toFixed(0)}`} stroke={DARK_THEME.textSecondary} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} width={50}  />
            <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} viewMode={viewMode} showPrev={showPrev && hasPrev} prevLabel={prevLabel} />} />
            <ReferenceLine x={currentDateStr} stroke="#fbbf24" strokeDasharray="6 3" strokeWidth={1.5} label={{ value: '現在', position: 'top', fill: '#fbbf24', fontSize: 11 }} />
            <Legend onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={(value: string, entry: any) => (<span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>{value}</span>)} />
            <Line type="monotone" dataKey="us_production" name="生産量 (bcf/d)" stroke={COLORS.us_production} strokeWidth={2} dot={false} hide={hiddenSeries.has('us_production')} connectNulls isAnimationActive={false} />
            <Line type="monotone" dataKey="us_consumption" name="消費量 (bcf/d)" stroke={COLORS.us_consumption} strokeWidth={2} dot={false} hide={hiddenSeries.has('us_consumption')} connectNulls isAnimationActive={false} />
            {renderPrevLines([
              { dataKey: 'us_production', prevKey: 'prev_us_production', color: COLORS.us_production, name: '生産量' },
              { dataKey: 'us_consumption', prevKey: 'prev_us_consumption', color: COLORS.us_consumption, name: '消費量' },
            ])}
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* Storage */}
      {viewMode === 'storage' && (
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
            <XAxis dataKey="date" tickFormatter={(v) => formatDayLabel(v)} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} minTickGap={40} />
            <YAxis domain={['dataMin * 0.9', 'dataMax * 1.05']} tickFormatter={(v: number) => `${(v / 1000).toFixed(1)}T`} stroke={DARK_THEME.textSecondary} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} width={50}  />
            <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} viewMode={viewMode} showPrev={showPrev && hasPrev} prevLabel={prevLabel} />} />
            <ReferenceLine x={currentDateStr} stroke="#fbbf24" strokeDasharray="6 3" strokeWidth={1.5} label={{ value: '現在', position: 'top', fill: '#fbbf24', fontSize: 11 }} />
            <Legend onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={(value: string, entry: any) => (<span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>{value}</span>)} />
            <Line type="monotone" dataKey="us_storage" name="貯蔵量 (bcf)" stroke={COLORS.us_storage} strokeWidth={2} dot={false} hide={hiddenSeries.has('us_storage')} connectNulls isAnimationActive={false} />
            {renderPrevLines([
              { dataKey: 'us_storage', prevKey: 'prev_us_storage', color: COLORS.us_storage, name: '貯蔵量' },
            ])}
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* LNG Exports */}
      {viewMode === 'lng_exports' && (
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
            <XAxis dataKey="date" tickFormatter={(v) => formatDayLabel(v)} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} minTickGap={40} />
            <YAxis domain={['dataMin * 0.9', 'dataMax * 1.05']} tickFormatter={(v: number) => `${v.toFixed(0)}`} stroke={DARK_THEME.textSecondary} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} width={50} />
            <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} viewMode={viewMode} showPrev={showPrev && hasPrev} prevLabel={prevLabel} />} />
            <ReferenceLine x={currentDateStr} stroke="#fbbf24" strokeDasharray="6 3" strokeWidth={1.5} label={{ value: '現在', position: 'top', fill: '#fbbf24', fontSize: 11 }} />
            <Legend onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={(value: string, entry: any) => (<span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>{value}</span>)} />
            <Line type="monotone" dataKey="lng_exports" name="LNG輸出 (bcf/d)" stroke={COLORS.lng_exports} strokeWidth={2} dot={false} hide={hiddenSeries.has('lng_exports')} connectNulls isAnimationActive={false} />
            {renderPrevLines([
              { dataKey: 'lng_exports', prevKey: 'prev_lng_exports', color: COLORS.lng_exports, name: 'LNG輸出' },
            ])}
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* Degree Days (HDD/CDD) - bar chart */}
      {viewMode === 'degree_days' && (
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
            <XAxis dataKey="date" tickFormatter={(v) => formatDayLabel(v)} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} minTickGap={40} />
            <YAxis domain={[0, 'dataMax * 1.1']} tickFormatter={(v: number) => `${v.toFixed(0)}`} stroke={DARK_THEME.textSecondary} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} width={50}  />
            <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} viewMode={viewMode} showPrev={showPrev && hasPrev} prevLabel={prevLabel} />} />
            <ReferenceLine x={currentDateStr} stroke="#fbbf24" strokeDasharray="6 3" strokeWidth={1.5} label={{ value: '現在', position: 'top', fill: '#fbbf24', fontSize: 11 }} />
            <Legend onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={(value: string, entry: any) => (<span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>{value}</span>)} />
            <Bar dataKey="hdd" name="HDD (暖房稼働日)" fill={COLORS.hdd} fillOpacity={0.7} hide={hiddenSeries.has('hdd')} isAnimationActive={false} />
            <Bar dataKey="cdd" name="CDD (冷房稼働日)" fill={COLORS.cdd} fillOpacity={0.7} hide={hiddenSeries.has('cdd')} isAnimationActive={false} />
            {renderPrevLines([
              { dataKey: 'hdd', prevKey: 'prev_hdd', color: COLORS.hdd, name: 'HDD' },
              { dataKey: 'cdd', prevKey: 'prev_cdd', color: COLORS.cdd, name: 'CDD' },
            ])}
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* Henry Hub Price */}
      {viewMode === 'price' && (
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
            <XAxis dataKey="date" tickFormatter={(v) => formatDayLabel(v)} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} minTickGap={40} />
            <YAxis domain={['dataMin * 0.9', 'dataMax * 1.05']} tickFormatter={(v: number) => `$${v.toFixed(0)}`} stroke={DARK_THEME.textSecondary} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} width={55} />
            <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} viewMode={viewMode} showPrev={showPrev && hasPrev} prevLabel={prevLabel} />} />
            <ReferenceLine x={currentDateStr} stroke="#fbbf24" strokeDasharray="6 3" strokeWidth={1.5} label={{ value: '現在', position: 'top', fill: '#fbbf24', fontSize: 11 }} />
            <Legend onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={(value: string, entry: any) => (<span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>{value}</span>)} />
            <Line type="monotone" dataKey="henry_hub_price" name="Henry Hub ($/MMBtu)" stroke={COLORS.henry_hub_price} strokeWidth={2} dot={false} hide={hiddenSeries.has('henry_hub_price')} connectNulls isAnimationActive={false} />
            {renderPrevLines([
              { dataKey: 'henry_hub_price', prevKey: 'prev_henry_hub_price', color: COLORS.henry_hub_price, name: 'Henry Hub' },
            ])}
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </ChartContainer>
  )
}
