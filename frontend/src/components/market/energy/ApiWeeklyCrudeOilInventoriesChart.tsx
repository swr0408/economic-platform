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

const COLOR_API = '#f59e0b'    // Amber
const COLOR_OIL = '#ef4444'    // Red (inverted)

interface ApiCrudeItem {
  date: string
  value: number | null
  forecast: number | null
  previous: number | null
}

interface ApiCrudeResponse {
  data: ApiCrudeItem[]
  latest: ApiCrudeItem | null
  next_release: { date: string; label?: string; time_jst?: string } | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

interface MergedItem extends ApiCrudeItem {
  oil_price: number | null
}

type ViewMode = 'raw' | 'heatmap'
const VIEW_MODE_OPTIONS = [
  { mode: 'raw' as ViewMode, label: '週次' },
  { mode: 'heatmap' as ViewMode, label: 'ヒートマップ' },
]

type ActiveTab = 'timeseries' | 'market_impact'

type SeriesKey = 'value' | 'oil_price'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ChartTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))
  const dp = payload[0]?.payload as MergedItem | undefined
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
      {!hiddenSeries.has('value') && dp.value != null && (
        <div style={{ color: COLOR_API, fontSize: 13, marginBottom: 3 }}>
          在庫変化: {dp.value >= 0 ? '+' : ''}{dp.value.toFixed(3)}M bbl
        </div>
      )}
      {dp.forecast != null && (
        <div style={{ color: DARK_THEME.textSecondary, fontSize: 12, marginBottom: 3 }}>
          予想: {dp.forecast >= 0 ? '+' : ''}{dp.forecast.toFixed(3)}M
        </div>
      )}
      {!hiddenSeries.has('oil_price') && dp.oil_price != null && (
        <div style={{ color: COLOR_OIL, fontSize: 13, marginBottom: 3 }}>
          WTI原油: ${dp.oil_price.toLocaleString(undefined, { maximumFractionDigits: 2 })} /bbl
        </div>
      )}
    </div>
  )
}


export default function ApiWeeklyCrudeOilInventoriesChart() {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(2)
  const [viewMode, setViewMode] = useState<ViewMode>('raw')
  const [activeTab, setActiveTab] = useState<ActiveTab>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<SeriesKey>()

  const { data: response } = useQuery<ApiCrudeResponse>({
    queryKey: ['api-weekly-crude-oil-inventories'],
    queryFn: async () => {
      const res = await axios.get('/api/market/api-weekly-crude-oil-inventories')
      return res.data
    },
    staleTime: 1000 * 60 * 30,
  })

  // WTI oil price
  const { data: marketData } = useMarketBatchData(['crude_oil'])

  const mergedData = useMemo(() => {
    if (!response?.data) return []

    const oilMap = new Map<string, number>()
    if (marketData?.crude_oil?.data) {
      for (const d of marketData.crude_oil.data) {
        if (d.close != null) oilMap.set(d.date, d.close)
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

  // Monthly averages of weekly stock changes for heatmap
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

  // Heatmap data: monthly average stock change
  const heatmapData = useMemo(() => {
    const currentYear = new Date().getFullYear()
    const startYear = currentYear - 9
    const years: number[] = []
    for (let y = startYear; y <= currentYear; y++) years.push(y)
    const monthlyData: Record<number, Record<number, number | null>> = {}
    for (const year of years) {
      monthlyData[year] = {}
      for (let m = 0; m < 12; m++) {
        const val = monthAvg[`${year}-${String(m).padStart(2, '0')}`]
        monthlyData[year][m] = val != null ? Math.round(val * 100) / 100 : null
      }
    }
    return { years, monthlyData }
  }, [monthAvg])

  const latest = response?.latest
  const nextRelease = response?.next_release
  const latestOil = marketData?.crude_oil?.latest

  return (
    <ChartContainer
      title="API（米国石油協会）週間原油在庫"
      dataSource="American Petroleum Institute"
      sourceUrl="https://www.api.org/energy-insights/statistics/wsb"
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
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>在庫変化: </span>
            <span style={{ fontSize: 20, fontWeight: 'bold', color: latest?.value != null ? (latest.value >= 0 ? '#22c55e' : '#ef4444') : TEXT_COLORS.secondary }}>
              {latest?.value != null ? `${latest.value >= 0 ? '+' : ''}${latest.value.toFixed(3)}M bbl` : '—'}
            </span>
          </div>
          {latest?.forecast != null && (
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>予想: </span>
              <span style={{ fontSize: 14, color: TEXT_COLORS.secondary }}>
                {latest.forecast >= 0 ? '+' : ''}{latest.forecast.toFixed(3)}M
              </span>
            </div>
          )}
          {latestOil?.close != null && (
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
                {/* View mode + compare button */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <ViewModeButtonGroup
                    options={VIEW_MODE_OPTIONS}
                    currentMode={viewMode}
                    onChange={(m) => setViewMode(m as ViewMode)}
                  />
                  <Tooltip title="比較ページを開く">
                    <Button
                      icon={<AreaChartOutlined />}
                      onClick={() => window.open('/compare?s=api_weekly_crude_oil_inventories', '_blank')}
                    >
                      データ比較
                    </Button>
                  </Tooltip>
                </div>

                {/* Weekly bar chart + WTI overlay */}
                {viewMode === 'raw' && (
                  <>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <ResponsiveContainer width="100%" height={400}>
                      <ComposedChart data={filteredData} margin={CHART_MARGIN}>
                        <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
                        <XAxis dataKey="date" tickFormatter={(v) => formatDayLabel(v)} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} minTickGap={40} />
                        <YAxis yAxisId="left" domain={['auto', 'auto']} tickFormatter={(v: number) => `${v.toFixed(0)}M`} stroke={COLOR_API} tick={{ fill: COLOR_API, fontSize: 11 }} width={55} />
                        <YAxis yAxisId="oil" orientation="right" reversed domain={['dataMin * 0.9', 'dataMax * 1.1']} tickFormatter={(v: number) => `$${v.toFixed(0)}`} stroke={COLOR_OIL} tick={{ fill: COLOR_OIL, fontSize: 10 }} width={50} axisLine={{ stroke: COLOR_OIL, strokeDasharray: '4 3' }} />
                        <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} />} />
                        <ReferenceLine yAxisId="left" y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />
                        <Legend onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={(value: string, entry: any) => (<span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>{value}</span>)} />
                        <Bar yAxisId="left" dataKey="value" name="API在庫変化 (M bbl)" fill={COLOR_API} hide={hiddenSeries.has('value')} isAnimationActive={false} />
                        <Line yAxisId="oil" type="monotone" dataKey="oil_price" name="WTI原油 (USD/bbl, 反転)" stroke={COLOR_OIL} strokeWidth={1.5} strokeDasharray="4 3" dot={false} hide={hiddenSeries.has('oil_price')} connectNulls isAnimationActive={false} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </>
                )}

                {/* Heatmap: monthly average stock change */}
                {viewMode === 'heatmap' && (
                  <MonthlyTable
                    data={heatmapData}
                    decimals={2}
                    showLegend
                    helperText="※ API週間原油在庫 月平均増減幅（週次データの月平均, 単位: M bbl）"
                  />
                )}
              </>
            ),
          },
          {
            key: 'market_impact',
            label: 'マーケットインパクト',
            children: (
              <MarketImpactTab indicatorId="api_weekly_crude_oil_inventories" />
            ),
          },
        ]}
      />
    </ChartContainer>
  )
}
