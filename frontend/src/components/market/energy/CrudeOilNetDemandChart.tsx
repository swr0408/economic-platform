import { useState, useMemo } from 'react'
import { Tabs, Tooltip, Button } from 'antd'
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
import { formatDayLabel } from '../../../utils/dateFormatters'
import { useHiddenSeries } from '../../country/usa/common/useChartData'
import { ViewModeButtonGroup } from '../../country/usa/common/ChartComponents'
import { MonthlyTable } from '../../country/usa/common/MonthlyTable'
import { useMarketBatchData } from '../../../hooks/useMarketData'
import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS, CHART_MARGIN } from '../../country/usa/common/chartConstants'
import MarketImpactTab from '../../indicator/MarketImpactTab'

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

const COLOR_NET = '#3b82f6'     // Blue - net demand
const COLOR_MA4 = '#f59e0b'     // Amber - 4W MA
const COLOR_OIL = '#ef4444'     // Red - oil price
const COLOR_SUPPLIED = '#a855f7' // Purple - products supplied
const COLOR_PROD = '#22c55e'    // Green - field production

interface NetDemandItem {
  date: string
  products_supplied: number | null
  field_production: number | null
  net_demand: number | null
  ma4: number | null
  yoy: number | null
  ma4_yoy: number | null
}

interface NetDemandResponse {
  data: NetDemandItem[]
  latest: NetDemandItem | null
  next_release: { date: string; label?: string; time_jst?: string } | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

interface MergedItem extends NetDemandItem {
  oil_price: number | null
}

type ViewMode = 'raw' | 'breakdown' | 'yoy'
const VIEW_MODE_OPTIONS = [
  { mode: 'raw' as ViewMode, label: '純需要' },
  { mode: 'breakdown' as ViewMode, label: '供給/生産' },
  { mode: 'yoy' as ViewMode, label: '前年比' },
]

type ActiveTab = 'timeseries' | 'market_impact'

type DisplayMode = 'chart' | 'heatmap'
const DISPLAY_MODE_OPTIONS = [
  { mode: 'chart' as DisplayMode, label: 'チャート' },
  { mode: 'heatmap' as DisplayMode, label: 'ヒートマップ' },
]

type SeriesKey = 'net_demand' | 'ma4' | 'oil_price' | 'products_supplied' | 'field_production' | 'yoy' | 'ma4_yoy'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ChartTooltip({ active, payload, label, hiddenSeries, viewMode }: {
  active?: boolean
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
  viewMode: ViewMode
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))
  const dp = payload[0]?.payload as MergedItem | undefined
  if (!dp) return null

  const fmtKbd = (v: number) => `${v.toLocaleString(undefined, { maximumFractionDigits: 1 })} 千bbl/日`
  const fmtPct = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`

  return (
    <div style={{
      backgroundColor: DARK_THEME.tooltipBg,
      border: `1px solid ${DARK_THEME.tooltipBorder}`,
      borderRadius: 8,
      padding: '12px 16px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
    }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>{formattedLabel}</div>

      {viewMode === 'raw' && (
        <>
          {!hiddenSeries.has('net_demand') && dp.net_demand != null && (
            <div style={{ color: COLOR_NET, fontSize: 13, marginBottom: 3 }}>
              純需要: {fmtKbd(dp.net_demand)}
            </div>
          )}
          {!hiddenSeries.has('ma4') && dp.ma4 != null && (
            <div style={{ color: COLOR_MA4, fontSize: 13, marginBottom: 3 }}>
              4W MA: {fmtKbd(dp.ma4)}
            </div>
          )}
        </>
      )}

      {viewMode === 'breakdown' && (
        <>
          {!hiddenSeries.has('products_supplied') && dp.products_supplied != null && (
            <div style={{ color: COLOR_SUPPLIED, fontSize: 13, marginBottom: 3 }}>
              製品供給: {fmtKbd(dp.products_supplied)}
            </div>
          )}
          {!hiddenSeries.has('field_production') && dp.field_production != null && (
            <div style={{ color: COLOR_PROD, fontSize: 13, marginBottom: 3 }}>
              原油生産: {fmtKbd(dp.field_production)}
            </div>
          )}
          {!hiddenSeries.has('net_demand') && dp.net_demand != null && (
            <div style={{ color: COLOR_NET, fontSize: 13, marginBottom: 3 }}>
              純需要: {fmtKbd(dp.net_demand)}
            </div>
          )}
        </>
      )}

      {viewMode === 'yoy' && (
        <>
          {!hiddenSeries.has('yoy') && dp.yoy != null && (
            <div style={{ color: COLOR_NET, fontSize: 13, marginBottom: 3 }}>
              YoY: {fmtPct(dp.yoy)}
            </div>
          )}
          {!hiddenSeries.has('ma4_yoy') && dp.ma4_yoy != null && (
            <div style={{ color: COLOR_MA4, fontSize: 13, marginBottom: 3 }}>
              4W MA YoY: {fmtPct(dp.ma4_yoy)}
            </div>
          )}
        </>
      )}

      {(viewMode === 'raw' || viewMode === 'breakdown') && !hiddenSeries.has('oil_price') && dp.oil_price != null && (
        <div style={{ color: COLOR_OIL, fontSize: 13, marginBottom: 3 }}>
          WTI原油: ${dp.oil_price.toLocaleString(undefined, { maximumFractionDigits: 2 })} /bbl
        </div>
      )}
    </div>
  )
}


export default function CrudeOilNetDemandChart() {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(5)
  const [viewMode, setViewMode] = useState<ViewMode>('raw')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [activeTab, setActiveTab] = useState<ActiveTab>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<SeriesKey>()

  const { data: response } = useQuery<NetDemandResponse>({
    queryKey: ['crude-oil-net-demand'],
    queryFn: async () => {
      const res = await axios.get('/api/market/crude-oil-net-demand')
      return res.data
    },
    staleTime: 1000 * 60 * 30,
  })

  // WTI oil price
  const { data: marketData } = useMarketBatchData(['crude_oil'])

  // Merge oil price data (weekly data - fuzzy match ±3 days)
  const mergedData = useMemo(() => {
    if (!response?.data) return []

    const oilMap = new Map<string, number>()
    if (marketData?.crude_oil?.data) {
      for (const d of marketData.crude_oil.data) {
        oilMap.set(d.date, d.close)
      }
    }

    return response.data.map(item => {
      let oilPrice: number | null = null
      for (let offset = 0; offset <= 3; offset++) {
        const d = new Date(item.date)
        if (offset === 0) {
          if (oilMap.has(item.date)) {
            oilPrice = oilMap.get(item.date)!
            break
          }
        } else {
          const before = new Date(d)
          before.setDate(before.getDate() - offset)
          const beforeStr = before.toISOString().slice(0, 10)
          if (oilMap.has(beforeStr)) {
            oilPrice = oilMap.get(beforeStr)!
            break
          }
          const after = new Date(d)
          after.setDate(after.getDate() + offset)
          const afterStr = after.toISOString().slice(0, 10)
          if (oilMap.has(afterStr)) {
            oilPrice = oilMap.get(afterStr)!
            break
          }
        }
      }

      return { ...item, oil_price: oilPrice }
    })
  }, [response, marketData])

  const filteredData = useMemo(() => {
    if (!mergedData.length) return []
    if (currentPeriod === 'all') return mergedData
    const years = typeof currentPeriod === 'number' ? currentPeriod : 5
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return mergedData.filter(d => d.date >= cutoffStr)
  }, [mergedData, currentPeriod])

  // Weekly → monthly averages for MoM heatmap (net_demand)
  const monthAvg = useMemo(() => {
    if (!mergedData.length) return {} as Record<string, number>
    const monthAccum: Record<string, number[]> = {}
    for (const item of mergedData) {
      if (item.net_demand == null) continue
      const d = new Date(item.date)
      const key = `${d.getFullYear()}-${String(d.getMonth()).padStart(2, '0')}`
      if (!monthAccum[key]) monthAccum[key] = []
      monthAccum[key].push(item.net_demand)
    }
    const avg: Record<string, number> = {}
    for (const [key, vals] of Object.entries(monthAccum)) {
      avg[key] = vals.reduce((a, b) => a + b, 0) / vals.length
    }
    return avg
  }, [mergedData])

  // MoM heatmap data (月平均から前月比%)
  const momHeatmapData = useMemo(() => {
    const currentYear = new Date().getFullYear()
    const startYear = currentYear - 9
    const years: number[] = []
    for (let y = startYear; y <= currentYear; y++) years.push(y)
    const monthlyData: Record<number, Record<number, number | null>> = {}
    for (const year of years) {
      monthlyData[year] = {}
      for (let m = 0; m < 12; m++) {
        const curVal = monthAvg[`${year}-${String(m).padStart(2, '0')}`]
        if (curVal == null) { monthlyData[year][m] = null; continue }
        let prevYear = year; let prevMonth = m - 1
        if (prevMonth < 0) { prevMonth = 11; prevYear-- }
        const prevVal = monthAvg[`${prevYear}-${String(prevMonth).padStart(2, '0')}`]
        monthlyData[year][m] = (prevVal != null && prevVal !== 0)
          ? Math.round(((curVal - prevVal) / Math.abs(prevVal)) * 10000) / 100 : null
      }
    }
    return { years, monthlyData }
  }, [monthAvg])

  const latest = response?.latest
  const nextRelease = response?.next_release
  const latestOil = marketData?.crude_oil?.latest

  return (
    <ChartContainer
      title="米国 原油純需要"
      dataSource="EIA"
      sourceUrl="https://www.eia.gov/petroleum/supply/weekly/"
      showPeriodSelector={false}
    >
      {/* Latest value box */}
      <div style={LATEST_VALUE_BOX_STYLE}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          {latest?.date && (
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
              {latest.date.replace(/-/g, '/')}
            </span>
          )}
          <div>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>純需要: </span>
            <span style={{ fontSize: 20, fontWeight: 'bold', color: COLOR_NET }}>
              {latest?.net_demand != null ? `${latest.net_demand.toLocaleString()} 千bbl/日` : '—'}
            </span>
          </div>
          {latest?.ma4 != null && (
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>4W MA: </span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: COLOR_MA4 }}>
                {latest.ma4.toLocaleString()} 千bbl/日
              </span>
            </div>
          )}
          {latest?.ma4_yoy != null && (
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>4W MA YoY: </span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: latest.ma4_yoy >= 0 ? '#22c55e' : '#ef4444' }}>
                {latest.ma4_yoy >= 0 ? '+' : ''}{latest.ma4_yoy.toFixed(2)}%
              </span>
            </div>
          )}
          {latestOil && (
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>WTI: </span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: COLOR_OIL }}>
                ${latestOil.close.toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </span>
            </div>
          )}
        </div>
        {nextRelease && (
          <span style={{ fontSize: 11, color: TEXT_COLORS.secondary, whiteSpace: 'nowrap' }}>
            次回: {nextRelease.date}{nextRelease.time_jst && ` ${nextRelease.time_jst} JST`}
          </span>
        )}
      </div>

      {/* Tab */}
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
                {/* ViewMode + Compare button */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <ViewModeButtonGroup
                    options={VIEW_MODE_OPTIONS}
                    currentMode={viewMode}
                    onChange={(m) => setViewMode(m as ViewMode)}
                  />
                  <Tooltip title="比較ページを開く">
                    <Button
                      icon={<AreaChartOutlined />}
                      onClick={() => window.open('/compare?s=crude_oil_net_demand', '_blank')}
                    >
                      データ比較
                    </Button>
                  </Tooltip>
                </div>

                {/* Display mode toggle (yoy only) */}
                {viewMode === 'yoy' && (
                  <div style={{ marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      options={DISPLAY_MODE_OPTIONS}
                      currentMode={displayMode}
                      onChange={(m) => setDisplayMode(m as DisplayMode)}
                    />
                  </div>
                )}

                {/* Raw: Net Demand + 4W MA + WTI */}
                {viewMode === 'raw' && (
                  <>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <ResponsiveContainer width="100%" height={400}>
                      <ComposedChart data={filteredData} margin={CHART_MARGIN}>
                        <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
                        <XAxis dataKey="date" tickFormatter={(v) => formatDayLabel(v)} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} minTickGap={40} />
                        <YAxis yAxisId="left" domain={['dataMin - 500', 'dataMax + 500']} tickFormatter={(v: number) => `${(v / 1000).toFixed(1)}K`} stroke={DARK_THEME.textSecondary} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} width={50}  />
                        <YAxis yAxisId="oil" orientation="right" domain={['dataMin * 0.9', 'dataMax * 1.1']} tickFormatter={(v: number) => `$${v.toFixed(0)}`} stroke={COLOR_OIL} tick={{ fill: COLOR_OIL, fontSize: 10 }} width={50} axisLine={{ stroke: COLOR_OIL, strokeDasharray: '4 3' }} />
                        <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} viewMode={viewMode} />} />
                        <ReferenceLine yAxisId="left" y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />
                        <Legend onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={(value: string, entry: any) => (<span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>{value}</span>)} />
                        <Bar yAxisId="left" dataKey="net_demand" name="純需要 (千bbl/日)" fill={COLOR_NET} opacity={0.5} hide={hiddenSeries.has('net_demand')} isAnimationActive={false} />
                        <Line yAxisId="left" type="monotone" dataKey="ma4" name="4W移動平均 (千bbl/日)" stroke={COLOR_MA4} strokeWidth={2.5} dot={false} hide={hiddenSeries.has('ma4')} connectNulls isAnimationActive={false} />
                        <Line yAxisId="oil" type="monotone" dataKey="oil_price" name="WTI原油 (USD/bbl)" stroke={COLOR_OIL} strokeWidth={1.5} strokeDasharray="4 3" dot={false} hide={hiddenSeries.has('oil_price')} connectNulls isAnimationActive={false} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </>
                )}

                {/* Breakdown: Products Supplied + Field Production + Net */}
                {viewMode === 'breakdown' && (
                  <>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <ResponsiveContainer width="100%" height={400}>
                      <ComposedChart data={filteredData} margin={CHART_MARGIN}>
                        <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
                        <XAxis dataKey="date" tickFormatter={(v) => formatDayLabel(v)} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} minTickGap={40} />
                        <YAxis yAxisId="left" domain={['dataMin * 0.95', 'dataMax * 1.02']} tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}K`} stroke={DARK_THEME.textSecondary} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} width={50} label={{ value: '千bbl/日', angle: -90, position: 'insideLeft', style: { fill: DARK_THEME.textSecondary, fontSize: 10 } }} />
                        <YAxis yAxisId="oil" orientation="right" domain={['dataMin * 0.9', 'dataMax * 1.1']} tickFormatter={(v: number) => `$${v.toFixed(0)}`} stroke={COLOR_OIL} tick={{ fill: COLOR_OIL, fontSize: 10 }} width={50} axisLine={{ stroke: COLOR_OIL, strokeDasharray: '4 3' }} />
                        <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} viewMode={viewMode} />} />
                        <Legend onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={(value: string, entry: any) => (<span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>{value}</span>)} />
                        <Line yAxisId="left" type="monotone" dataKey="products_supplied" name="製品供給 (千bbl/日)" stroke={COLOR_SUPPLIED} strokeWidth={2} dot={false} hide={hiddenSeries.has('products_supplied')} connectNulls isAnimationActive={false} />
                        <Line yAxisId="left" type="monotone" dataKey="field_production" name="原油生産 (千bbl/日)" stroke={COLOR_PROD} strokeWidth={2} dot={false} hide={hiddenSeries.has('field_production')} connectNulls isAnimationActive={false} />
                        <Line yAxisId="left" type="monotone" dataKey="net_demand" name="純需要 (千bbl/日)" stroke={COLOR_NET} strokeWidth={1.5} strokeDasharray="4 3" dot={false} hide={hiddenSeries.has('net_demand')} connectNulls isAnimationActive={false} />
                        <Line yAxisId="oil" type="monotone" dataKey="oil_price" name="WTI原油 (USD/bbl)" stroke={COLOR_OIL} strokeWidth={1.5} strokeDasharray="4 3" dot={false} hide={hiddenSeries.has('oil_price')} connectNulls isAnimationActive={false} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </>
                )}

                {/* YoY chart: raw YoY + 4W MA YoY + WTI */}
                {viewMode === 'yoy' && displayMode === 'chart' && (
                  <>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <ResponsiveContainer width="100%" height={400}>
                      <ComposedChart data={filteredData} margin={CHART_MARGIN}>
                        <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
                        <XAxis dataKey="date" tickFormatter={(v) => formatDayLabel(v)} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} minTickGap={40} />
                        <YAxis yAxisId="left" domain={['auto', 'auto']} tickFormatter={(v: number) => `${v.toFixed(0)}%`} stroke={DARK_THEME.textSecondary} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} width={55} />
                        <YAxis yAxisId="oil" orientation="right" domain={['dataMin * 0.9', 'dataMax * 1.1']} tickFormatter={(v: number) => `$${v.toFixed(0)}`} stroke={COLOR_OIL} tick={{ fill: COLOR_OIL, fontSize: 10 }} width={50} axisLine={{ stroke: COLOR_OIL, strokeDasharray: '4 3' }} />
                        <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} viewMode={viewMode} />} />
                        <ReferenceLine yAxisId="left" y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />
                        <Legend onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={(value: string, entry: any) => (<span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>{value}</span>)} />
                        <Bar yAxisId="left" dataKey="yoy" name="純需要 YoY (%)" fill={COLOR_NET} opacity={0.4} hide={hiddenSeries.has('yoy')} isAnimationActive={false} />
                        <Line yAxisId="left" type="monotone" dataKey="ma4_yoy" name="4W MA YoY (%)" stroke={COLOR_MA4} strokeWidth={2.5} dot={false} hide={hiddenSeries.has('ma4_yoy')} connectNulls isAnimationActive={false} />
                        <Line yAxisId="oil" type="monotone" dataKey="oil_price" name="WTI原油 (USD/bbl)" stroke={COLOR_OIL} strokeWidth={1.5} strokeDasharray="4 3" dot={false} hide={hiddenSeries.has('oil_price')} connectNulls isAnimationActive={false} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </>
                )}

                {/* YoY heatmap */}
                {viewMode === 'yoy' && displayMode === 'heatmap' && (
                  <MonthlyTable
                    data={momHeatmapData}
                    decimals={2}
                    showLegend
                    helperText="※ 純需要 前月比（週次データの月平均から算出, 単位: %）"
                  />
                )}
              </>
            ),
          },
          {
            key: 'market_impact',
            label: 'マーケットインパクト',
            children: (
              <MarketImpactTab indicatorId="weekly_crude_oil_inventories" />
            ),
          },
        ]}
      />
    </ChartContainer>
  )
}
