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

const COLOR_DISTILLATE = '#60a5fa'  // Blue
const COLOR_OIL = '#ef4444'         // Red (inverted)

interface DistillateItem {
  date: string
  value: number | null
  yoy: number | null
}

interface DistillateResponse {
  data: DistillateItem[]
  latest: DistillateItem | null
  next_release: { date: string; label?: string; time_jst?: string } | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

interface MergedItem extends DistillateItem {
  oil_price: number | null
}

type ViewMode = 'raw' | 'mom' | 'yoy'
const VIEW_MODE_OPTIONS = [
  { mode: 'raw' as ViewMode, label: '水準' },
  { mode: 'mom' as ViewMode, label: '前月比' },
  { mode: 'yoy' as ViewMode, label: '前年比' },
]

type ActiveTab = 'timeseries' | 'market_impact'

type DisplayMode = 'chart' | 'heatmap'
const DISPLAY_MODE_OPTIONS = [
  { mode: 'chart' as DisplayMode, label: 'チャート' },
  { mode: 'heatmap' as DisplayMode, label: 'ヒートマップ' },
]

type SeriesKey = 'value' | 'yoy' | 'oil_price'

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

  const formatKb = (v: number) => `${v.toLocaleString()} 千bbl`
  const formatYoy = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`

  return (
    <div style={{
      backgroundColor: DARK_THEME.tooltipBg,
      border: `1px solid ${DARK_THEME.tooltipBorder}`,
      borderRadius: 8,
      padding: '12px 16px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
    }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>{formattedLabel}</div>
      {viewMode === 'raw' ? (
        !hiddenSeries.has('value') && dp.value != null && (
          <div style={{ color: COLOR_DISTILLATE, fontSize: 13, marginBottom: 3 }}>
            蒸留燃料在庫: {formatKb(dp.value)}
          </div>
        )
      ) : (
        !hiddenSeries.has('yoy') && dp.yoy != null && (
          <div style={{ color: COLOR_DISTILLATE, fontSize: 13, marginBottom: 3 }}>
            蒸留燃料在庫 YoY: {formatYoy(dp.yoy)}
          </div>
        )
      )}
      {!hiddenSeries.has('oil_price') && dp.oil_price != null && (
        <div style={{ color: COLOR_OIL, fontSize: 13, marginBottom: 3 }}>
          WTI原油: ${dp.oil_price.toLocaleString(undefined, { maximumFractionDigits: 2 })} /bbl
        </div>
      )}
    </div>
  )
}


export default function DistillateFuelInventoriesChart() {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(5)
  const [viewMode, setViewMode] = useState<ViewMode>('raw')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [activeTab, setActiveTab] = useState<ActiveTab>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<SeriesKey>()

  const { data: response } = useQuery<DistillateResponse>({
    queryKey: ['distillate-fuel-inventories'],
    queryFn: async () => {
      const res = await axios.get('/api/market/distillate-fuel-inventories')
      return res.data
    },
    staleTime: 1000 * 60 * 30,
  })

  // WTI oil price (weekly from daily data)
  const { data: marketData } = useMarketBatchData(['crude_oil'])

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
      if (oilMap.has(item.date)) {
        oilPrice = oilMap.get(item.date)!
      } else {
        const d = new Date(item.date)
        for (let offset = 1; offset <= 3; offset++) {
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

  // Monthly averages (shared)
  const monthAvg = useMemo(() => {
    if (!mergedData.length) return {} as Record<string, number>
    const monthAccum: Record<string, number[]> = {}
    for (const item of mergedData) {
      const d = new Date(item.date)
      const val = item.value
      if (val == null) continue
      const key = `${d.getFullYear()}-${String(d.getMonth()).padStart(2, '0')}`
      if (!monthAccum[key]) monthAccum[key] = []
      monthAccum[key].push(val)
    }
    const avg: Record<string, number> = {}
    for (const [key, vals] of Object.entries(monthAccum)) {
      avg[key] = vals.reduce((a, b) => a + b, 0) / vals.length
    }
    return avg
  }, [mergedData])

  // MoM heatmap
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
          ? Math.round(((curVal - prevVal) / prevVal) * 10000) / 100 : null
      }
    }
    return { years, monthlyData }
  }, [monthAvg])

  // MoM bar chart data
  const momChartData = useMemo(() => {
    const entries = Object.entries(monthAvg).sort(([a], [b]) => a.localeCompare(b))
    const result: { date: string; mom: number | null }[] = []
    for (let i = 1; i < entries.length; i++) {
      const [curKey, curVal] = entries[i]
      const [, prevVal] = entries[i - 1]
      const [y, m] = curKey.split('-').map(Number)
      result.push({
        date: `${y}-${String(m + 1).padStart(2, '0')}-15`,
        mom: (prevVal != null && prevVal !== 0)
          ? Math.round(((curVal - prevVal) / prevVal) * 10000) / 100 : null,
      })
    }
    return result
  }, [monthAvg])

  const filteredMomChartData = useMemo(() => {
    if (!momChartData.length) return []
    if (currentPeriod === 'all') return momChartData
    const years = typeof currentPeriod === 'number' ? currentPeriod : 5
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return momChartData.filter(d => d.date >= cutoffStr)
  }, [momChartData, currentPeriod])

  const latest = response?.latest
  const nextRelease = response?.next_release
  const latestOil = marketData?.crude_oil?.latest

  return (
    <ChartContainer
      title="米国蒸留燃料在庫"
      dataSource="EIA"
      sourceUrl="https://www.eia.gov/petroleum/"
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
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>蒸留燃料在庫: </span>
            <span style={{ fontSize: 20, fontWeight: 'bold', color: COLOR_DISTILLATE }}>
              {latest?.value != null ? `${latest.value.toLocaleString()} 千bbl` : '—'}
            </span>
          </div>
          {latest?.yoy != null && (
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>YoY: </span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: latest.yoy >= 0 ? '#22c55e' : '#ef4444' }}>
                {latest.yoy >= 0 ? '+' : ''}{latest.yoy.toFixed(2)}%
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

      {/* タブ切替 */}
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
                {/* 水準/前月比/前年比 + データ比較ボタン */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <ViewModeButtonGroup
                    options={VIEW_MODE_OPTIONS}
                    currentMode={viewMode}
                    onChange={(m) => setViewMode(m as ViewMode)}
                  />
                  <Tooltip title="比較ページを開く">
                    <Button
                      icon={<AreaChartOutlined />}
                      onClick={() => window.open('/compare?s=us_distillate_fuel_inventories', '_blank')}
                    >
                      データ比較
                    </Button>
                  </Tooltip>
                </div>

                {/* チャート/ヒートマップ切替（前月比のみ） */}
                {viewMode === 'mom' && (
                  <div style={{ marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      options={DISPLAY_MODE_OPTIONS}
                      currentMode={displayMode}
                      onChange={(m) => setDisplayMode(m as DisplayMode)}
                    />
                  </div>
                )}

                {/* 水準チャート */}
                {viewMode === 'raw' && (
                  <>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <ResponsiveContainer width="100%" height={400}>
                      <ComposedChart data={filteredData} margin={CHART_MARGIN}>
                        <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
                        <XAxis dataKey="date" tickFormatter={(v) => formatDayLabel(v)} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} minTickGap={40} />
                        <YAxis yAxisId="left" domain={['dataMin * 0.9', 'dataMax * 1.05']} tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}K`} stroke={COLOR_DISTILLATE} tick={{ fill: COLOR_DISTILLATE, fontSize: 11 }} width={55} />
                        <YAxis yAxisId="oil" orientation="right" reversed domain={['dataMin * 0.9', 'dataMax * 1.1']} tickFormatter={(v: number) => `$${v.toFixed(0)}`} stroke={COLOR_OIL} tick={{ fill: COLOR_OIL, fontSize: 10 }} width={50} axisLine={{ stroke: COLOR_OIL, strokeDasharray: '4 3' }} />
                        <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} viewMode={viewMode} />} />
                        <Legend onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={(value: string, entry: any) => (<span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>{value}</span>)} />
                        <Line yAxisId="left" type="monotone" dataKey="value" name="蒸留燃料在庫 (千bbl)" stroke={COLOR_DISTILLATE} strokeWidth={2} dot={false} hide={hiddenSeries.has('value')} connectNulls isAnimationActive={false} />
                        <Line yAxisId="oil" type="monotone" dataKey="oil_price" name="WTI原油 (USD/bbl, 反転)" stroke={COLOR_OIL} strokeWidth={1.5} strokeDasharray="4 3" dot={false} hide={hiddenSeries.has('oil_price')} connectNulls isAnimationActive={false} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </>
                )}

                {/* 前年比チャート */}
                {viewMode === 'yoy' && (
                  <>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <ResponsiveContainer width="100%" height={400}>
                      <ComposedChart data={filteredData} margin={CHART_MARGIN}>
                        <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
                        <XAxis dataKey="date" tickFormatter={(v) => formatDayLabel(v)} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} minTickGap={40} />
                        <YAxis yAxisId="left" domain={['auto', 'auto']} tickFormatter={(v: number) => `${v.toFixed(1)}%`} stroke={COLOR_DISTILLATE} tick={{ fill: COLOR_DISTILLATE, fontSize: 11 }} width={55} />
                        <YAxis yAxisId="oil" orientation="right" reversed domain={['dataMin * 0.9', 'dataMax * 1.1']} tickFormatter={(v: number) => `$${v.toFixed(0)}`} stroke={COLOR_OIL} tick={{ fill: COLOR_OIL, fontSize: 10 }} width={50} axisLine={{ stroke: COLOR_OIL, strokeDasharray: '4 3' }} />
                        <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} viewMode={viewMode} />} />
                        <ReferenceLine yAxisId="left" y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />
                        <Legend onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={(value: string, entry: any) => (<span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>{value}</span>)} />
                        <Line yAxisId="left" type="monotone" dataKey="yoy" name="蒸留燃料在庫 YoY %" stroke={COLOR_DISTILLATE} strokeWidth={2} dot={false} hide={hiddenSeries.has('yoy')} connectNulls isAnimationActive={false} />
                        <Line yAxisId="oil" type="monotone" dataKey="oil_price" name="WTI原油 (USD/bbl, 反転)" stroke={COLOR_OIL} strokeWidth={1.5} strokeDasharray="4 3" dot={false} hide={hiddenSeries.has('oil_price')} connectNulls isAnimationActive={false} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </>
                )}

                {/* 前月比バーチャート */}
                {viewMode === 'mom' && displayMode === 'chart' && (
                  <>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <ResponsiveContainer width="100%" height={400}>
                      <ComposedChart data={filteredMomChartData} margin={CHART_MARGIN}>
                        <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
                        <XAxis dataKey="date" tickFormatter={(v) => formatDayLabel(v)} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} minTickGap={40} />
                        <YAxis domain={['auto', 'auto']} tickFormatter={(v: number) => `${v.toFixed(1)}%`} stroke={DARK_THEME.textSecondary} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} width={55} />
                        <RechartsTooltip
                          contentStyle={{ backgroundColor: DARK_THEME.tooltipBg, border: `1px solid ${DARK_THEME.tooltipBorder}`, borderRadius: 8 }}
                          labelFormatter={(v) => formatDayLabel(String(v))}
                          formatter={(value: number) => [`${value >= 0 ? '+' : ''}${value.toFixed(2)}%`, '蒸留燃料在庫 MoM']}
                        />
                        <ReferenceLine y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />
                        <Bar dataKey="mom" name="蒸留燃料在庫 前月比 (%)" fill={COLOR_DISTILLATE} isAnimationActive={false} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </>
                )}

                {/* 前月比ヒートマップ */}
                {viewMode === 'mom' && displayMode === 'heatmap' && (
                  <MonthlyTable
                    data={momHeatmapData}
                    decimals={2}
                    showLegend
                    helperText="※ 蒸留燃料在庫 前月比（週次データの月平均から算出, 単位: %）"
                  />
                )}
              </>
            ),
          },
          {
            key: 'market_impact',
            label: 'マーケットインパクト',
            children: (
              <MarketImpactTab indicatorId="us_distillate_fuel_inventories" />
            ),
          },
        ]}
      />
    </ChartContainer>
  )
}
