import { useState, useMemo } from 'react'
import { Tooltip, Switch } from 'antd'
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
  Area,
} from 'recharts'
import ChartContainer from '../../common/ChartContainer'
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

const COLORS = {
  world_demand: '#ef4444',
  total_production: '#3b82f6',
  balance: '#06b6d4',
  demand_yoy: '#ef4444',
  supply_yoy: '#22c55e',
  demand_chg: '#ef4444',
  supply_chg: '#3b82f6',
  balance_chg: '#06b6d4',
  oecd_commercial: '#3b82f6',
  oecd_spr: '#f59e0b',
  oil_on_water: '#06b6d4',
  days_commercial: '#3b82f6',
  days_spr: '#f59e0b',
  days_total: '#a855f7',
}

// API response types
interface TableData {
  data: Record<string, unknown>[]
  fields: string[]
  periods: string[]
}

interface NextRelease {
  date: string
  datetime_jst?: string
  time_jst?: string
  label?: string
  estimate?: number | null
}

interface OpecMomrResponse {
  current: {
    table_11_1: TableData
    table_11_3: TableData
  } | null
  previous: {
    table_11_1: TableData
    table_11_3: TableData
  } | null
  changes: {
    data: Record<string, unknown>[]
    fields: string[]
  } | null
  next_release?: NextRelease | null
  report_month: string
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

type ViewMode = 'demand_supply' | 'yoy' | 'changes' | 'stocks' | 'days'
const VIEW_MODE_OPTIONS = [
  { mode: 'demand_supply' as ViewMode, label: '需給バランス' },
  { mode: 'yoy' as ViewMode, label: '前年比' },
  { mode: 'changes' as ViewMode, label: '前月修正' },
  { mode: 'stocks' as ViewMode, label: 'OECD在庫' },
  { mode: 'days' as ViewMode, label: '在庫日数' },
]

type SeriesKey = string

const fmtMbd = (v: number) => `${v.toFixed(3)} mb/d`
const fmtMb = (v: number) => `${v.toFixed(1)} mb`
const fmtDays = (v: number) => `${v.toFixed(1)} days`

function formatPeriod(period: string): string {
  const qm = period.match(/^(\d{4})-Q(\d)$/)
  if (qm) return `${qm[1].slice(2)}Q${qm[2]}`
  return period
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ChartTooltipContent({ active, payload, label, hiddenSeries, viewMode, showPrev }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
  viewMode: ViewMode
  showPrev: boolean
}) {
  if (!active || !payload || payload.length === 0) return null
  const dp = payload[0]?.payload as Record<string, unknown> | undefined
  if (!dp) return null

  const items = payload.filter(p => !hiddenSeries.has(p.dataKey) && p.value != null)

  return (
    <div style={{
      backgroundColor: DARK_THEME.tooltipBg,
      border: `1px solid ${DARK_THEME.tooltipBorder}`,
      borderRadius: 8,
      padding: '12px 16px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
    }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
        {label}
      </div>
      {items.map((item, i) => {
        const val = item.value as number
        let formatted: string
        if (viewMode === 'stocks') formatted = fmtMb(val)
        else if (viewMode === 'days') formatted = fmtDays(val)
        else if (viewMode === 'changes') formatted = `${val >= 0 ? '+' : ''}${val.toFixed(3)} mb/d`
        else if (viewMode === 'yoy') formatted = `${val >= 0 ? '+' : ''}${val.toFixed(3)} mb/d`
        else formatted = fmtMbd(val)

        const prevKey = `prev_${item.dataKey}`
        const prevVal = showPrev ? dp[prevKey] as number | undefined : undefined

        return (
          <div key={i} style={{ marginBottom: 4 }}>
            <div style={{ color: item.color || item.stroke, fontSize: 13 }}>
              {item.name}: {formatted}
              {prevVal != null && (
                <span style={{ fontSize: 11, marginLeft: 6, color: TEXT_COLORS.secondary }}>
                  (前月: {viewMode === 'stocks' ? fmtMb(prevVal) : fmtMbd(prevVal)})
                </span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}


export default function OpecMomrChart() {
  const [viewMode, setViewMode] = useState<ViewMode>('demand_supply')
  const [showPrev, setShowPrev] = useState(true)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<SeriesKey>()

  const { data: response } = useQuery<OpecMomrResponse>({
    queryKey: ['opec-momr'],
    queryFn: async () => {
      const res = await axios.get('/api/market/opec-momr')
      return res.data
    },
    staleTime: 1000 * 60 * 60,
  })

  const hasPrev = !!response?.previous?.table_11_1?.data?.length

  // Merge current and previous data for Table 11-1
  const balanceData = useMemo(() => {
    const current = response?.current?.table_11_1?.data
    if (!current) return []

    const prevMap = new Map<string, Record<string, unknown>>()
    if (response?.previous?.table_11_1?.data) {
      for (const item of response.previous.table_11_1.data) {
        prevMap.set(item.period as string, item)
      }
    }

    return current.map(item => {
      const merged: Record<string, unknown> = { ...item }
      const prev = prevMap.get(item.period as string)
      if (prev) {
        for (const key of Object.keys(prev)) {
          if (key !== 'period') merged[`prev_${key}`] = prev[key]
        }
      }
      return merged
    })
  }, [response])

  // Merge current and previous for Table 11-3
  const stocksData = useMemo(() => {
    const current = response?.current?.table_11_3?.data
    if (!current) return []

    const prevMap = new Map<string, Record<string, unknown>>()
    if (response?.previous?.table_11_3?.data) {
      for (const item of response.previous.table_11_3.data) {
        prevMap.set(item.period as string, item)
      }
    }

    return current.map(item => {
      const merged: Record<string, unknown> = { ...item }
      const prev = prevMap.get(item.period as string)
      if (prev) {
        for (const key of Object.keys(prev)) {
          if (key !== 'period') merged[`prev_${key}`] = prev[key]
        }
      }
      return merged
    })
  }, [response])

  const changesData = useMemo(() => {
    return response?.changes?.data ?? []
  }, [response])

  // Latest = most recent period with actual total_production data
  const latest = balanceData.length > 0 ? balanceData.find(d => d.total_production != null) || balanceData[0] : null

  const reportMonth = response?.report_month

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const legendFormatter = (value: string, entry: any) => (
    <span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>
      {value}
    </span>
  )

  const renderPrevLines = (fields: { dataKey: string; prevKey: string; color: string; name: string; yAxisId?: string }[]) => {
    if (!showPrev || !hasPrev) return null
    return fields.map(f => (
      <Line
        key={f.prevKey}
        yAxisId={f.yAxisId}
        type="monotone"
        dataKey={f.prevKey}
        name={`${f.name} (前月)`}
        stroke={f.color}
        strokeWidth={1}
        strokeDasharray="6 4"
        strokeOpacity={0.4}
        dot={false}
        hide={hiddenSeries.has(f.prevKey)}
        connectNulls
        isAnimationActive={false}
      />
    ))
  }

  return (
    <ChartContainer
      title="OPEC MOMR (月次石油市場レポート)"
      dataSource="OPEC"
      sourceUrl="https://publications.opec.org/momr/Home"
      showPeriodSelector={false}
    >
      {/* Latest value box */}
      <div style={LATEST_VALUE_BOX_STYLE}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          {reportMonth && (
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
              レポート月: {reportMonth}
            </span>
          )}
          {latest?.world_demand != null && (
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>世界需要: </span>
              <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.world_demand }}>
                {(latest.world_demand as number).toFixed(2)} mb/d
              </span>
            </div>
          )}
          {latest?.total_production != null && (
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>総生産: </span>
              <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.total_production }}>
                {(latest.total_production as number).toFixed(2)} mb/d
              </span>
            </div>
          )}
          {latest?.balance != null && (
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>バランス: </span>
              <span style={{ fontSize: 18, fontWeight: 'bold', color: (latest.balance as number) >= 0 ? '#22c55e' : '#ef4444' }}>
                {(latest.balance as number) >= 0 ? '+' : ''}{(latest.balance as number).toFixed(3)} mb/d
              </span>
            </div>
          )}
        </div>
        {response?.next_release && (
          <span style={{ fontSize: 11, color: TEXT_COLORS.secondary, whiteSpace: 'nowrap' }}>
            次回: {response.next_release.date}
            {response.next_release.time_jst && ` ${response.next_release.time_jst} (JST)`}
          </span>
        )}
      </div>

      {/* ViewMode + Previous toggle */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <ViewModeButtonGroup
          options={VIEW_MODE_OPTIONS}
          currentMode={viewMode}
          onChange={(m) => setViewMode(m as ViewMode)}
        />
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {hasPrev && (viewMode === 'demand_supply' || viewMode === 'stocks' || viewMode === 'days') && (
            <Tooltip title="前月レポートとの比較を表示">
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <Switch size="small" checked={showPrev} onChange={setShowPrev} />
                <span style={{ fontSize: 11, color: TEXT_COLORS.secondary }}>前月比較</span>
              </div>
            </Tooltip>
          )}
        </div>
      </div>

      {/* ── 1. 需給バランス: World demand vs Total liquids production ── */}
      {viewMode === 'demand_supply' && (
        <ResponsiveContainer width="100%" height={420}>
          <ComposedChart data={balanceData} margin={CHART_MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
            <XAxis dataKey="period" tickFormatter={formatPeriod} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} />
            <YAxis yAxisId="left" domain={['dataMin * 0.95', 'dataMax * 1.02']} tickFormatter={(v: number) => `${v.toFixed(0)}`} stroke={DARK_THEME.textSecondary} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} width={50} />
            <YAxis yAxisId="right" orientation="right" domain={['dataMin - 1', 'dataMax + 1']} tickFormatter={(v: number) => `${v.toFixed(1)}`} stroke={COLORS.balance} tick={{ fill: COLORS.balance, fontSize: 11 }} width={50} />
            <RechartsTooltip content={<ChartTooltipContent hiddenSeries={hiddenSeries} viewMode={viewMode} showPrev={showPrev && hasPrev} />} />
            <ReferenceLine yAxisId="right" y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />
            <Legend onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={legendFormatter} />
            <Line yAxisId="left" type="monotone" dataKey="world_demand" name="世界需要 (mb/d)" stroke={COLORS.world_demand} strokeWidth={2} dot={{ r: 3, fill: COLORS.world_demand }} hide={hiddenSeries.has('world_demand')} connectNulls isAnimationActive={false} />
            <Line yAxisId="left" type="monotone" dataKey="total_production" name="総生産 (mb/d)" stroke={COLORS.total_production} strokeWidth={2} dot={{ r: 3, fill: COLORS.total_production }} hide={hiddenSeries.has('total_production')} connectNulls isAnimationActive={false} />
            <Area yAxisId="right" type="monotone" dataKey="balance" name="バランス (mb/d)" stroke={COLORS.balance} fill={COLORS.balance} fillOpacity={0.15} strokeWidth={1.5} hide={hiddenSeries.has('balance')} connectNulls isAnimationActive={false} />
            {renderPrevLines([
              { dataKey: 'world_demand', prevKey: 'prev_world_demand', color: COLORS.world_demand, name: '世界需要', yAxisId: 'left' },
              { dataKey: 'total_production', prevKey: 'prev_total_production', color: COLORS.total_production, name: '総生産', yAxisId: 'left' },
            ])}
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* ── 2. 前年比: Demand YoY vs Supply YoY ── */}
      {viewMode === 'yoy' && (
        <ResponsiveContainer width="100%" height={420}>
          <ComposedChart data={balanceData} margin={CHART_MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
            <XAxis dataKey="period" tickFormatter={formatPeriod} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} />
            <YAxis domain={['dataMin - 0.5', 'dataMax + 0.5']} tickFormatter={(v: number) => `${v.toFixed(1)}`} stroke={DARK_THEME.textSecondary} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} width={50} />
            <RechartsTooltip content={<ChartTooltipContent hiddenSeries={hiddenSeries} viewMode={viewMode} showPrev={false} />} />
            <ReferenceLine y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />
            <Legend onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={legendFormatter} />
            <Line type="monotone" dataKey="demand_yoy_change" name="需要 YoY (mb/d)" stroke={COLORS.demand_yoy} strokeWidth={2} dot={{ r: 3, fill: COLORS.demand_yoy }} hide={hiddenSeries.has('demand_yoy_change')} connectNulls isAnimationActive={false} />
            <Line type="monotone" dataKey="supply_yoy_change" name="供給 YoY (mb/d)" stroke={COLORS.supply_yoy} strokeWidth={2} dot={{ r: 3, fill: COLORS.supply_yoy }} hide={hiddenSeries.has('supply_yoy_change')} connectNulls isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* ── 3. 前月修正: Demand / Supply / Balance revision (bars only) ── */}
      {viewMode === 'changes' && (
        <ResponsiveContainer width="100%" height={420}>
          <ComposedChart data={changesData} margin={CHART_MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
            <XAxis dataKey="period" tickFormatter={formatPeriod} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} />
            <YAxis domain={[-0.3, 0.3]} tickFormatter={(v: number) => `${v.toFixed(2)}`} stroke={DARK_THEME.textSecondary} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} width={55} />
            <RechartsTooltip content={<ChartTooltipContent hiddenSeries={hiddenSeries} viewMode={viewMode} showPrev={false} />} />
            <ReferenceLine y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />
            <Legend onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={legendFormatter} />
            <Bar dataKey="world_demand_chg" name="需要修正 (mb/d)" fill={COLORS.demand_chg} fillOpacity={0.8} hide={hiddenSeries.has('world_demand_chg')} isAnimationActive={false} />
            <Bar dataKey="non_doc_production_chg" name="供給修正 (mb/d)" fill={COLORS.supply_chg} fillOpacity={0.8} hide={hiddenSeries.has('non_doc_production_chg')} isAnimationActive={false} />
            <Bar dataKey="balance_chg" name="バランス修正 (mb/d)" fill={COLORS.balance_chg} fillOpacity={0.8} hide={hiddenSeries.has('balance_chg')} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* ── 4. OECD在庫: Commercial (Y1) / SPR + Oil-on-water (Y2) ── */}
      {viewMode === 'stocks' && (
        <ResponsiveContainer width="100%" height={420}>
          <ComposedChart data={stocksData} margin={CHART_MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
            <XAxis dataKey="period" tickFormatter={formatPeriod} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} />
            <YAxis yAxisId="left" domain={['dataMin * 0.95', 'dataMax * 1.02']} tickFormatter={(v: number) => `${v.toFixed(0)}`} stroke={DARK_THEME.textSecondary} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} width={55} label={{ value: 'OECD商業在庫 (mb)', angle: -90, position: 'insideLeft', style: { fill: DARK_THEME.textSecondary, fontSize: 10 }, offset: -5 }} />
            <YAxis yAxisId="right" orientation="right" domain={['dataMin * 0.85', 'dataMax * 1.1']} tickFormatter={(v: number) => `${v.toFixed(0)}`} stroke={COLORS.oecd_spr} tick={{ fill: COLORS.oecd_spr, fontSize: 11 }} width={55} label={{ value: 'SPR / Oil-on-water (mb)', angle: 90, position: 'insideRight', style: { fill: COLORS.oecd_spr, fontSize: 10 }, offset: -5 }} />
            <RechartsTooltip content={<ChartTooltipContent hiddenSeries={hiddenSeries} viewMode={viewMode} showPrev={showPrev && hasPrev} />} />
            <Legend onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={legendFormatter} />
            <Line yAxisId="left" type="monotone" dataKey="oecd_commercial" name="OECD商業在庫 (mb)" stroke={COLORS.oecd_commercial} strokeWidth={2} dot={{ r: 3, fill: COLORS.oecd_commercial }} hide={hiddenSeries.has('oecd_commercial')} connectNulls isAnimationActive={false} />
            <Line yAxisId="right" type="monotone" dataKey="oecd_spr" name="OECD SPR (mb)" stroke={COLORS.oecd_spr} strokeWidth={2} dot={{ r: 3, fill: COLORS.oecd_spr }} hide={hiddenSeries.has('oecd_spr')} connectNulls isAnimationActive={false} />
            <Line yAxisId="right" type="monotone" dataKey="oil_on_water" name="Oil-on-water (mb)" stroke={COLORS.oil_on_water} strokeWidth={2} dot={{ r: 3, fill: COLORS.oil_on_water }} hide={hiddenSeries.has('oil_on_water')} connectNulls isAnimationActive={false} />
            {renderPrevLines([
              { dataKey: 'oecd_commercial', prevKey: 'prev_oecd_commercial', color: COLORS.oecd_commercial, name: 'OECD商業在庫', yAxisId: 'left' },
              { dataKey: 'oecd_spr', prevKey: 'prev_oecd_spr', color: COLORS.oecd_spr, name: 'OECD SPR', yAxisId: 'right' },
              { dataKey: 'oil_on_water', prevKey: 'prev_oil_on_water', color: COLORS.oil_on_water, name: 'Oil-on-water', yAxisId: 'right' },
            ])}
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* ── 5. 在庫日数: Days of forward consumption ── */}
      {viewMode === 'days' && (
        <ResponsiveContainer width="100%" height={420}>
          <ComposedChart data={stocksData} margin={CHART_MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
            <XAxis dataKey="period" tickFormatter={formatPeriod} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} />
            <YAxis domain={['dataMin * 0.9', 'dataMax * 1.05']} tickFormatter={(v: number) => `${v.toFixed(0)}`} stroke={DARK_THEME.textSecondary} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} width={50} />
            <RechartsTooltip content={<ChartTooltipContent hiddenSeries={hiddenSeries} viewMode={viewMode} showPrev={showPrev && hasPrev} />} />
            <Legend onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={legendFormatter} />
            <Line type="monotone" dataKey="days_commercial" name="商業在庫日数" stroke={COLORS.days_commercial} strokeWidth={2} dot={{ r: 3, fill: COLORS.days_commercial }} hide={hiddenSeries.has('days_commercial')} connectNulls isAnimationActive={false} />
            <Line type="monotone" dataKey="days_spr" name="SPR日数" stroke={COLORS.days_spr} strokeWidth={2} dot={{ r: 3, fill: COLORS.days_spr }} hide={hiddenSeries.has('days_spr')} connectNulls isAnimationActive={false} />
            <Line type="monotone" dataKey="days_total" name="合計日数" stroke={COLORS.days_total} strokeWidth={2} dot={{ r: 3, fill: COLORS.days_total }} hide={hiddenSeries.has('days_total')} connectNulls isAnimationActive={false} />
            {renderPrevLines([
              { dataKey: 'days_commercial', prevKey: 'prev_days_commercial', color: COLORS.days_commercial, name: '商業在庫日数' },
              { dataKey: 'days_spr', prevKey: 'prev_days_spr', color: COLORS.days_spr, name: 'SPR日数' },
              { dataKey: 'days_total', prevKey: 'prev_days_total', color: COLORS.days_total, name: '合計日数' },
            ])}
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </ChartContainer>
  )
}
