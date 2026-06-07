import { useState, useMemo } from 'react'
import { Typography, Tabs, Select, Table, Tooltip, Button, Checkbox } from 'antd'
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
import { ViewModeButtonGroup } from '../../country/usa/common/ChartComponents'
import { useHiddenSeries } from '../../country/usa/common/useChartData'
import { formatDayLabel } from '../../../utils/dateFormatters'

const { Text } = Typography

// ===== Theme & Colors =====

const DARK_THEME = {
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  textTertiary: '#64748b',
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
  gridLine: '#475569',
  axisLine: '#64748b',
  tooltipBg: '#334155',
  tooltipBorder: '#475569',
  chartBg: '#1e293b',
}

const COLOR_CALL = '#3b82f6'       // blue
const COLOR_PUT = '#ef4444'        // red
const COLOR_ATM_IV = '#06b6d4'     // cyan
const COLOR_UNDERLYING = '#f59e0b' // amber
const COLOR_ATM_LINE = '#a855f7'   // purple
const COLOR_PREV_CALL = 'rgba(59, 130, 246, 0.45)'
const COLOR_PREV_PUT = 'rgba(239, 68, 68, 0.45)'
const COLOR_PREV_ATM = 'rgba(6, 182, 212, 0.45)'
const COLOR_POSITIVE = '#10b981'   // green
const COLOR_NEGATIVE = '#ef4444'   // red

const CHART_MARGIN = { top: 16, right: 16, bottom: 0, left: 0 }

const BOX_STYLE: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  marginBottom: 12,
  padding: '10px 14px',
  background: DARK_THEME.bgSecondary,
  borderRadius: 8,
  border: '1px solid rgba(16, 185, 129, 0.4)',
  flexWrap: 'wrap',
  gap: 12,
}

// ===== Types =====

interface StrikeData {
  strike: number
  put_settlement: number | null
  put_theoretical: number | null
  put_iv: number | null
  call_settlement: number | null
  call_theoretical: number | null
  call_iv: number | null
  put_oi: number | null
  call_oi: number | null
  put_volume: number | null
  call_volume: number | null
  prev_put_iv: number | null
  prev_call_iv: number | null
  prev_put_oi: number | null
  prev_call_oi: number | null
  oi_change_put: number | null
  oi_change_call: number | null
  quality: 'good' | 'fair' | 'distant'
}

interface ExpiryData {
  expiry: string
  contract_month: string
  dte: number | null
  atm_strike: number
  atm_iv_call: number | null
  atm_iv_put: number | null
  atm_iv_mid: number | null
  prev_atm_iv_mid: number | null
  skew_25d_put_iv: number | null
  skew_25d_call_iv: number | null
  skew_25d_rr: number | null
  skew_25d_butterfly: number | null
  prev_skew_25d_rr: number | null
  total_call_oi: number | null
  total_put_oi: number | null
  prev_total_call_oi: number | null
  prev_total_put_oi: number | null
  total_call_volume: number | null
  total_put_volume: number | null
  strikes: StrikeData[]
}

interface AggregateData {
  total_call_oi: number
  total_put_oi: number
  prev_total_call_oi: number
  prev_total_put_oi: number
  total_call_volume: number
  total_put_volume: number
  volume_5d_avg: number | null
}

interface AtmIvHistoryItem {
  date: string
  expiry: string
  contract_month: string
  dte: number | null
  atm_iv_mid: number
  atm_iv_call: number | null
  atm_iv_put: number | null
  underlying: number
}

interface OptionsData {
  underlying_price: number
  prev_underlying_price: number | null
  date: string
  prev_date: string | null
  expiries: ExpiryData[]
  atm_iv_history: AtmIvHistoryItem[]
  aggregate: AggregateData | null
}

interface OptionsLatest {
  date: string
  underlying_price: number
  nearest_expiry: string | null
  nearest_dte: number | null
  atm_iv_mid: number | null
  atm_iv_call: number | null
  atm_iv_put: number | null
}

interface OptionsResponse {
  data: OptionsData
  latest: OptionsLatest | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

// ===== Helpers =====

function fmtNum(v: number | null | undefined, decimals = 0): string {
  if (v == null) return 'N/A'
  return v.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

function fmtK(v: number | null | undefined): string {
  if (v == null) return 'N/A'
  if (Math.abs(v) >= 1000) return `${(v / 1000).toFixed(1)}K`
  return `${v}`
}

function DeltaSpan({ value, suffix = '', decimals = 2 }: { value: number | null | undefined; suffix?: string; decimals?: number }) {
  if (value == null) return null
  const color = value > 0 ? COLOR_POSITIVE : value < 0 ? COLOR_NEGATIVE : DARK_THEME.textSecondary
  const sign = value > 0 ? '+' : ''
  return (
    <span style={{ color, fontSize: 11, fontWeight: 600 }} className="tabular-nums">
      ({sign}{value.toFixed(decimals)}{suffix})
    </span>
  )
}

// ===== Data Hook =====

function useNikkei225OptionsData() {
  return useQuery({
    queryKey: ['market', 'nikkei225-options'],
    queryFn: async () => {
      const { data } = await axios.get<OptionsResponse>('/api/market/nikkei225-options')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

// ===== Sub-components =====

type AtmIvViewMode = 'term_structure' | 'atm_iv_history'
const ATM_IV_VIEW_OPTIONS = [
  { mode: 'term_structure' as AtmIvViewMode, label: 'ターム構造' },
  { mode: 'atm_iv_history' as AtmIvViewMode, label: 'ATM IV推移' },
]

// --- Tab 1: ATM IV ---
function AtmIvTab({
  expiries,
  atmIvHistory,
  selectedExpiry,
  onExpiryChange,
}: {
  expiries: ExpiryData[]
  atmIvHistory: AtmIvHistoryItem[]
  selectedExpiry: string
  onExpiryChange: (v: string) => void
}) {
  const [viewMode, setViewMode] = useState<AtmIvViewMode>('term_structure')
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(1)
  const [showPrev, setShowPrev] = useState(true)
  const { hiddenSeries, handleLegendClick, isHidden } = useHiddenSeries<'atm_iv_mid' | 'underlying'>()

  const hasPrevData = expiries.some(e => e.prev_atm_iv_mid != null)

  // Term structure data
  const termStructureData = useMemo(() => {
    return expiries
      .filter(e => e.atm_iv_mid != null)
      .map(e => ({
        expiry: e.expiry,
        label: `${e.contract_month.slice(2)}${e.dte != null ? ` (${e.dte}d)` : ''}`,
        atm_iv_mid: e.atm_iv_mid,
        atm_iv_call: e.atm_iv_call,
        atm_iv_put: e.atm_iv_put,
        prev_atm_iv_mid: e.prev_atm_iv_mid,
        dte: e.dte,
      }))
  }, [expiries])

  // History data: filtered by selected expiry
  const historyData = useMemo(() => {
    const filtered = atmIvHistory
      .filter(h => h.expiry === selectedExpiry)
      .sort((a, b) => a.date.localeCompare(b.date))

    if (selectedPeriod === 'all') return filtered
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 1
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return filtered.filter(d => d.date >= cutoffStr)
  }, [atmIvHistory, selectedExpiry, selectedPeriod])

  // Nearest 4 expiries summary cards
  const summaryExpiries = expiries.filter(e => e.atm_iv_mid != null).slice(0, 4)

  return (
    <div>
      {/* Expiry summary cards */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        {summaryExpiries.map(e => {
          const diff = (e.prev_atm_iv_mid != null && e.atm_iv_mid != null) ? e.atm_iv_mid - e.prev_atm_iv_mid : null
          return (
            <div key={e.contract_month} style={{ background: DARK_THEME.bgTertiary, borderRadius: 6, padding: '6px 12px', minWidth: 120 }}>
              <div style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>{e.contract_month.slice(2)} ({e.dte ?? '?'}d)</div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
                <Text style={{ color: COLOR_ATM_IV, fontSize: 14, fontWeight: 700 }} className="tabular-nums">
                  {e.atm_iv_mid?.toFixed(2)}%
                </Text>
                <DeltaSpan value={diff} suffix="pt" />
              </div>
            </div>
          )
        })}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <ViewModeButtonGroup options={ATM_IV_VIEW_OPTIONS} currentMode={viewMode} onChange={(m) => setViewMode(m as AtmIvViewMode)} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {viewMode === 'term_structure' && hasPrevData && (
            <Checkbox checked={showPrev} onChange={(e) => setShowPrev(e.target.checked)}>
              <span style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>前日線</span>
            </Checkbox>
          )}
          {viewMode === 'atm_iv_history' && (
            <Select
              value={selectedExpiry}
              onChange={onExpiryChange}
              style={{ width: 200 }}
              size="small"
              options={expiries.map(e => ({
                value: e.expiry,
                label: `${e.expiry}${e.dte != null ? ` (${e.dte}日)` : ''}`,
              }))}
            />
          )}
        </div>
      </div>

      {viewMode === 'term_structure' && (
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={termStructureData} margin={CHART_MARGIN} style={{ backgroundColor: DARK_THEME.chartBg }}>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
            <XAxis dataKey="label" axisLine={{ stroke: DARK_THEME.axisLine }} tickLine={{ stroke: DARK_THEME.axisLine }} tick={{ fill: DARK_THEME.textSecondary, fontSize: 10 }} interval={0} angle={-45} textAnchor="end" height={80} />
            <YAxis domain={['dataMin - 2', 'dataMax + 2']} tickFormatter={(v: number) => `${v.toFixed(1)}%`} axisLine={{ stroke: DARK_THEME.axisLine }} tickLine={{ stroke: DARK_THEME.axisLine }} tick={{ fill: COLOR_ATM_IV, fontSize: 11 }} />
            <RechartsTooltip
              contentStyle={{ backgroundColor: DARK_THEME.tooltipBg, border: `1px solid ${DARK_THEME.tooltipBorder}`, borderRadius: 8 }}
              labelStyle={{ color: DARK_THEME.textPrimary, fontWeight: 'bold' }}
              formatter={(value: number, name: string) => {
                const labels: Record<string, string> = {
                  atm_iv_mid: 'ATM IV (Mid)',
                  atm_iv_call: 'Call IV',
                  atm_iv_put: 'Put IV',
                  prev_atm_iv_mid: '前日 ATM IV',
                }
                return [`${value.toFixed(2)}%`, labels[name] ?? name]
              }}
            />
            <Legend formatter={(value: string) => {
              const labels: Record<string, string> = {
                atm_iv_mid: 'ATM IV (Mid)',
                atm_iv_call: 'Call IV',
                atm_iv_put: 'Put IV',
                prev_atm_iv_mid: '前日 ATM IV',
              }
              return <span style={{ color: DARK_THEME.textPrimary, fontSize: 11 }}>{labels[value] ?? value}</span>
            }} />
            <Line type="monotone" dataKey="atm_iv_mid" name="atm_iv_mid" stroke={COLOR_ATM_IV} strokeWidth={2} dot={{ r: 4, fill: COLOR_ATM_IV }} isAnimationActive={false} />
            <Line type="monotone" dataKey="atm_iv_call" name="atm_iv_call" stroke={COLOR_CALL} strokeWidth={1.5} strokeDasharray="4 2" dot={{ r: 3 }} isAnimationActive={false} />
            <Line type="monotone" dataKey="atm_iv_put" name="atm_iv_put" stroke={COLOR_PUT} strokeWidth={1.5} strokeDasharray="4 2" dot={{ r: 3 }} isAnimationActive={false} />
            {showPrev && hasPrevData && (
              <Line type="monotone" dataKey="prev_atm_iv_mid" name="prev_atm_iv_mid" stroke={COLOR_PREV_ATM} strokeWidth={1.5} strokeDasharray="6 3" dot={{ r: 3, fill: COLOR_PREV_ATM }} isAnimationActive={false} connectNulls />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {viewMode === 'atm_iv_history' && (
        <>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          {historyData.length < 5 ? (
            <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
              ATM IV の履歴データが蓄積中です（現在 {historyData.length} 件）
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={400}>
              <ComposedChart data={historyData} margin={CHART_MARGIN} style={{ backgroundColor: DARK_THEME.chartBg }}>
                <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
                <XAxis dataKey="date" tickFormatter={formatDayLabel} axisLine={{ stroke: DARK_THEME.axisLine }} tickLine={{ stroke: DARK_THEME.axisLine }} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} tickMargin={16} height={60} interval="preserveStartEnd" />
                <YAxis yAxisId="left" domain={['dataMin - 2', 'dataMax + 2']} tickFormatter={(v: number) => `${v.toFixed(1)}%`} axisLine={{ stroke: COLOR_ATM_IV }} tickLine={{ stroke: COLOR_ATM_IV }} tick={{ fill: COLOR_ATM_IV, fontSize: 11 }} />
                <YAxis yAxisId="right" orientation="right" domain={['dataMin - 500', 'dataMax + 500']} tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(1)}K` : `${v}`} axisLine={{ stroke: COLOR_UNDERLYING }} tickLine={{ stroke: COLOR_UNDERLYING }} tick={{ fill: COLOR_UNDERLYING, fontSize: 11 }} />
                <RechartsTooltip
                  contentStyle={{ backgroundColor: DARK_THEME.tooltipBg, border: `1px solid ${DARK_THEME.tooltipBorder}`, borderRadius: 8 }}
                  labelFormatter={(label: string) => formatDayLabel(label)}
                  formatter={(value: number, name: string) => {
                    if (name === 'underlying') return [value.toLocaleString(undefined, { maximumFractionDigits: 0 }), '日経平均']
                    return [`${value.toFixed(2)}%`, 'ATM IV']
                  }}
                />
                <Legend
                  onClick={(e) => handleLegendClick(e.dataKey as string)}
                  formatter={(value: string, entry) => (
                    <span style={{ color: hiddenSeries.has(entry.dataKey as 'atm_iv_mid' | 'underlying') ? '#64748b' : DARK_THEME.textPrimary, fontSize: 11 }}>
                      {value === 'atm_iv_mid' ? 'ATM IV' : '日経平均'}
                    </span>
                  )}
                />
                <Line yAxisId="left" type="monotone" dataKey="atm_iv_mid" name="atm_iv_mid" stroke={COLOR_ATM_IV} strokeWidth={2} dot={false} connectNulls isAnimationActive={false} hide={isHidden('atm_iv_mid')} />
                <Line yAxisId="right" type="monotone" dataKey="underlying" name="underlying" stroke={COLOR_UNDERLYING} strokeWidth={1.5} strokeDasharray="4 2" dot={false} connectNulls isAnimationActive={false} hide={isHidden('underlying')} />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </>
      )}
    </div>
  )
}

// --- Tab 2: IV Smile ---

type SmileXMode = 'strike' | 'moneyness'
const SMILE_X_OPTIONS = [
  { mode: 'strike' as SmileXMode, label: '行使価格' },
  { mode: 'moneyness' as SmileXMode, label: 'ATM比 (%)' },
]

function IvSmileTab({ expiries, selectedExpiry, onExpiryChange }: {
  expiries: ExpiryData[]
  selectedExpiry: string
  onExpiryChange: (v: string) => void
}) {
  const [xMode, setXMode] = useState<SmileXMode>('strike')
  const [showAll, setShowAll] = useState(false)
  const [showPrev, setShowPrev] = useState(true)

  const expiry = expiries.find(e => e.expiry === selectedExpiry)
  const hasPrevIv = expiry?.strikes.some(s => s.prev_put_iv != null || s.prev_call_iv != null)

  const smileData = useMemo(() => {
    if (!expiry) return []
    const atm = expiry.atm_strike
    const dte = expiry.dte ?? 30
    const filterPct = dte > 90 ? 0.15 : 0.20

    return expiry.strikes
      .filter(s => {
        if (s.put_iv == null && s.call_iv == null) return false
        // IV quality filter
        const ivOk = (iv: number | null) => iv != null && iv > 0.5 && iv < 150
        if (!ivOk(s.put_iv) && !ivOk(s.call_iv)) return false
        if (!showAll) {
          const moneyness = Math.abs(s.strike - atm) / atm
          if (moneyness > filterPct) return false
          if ((s.put_oi ?? 0) === 0 && (s.call_oi ?? 0) === 0 && (s.put_volume ?? 0) === 0 && (s.call_volume ?? 0) === 0) return false
        }
        return true
      })
      .map(s => {
        const moneyness = ((s.strike - atm) / atm) * 100
        return {
          strike: s.strike,
          moneyness: Math.round(moneyness * 100) / 100,
          put_iv: s.put_iv,
          call_iv: s.call_iv,
          prev_put_iv: s.prev_put_iv,
          prev_call_iv: s.prev_call_iv,
        }
      })
  }, [expiry, showAll])

  const xKey = xMode === 'moneyness' ? 'moneyness' : 'strike'

  return (
    <div>
      {/* Skew summary */}
      {expiry && expiry.skew_25d_rr != null && (
        <div style={{ display: 'flex', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
          <div style={{ background: DARK_THEME.bgTertiary, borderRadius: 6, padding: '4px 10px' }}>
            <span style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>25D RR</span>{' '}
            <span style={{ color: DARK_THEME.textPrimary, fontSize: 13, fontWeight: 600 }} className="tabular-nums">
              {expiry.skew_25d_rr.toFixed(2)}pt
            </span>
            {expiry.prev_skew_25d_rr != null && (
              <> <DeltaSpan value={expiry.skew_25d_rr - expiry.prev_skew_25d_rr} suffix="pt" /></>
            )}
          </div>
          {expiry.skew_25d_butterfly != null && (
            <div style={{ background: DARK_THEME.bgTertiary, borderRadius: 6, padding: '4px 10px' }}>
              <span style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>25D Fly</span>{' '}
              <span style={{ color: DARK_THEME.textPrimary, fontSize: 13, fontWeight: 600 }} className="tabular-nums">
                {expiry.skew_25d_butterfly.toFixed(2)}pt
              </span>
            </div>
          )}
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Select
            value={selectedExpiry}
            onChange={onExpiryChange}
            style={{ width: 200 }}
            size="small"
            options={expiries.map(e => ({
              value: e.expiry,
              label: `${e.expiry}${e.dte != null ? ` (${e.dte}日)` : ''}`,
            }))}
          />
          <ViewModeButtonGroup options={SMILE_X_OPTIONS} currentMode={xMode} onChange={(m) => setXMode(m as SmileXMode)} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {hasPrevIv && (
            <Checkbox checked={showPrev} onChange={(e) => setShowPrev(e.target.checked)}>
              <span style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>前日スマイル</span>
            </Checkbox>
          )}
          <Checkbox checked={showAll} onChange={(e) => setShowAll(e.target.checked)}>
            <span style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>全行使価格</span>
          </Checkbox>
        </div>
      </div>

      {smileData.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>データがありません</div>
      ) : (
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={smileData} margin={CHART_MARGIN} style={{ backgroundColor: DARK_THEME.chartBg }}>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
            <XAxis
              dataKey={xKey}
              type="number"
              domain={['dataMin', 'dataMax']}
              tickFormatter={(v: number) => xMode === 'moneyness' ? `${v.toFixed(0)}%` : v >= 1000 ? `${(v / 1000).toFixed(0)}K` : `${v}`}
              axisLine={{ stroke: DARK_THEME.axisLine }}
              tickLine={{ stroke: DARK_THEME.axisLine }}
              tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            />
            <YAxis domain={['dataMin - 2', 'dataMax + 2']} tickFormatter={(v: number) => `${v.toFixed(0)}%`} axisLine={{ stroke: DARK_THEME.axisLine }} tickLine={{ stroke: DARK_THEME.axisLine }} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} />
            {expiry && xMode === 'strike' && (
              <ReferenceLine x={expiry.atm_strike} stroke={COLOR_ATM_LINE} strokeDasharray="6 3" label={{ value: 'ATM', position: 'top', fill: COLOR_ATM_LINE, fontSize: 11 }} />
            )}
            {xMode === 'moneyness' && (
              <ReferenceLine x={0} stroke={COLOR_ATM_LINE} strokeDasharray="6 3" label={{ value: 'ATM', position: 'top', fill: COLOR_ATM_LINE, fontSize: 11 }} />
            )}
            <RechartsTooltip
              contentStyle={{ backgroundColor: DARK_THEME.tooltipBg, border: `1px solid ${DARK_THEME.tooltipBorder}`, borderRadius: 8 }}
              labelFormatter={(label: number) => xMode === 'moneyness' ? `ATM${label >= 0 ? '+' : ''}${label.toFixed(1)}%` : `Strike: ${label.toLocaleString()}`}
              formatter={(value: number, name: string) => {
                const labels: Record<string, string> = { call_iv: 'Call IV', put_iv: 'Put IV', prev_call_iv: '前日 Call IV', prev_put_iv: '前日 Put IV' }
                return [`${value.toFixed(2)}%`, labels[name] ?? name]
              }}
            />
            <Legend formatter={(value: string) => {
              const labels: Record<string, string> = { call_iv: 'Call IV', put_iv: 'Put IV', prev_call_iv: '前日 Call IV', prev_put_iv: '前日 Put IV' }
              return <span style={{ color: DARK_THEME.textPrimary, fontSize: 11 }}>{labels[value] ?? value}</span>
            }} />
            <Line type="monotone" dataKey="call_iv" name="call_iv" stroke={COLOR_CALL} strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
            <Line type="monotone" dataKey="put_iv" name="put_iv" stroke={COLOR_PUT} strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
            {showPrev && hasPrevIv && (
              <>
                <Line type="monotone" dataKey="prev_call_iv" name="prev_call_iv" stroke={COLOR_PREV_CALL} strokeWidth={1.5} strokeDasharray="6 3" dot={false} connectNulls isAnimationActive={false} />
                <Line type="monotone" dataKey="prev_put_iv" name="prev_put_iv" stroke={COLOR_PREV_PUT} strokeWidth={1.5} strokeDasharray="6 3" dot={false} connectNulls isAnimationActive={false} />
              </>
            )}
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

// --- Tab 3: Open Interest ---

type OiViewMode = 'level' | 'change'
const OI_VIEW_OPTIONS = [
  { mode: 'level' as OiViewMode, label: '水準' },
  { mode: 'change' as OiViewMode, label: '前日差' },
]

function OpenInterestTab({ expiries, selectedExpiry, onExpiryChange }: {
  expiries: ExpiryData[]
  selectedExpiry: string
  onExpiryChange: (v: string) => void
}) {
  const [viewMode, setViewMode] = useState<OiViewMode>('level')
  const expiry = expiries.find(e => e.expiry === selectedExpiry)
  const hasChange = expiry?.strikes.some(s => s.oi_change_put != null || s.oi_change_call != null)

  const oiData = useMemo(() => {
    if (!expiry) return []
    return expiry.strikes
      .filter(s => {
        if (viewMode === 'level') return s.put_oi != null || s.call_oi != null
        return s.oi_change_put != null || s.oi_change_call != null
      })
      .map(s => ({
        strike: s.strike,
        call_oi: s.call_oi ?? 0,
        neg_put_oi: s.put_oi != null ? -s.put_oi : 0,
        call_oi_change: s.oi_change_call ?? 0,
        neg_put_oi_change: s.oi_change_put != null ? -s.oi_change_put : 0,
      }))
  }, [expiry, viewMode])

  // Find max OI strike
  const maxOiStrike = useMemo(() => {
    if (!expiry) return null
    let maxOi = 0
    let maxStrike: number | null = null
    for (const s of expiry.strikes) {
      const total = (s.call_oi ?? 0) + (s.put_oi ?? 0)
      if (total > maxOi) { maxOi = total; maxStrike = s.strike }
    }
    return maxStrike
  }, [expiry])

  // P/C ratio
  const totalCallOi = expiry?.total_call_oi ?? 0
  const totalPutOi = expiry?.total_put_oi ?? 0
  const pcRatio = totalCallOi > 0 ? (totalPutOi / totalCallOi).toFixed(2) : 'N/A'

  return (
    <div>
      {/* OI summary */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
        <div style={{ background: DARK_THEME.bgTertiary, borderRadius: 6, padding: '4px 10px' }}>
          <span style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>Call OI</span>{' '}
          <span style={{ color: COLOR_CALL, fontSize: 13, fontWeight: 600 }} className="tabular-nums">{fmtK(totalCallOi)}</span>
          {expiry?.prev_total_call_oi != null && totalCallOi > 0 && (
            <> <DeltaSpan value={totalCallOi - expiry.prev_total_call_oi} decimals={0} /></>
          )}
        </div>
        <div style={{ background: DARK_THEME.bgTertiary, borderRadius: 6, padding: '4px 10px' }}>
          <span style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>Put OI</span>{' '}
          <span style={{ color: COLOR_PUT, fontSize: 13, fontWeight: 600 }} className="tabular-nums">{fmtK(totalPutOi)}</span>
          {expiry?.prev_total_put_oi != null && totalPutOi > 0 && (
            <> <DeltaSpan value={totalPutOi - expiry.prev_total_put_oi} decimals={0} /></>
          )}
        </div>
        <div style={{ background: DARK_THEME.bgTertiary, borderRadius: 6, padding: '4px 10px' }}>
          <span style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>P/C比</span>{' '}
          <span style={{ color: DARK_THEME.textPrimary, fontSize: 13, fontWeight: 600 }} className="tabular-nums">{pcRatio}</span>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Select
            value={selectedExpiry}
            onChange={onExpiryChange}
            style={{ width: 200 }}
            size="small"
            options={expiries.map(e => ({
              value: e.expiry,
              label: `${e.expiry}${e.dte != null ? ` (${e.dte}日)` : ''}`,
            }))}
          />
          {hasChange && (
            <ViewModeButtonGroup options={OI_VIEW_OPTIONS} currentMode={viewMode} onChange={(m) => setViewMode(m as OiViewMode)} />
          )}
        </div>
      </div>

      {oiData.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>建玉データがありません</div>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={400}>
            <ComposedChart data={oiData} margin={CHART_MARGIN} stackOffset="sign" style={{ backgroundColor: DARK_THEME.chartBg }}>
              <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
              <XAxis dataKey="strike" type="number" domain={['dataMin', 'dataMax']} tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}K` : `${v}`} axisLine={{ stroke: DARK_THEME.axisLine }} tickLine={{ stroke: DARK_THEME.axisLine }} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} />
              <YAxis tickFormatter={(v: number) => `${Math.abs(v).toLocaleString()}`} axisLine={{ stroke: DARK_THEME.axisLine }} tickLine={{ stroke: DARK_THEME.axisLine }} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} />
              {expiry && (
                <ReferenceLine x={expiry.atm_strike} stroke={COLOR_ATM_LINE} strokeDasharray="6 3" label={{ value: 'ATM', position: 'top', fill: COLOR_ATM_LINE, fontSize: 11 }} />
              )}
              {viewMode === 'level' && maxOiStrike && maxOiStrike !== expiry?.atm_strike && (
                <ReferenceLine x={maxOiStrike} stroke={COLOR_UNDERLYING} strokeDasharray="4 3" label={{ value: 'Max OI', position: 'top', fill: COLOR_UNDERLYING, fontSize: 10 }} />
              )}
              <ReferenceLine y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />
              <RechartsTooltip
                contentStyle={{ backgroundColor: DARK_THEME.tooltipBg, border: `1px solid ${DARK_THEME.tooltipBorder}`, borderRadius: 8 }}
                labelFormatter={(label: number) => `Strike: ${label.toLocaleString()}`}
                formatter={(value: number, name: string) => {
                  const labels: Record<string, string> = {
                    call_oi: 'Call OI', neg_put_oi: 'Put OI',
                    call_oi_change: 'Call OI 変化', neg_put_oi_change: 'Put OI 変化',
                  }
                  return [Math.abs(value).toLocaleString(), labels[name] ?? name]
                }}
              />
              <Legend formatter={(value: string) => {
                const labels: Record<string, string> = {
                  call_oi: 'Call 建玉', neg_put_oi: 'Put 建玉',
                  call_oi_change: 'Call 建玉変化', neg_put_oi_change: 'Put 建玉変化',
                }
                return <span style={{ color: DARK_THEME.textPrimary, fontSize: 11 }}>{labels[value] ?? value}</span>
              }} />
              {viewMode === 'level' && (
                <>
                  <Bar dataKey="call_oi" name="call_oi" fill={COLOR_CALL} stackId="a" isAnimationActive={false} />
                  <Bar dataKey="neg_put_oi" name="neg_put_oi" fill={COLOR_PUT} stackId="a" isAnimationActive={false} />
                </>
              )}
              {viewMode === 'change' && (
                <>
                  <Bar dataKey="call_oi_change" name="call_oi_change" fill={COLOR_CALL} stackId="a" isAnimationActive={false} />
                  <Bar dataKey="neg_put_oi_change" name="neg_put_oi_change" fill={COLOR_PUT} stackId="a" isAnimationActive={false} />
                </>
              )}
            </ComposedChart>
          </ResponsiveContainer>
          <div style={{ textAlign: 'center', color: DARK_THEME.textTertiary, fontSize: 10, marginTop: 4 }}>
            ※ 視覚上の区別のため Put 建玉をマイナス側に表示しています
          </div>
        </>
      )}
    </div>
  )
}

// --- Tab 4: Volume ---
function VolumeTab({ expiries, selectedExpiry, onExpiryChange, aggregate }: {
  expiries: ExpiryData[]
  selectedExpiry: string
  onExpiryChange: (v: string) => void
  aggregate: AggregateData | null
}) {
  const expiry = expiries.find(e => e.expiry === selectedExpiry)

  const totalCallVol = expiry?.total_call_volume ?? 0
  const totalPutVol = expiry?.total_put_volume ?? 0
  const totalVol = totalCallVol + totalPutVol
  const pcRatio = totalCallVol > 0 ? (totalPutVol / totalCallVol).toFixed(2) : 'N/A'

  const volData = useMemo(() => {
    if (!expiry) return []
    return expiry.strikes
      .filter(s => s.put_volume != null || s.call_volume != null)
      .map(s => ({
        strike: s.strike,
        call_volume: s.call_volume ?? 0,
        neg_put_volume: s.put_volume != null ? -s.put_volume : 0,
      }))
  }, [expiry])

  return (
    <div>
      {/* Volume summary */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
        <div style={{ background: DARK_THEME.bgTertiary, borderRadius: 6, padding: '4px 10px' }}>
          <span style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>Call Vol</span>{' '}
          <span style={{ color: COLOR_CALL, fontSize: 13, fontWeight: 600 }} className="tabular-nums">{fmtK(totalCallVol)}</span>
        </div>
        <div style={{ background: DARK_THEME.bgTertiary, borderRadius: 6, padding: '4px 10px' }}>
          <span style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>Put Vol</span>{' '}
          <span style={{ color: COLOR_PUT, fontSize: 13, fontWeight: 600 }} className="tabular-nums">{fmtK(totalPutVol)}</span>
        </div>
        <div style={{ background: DARK_THEME.bgTertiary, borderRadius: 6, padding: '4px 10px' }}>
          <span style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>合計</span>{' '}
          <span style={{ color: DARK_THEME.textPrimary, fontSize: 13, fontWeight: 600 }} className="tabular-nums">{fmtK(totalVol)}</span>
        </div>
        <div style={{ background: DARK_THEME.bgTertiary, borderRadius: 6, padding: '4px 10px' }}>
          <span style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>P/C比</span>{' '}
          <span style={{ color: DARK_THEME.textPrimary, fontSize: 13, fontWeight: 600 }} className="tabular-nums">{pcRatio}</span>
        </div>
        {aggregate?.volume_5d_avg != null && (
          <div style={{ background: DARK_THEME.bgTertiary, borderRadius: 6, padding: '4px 10px' }}>
            <span style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>5日平均</span>{' '}
            <span style={{ color: DARK_THEME.textPrimary, fontSize: 13, fontWeight: 600 }} className="tabular-nums">{fmtK(aggregate.volume_5d_avg)}</span>
          </div>
        )}
      </div>

      <div style={{ marginBottom: 8 }}>
        <Select
          value={selectedExpiry}
          onChange={onExpiryChange}
          style={{ width: 200 }}
          size="small"
          options={expiries.map(e => ({
            value: e.expiry,
            label: `${e.expiry}${e.dte != null ? ` (${e.dte}日)` : ''}`,
          }))}
        />
      </div>

      {volData.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>出来高データがありません</div>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={400}>
            <ComposedChart data={volData} margin={CHART_MARGIN} stackOffset="sign" style={{ backgroundColor: DARK_THEME.chartBg }}>
              <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
              <XAxis dataKey="strike" type="number" domain={['dataMin', 'dataMax']} tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}K` : `${v}`} axisLine={{ stroke: DARK_THEME.axisLine }} tickLine={{ stroke: DARK_THEME.axisLine }} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} />
              <YAxis tickFormatter={(v: number) => `${Math.abs(v).toLocaleString()}`} axisLine={{ stroke: DARK_THEME.axisLine }} tickLine={{ stroke: DARK_THEME.axisLine }} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} />
              {expiry && (
                <ReferenceLine x={expiry.atm_strike} stroke={COLOR_ATM_LINE} strokeDasharray="6 3" label={{ value: 'ATM', position: 'top', fill: COLOR_ATM_LINE, fontSize: 11 }} />
              )}
              <ReferenceLine y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />
              <RechartsTooltip
                contentStyle={{ backgroundColor: DARK_THEME.tooltipBg, border: `1px solid ${DARK_THEME.tooltipBorder}`, borderRadius: 8 }}
                labelFormatter={(label: number) => `Strike: ${label.toLocaleString()}`}
                formatter={(value: number, name: string) => [Math.abs(value).toLocaleString(), name === 'call_volume' ? 'Call Volume' : 'Put Volume']}
              />
              <Legend formatter={(value: string) => <span style={{ color: DARK_THEME.textPrimary, fontSize: 11 }}>{value === 'call_volume' ? 'Call 出来高' : 'Put 出来高'}</span>} />
              <Bar dataKey="call_volume" name="call_volume" fill={COLOR_CALL} stackId="a" isAnimationActive={false} />
              <Bar dataKey="neg_put_volume" name="neg_put_volume" fill={COLOR_PUT} stackId="a" isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
          <div style={{ textAlign: 'center', color: DARK_THEME.textTertiary, fontSize: 10, marginTop: 4 }}>
            ※ 視覚上の区別のため Put 出来高をマイナス側に表示しています
          </div>
        </>
      )}
    </div>
  )
}

// --- Tab 5: Settlement Table ---
function SettlementTableTab({ expiries, selectedExpiry, onExpiryChange }: {
  expiries: ExpiryData[]
  selectedExpiry: string
  onExpiryChange: (v: string) => void
}) {
  const expiry = expiries.find(e => e.expiry === selectedExpiry)
  const hasPrev = expiry?.strikes.some(s => s.prev_put_iv != null || s.prev_call_iv != null)
  const hasOiChange = expiry?.strikes.some(s => s.oi_change_put != null || s.oi_change_call != null)

  const renderDelta = (val: number | null) => {
    if (val == null) return <span style={{ color: DARK_THEME.textTertiary }}>N/A</span>
    const color = val > 0 ? COLOR_POSITIVE : val < 0 ? COLOR_NEGATIVE : DARK_THEME.textSecondary
    const sign = val > 0 ? '+' : ''
    return <span style={{ color, fontSize: 11 }} className="tabular-nums">{sign}{val.toFixed(2)}</span>
  }

  const renderOiDelta = (val: number | null) => {
    if (val == null) return <span style={{ color: DARK_THEME.textTertiary }}>N/A</span>
    if (val === 0) return <span style={{ color: DARK_THEME.textSecondary }} className="tabular-nums">0</span>
    const color = val > 0 ? COLOR_POSITIVE : COLOR_NEGATIVE
    const sign = val > 0 ? '+' : ''
    return <span style={{ color, fontSize: 11 }} className="tabular-nums">{sign}{val.toLocaleString()}</span>
  }

  const renderNullable = (val: number | null, fmt: (v: number) => string) => {
    if (val == null) return <span style={{ color: DARK_THEME.textTertiary }}>N/A</span>
    return <span className="tabular-nums">{fmt(val)}</span>
  }

  const columns: any[] = [
    {
      title: '行使価格',
      dataIndex: 'strike',
      key: 'strike',
      fixed: 'left',
      width: 90,
      render: (val: number, record: StrikeData & { isAtm: boolean }) => (
        <span style={{ fontWeight: record.isAtm ? 700 : 400, color: record.isAtm ? COLOR_ATM_LINE : undefined }}>
          {val.toLocaleString()}
        </span>
      ),
      sorter: (a: StrikeData, b: StrikeData) => a.strike - b.strike,
      defaultSortOrder: 'ascend' as const,
    },
    {
      title: 'Put 清算値',
      dataIndex: 'put_settlement',
      key: 'put_settlement',
      width: 80,
      render: (val: number | null) => renderNullable(val, v => v.toLocaleString(undefined, { maximumFractionDigits: 1 })),
      align: 'right' as const,
      sorter: (a: StrikeData, b: StrikeData) => (a.put_settlement ?? 0) - (b.put_settlement ?? 0),
    },
    {
      title: 'Put IV',
      dataIndex: 'put_iv',
      key: 'put_iv',
      width: 70,
      render: (val: number | null) => renderNullable(val, v => `${v.toFixed(2)}%`),
      align: 'right' as const,
      sorter: (a: StrikeData, b: StrikeData) => (a.put_iv ?? 0) - (b.put_iv ?? 0),
    },
    ...(hasPrev ? [{
      title: 'Put IV Chg',
      key: 'put_iv_chg',
      width: 75,
      render: (_: unknown, record: StrikeData) => {
        if (record.put_iv == null || record.prev_put_iv == null) return <span style={{ color: DARK_THEME.textTertiary }}>N/A</span>
        return renderDelta(record.put_iv - record.prev_put_iv)
      },
      align: 'right' as const,
      sorter: (a: StrikeData, b: StrikeData) => {
        const aChg = (a.put_iv != null && a.prev_put_iv != null) ? a.put_iv - a.prev_put_iv : 0
        const bChg = (b.put_iv != null && b.prev_put_iv != null) ? b.put_iv - b.prev_put_iv : 0
        return aChg - bChg
      },
    }] : []),
    {
      title: 'Call 清算値',
      dataIndex: 'call_settlement',
      key: 'call_settlement',
      width: 80,
      render: (val: number | null) => renderNullable(val, v => v.toLocaleString(undefined, { maximumFractionDigits: 1 })),
      align: 'right' as const,
      sorter: (a: StrikeData, b: StrikeData) => (a.call_settlement ?? 0) - (b.call_settlement ?? 0),
    },
    {
      title: 'Call IV',
      dataIndex: 'call_iv',
      key: 'call_iv',
      width: 70,
      render: (val: number | null) => renderNullable(val, v => `${v.toFixed(2)}%`),
      align: 'right' as const,
      sorter: (a: StrikeData, b: StrikeData) => (a.call_iv ?? 0) - (b.call_iv ?? 0),
    },
    ...(hasPrev ? [{
      title: 'Call IV Chg',
      key: 'call_iv_chg',
      width: 75,
      render: (_: unknown, record: StrikeData) => {
        if (record.call_iv == null || record.prev_call_iv == null) return <span style={{ color: DARK_THEME.textTertiary }}>N/A</span>
        return renderDelta(record.call_iv - record.prev_call_iv)
      },
      align: 'right' as const,
      sorter: (a: StrikeData, b: StrikeData) => {
        const aChg = (a.call_iv != null && a.prev_call_iv != null) ? a.call_iv - a.prev_call_iv : 0
        const bChg = (b.call_iv != null && b.prev_call_iv != null) ? b.call_iv - b.prev_call_iv : 0
        return aChg - bChg
      },
    }] : []),
    {
      title: 'Put OI',
      dataIndex: 'put_oi',
      key: 'put_oi',
      width: 70,
      render: (val: number | null) => renderNullable(val, v => v.toLocaleString()),
      align: 'right' as const,
      sorter: (a: StrikeData, b: StrikeData) => (a.put_oi ?? 0) - (b.put_oi ?? 0),
    },
    ...(hasOiChange ? [{
      title: 'Put OI Chg',
      key: 'put_oi_chg',
      width: 75,
      dataIndex: 'oi_change_put',
      render: (val: number | null) => renderOiDelta(val),
      align: 'right' as const,
      sorter: (a: StrikeData, b: StrikeData) => (a.oi_change_put ?? 0) - (b.oi_change_put ?? 0),
    }] : []),
    {
      title: 'Call OI',
      dataIndex: 'call_oi',
      key: 'call_oi',
      width: 70,
      render: (val: number | null) => renderNullable(val, v => v.toLocaleString()),
      align: 'right' as const,
      sorter: (a: StrikeData, b: StrikeData) => (a.call_oi ?? 0) - (b.call_oi ?? 0),
    },
    ...(hasOiChange ? [{
      title: 'Call OI Chg',
      key: 'call_oi_chg',
      width: 80,
      dataIndex: 'oi_change_call',
      render: (val: number | null) => renderOiDelta(val),
      align: 'right' as const,
      sorter: (a: StrikeData, b: StrikeData) => (a.oi_change_call ?? 0) - (b.oi_change_call ?? 0),
    }] : []),
    {
      title: 'Put Vol',
      dataIndex: 'put_volume',
      key: 'put_volume',
      width: 65,
      render: (val: number | null) => renderNullable(val, v => v.toLocaleString()),
      align: 'right' as const,
      sorter: (a: StrikeData, b: StrikeData) => (a.put_volume ?? 0) - (b.put_volume ?? 0),
    },
    {
      title: 'Call Vol',
      dataIndex: 'call_volume',
      key: 'call_volume',
      width: 65,
      render: (val: number | null) => renderNullable(val, v => v.toLocaleString()),
      align: 'right' as const,
      sorter: (a: StrikeData, b: StrikeData) => (a.call_volume ?? 0) - (b.call_volume ?? 0),
    },
  ]

  const tableData = useMemo(() => {
    if (!expiry) return []
    return expiry.strikes.map(s => ({
      ...s,
      key: s.strike,
      isAtm: s.strike === expiry.atm_strike,
    }))
  }, [expiry])

  // ATM-centered default page
  const defaultPage = useMemo(() => {
    if (!expiry || tableData.length === 0) return 1
    const atmIdx = tableData.findIndex(s => s.isAtm)
    if (atmIdx < 0) return 1
    return Math.floor(atmIdx / 20) + 1
  }, [expiry, tableData])

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Select
          value={selectedExpiry}
          onChange={onExpiryChange}
          style={{ width: 200 }}
          size="small"
          options={expiries.map(e => ({
            value: e.expiry,
            label: `${e.expiry}${e.dte != null ? ` (${e.dte}日)` : ''}`,
          }))}
        />
      </div>

      <Table
        columns={columns}
        dataSource={tableData}
        size="small"
        pagination={{ pageSize: 20, showSizeChanger: true, pageSizeOptions: ['20', '50', '100'], defaultCurrent: defaultPage }}
        scroll={{ x: 900 }}
        rowClassName={(record) => {
          const r = record as StrikeData & { isAtm: boolean }
          if (r.isAtm) return 'atm-row'
          if (r.quality === 'distant') return 'distant-row'
          return ''
        }}
        style={{ marginTop: 8 }}
      />

      <style>{`
        .atm-row td {
          background-color: rgba(168, 85, 247, 0.15) !important;
        }
        .distant-row td {
          color: ${DARK_THEME.textTertiary} !important;
        }
      `}</style>
    </div>
  )
}


// ===== Main Component =====

export default function Nikkei225OptionsChart() {
  const { data: apiData, isLoading, error } = useNikkei225OptionsData()
  const [activeTab, setActiveTab] = useState('atm_iv')
  const [selectedExpiry, setSelectedExpiry] = useState<string>('')

  // Initialize selected expiry to nearest
  const expiries = apiData?.data?.expiries ?? []
  const effectiveExpiry = selectedExpiry || (expiries.length > 0 ? expiries[0].expiry : '')

  if (isLoading) {
    return (
      <ChartContainer title="日経225オプション" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (error || !apiData?.data || expiries.length === 0) {
    return (
      <ChartContainer title="日経225オプション" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  const { underlying_price, prev_underlying_price, atm_iv_history, aggregate } = apiData.data
  const latest = apiData.latest
  const nearestExpiry = expiries[0]

  // Computed deltas for summary
  const underlyingChg = (prev_underlying_price != null) ? underlying_price - prev_underlying_price : null
  const underlyingChgPct = (prev_underlying_price != null && prev_underlying_price > 0) ? ((underlying_price - prev_underlying_price) / prev_underlying_price) * 100 : null
  const atmIvChg = (nearestExpiry.prev_atm_iv_mid != null && nearestExpiry.atm_iv_mid != null) ? nearestExpiry.atm_iv_mid - nearestExpiry.prev_atm_iv_mid : null

  const aggTotalOi = aggregate ? aggregate.total_call_oi + aggregate.total_put_oi : null
  const prevAggTotalOi = aggregate ? aggregate.prev_total_call_oi + aggregate.prev_total_put_oi : null
  const aggOiChg = (aggTotalOi != null && prevAggTotalOi != null && prevAggTotalOi > 0) ? aggTotalOi - prevAggTotalOi : null
  const aggTotalVol = aggregate ? aggregate.total_call_volume + aggregate.total_put_volume : null

  return (
    <ChartContainer
      title="日経225オプション"
      dataSource="JPX / OSE"
      sourceUrl="https://www.jpx.co.jp/markets/derivatives/settlement-price/index.html"
      showPeriodSelector={false}
      handbookId="nikkei225-options"
    >
      {/* Enhanced summary card */}
      <div style={BOX_STYLE}>
        {/* Underlying */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
          <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>日経225</Text>
          <Text style={{ color: COLOR_UNDERLYING, fontSize: 16, fontWeight: 700 }} className="tabular-nums">
            {fmtNum(underlying_price, 0)}
          </Text>
          {underlyingChg != null && (
            <DeltaSpan value={underlyingChg} suffix="" decimals={0} />
          )}
          {underlyingChgPct != null && (
            <span style={{ color: underlyingChgPct >= 0 ? COLOR_POSITIVE : COLOR_NEGATIVE, fontSize: 10 }} className="tabular-nums">
              {underlyingChgPct >= 0 ? '+' : ''}{underlyingChgPct.toFixed(1)}%
            </span>
          )}
        </div>

        {/* ATM IV (nearest) */}
        {nearestExpiry.atm_iv_mid != null && (
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>
              ATM IV ({nearestExpiry.contract_month.slice(2)})
            </Text>
            <Text style={{ color: COLOR_ATM_IV, fontSize: 16, fontWeight: 700 }} className="tabular-nums">
              {nearestExpiry.atm_iv_mid.toFixed(2)}%
            </Text>
            <DeltaSpan value={atmIvChg} suffix="pt" />
          </div>
        )}

        {/* 25D RR */}
        {nearestExpiry.skew_25d_rr != null && (
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>25D RR</Text>
            <Text style={{ color: DARK_THEME.textPrimary, fontSize: 14, fontWeight: 600 }} className="tabular-nums">
              {nearestExpiry.skew_25d_rr.toFixed(2)}pt
            </Text>
            {nearestExpiry.prev_skew_25d_rr != null && (
              <DeltaSpan value={nearestExpiry.skew_25d_rr - nearestExpiry.prev_skew_25d_rr} suffix="pt" />
            )}
          </div>
        )}

        {/* OI Total */}
        {aggTotalOi != null && aggTotalOi > 0 && (
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>OI合計</Text>
            <Text style={{ color: DARK_THEME.textPrimary, fontSize: 14, fontWeight: 600 }} className="tabular-nums">
              {fmtK(aggTotalOi)}
            </Text>
            {aggOiChg != null && <DeltaSpan value={aggOiChg} decimals={0} />}
          </div>
        )}

        {/* Volume */}
        {aggTotalVol != null && aggTotalVol > 0 && (
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>出来高</Text>
            <Text style={{ color: DARK_THEME.textPrimary, fontSize: 14, fontWeight: 600 }} className="tabular-nums">
              {fmtK(aggTotalVol)}
            </Text>
            {aggregate?.volume_5d_avg != null && (
              <span style={{ color: DARK_THEME.textTertiary, fontSize: 10 }}>
                (5d avg {fmtK(aggregate.volume_5d_avg)})
              </span>
            )}
          </div>
        )}

        {/* Date & DTE */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginLeft: 'auto' }}>
          {nearestExpiry.dte != null && (
            <>
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>DTE</Text>
              <Text style={{ color: DARK_THEME.textPrimary, fontSize: 13, fontWeight: 600 }} className="tabular-nums">
                {nearestExpiry.dte}
              </Text>
            </>
          )}
          {latest && (
            <Text style={{ color: DARK_THEME.textTertiary, fontSize: 10 }}>({latest.date})</Text>
          )}
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              size="small"
              onClick={() => window.open('/compare?s=nikkei225_vi&s=vix', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>
      </div>

      {/* Tabs */}
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        style={{ marginTop: 4 }}
        items={[
          {
            key: 'atm_iv',
            label: 'ATM IV',
            children: (
              <AtmIvTab
                expiries={expiries}
                atmIvHistory={atm_iv_history}
                selectedExpiry={effectiveExpiry}
                onExpiryChange={setSelectedExpiry}
              />
            ),
          },
          {
            key: 'iv_smile',
            label: 'IVスマイル',
            children: (
              <IvSmileTab
                expiries={expiries}
                selectedExpiry={effectiveExpiry}
                onExpiryChange={setSelectedExpiry}
              />
            ),
          },
          {
            key: 'open_interest',
            label: '建玉',
            children: (
              <OpenInterestTab
                expiries={expiries}
                selectedExpiry={effectiveExpiry}
                onExpiryChange={setSelectedExpiry}
              />
            ),
          },
          {
            key: 'volume',
            label: '出来高',
            children: (
              <VolumeTab
                expiries={expiries}
                selectedExpiry={effectiveExpiry}
                onExpiryChange={setSelectedExpiry}
                aggregate={aggregate}
              />
            ),
          },
          {
            key: 'table',
            label: '一覧',
            children: (
              <SettlementTableTab
                expiries={expiries}
                selectedExpiry={effectiveExpiry}
                onExpiryChange={setSelectedExpiry}
              />
            ),
          },
        ]}
      />
    </ChartContainer>
  )
}
