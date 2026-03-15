import { useState, useMemo } from 'react'
import { Tabs, Tooltip, Button } from 'antd'
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

// Export colors (warm tones)
const COLORS = {
  export_pipeline: '#f59e0b',   // Amber
  export_lng: '#ef4444',        // Red
  export_re_export: '#f97316',  // Orange
  import_pipeline: '#3b82f6',   // Blue
  import_lng: '#06b6d4',        // Cyan
  net_export: '#22c55e',        // Green (line)
  export_total: '#f59e0b',
  import_total: '#3b82f6',
}

interface TradeItem {
  date: string
  export_total: number | null
  export_pipeline: number | null
  export_lng: number | null
  export_re_export: number | null
  import_total: number | null
  import_pipeline: number | null
  import_lng: number | null
  net_export: number | null
}

interface TradeResponse {
  data: TradeItem[]
  latest: TradeItem | null
  next_release: { date: string; label?: string } | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

// For breakdown view: imports shown as negative
interface BreakdownItem extends TradeItem {
  neg_import_pipeline: number | null
  neg_import_lng: number | null
}

type ViewMode = 'breakdown' | 'total'
const VIEW_MODE_OPTIONS = [
  { mode: 'breakdown' as ViewMode, label: '内訳' },
  { mode: 'total' as ViewMode, label: '合計' },
]

type ActiveTab = 'timeseries'

type SeriesKey =
  | 'export_pipeline' | 'export_lng' | 'export_re_export'
  | 'neg_import_pipeline' | 'neg_import_lng'
  | 'net_export' | 'export_total' | 'import_total'

interface SeriesConfig {
  key: string
  label: string
  color: string
}

const EXPORT_SERIES: SeriesConfig[] = [
  { key: 'export_pipeline', label: 'パイプライン輸出', color: COLORS.export_pipeline },
  { key: 'export_lng', label: 'LNG輸出', color: COLORS.export_lng },
  { key: 'export_re_export', label: '再輸出', color: COLORS.export_re_export },
]

const IMPORT_SERIES: SeriesConfig[] = [
  { key: 'neg_import_pipeline', label: 'パイプライン輸入', color: COLORS.import_pipeline },
  { key: 'neg_import_lng', label: 'LNG輸入', color: COLORS.import_lng },
]

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function BreakdownTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatMonthLabel(String(label))
  const dp = payload[0]?.payload as BreakdownItem | undefined
  if (!dp) return null

  const fmtBcf = (v: number) => `${v >= 0 ? '' : ''}${v.toLocaleString(undefined, { maximumFractionDigits: 1 })} BCF`

  return (
    <div style={{
      backgroundColor: DARK_THEME.tooltipBg,
      border: `1px solid ${DARK_THEME.tooltipBorder}`,
      borderRadius: 8,
      padding: '12px 16px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
    }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>{formattedLabel}</div>

      {/* Export section */}
      <div style={{ fontSize: 11, color: DARK_THEME.textSecondary, marginBottom: 2 }}>輸出</div>
      {EXPORT_SERIES.map(({ key, label: sLabel, color }) => {
        if (hiddenSeries.has(key)) return null
        const val = dp[key as keyof BreakdownItem] as number | null
        if (val == null) return null
        return (
          <div key={key} style={{ display: 'flex', justifyContent: 'space-between', gap: 16, marginBottom: 2, fontSize: 12 }}>
            <span style={{ display: 'flex', alignItems: 'center' }}>
              <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 2, backgroundColor: color, marginRight: 6 }} />
              <span style={{ color: DARK_THEME.textPrimary }}>{sLabel}</span>
            </span>
            <span style={{ color, fontWeight: 500 }}>{fmtBcf(val)}</span>
          </div>
        )
      })}

      {/* Import section */}
      <div style={{ fontSize: 11, color: DARK_THEME.textSecondary, marginTop: 4, marginBottom: 2 }}>輸入</div>
      {IMPORT_SERIES.map(({ key, label: sLabel, color }) => {
        if (hiddenSeries.has(key)) return null
        const val = dp[key as keyof BreakdownItem] as number | null
        if (val == null) return null
        return (
          <div key={key} style={{ display: 'flex', justifyContent: 'space-between', gap: 16, marginBottom: 2, fontSize: 12 }}>
            <span style={{ display: 'flex', alignItems: 'center' }}>
              <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 2, backgroundColor: color, marginRight: 6 }} />
              <span style={{ color: DARK_THEME.textPrimary }}>{sLabel}</span>
            </span>
            <span style={{ color, fontWeight: 500 }}>{fmtBcf(Math.abs(val))}</span>
          </div>
        )
      })}

      {/* Net export */}
      {!hiddenSeries.has('net_export') && dp.net_export != null && (
        <div style={{ borderTop: '1px solid #475569', marginTop: 4, paddingTop: 4, display: 'flex', justifyContent: 'space-between', gap: 16, fontSize: 13 }}>
          <span style={{ color: COLORS.net_export, fontWeight: 600 }}>純輸出</span>
          <span style={{ color: dp.net_export >= 0 ? '#22c55e' : '#ef4444', fontWeight: 600 }}>{fmtBcf(dp.net_export)}</span>
        </div>
      )}
    </div>
  )
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function TotalTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatMonthLabel(String(label))
  const dp = payload[0]?.payload as TradeItem | undefined
  if (!dp) return null

  const fmtBcf = (v: number) => `${v.toLocaleString(undefined, { maximumFractionDigits: 1 })} BCF`

  return (
    <div style={{
      backgroundColor: DARK_THEME.tooltipBg,
      border: `1px solid ${DARK_THEME.tooltipBorder}`,
      borderRadius: 8,
      padding: '12px 16px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
    }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>{formattedLabel}</div>
      {!hiddenSeries.has('export_total') && dp.export_total != null && (
        <div style={{ color: COLORS.export_total, fontSize: 13, marginBottom: 3 }}>
          輸出合計: {fmtBcf(dp.export_total)}
        </div>
      )}
      {!hiddenSeries.has('import_total') && dp.import_total != null && (
        <div style={{ color: COLORS.import_total, fontSize: 13, marginBottom: 3 }}>
          輸入合計: {fmtBcf(dp.import_total)}
        </div>
      )}
      {!hiddenSeries.has('net_export') && dp.net_export != null && (
        <div style={{ borderTop: '1px solid #475569', marginTop: 4, paddingTop: 4, color: dp.net_export >= 0 ? '#22c55e' : '#ef4444', fontSize: 13, fontWeight: 600 }}>
          純輸出: {fmtBcf(dp.net_export)}
        </div>
      )}
    </div>
  )
}


export default function UsNaturalGasTradeChart() {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)
  const [viewMode, setViewMode] = useState<ViewMode>('breakdown')
  const [activeTab, setActiveTab] = useState<ActiveTab>('timeseries')
  const { hiddenSeries, handleLegendClick, isHidden } = useHiddenSeries<SeriesKey>()

  const { data: response } = useQuery<TradeResponse>({
    queryKey: ['natural-gas-trade'],
    queryFn: async () => {
      const res = await axios.get('/api/market/natural-gas-trade')
      return res.data
    },
    staleTime: 1000 * 60 * 30,
  })

  // For breakdown view: create negative import values
  const breakdownData = useMemo(() => {
    if (!response?.data) return []
    return response.data.map(item => ({
      ...item,
      neg_import_pipeline: item.import_pipeline != null ? -item.import_pipeline : null,
      neg_import_lng: item.import_lng != null ? -item.import_lng : null,
    }))
  }, [response])

  const filteredBreakdown = useMemo(() => {
    if (!breakdownData.length) return []
    if (currentPeriod === 'all') return breakdownData
    const years = typeof currentPeriod === 'number' ? currentPeriod : 10
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return breakdownData.filter(d => d.date >= cutoffStr)
  }, [breakdownData, currentPeriod])

  const filteredTotal = useMemo(() => {
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

  return (
    <ChartContainer
      title="米国天然ガス輸出入"
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
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>輸出: </span>
            <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.export_total }}>
              {latest?.export_total != null ? `${latest.export_total.toLocaleString()} BCF` : '—'}
            </span>
          </div>
          <div>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>輸入: </span>
            <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.import_total }}>
              {latest?.import_total != null ? `${latest.import_total.toLocaleString()} BCF` : '—'}
            </span>
          </div>
          <div>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>純輸出: </span>
            <span style={{ fontSize: 18, fontWeight: 'bold', color: latest?.net_export != null && latest.net_export >= 0 ? '#22c55e' : '#ef4444' }}>
              {latest?.net_export != null ? `${latest.net_export >= 0 ? '+' : ''}${latest.net_export.toLocaleString()} BCF` : '—'}
            </span>
          </div>
        </div>
        {nextRelease && (
          <span style={{ fontSize: 11, color: TEXT_COLORS.secondary, whiteSpace: 'nowrap' }}>
            次回: {nextRelease.date}
          </span>
        )}
      </div>

      {/* Tabs */}
      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as ActiveTab)}
        style={{ marginTop: 8 }}
        items={[
          {
            key: 'timeseries',
            label: '時系列',
            children: (
              <>
                {/* ViewMode + データ比較ボタン */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <ViewModeButtonGroup
                    options={VIEW_MODE_OPTIONS}
                    currentMode={viewMode}
                    onChange={(m) => setViewMode(m as ViewMode)}
                  />
                  <Tooltip title="比較ページを開く">
                    <Button
                      icon={<AreaChartOutlined />}
                      onClick={() => window.open('/compare?s=us_natural_gas_trade_net', '_blank')}
                    >
                      データ比較
                    </Button>
                  </Tooltip>
                </div>

                <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                {/* 内訳ビュー: stackOffset="sign" で正(輸出)は上、負(輸入)は下にスタック */}
                {viewMode === 'breakdown' && (
                  <ResponsiveContainer width="100%" height={450}>
                    <ComposedChart data={filteredBreakdown} margin={CHART_MARGIN} stackOffset="sign">
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
                        domain={['auto', 'auto']}
                        tickFormatter={(v: number) => `${v.toFixed(0)}`}
                        stroke={DARK_THEME.textSecondary}
                        tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
                        width={55}
                        // label={{ value: 'BCF', position: 'top', offset: 8, style: { fill: DARK_THEME.textSecondary, fontSize: 10 } }}
                      />

                      <RechartsTooltip content={<BreakdownTooltip hiddenSeries={hiddenSeries} />} />
                      <ReferenceLine yAxisId="left" y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />

                      <Legend
                        wrapperStyle={{ paddingTop: 8 }}
                        onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)}
                        formatter={(value: string, entry: any) => (
                          <span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : DARK_THEME.textPrimary, fontSize: 12 }}>
                            {value}
                          </span>
                        )}
                      />

                      {/* Export bars (positive) + Import bars (negative) — all in one stackId */}
                      <Bar dataKey="export_pipeline" fill={COLORS.export_pipeline} fillOpacity={0.85} name="パイプライン輸出" yAxisId="left" stackId="a" isAnimationActive={false} hide={isHidden('export_pipeline')} />
                      <Bar dataKey="export_lng" fill={COLORS.export_lng} fillOpacity={0.85} name="LNG輸出" yAxisId="left" stackId="a" isAnimationActive={false} hide={isHidden('export_lng')} />
                      <Bar dataKey="export_re_export" fill={COLORS.export_re_export} fillOpacity={0.85} name="再輸出" yAxisId="left" stackId="a" isAnimationActive={false} hide={isHidden('export_re_export')} />
                      <Bar dataKey="neg_import_pipeline" fill={COLORS.import_pipeline} fillOpacity={0.85} name="パイプライン輸入" yAxisId="left" stackId="a" isAnimationActive={false} hide={isHidden('neg_import_pipeline')} />
                      <Bar dataKey="neg_import_lng" fill={COLORS.import_lng} fillOpacity={0.85} name="LNG輸入" yAxisId="left" stackId="a" isAnimationActive={false} hide={isHidden('neg_import_lng')} />

                      {/* Net export line */}
                      <Line
                        type="monotone"
                        dataKey="net_export"
                        stroke={COLORS.net_export}
                        strokeWidth={2}
                        dot={false}
                        name="純輸出"
                        yAxisId="left"
                        connectNulls
                        isAnimationActive={false}
                        hide={isHidden('net_export')}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                )}

                {/* 合計ビュー: 輸出合計 + 輸入合計 + 純輸出 */}
                {viewMode === 'total' && (
                  <ResponsiveContainer width="100%" height={450}>
                    <ComposedChart data={filteredTotal} margin={CHART_MARGIN}>
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
                        domain={['dataMin - 10', 'dataMax + 50']}
                        tickFormatter={(v: number) => `${v.toFixed(0)}`}
                        stroke={DARK_THEME.textSecondary}
                        tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
                        width={55}
                        // label={{ value: 'BCF', position: 'top', offset: 8, style: { fill: DARK_THEME.textSecondary, fontSize: 10 } }}
                      />

                      <RechartsTooltip content={<TotalTooltip hiddenSeries={hiddenSeries} />} />
                      <ReferenceLine yAxisId="left" y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />

                      <Legend
                        wrapperStyle={{ paddingTop: 8 }}
                        onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)}
                        formatter={(value: string, entry: any) => (
                          <span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : DARK_THEME.textPrimary, fontSize: 12 }}>
                            {value}
                          </span>
                        )}
                      />

                      <Line type="monotone" dataKey="export_total" stroke={COLORS.export_total} strokeWidth={2} dot={false} name="輸出合計" yAxisId="left" connectNulls isAnimationActive={false} hide={isHidden('export_total')} />
                      <Line type="monotone" dataKey="import_total" stroke={COLORS.import_total} strokeWidth={2} dot={false} name="輸入合計" yAxisId="left" connectNulls isAnimationActive={false} hide={isHidden('import_total')} />
                      <Line type="monotone" dataKey="net_export" stroke={COLORS.net_export} strokeWidth={2.5} dot={false} name="純輸出" yAxisId="left" connectNulls isAnimationActive={false} hide={isHidden('net_export')} />
                    </ComposedChart>
                  </ResponsiveContainer>
                )}
              </>
            ),
          },
        ]}
      />
    </ChartContainer>
  )
}
