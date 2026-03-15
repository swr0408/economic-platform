import { useState, useMemo } from 'react'
import { Tooltip, Button, Switch } from 'antd'
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
  Area,
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
  opec_production: '#f59e0b',
  opec_plus_production: '#f97316',
  world_production: '#3b82f6',
  world_consumption: '#a855f7',
  world_balance: '#06b6d4',
  china_consumption: '#ec4899',
  wti_price: '#3b82f6',
  brent_price: '#06b6d4',
}

interface STEOItem {
  date: string
  us_production: number | null
  us_consumption: number | null
  opec_production: number | null
  opec_plus_production: number | null
  world_production: number | null
  world_consumption: number | null
  world_balance: number | null
  china_consumption: number | null
  wti_price: number | null
  brent_price: number | null
}

interface PreviousForecast {
  data: STEOItem[]
  forecast_month: string
  saved_at: string
}

interface STEOResponse {
  data: STEOItem[]
  latest: STEOItem | null
  next_release: { date: string; label?: string } | null
  previous_forecast: PreviousForecast | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

// Merged item includes prev_ fields
interface MergedItem extends STEOItem {
  prev_us_production: number | null
  prev_us_consumption: number | null
  prev_opec_production: number | null
  prev_opec_plus_production: number | null
  prev_world_production: number | null
  prev_world_consumption: number | null
  prev_world_balance: number | null
  prev_china_consumption: number | null
  prev_wti_price: number | null
  prev_brent_price: number | null
}

type ViewMode = 'us_supply' | 'opec' | 'world' | 'china' | 'price'
const VIEW_MODE_OPTIONS = [
  { mode: 'us_supply' as ViewMode, label: '米国需給' },
  { mode: 'opec' as ViewMode, label: 'OPEC/OPEC+' },
  { mode: 'world' as ViewMode, label: '世界需給' },
  { mode: 'china' as ViewMode, label: '中国消費' },
  { mode: 'price' as ViewMode, label: '原油価格' },
]

type SeriesKey = 'us_production' | 'us_consumption' | 'opec_production' | 'opec_plus_production' |
  'world_production' | 'world_consumption' | 'world_balance' | 'china_consumption' |
  'wti_price' | 'brent_price' |
  'prev_us_production' | 'prev_us_consumption' | 'prev_opec_production' | 'prev_opec_plus_production' |
  'prev_world_production' | 'prev_world_consumption' | 'prev_world_balance' | 'prev_china_consumption' |
  'prev_wti_price' | 'prev_brent_price'

// Tooltip config per viewMode
interface TooltipItem {
  key: string
  prevKey: string
  label: string
  color: string
  format: (v: number) => string
}

const fmtMbd = (v: number) => `${v.toFixed(3)} mb/d`
const fmtUsd = (v: number) => `$${v.toFixed(2)}`

function getTooltipItems(viewMode: ViewMode): TooltipItem[] {
  if (viewMode === 'us_supply') return [
    { key: 'us_production', prevKey: 'prev_us_production', label: '米国生産', color: COLORS.us_production, format: fmtMbd },
    { key: 'us_consumption', prevKey: 'prev_us_consumption', label: '米国消費', color: COLORS.us_consumption, format: fmtMbd },
  ]
  if (viewMode === 'opec') return [
    { key: 'opec_production', prevKey: 'prev_opec_production', label: 'OPEC生産', color: COLORS.opec_production, format: fmtMbd },
    { key: 'opec_plus_production', prevKey: 'prev_opec_plus_production', label: 'OPEC+生産', color: COLORS.opec_plus_production, format: fmtMbd },
  ]
  if (viewMode === 'world') return [
    { key: 'world_production', prevKey: 'prev_world_production', label: '世界生産', color: COLORS.world_production, format: fmtMbd },
    { key: 'world_consumption', prevKey: 'prev_world_consumption', label: '世界消費', color: COLORS.world_consumption, format: fmtMbd },
    { key: 'world_balance', prevKey: 'prev_world_balance', label: '需給バランス', color: COLORS.world_balance, format: fmtMbd },
  ]
  if (viewMode === 'china') return [
    { key: 'china_consumption', prevKey: 'prev_china_consumption', label: '中国消費', color: COLORS.china_consumption, format: fmtMbd },
  ]
  if (viewMode === 'price') return [
    { key: 'wti_price', prevKey: 'prev_wti_price', label: 'WTI', color: COLORS.wti_price, format: fmtUsd },
    { key: 'brent_price', prevKey: 'prev_brent_price', label: 'Brent', color: COLORS.brent_price, format: fmtUsd },
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
                  ({diff >= 0 ? '+' : ''}{item.key.includes('price') ? diff.toFixed(2) : diff.toFixed(3)})
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


export default function ShortTermEnergyOutlookChart() {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)
  const [viewMode, setViewMode] = useState<ViewMode>('us_supply')
  const [showPrev, setShowPrev] = useState(true)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<SeriesKey>()

  const { data: response } = useQuery<STEOResponse>({
    queryKey: ['short-term-energy-outlook'],
    queryFn: async () => {
      const res = await axios.get('/api/market/short-term-energy-outlook')
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

    const prevMap = new Map<string, STEOItem>()
    if (response.previous_forecast?.data) {
      for (const item of response.previous_forecast.data) {
        prevMap.set(item.date, item)
      }
    }

    const FIELDS = [
      'us_production', 'us_consumption', 'opec_production', 'opec_plus_production',
      'world_production', 'world_consumption', 'world_balance', 'china_consumption',
      'wti_price', 'brent_price',
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
      title="短期エネルギー見通し（原油）"
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
          {latest?.wti_price != null && (
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>WTI: </span>
              <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.wti_price }}>
                ${latest.wti_price.toFixed(2)}
              </span>
            </div>
          )}
          {latest?.brent_price != null && (
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>Brent: </span>
              <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.brent_price }}>
                ${latest.brent_price.toFixed(2)}
              </span>
            </div>
          )}
          {latest?.us_production != null && (
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>米国生産: </span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.us_production }}>
                {latest.us_production.toFixed(2)} mb/d
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
              onClick={() => window.open('/compare?s=steo_us_production&s=steo_us_consumption', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>
      </div>

      {/* Period selector */}
      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

      {/* US Supply/Demand */}
      {viewMode === 'us_supply' && (
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
            <XAxis dataKey="date" tickFormatter={(v) => formatDayLabel(v)} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} minTickGap={40} />
            <YAxis domain={['dataMin * 0.95', 'dataMax * 1.02']} tickFormatter={(v: number) => `${v.toFixed(1)}`} stroke={DARK_THEME.textSecondary} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} width={50}  />
            <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} viewMode={viewMode} showPrev={showPrev && hasPrev} prevLabel={prevLabel} />} />
            <ReferenceLine x={currentDateStr} stroke="#fbbf24" strokeDasharray="6 3" strokeWidth={1.5} label={{ value: '現在', position: 'top', fill: '#fbbf24', fontSize: 11 }} />
            <Legend onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={(value: string, entry: any) => (<span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>{value}</span>)} />
            <Line type="monotone" dataKey="us_production" name="米国生産 (mb/d)" stroke={COLORS.us_production} strokeWidth={2} dot={false} hide={hiddenSeries.has('us_production')} connectNulls isAnimationActive={false} />
            <Line type="monotone" dataKey="us_consumption" name="米国消費 (mb/d)" stroke={COLORS.us_consumption} strokeWidth={2} dot={false} hide={hiddenSeries.has('us_consumption')} connectNulls isAnimationActive={false} />
            {renderPrevLines([
              { dataKey: 'us_production', prevKey: 'prev_us_production', color: COLORS.us_production, name: '米国生産' },
              { dataKey: 'us_consumption', prevKey: 'prev_us_consumption', color: COLORS.us_consumption, name: '米国消費' },
            ])}
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* OPEC / OPEC+ */}
      {viewMode === 'opec' && (
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
            <XAxis dataKey="date" tickFormatter={(v) => formatDayLabel(v)} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} minTickGap={40} />
            <YAxis domain={['dataMin * 0.95', 'dataMax * 1.02']} tickFormatter={(v: number) => `${v.toFixed(1)}`} stroke={DARK_THEME.textSecondary} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} width={50}  />
            <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} viewMode={viewMode} showPrev={showPrev && hasPrev} prevLabel={prevLabel} />} />
            <ReferenceLine x={currentDateStr} stroke="#fbbf24" strokeDasharray="6 3" strokeWidth={1.5} label={{ value: '現在', position: 'top', fill: '#fbbf24', fontSize: 11 }} />
            <Legend onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={(value: string, entry: any) => (<span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>{value}</span>)} />
            <Line type="monotone" dataKey="opec_production" name="OPEC生産 (mb/d)" stroke={COLORS.opec_production} strokeWidth={2} dot={false} hide={hiddenSeries.has('opec_production')} connectNulls isAnimationActive={false} />
            <Line type="monotone" dataKey="opec_plus_production" name="OPEC+生産 (mb/d)" stroke={COLORS.opec_plus_production} strokeWidth={2} dot={false} hide={hiddenSeries.has('opec_plus_production')} connectNulls isAnimationActive={false} />
            {renderPrevLines([
              { dataKey: 'opec_production', prevKey: 'prev_opec_production', color: COLORS.opec_production, name: 'OPEC生産' },
              { dataKey: 'opec_plus_production', prevKey: 'prev_opec_plus_production', color: COLORS.opec_plus_production, name: 'OPEC+生産' },
            ])}
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* World Supply/Demand */}
      {viewMode === 'world' && (
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
            <XAxis dataKey="date" tickFormatter={(v) => formatDayLabel(v)} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} minTickGap={40} />
            <YAxis yAxisId="left" domain={['dataMin * 0.95', 'dataMax * 1.02']} tickFormatter={(v: number) => `${v.toFixed(0)}`} stroke={DARK_THEME.textSecondary} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} width={50}  />
            <YAxis yAxisId="right" orientation="right" domain={['dataMin - 2', 'dataMax + 2']} tickFormatter={(v: number) => `${v.toFixed(1)}`} stroke={COLORS.world_balance} tick={{ fill: COLORS.world_balance, fontSize: 11 }} width={50} label={{ value: 'バランス', angle: 90, position: 'insideRight', style: { fill: COLORS.world_balance, fontSize: 10 } }} />
            <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} viewMode={viewMode} showPrev={showPrev && hasPrev} prevLabel={prevLabel} />} />
            <ReferenceLine yAxisId="right" y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />
            <ReferenceLine yAxisId="left" x={currentDateStr} stroke="#fbbf24" strokeDasharray="6 3" strokeWidth={1.5} label={{ value: '現在', position: 'top', fill: '#fbbf24', fontSize: 11 }} />
            <Legend onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={(value: string, entry: any) => (<span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>{value}</span>)} />
            <Line yAxisId="left" type="monotone" dataKey="world_production" name="世界生産 (mb/d)" stroke={COLORS.world_production} strokeWidth={2} dot={false} hide={hiddenSeries.has('world_production')} connectNulls isAnimationActive={false} />
            <Line yAxisId="left" type="monotone" dataKey="world_consumption" name="世界消費 (mb/d)" stroke={COLORS.world_consumption} strokeWidth={2} dot={false} hide={hiddenSeries.has('world_consumption')} connectNulls isAnimationActive={false} />
            <Area yAxisId="right" type="monotone" dataKey="world_balance" name="需給バランス (mb/d)" stroke={COLORS.world_balance} fill={COLORS.world_balance} fillOpacity={0.15} strokeWidth={1.5} hide={hiddenSeries.has('world_balance')} connectNulls isAnimationActive={false} />
            {renderPrevLines([
              { dataKey: 'world_production', prevKey: 'prev_world_production', color: COLORS.world_production, name: '世界生産', yAxisId: 'left' },
              { dataKey: 'world_consumption', prevKey: 'prev_world_consumption', color: COLORS.world_consumption, name: '世界消費', yAxisId: 'left' },
            ])}
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* China Consumption */}
      {viewMode === 'china' && (
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
            <XAxis dataKey="date" tickFormatter={(v) => formatDayLabel(v)} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} minTickGap={40} />
            <YAxis domain={['dataMin * 0.9', 'dataMax * 1.05']} tickFormatter={(v: number) => `${v.toFixed(1)}`} stroke={DARK_THEME.textSecondary} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} width={50}  />
            <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} viewMode={viewMode} showPrev={showPrev && hasPrev} prevLabel={prevLabel} />} />
            <ReferenceLine x={currentDateStr} stroke="#fbbf24" strokeDasharray="6 3" strokeWidth={1.5} label={{ value: '現在', position: 'top', fill: '#fbbf24', fontSize: 11 }} />
            <Legend onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={(value: string, entry: any) => (<span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>{value}</span>)} />
            <Line type="monotone" dataKey="china_consumption" name="中国石油消費 (mb/d)" stroke={COLORS.china_consumption} strokeWidth={2} dot={false} hide={hiddenSeries.has('china_consumption')} connectNulls isAnimationActive={false} />
            {renderPrevLines([
              { dataKey: 'china_consumption', prevKey: 'prev_china_consumption', color: COLORS.china_consumption, name: '中国消費' },
            ])}
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* Oil Price Forecast */}
      {viewMode === 'price' && (
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
            <XAxis dataKey="date" tickFormatter={(v) => formatDayLabel(v)} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} minTickGap={40} />
            <YAxis domain={['dataMin * 0.9', 'dataMax * 1.05']} tickFormatter={(v: number) => `$${v.toFixed(0)}`} stroke={DARK_THEME.textSecondary} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} width={55} />
            <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} viewMode={viewMode} showPrev={showPrev && hasPrev} prevLabel={prevLabel} />} />
            <ReferenceLine x={currentDateStr} stroke="#fbbf24" strokeDasharray="6 3" strokeWidth={1.5} label={{ value: '現在', position: 'top', fill: '#fbbf24', fontSize: 11 }} />
            <Legend onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={(value: string, entry: any) => (<span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>{value}</span>)} />
            <Line type="monotone" dataKey="wti_price" name="WTI ($/bbl)" stroke={COLORS.wti_price} strokeWidth={2} dot={false} hide={hiddenSeries.has('wti_price')} connectNulls isAnimationActive={false} />
            <Line type="monotone" dataKey="brent_price" name="Brent ($/bbl)" stroke={COLORS.brent_price} strokeWidth={2} dot={false} hide={hiddenSeries.has('brent_price')} connectNulls isAnimationActive={false} />
            {renderPrevLines([
              { dataKey: 'wti_price', prevKey: 'prev_wti_price', color: COLORS.wti_price, name: 'WTI' },
              { dataKey: 'brent_price', prevKey: 'prev_brent_price', color: COLORS.brent_price, name: 'Brent' },
            ])}
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </ChartContainer>
  )
}
