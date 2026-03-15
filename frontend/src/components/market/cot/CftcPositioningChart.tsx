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
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../common/ChartContainer'
import PeriodSelector, { type PeriodValue } from '../../common/PeriodSelector'
import { formatDayLabel } from '../../../utils/dateFormatters'
import { useHiddenSeries } from '../../country/usa/common/useChartData'
import { ViewModeButtonGroup } from '../../country/usa/common/ChartComponents'
import { LATEST_VALUE_BOX_STYLE, CHART_MARGIN } from '../../country/usa/common/chartConstants'

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

// Colors
const COLOR_SPEC_NET = '#3b82f6'    // Blue - speculative net
const COLOR_COMM_NET = '#ef4444'    // Red - commercial net
const COLOR_LONG = '#22c55e'        // Green - long
const COLOR_SHORT = '#f97316'       // Orange - short
const COLOR_PRICE = '#e2e8f0'       // Light gray - price

interface PositionItem {
  date: string
  open_interest: number | null
  spec_long: number | null
  spec_short: number | null
  spec_net: number | null
  comm_long: number | null
  comm_short: number | null
  comm_net: number | null
  price: number | null
}

interface CftcResponse {
  data: PositionItem[]
  latest: PositionItem | null
  metadata: {
    asset: string
    asset_label: string
    report_type: string
    source: string
    frequency: string
    unit: string
    data_count: number
    start_date: string | null
    end_date: string | null
  }
  cached: boolean
  source: string
  last_updated: string | null
}

type ViewMode = 'speculative' | 'commercial' | 'comparison'
const VIEW_MODE_OPTIONS = [
  { mode: 'speculative' as ViewMode, label: '投機筋' },
  { mode: 'commercial' as ViewMode, label: '実需筋' },
  { mode: 'comparison' as ViewMode, label: 'ネット比較' },
]

type SpecSeriesKey = 'spec_net' | 'spec_long' | 'spec_short' | 'price'
type CommSeriesKey = 'comm_net' | 'comm_long' | 'comm_short' | 'price'
type CompSeriesKey = 'spec_net' | 'comm_net' | 'price'
type AllSeriesKey = SpecSeriesKey | CommSeriesKey | CompSeriesKey

interface Props {
  asset: string
  assetLabel: string
  reportType: 'disagg' | 'tff'
  compareId?: string
}

function formatContracts(v: number): string {
  if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
  if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(1)}K`
  return v.toLocaleString()
}

function ChartTooltipContent({ active, payload, hiddenSeries, viewMode }: any) {
  if (!active || !payload?.length) return null
  const dp = payload[0]?.payload as PositionItem | undefined
  if (!dp) return null

  const specLabel = viewMode === 'speculative'
    ? '投機筋'
    : viewMode === 'commercial'
    ? '実需筋'
    : null

  return (
    <div style={{ background: DARK_THEME.tooltipBg, border: `1px solid ${DARK_THEME.tooltipBorder}`, borderRadius: 6, padding: '8px 12px', fontSize: 13 }}>
      <div style={{ color: DARK_THEME.textPrimary, fontWeight: 600, marginBottom: 4 }}>{dp.date}</div>

      {viewMode === 'speculative' && (
        <>
          {!hiddenSeries.has('spec_net') && dp.spec_net != null && (
            <div style={{ color: COLOR_SPEC_NET }}>ネット: {formatContracts(dp.spec_net)}</div>
          )}
          {!hiddenSeries.has('spec_long') && dp.spec_long != null && (
            <div style={{ color: COLOR_LONG }}>ロング: {formatContracts(dp.spec_long)}</div>
          )}
          {!hiddenSeries.has('spec_short') && dp.spec_short != null && (
            <div style={{ color: COLOR_SHORT }}>ショート: {formatContracts(dp.spec_short)}</div>
          )}
        </>
      )}

      {viewMode === 'commercial' && (
        <>
          {!hiddenSeries.has('comm_net') && dp.comm_net != null && (
            <div style={{ color: COLOR_COMM_NET }}>ネット: {formatContracts(dp.comm_net)}</div>
          )}
          {!hiddenSeries.has('comm_long') && dp.comm_long != null && (
            <div style={{ color: COLOR_LONG }}>ロング: {formatContracts(dp.comm_long)}</div>
          )}
          {!hiddenSeries.has('comm_short') && dp.comm_short != null && (
            <div style={{ color: COLOR_SHORT }}>ショート: {formatContracts(dp.comm_short)}</div>
          )}
        </>
      )}

      {viewMode === 'comparison' && (
        <>
          {!hiddenSeries.has('spec_net') && dp.spec_net != null && (
            <div style={{ color: COLOR_SPEC_NET }}>投機筋ネット: {formatContracts(dp.spec_net)}</div>
          )}
          {!hiddenSeries.has('comm_net') && dp.comm_net != null && (
            <div style={{ color: COLOR_COMM_NET }}>実需筋ネット: {formatContracts(dp.comm_net)}</div>
          )}
        </>
      )}

      {!hiddenSeries.has('price') && dp.price != null && (
        <div style={{ color: COLOR_PRICE, marginTop: 2 }}>価格: {dp.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}</div>
      )}
    </div>
  )
}


export default function CftcPositioningChart({ asset, assetLabel, reportType, compareId }: Props) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(5)
  const [viewMode, setViewMode] = useState<ViewMode>('speculative')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<AllSeriesKey>()

  const { data: response, isLoading } = useQuery<CftcResponse>({
    queryKey: ['cftc-positioning', asset],
    queryFn: async () => {
      const res = await axios.get(`/api/market/cftc-positioning?asset=${asset}`)
      return res.data
    },
    staleTime: 1000 * 60 * 60,  // 1 hour
  })

  const filteredData = useMemo(() => {
    if (!response?.data?.length) return []
    if (currentPeriod === 'all') return response.data
    const years = typeof currentPeriod === 'number' ? currentPeriod : 5
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return response.data.filter(d => d.date >= cutoffStr)
  }, [response, currentPeriod])

  const latest = response?.latest
  const specLabel = 'Non-Commercial'
  const commLabel = 'Commercial'

  return (
    <ChartContainer
      title={`${assetLabel} CFTCポジション動向`}
      sourceUrl="https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm"
      sourceLabel="CFTC COT"
      showPeriodSelector={false}
      isLoading={isLoading}
    >
      {/* Latest value box */}
      <div style={LATEST_VALUE_BOX_STYLE}>
        {latest && (
          <>
            <span style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>
              {latest.date} | {specLabel}
            </span>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 4 }}>
              <span style={{ color: COLOR_SPEC_NET, fontSize: 14 }}>
                投機筋ネット: {latest.spec_net != null ? formatContracts(latest.spec_net) : '—'}
              </span>
              <span style={{ color: COLOR_COMM_NET, fontSize: 14 }}>
                実需筋ネット: {latest.comm_net != null ? formatContracts(latest.comm_net) : '—'}
              </span>
              {latest.price != null && (
                <span style={{ color: COLOR_PRICE, fontSize: 14 }}>
                  価格: {latest.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </span>
              )}
            </div>
          </>
        )}
      </div>

      {/* ViewMode + Compare button */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <ViewModeButtonGroup
          options={VIEW_MODE_OPTIONS}
          currentMode={viewMode}
          onChange={(m) => setViewMode(m as ViewMode)}
        />
        {compareId && (
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open(`/compare?s=${compareId}`, '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        )}
      </div>

      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

      {/* Tab 1: Speculative (投機筋) */}
      {viewMode === 'speculative' && (
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
            <XAxis dataKey="date" tickFormatter={(v) => formatDayLabel(v)} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} minTickGap={40} />
            <YAxis yAxisId="left" domain={['auto', 'auto']} tickFormatter={(v: number) => formatContracts(v)} stroke={DARK_THEME.textSecondary} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} width={60} />
            <YAxis yAxisId="price" orientation="right" domain={['dataMin * 0.9', 'dataMax * 1.1']} tickFormatter={(v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 0 })} stroke={COLOR_PRICE} tick={{ fill: COLOR_PRICE, fontSize: 10 }} width={60} axisLine={{ stroke: COLOR_PRICE, strokeDasharray: '4 3' }} />
            <RechartsTooltip content={<ChartTooltipContent hiddenSeries={hiddenSeries} viewMode={viewMode} />} />
            <ReferenceLine yAxisId="left" y={0} stroke="#e2e8f0" strokeWidth={2} />
            <Legend onClick={(e) => handleLegendClick(e.dataKey as AllSeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={(value: string, entry: any) => (<span style={{ color: hiddenSeries.has(entry.dataKey as AllSeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>{value}</span>)} />
            <Area yAxisId="left" type="monotone" dataKey="spec_net" name={`${specLabel} ネット`} fill={COLOR_SPEC_NET} fillOpacity={0.3} stroke={COLOR_SPEC_NET} strokeWidth={1.5} baseValue={0} hide={hiddenSeries.has('spec_net')} isAnimationActive={false} />
            <Line yAxisId="left" type="monotone" dataKey="spec_long" name={`${specLabel} ロング`} stroke={COLOR_LONG} strokeWidth={1.5} dot={false} hide={hiddenSeries.has('spec_long')} connectNulls isAnimationActive={false} />
            <Line yAxisId="left" type="monotone" dataKey="spec_short" name={`${specLabel} ショート`} stroke={COLOR_SHORT} strokeWidth={1.5} dot={false} hide={hiddenSeries.has('spec_short')} connectNulls isAnimationActive={false} />
            <Line yAxisId="price" type="monotone" dataKey="price" name="価格" stroke={COLOR_PRICE} strokeWidth={1.5} strokeDasharray="4 3" dot={false} hide={hiddenSeries.has('price')} connectNulls isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* Tab 2: Commercial (実需筋) */}
      {viewMode === 'commercial' && (
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
            <XAxis dataKey="date" tickFormatter={(v) => formatDayLabel(v)} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} minTickGap={40} />
            <YAxis yAxisId="left" domain={['auto', 'auto']} tickFormatter={(v: number) => formatContracts(v)} stroke={DARK_THEME.textSecondary} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} width={60} />
            <YAxis yAxisId="price" orientation="right" domain={['dataMin * 0.9', 'dataMax * 1.1']} tickFormatter={(v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 0 })} stroke={COLOR_PRICE} tick={{ fill: COLOR_PRICE, fontSize: 10 }} width={60} axisLine={{ stroke: COLOR_PRICE, strokeDasharray: '4 3' }} />
            <RechartsTooltip content={<ChartTooltipContent hiddenSeries={hiddenSeries} viewMode={viewMode} />} />
            <ReferenceLine yAxisId="left" y={0} stroke="#e2e8f0" strokeWidth={2} />
            <Legend onClick={(e) => handleLegendClick(e.dataKey as AllSeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={(value: string, entry: any) => (<span style={{ color: hiddenSeries.has(entry.dataKey as AllSeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>{value}</span>)} />
            <Area yAxisId="left" type="monotone" dataKey="comm_net" name={`${commLabel} ネット`} fill={COLOR_COMM_NET} fillOpacity={0.3} stroke={COLOR_COMM_NET} strokeWidth={1.5} baseValue={0} hide={hiddenSeries.has('comm_net')} isAnimationActive={false} />
            <Line yAxisId="left" type="monotone" dataKey="comm_long" name={`${commLabel} ロング`} stroke={COLOR_LONG} strokeWidth={1.5} dot={false} hide={hiddenSeries.has('comm_long')} connectNulls isAnimationActive={false} />
            <Line yAxisId="left" type="monotone" dataKey="comm_short" name={`${commLabel} ショート`} stroke={COLOR_SHORT} strokeWidth={1.5} dot={false} hide={hiddenSeries.has('comm_short')} connectNulls isAnimationActive={false} />
            <Line yAxisId="price" type="monotone" dataKey="price" name="価格" stroke={COLOR_PRICE} strokeWidth={1.5} strokeDasharray="4 3" dot={false} hide={hiddenSeries.has('price')} connectNulls isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* Tab 3: Comparison (ネット比較) */}
      {viewMode === 'comparison' && (
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
            <XAxis dataKey="date" tickFormatter={(v) => formatDayLabel(v)} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} minTickGap={40} />
            <YAxis yAxisId="left" domain={['auto', 'auto']} tickFormatter={(v: number) => formatContracts(v)} stroke={DARK_THEME.textSecondary} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} width={60} />
            <YAxis yAxisId="price" orientation="right" domain={['dataMin * 0.9', 'dataMax * 1.1']} tickFormatter={(v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 0 })} stroke={COLOR_PRICE} tick={{ fill: COLOR_PRICE, fontSize: 10 }} width={60} axisLine={{ stroke: COLOR_PRICE, strokeDasharray: '4 3' }} />
            <RechartsTooltip content={<ChartTooltipContent hiddenSeries={hiddenSeries} viewMode={viewMode} />} />
            <ReferenceLine yAxisId="left" y={0} stroke="#e2e8f0" strokeWidth={2} />
            <Legend onClick={(e) => handleLegendClick(e.dataKey as AllSeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={(value: string, entry: any) => (<span style={{ color: hiddenSeries.has(entry.dataKey as AllSeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>{value}</span>)} />
            <Area yAxisId="left" type="monotone" dataKey="spec_net" name="投機筋ネット" fill={COLOR_SPEC_NET} fillOpacity={0.3} stroke={COLOR_SPEC_NET} strokeWidth={1.5} baseValue={0} hide={hiddenSeries.has('spec_net')} isAnimationActive={false} />
            <Area yAxisId="left" type="monotone" dataKey="comm_net" name="実需筋ネット" fill={COLOR_COMM_NET} fillOpacity={0.3} stroke={COLOR_COMM_NET} strokeWidth={1.5} baseValue={0} hide={hiddenSeries.has('comm_net')} isAnimationActive={false} />
            <Line yAxisId="price" type="monotone" dataKey="price" name="価格" stroke={COLOR_PRICE} strokeWidth={1.5} strokeDasharray="4 3" dot={false} hide={hiddenSeries.has('price')} connectNulls isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </ChartContainer>
  )
}
